"""Run with python -m unittest -v. Fixtures are synthetic and never touch real data."""
import http.client
import json
import tempfile
import threading
import unittest
import unicodedata
from pathlib import Path
from unittest.mock import Mock, patch

from dataset import clean_text, csv_bytes, fingerprint, parse_import, prepare, row_id, summary, text_hash, word_tokens
from experiments import build_report, metrics, predict, split_dataset, train_experiment
from lab import Lab


def fixture():
    rows = []
    for post in range(12):
        for index in range(6):
            for label in ('non-toxic', 'toxic'):
                text = ('cảm ơn bạn chia sẻ thông tin hữu ích' if label == 'non-toxic' else 'đồ ngu câm mồm đi đừng sủa nữa')
                rows.append(dict(post_id=str(post), comment_id=f'{post}-{index}-{label}',
                                 text_raw=f'{text} trườnghợp{post} vídụ{index}', label=label))
    return rows


class DatasetTests(unittest.TestCase):
    def test_unicode_negation_privacy_and_idempotence(self):
        text = unicodedata.normalize('NFD', 'TÔI ko ghét bạn 😡 &amp; dc liên hệ abc@example.com 0912 345 678 https://fb.com/a')
        cleaned = clean_text(text)
        self.assertIn('không ghét bạn 😡', cleaned)
        self.assertIn('emailtoken', cleaned)
        self.assertIn('phonetoken', cleaned)
        self.assertIn('urltoken', cleaned)
        self.assertNotIn('abc@', cleaned)
        self.assertEqual(clean_text(cleaned), cleaned)
        self.assertIn('không', clean_text('không phải đồ ngu'))

    def test_duplicates_annotations_and_conflicts(self):
        rows = [dict(post_id='1', comment_id='1', text_raw='Xin chào!', label=''),
                dict(post_id='2', comment_id='2', text_raw='xin chào', label='non-toxic')]
        original = json.dumps(rows)
        result = prepare(rows)
        self.assertEqual([r['quality'] for r in result], ['duplicate', 'ready'])
        self.assertEqual(json.dumps(rows), original)
        result = prepare(rows, {row_id(rows[0]): dict(label='toxic')})
        self.assertTrue(all(r['quality'] == 'conflict' for r in result))
        self.assertEqual(summary(result)['usable'], 0)
        result = prepare(rows, {row_id(rows[0]): dict(excluded=True, label='toxic')})
        self.assertEqual([r['quality'] for r in result], ['excluded', 'ready'])

    def test_empty_and_csv_injection(self):
        rows = prepare([dict(post_id='1', comment_id=str(i), text_raw=text) for i, text in enumerate(['', 'Thích', '!!!', '=1+1'])])
        self.assertEqual(summary(rows)['quality']['empty_or_ui'], 3)
        self.assertIn("'=1+1", csv_bytes(rows).decode('utf-8-sig'))

    def test_import_validation(self):
        with self.assertRaises(ValueError):
            parse_import(json.dumps([dict(text_raw='text', label='positive')]), 'test.json')
        with self.assertRaises(ValueError):
            parse_import('[{"text_raw":"text"}]', 'test.json')
        sample = fixture()[:2]
        self.assertEqual(len(parse_import(json.dumps(sample), 'test.json')), 2)
        with self.assertRaises(ValueError):
            parse_import(json.dumps(sample + sample), 'test.json')

    def test_annotation_persistence_and_raw_unchanged(self):
        raw = fixture()[:2]
        original = json.dumps(raw)
        with tempfile.TemporaryDirectory() as temp:
            lab = Lab(Path(temp), lambda: raw)
            before = fingerprint(lab.rows())
            lab.annotate(dict(id=row_id(raw[0]), text_hash=text_hash(raw[0]['text_raw']), label='toxic', note='reviewed', excluded=False))
            restored = Lab(Path(temp), lambda: raw)
            self.assertEqual(restored.rows()[0]['label'], 'toxic')
            self.assertNotEqual(before, fingerprint(restored.rows()))
            self.assertEqual(json.dumps(raw), original)
            with self.assertRaises(ValueError):
                lab.annotate(dict(id='missing', label='toxic'))
            lab.job['running'] = True
            with self.assertRaises(ValueError):
                lab.predict(dict(text='test'))

    def test_failed_save_does_not_change_in_memory_label(self):
        with tempfile.TemporaryDirectory() as temp:
            lab = Lab(Path(temp), lambda: fixture()[:2])
            with patch('lab.atomic_json', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    lab.annotate(dict(id=row_id(fixture()[0]), text_hash=text_hash(fixture()[0]['text_raw']), label='toxic'))
            self.assertEqual(lab.rows()[0]['label'], 'non-toxic')

    def test_import_conflict_is_atomic(self):
        raw = fixture()[:2]
        with tempfile.TemporaryDirectory() as temp:
            lab = Lab(Path(temp), lambda: raw)
            conflicting = [dict(raw[0], label='toxic')]
            with self.assertRaises(ValueError):
                lab.import_rows(dict(content=json.dumps(conflicting), filename='test.json'))
            self.assertFalse((Path(temp) / 'imported.json').exists())
            self.assertEqual(lab.rows()[0]['label'], 'non-toxic')


class ExperimentTests(unittest.TestCase):
    def test_split_prevents_post_and_duplicate_leakage(self):
        raw = fixture()
        raw.append(dict(raw[0], post_id='1', comment_id='cross-post-duplicate'))
        rows = prepare(raw)
        eligible, split, groups = split_dataset(rows)
        buckets = {}
        for name, indexes in split.items():
            buckets[name] = {groups[i] for i in indexes}
            self.assertEqual({eligible[i]['label'] for i in indexes}, {'toxic', 'non-toxic'})
        for first, second in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
            self.assertFalse(buckets[first] & buckets[second])
            self.assertFalse({eligible[i]['text_clean'] for i in split[first]} & {eligible[i]['text_clean'] for i in split[second]})
        group_by_post = {r['post_id']: groups[i] for i, r in enumerate(eligible)}
        self.assertEqual(group_by_post['0'], group_by_post['1'])

    def test_training_requires_labels_and_independent_groups(self):
        with self.assertRaisesRegex(ValueError, '10'):
            split_dataset(prepare([dict(r, label='') for r in fixture()]))
        with self.assertRaisesRegex(ValueError, '5'):
            split_dataset(prepare([dict(r, post_id='same') for r in fixture()]))

    def test_metrics_orientation(self):
        m = metrics([0, 0, 1, 1], [0, 1, 1, 1])
        self.assertEqual(m['confusion_matrix'], [[1, 1], [0, 2]])
        self.assertEqual(m['accuracy'], .75)
        self.assertEqual(m['recall'], 1)
        self.assertAlmostEqual(m['precision'], 2 / 3)

    def test_all_five_models_save_reload_predict_and_report(self):
        import joblib
        rows = prepare(fixture())
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'experiment'
            result = train_experiment(rows, directory, epochs=2)
            self.assertEqual(len(result['models']), 5)
            self.assertEqual(result['selected_model'], max(result['models'], key=lambda m: m['validation']['f1_macro'])['name'])
            split = json.loads((directory / 'split.json').read_text())
            train_ids = {r['id'] for r in split['train']}
            train_tokens = {t for r in rows if r['id'] in train_ids for t in word_tokens(r['text_clean'])}
            vocabulary = json.loads((directory / 'vocabulary.json').read_text(encoding='utf-8'))
            self.assertEqual(set(vocabulary), train_tokens)
            for model in result['models']:
                prediction = predict('cảm ơn bạn chia sẻ thông tin', directory, model['name'])
                self.assertIn(prediction['label'], ('toxic', 'non-toxic'))
                self.assertEqual(sum(map(sum, model['test']['confusion_matrix'])), result['split']['test']['count'])
                if model['name'] != 'TextCNN':
                    fitted = joblib.load(directory / (model['name'] + '.joblib'))
                    self.assertTrue(set(fitted['vectorizer'].vocabulary_) <= train_tokens | {a+' '+b for r in rows if r['id'] in train_ids for a,b in zip(word_tokens(r['text_clean']),word_tokens(r['text_clean'])[1:])})
            report = (directory / 'report.md').read_text(encoding='utf-8')
            self.assertIn('TextCNN', report)
            self.assertIn('|\n|---', report)
            self.assertIn('đã thay đổi', build_report(prepare(fixture()[:-1]), result))
            result['summary']['label_sources'] = {'automatic': len(rows)}
            self.assertIn('Lần huấn luyện này dùng nhãn tự động', build_report(rows, result))
            self.assertIn('automatic_labels', result['split']['test'])


class CrawlerTests(unittest.TestCase):
    def test_retry_incomplete_posts_preserves_rows_and_updates_longer_text(self):
        import app
        source = 'https://www.facebook.com/groups/ptit/'
        post = dict(id='1', url=source + 'posts/1/')
        state = dict(app.STATE, source=source, target=1, results=[dict(post_id='1', reason='no_progress')])
        rows = {('1', 'a'): dict(post_id='1', comment_id='a', text_raw='Nội dung', label='non-toxic')}
        driver = Mock(current_url=source, current_window_handle='feed')
        stop = Mock()
        stop.is_set.return_value = stop.wait.return_value = False

        def script(_script, action=None, _expected=None):
            if action == 'feed':
                return dict(posts=[post])
            if action == 'read':
                return dict(rows=[dict(comment_id='a', text_raw='Nội dung đầy đủ'), dict(comment_id='b', text_raw='Bình luận mới')])
            return dict(moved=False)

        driver.execute_script.side_effect = script
        with patch.multiple(app, STATE=state, ROWS=rows, STOP=stop), patch.object(app, 'save'):
            app.run_batch(driver)
        driver.switch_to.new_window.assert_called_once_with('tab')
        driver.switch_to.window.assert_called_once_with('feed')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[('1', 'a')]['text_raw'], 'Nội dung đầy đủ')
        self.assertEqual(rows[('1', 'a')]['label'], '')
        self.assertEqual(state['results'][0]['reason'], 'no_progress')
        self.assertFalse(state['running'])

    def test_hover_new_timestamps_even_when_old_links_remain(self):
        import app
        source = 'https://www.facebook.com/groups/ptit/'
        state = dict(app.STATE, source=source, target=2, results=[])
        first = dict(id='1', url=source + 'posts/1/')
        second = dict(id='2', url=source + 'posts/2/')
        driver = Mock(current_url=source, current_window_handle='feed')
        stop = Mock()
        stop.is_set.return_value = stop.wait.return_value = False
        calls = []

        def script(_script, action=None, _expected=None):
            calls.append(action)
            if action == 'feed':
                return dict(posts=[first, second] if 'feed_hover' in calls else [first])
            if action == 'feed_hover':
                return []
            if action == 'read':
                return dict(rows=[])
            return dict(moved=False)

        driver.execute_script.side_effect = script
        with patch.multiple(app, STATE=state, ROWS={}, STOP=stop), patch.object(app, 'save'):
            app.run_batch(driver)
        self.assertIn('feed_hover', calls)
        self.assertEqual(driver.switch_to.new_window.call_count, 2)
        self.assertEqual(state['posts'], 2)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app
        cls.app = app
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_lab = app.LAB
        app.LAB = Lab(Path(cls.temp.name), lambda: fixture()[:2])
        cls.server = app.LocalHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.app.LAB = cls.old_lab
        cls.temp.cleanup()

    def request(self, path, body=None, origin=True, host=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port)
        headers = {'Content-Type': 'application/json'}
        if host:
            headers['Host'] = host
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{self.port}'
        connection.request('POST' if body is not None else 'GET', path,
                           body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_local_fonts_are_served_without_external_requests(self):
        for weight in (400, 500, 600, 700):
            with self.subTest(weight=weight):
                status, body = self.request(f'/assets/fonts/be-vietnam-pro-{weight}.ttf')
                self.assertEqual(status, 200)
                self.assertEqual(body[:4], b'\x00\x01\x00\x00')
        self.assertEqual(self.request('/assets/fonts/../../app.py')[0], 404)

    def test_api_validation_host_origin_and_paging(self):
        self.assertEqual(self.request('/api/status', host='evil.test')[0], 403)
        self.assertEqual(self.request('/api/annotate', {}, origin=False)[0], 403)
        self.assertEqual(self.request('/start', dict(target=True))[0], 400)
        self.assertEqual(self.request('/api/rows?page=oops')[0], 400)
        status, body = self.request('/api/rows?label=non-toxic&quality=ready')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['total'], 1)

    def test_second_server_cannot_share_workspace_port(self):
        with self.assertRaises(OSError):
            duplicate = self.app.LocalHTTPServer(('127.0.0.1', self.port), self.app.Handler)
            duplicate.server_close()

    def test_annotation_and_report_endpoints(self):
        self.assertEqual(self.request('/api/annotate', dict(id=row_id(fixture()[0]), text_hash=text_hash(fixture()[0]['text_raw']), label='non-toxic', note='test'))[0], 200)
        status, body = self.request('/api/report')
        self.assertEqual(status, 200)
        self.assertIn('Chưa có thực nghiệm', body.decode())
        self.assertEqual(self.request('/api/train', {})[0], 400)

    def test_source_url_boundary(self):
        self.assertTrue(self.app.scope_url('https://www.facebook.com/groups/ptit/'))
        for url in ('http://facebook.com/groups/x', 'https://facebook.com.evil.test/groups/x', 'https://facebook.com/login', 'file:///etc/passwd'):
            self.assertFalse(self.app.scope_url(url))

    def test_reviewed_exports_and_required_hash(self):
        rows = [dict(r, label='') for r in fixture()[:3]]
        rows[2]['text_complete'] = False
        with tempfile.TemporaryDirectory() as temp, patch.object(self.app, 'LAB', Lab(Path(temp), lambda: rows)):
            lab = self.app.LAB
            first = lab.rows()[0]
            lab.suggestions[first['id']] = dict(text_hash=first['text_hash'], suggested_label='toxic', model_score=.99)
            self.assertEqual(self.request('/api/dataset.json')[0], 400)
            body = dict(id=first['id'], label='non-toxic')
            self.assertEqual(self.request('/api/annotate', body)[0], 400)
            self.assertEqual(self.request('/api/annotate', dict(body, text_hash='old-hash'))[0], 400)
            self.assertEqual(self.request('/api/annotate', dict(body, text_hash=first['text_hash']))[0], 200)
            status, payload = self.request('/api/dataset.json')
            self.assertEqual(status, 200)
            exported = json.loads(payload)
            self.assertEqual(exported['label_policy'], 'reviewed_only')
            self.assertEqual([(r['id'], r['label'], r['label_source']) for r in exported['rows']], [(first['id'], 'non-toxic', 'manual')])
            status, payload = self.request('/api/dataset.csv')
            self.assertEqual(status, 200)
            imported = parse_import(payload.decode('utf-8-sig'), 'dataset.csv')
            self.assertEqual(len(imported), 1)
            self.assertEqual(imported[0]['text_raw'], first['text_raw'])

    def test_bulk_reviews_validate_the_entire_batch_and_persist(self):
        rows = [dict(r, label='') for r in fixture()[:3]]
        with tempfile.TemporaryDirectory() as temp, patch.object(self.app, 'LAB', Lab(Path(temp), lambda: rows)):
            lab = self.app.LAB
            items = [dict(id=r['id'], text_hash=r['text_hash'], label='toxic', note='reviewed') for r in lab.rows()[:2]]
            self.assertEqual(self.request('/api/annotate-bulk', dict(rows=items), origin=False)[0], 403)
            self.assertEqual(self.request('/api/annotate-bulk', {})[0], 400)
            invalid = [items[0], dict(items[1], text_hash='old-hash')]
            self.assertEqual(self.request('/api/annotate-bulk', dict(rows=invalid))[0], 400)
            self.assertEqual(lab.annotations, {})
            status, body = self.request('/api/annotate-bulk', dict(rows=items))
            self.assertEqual((status, json.loads(body)), (200, dict(saved=2)))
            restored = Lab(Path(temp), lambda: rows)
            self.assertEqual(restored.annotations, lab.annotations)
            self.assertEqual(len(restored.annotations), 2)
            status, body = self.request('/api/dataset.json')
            self.assertEqual(status, 200)
            self.assertEqual([(r['id'], r['label_source']) for r in json.loads(body)['rows']],
                             [(item['id'], 'manual') for item in items])

    def test_bulk_endpoint_and_automatic_exports(self):
        import time
        from test_bulk_labeling import BulkLabelingTests
        rows = [dict(r, label='') for r in fixture()[:30]]
        with tempfile.TemporaryDirectory() as temp, patch.object(self.app, 'LAB', Lab(Path(temp), lambda: rows)), \
                patch('labeling.generate_suggestions', side_effect=BulkLabelingTests.generate):
            self.assertEqual(self.request('/api/auto-label', {}, origin=False)[0], 403)
            status, body = self.request('/api/auto-label', {})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['total'], 30)
            deadline = time.monotonic() + 5
            while self.app.LAB.annotation_job['running'] and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertFalse(self.app.LAB.annotation_job['running'])
            self.assertFalse(self.app.LAB.annotation_job['error'])
            self.assertEqual(self.request('/api/dataset.json')[0], 400)
            status, body = self.request('/api/dataset-auto.json')
            self.assertEqual(status, 200)
            exported = json.loads(body)
            self.assertEqual(exported['label_policy'], 'includes_automatic')
            self.assertEqual(len(exported['rows']), 30)
            self.assertTrue(all(r['label_source'] == 'automatic' for r in exported['rows']))
            status, body = self.request('/api/dataset-auto.csv')
            self.assertEqual(status, 200)
            self.assertEqual(len(parse_import(body.decode('utf-8-sig'), 'auto.csv')), 30)


if __name__ == '__main__':
    unittest.main()
