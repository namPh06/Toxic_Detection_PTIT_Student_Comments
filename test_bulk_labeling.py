"""Bulk labels, persistence and provenance; synthetic fixtures only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dataset import csv_bytes, fingerprint, parse_import
from lab import Lab
from labeling import automatic_annotation
from test_lab_integrity import suggestion
from test_project import fixture


class BulkLabelingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'data'
        self.raw = [dict(r, label='', text_complete=True) for r in fixture()]
        self.lab = Lab(self.directory, lambda: copy.deepcopy(self.raw))

    @staticmethod
    def generate(rows, *_):
        return [dict(suggestion(r), model_score=.9 if r['comment_id'].endswith('-toxic') and
                     not r['comment_id'].endswith('-non-toxic') else .1) for r in rows]

    def run_bulk(self):
        with patch('labeling.generate_suggestions', side_effect=self.generate):
            self.lab.suggest(self.lab.rows(), automatic=True)
        self.assertFalse(self.lab.annotation_job['error'], self.lab.annotation_job)

    def test_entire_dataset_reuses_cache_preserves_manual_and_filters_bad_rows(self):
        raw_before = copy.deepcopy(self.raw)
        manual = self.lab.rows()[0]
        self.lab.annotate(dict(id=manual['id'], text_hash=manual['text_hash'], label='non-toxic', note='Giữ nguyên'))
        self.raw += [dict(self.raw[2], comment_id='duplicate'),
                     dict(post_id='extra', comment_id='empty', text_raw='!!!', label=''),
                     dict(post_id='extra', comment_id='incomplete', text_raw='Chưa mở hết nội dung', text_complete=False)]
        cached = self.lab.rows()[1]
        self.lab.suggestions[cached['id']] = dict(suggestion(cached), model_score=.5, suggested_label='', abstain_reason='uncertain')
        eligible = [r for r in self.lab.rows() if r['quality'] == 'ready' and not r['label']]
        with patch('labeling.generate_suggestions', side_effect=self.generate) as infer:
            # start_suggestions selects the whole workspace, not the UI's 25-row page.
            with patch('lab.threading.Thread') as thread:
                started = self.lab.start_suggestions(automatic=True)
                selected, automatic = thread.call_args.kwargs['args']
            self.lab.suggest(selected, automatic)
        self.assertEqual(started['total'], len(eligible))
        self.assertGreater(started['total'], 25)
        self.assertNotIn(cached['id'], {r['id'] for r in infer.call_args.args[0]})
        dataset = self.lab.dataset_rows(reviewed_only=False)
        self.assertEqual(len(dataset), len(raw_before))
        self.assertTrue(all(r['label'] for r in dataset))
        self.assertEqual(self.lab.dataset_rows()[0]['annotation_note'], 'Giữ nguyên')
        self.assertEqual(len(self.lab.dataset_rows()), 1)
        uncertain = next(r for r in dataset if r['id'] == cached['id'])
        self.assertEqual((uncertain['label'], uncertain['needs_review']), ('toxic', True))
        self.assertEqual(self.raw[:len(raw_before)], raw_before)
        health = self.lab.status()['dataset_health']
        self.assertEqual((health['automatic'], health['reviewed']), (len(dataset)-1, 1))
        self.assertTrue(health['training_ready'])
        self.assertEqual(len(json.loads((self.directory/'dataset_auto.json').read_text(encoding='utf-8'))['rows']), len(dataset))
        self.assertEqual(len(json.loads((self.directory/'processed.json').read_text(encoding='utf-8'))['rows']), len(self.raw))
        self.assertEqual(Lab(self.directory, self.lab.source).annotations, self.lab.annotations)
        with self.assertRaises(ValueError):
            self.lab.start_suggestions(automatic=True)

    def test_threshold_flags_and_invalid_scores(self):
        item = suggestion(self.lab.rows()[0])
        for score, expected, flag in [(0, 'non-toxic', False), (.2, 'non-toxic', False), (.49, 'non-toxic', True),
                                      (.5, 'toxic', True), (.8, 'toxic', False), (1, 'toxic', False)]:
            result = automatic_annotation(dict(item, model_score=score))
            self.assertEqual((result['label'], result['needs_review']), (expected, flag))
        self.assertEqual(automatic_annotation(dict(item, truncated=True))['review_reason'], 'truncated')
        for bad in (float('nan'), float('inf'), -1, 2, True, '.5'):
            with self.assertRaises(ValueError):
                automatic_annotation(dict(item, model_score=bad))

    def test_roundtrip_keeps_machine_origin_and_manual_review_supersedes_it(self):
        self.raw[0]['text_raw'] = '@bạn lịch thi xem ở đâu?'
        self.run_bulk()
        rows = self.lab.dataset_rows(reviewed_only=False)
        for filename, content in [('auto.csv', csv_bytes(rows).decode('utf-8-sig')),
                                  ('auto.json', json.dumps(dict(rows=rows), ensure_ascii=False))]:
            with self.subTest(filename=filename):
                imported = parse_import(content, filename)
                self.assertTrue(all(r['label_source'] == 'automatic' for r in imported))
                target = Lab(Path(self.temp.name)/filename, lambda: [])
                target.import_rows(dict(filename=filename, content=content))
                self.assertEqual(target.status()['dataset_health']['reviewed'], 0)
                self.assertEqual(target.dataset_rows(False)[0]['model_score'], rows[0]['model_score'])
                self.assertEqual(target.dataset_rows(False)[0]['text_raw'], self.raw[0]['text_raw'])
                with self.assertRaises(ValueError):
                    target.dataset_rows()
        before = fingerprint(self.lab.rows())
        row = rows[0]
        self.lab.annotate(dict(id=row['id'], text_hash=row['text_hash'], label=row['label']))
        reviewed = self.lab.dataset_rows()[0]
        self.assertEqual(reviewed['label_source'], 'manual')
        self.assertIsNone(reviewed['model_score'])
        self.assertNotEqual(fingerprint(self.lab.rows()), before)
        self.lab.import_rows(dict(filename='review.json', content=json.dumps([dict(self.raw[1], label='non-toxic')])))
        self.assertEqual(self.lab.rows()[1]['label_source'], 'imported')
        self.assertEqual(self.lab.rows()[1]['label'], 'non-toxic')

    def test_commit_failure_does_not_partially_label(self):
        before = copy.deepcopy(self.lab.annotations)
        with patch('labeling.generate_suggestions', side_effect=self.generate), patch('lab.atomic_json', side_effect=OSError('disk full')):
            self.lab.suggest(self.lab.rows(), automatic=True)
        self.assertTrue(self.lab.annotation_job['error'])
        self.assertFalse(self.lab.annotation_job['running'])
        self.assertEqual(self.lab.annotations, before)
        self.assertFalse((self.directory/'workspace.json').exists())

    def test_export_failure_keeps_committed_labels_downloadable(self):
        with patch('labeling.generate_suggestions', side_effect=self.generate), patch.object(self.lab, 'save_cleaned', side_effect=OSError('disk full')):
            self.lab.suggest(self.lab.rows(), automatic=True)
        self.assertTrue(self.lab.annotation_job['error'])
        self.assertIn('Nhãn đã lưu', self.lab.annotation_job['message'])
        self.assertEqual(len(self.lab.dataset_rows(False)), len(self.raw))
        self.assertEqual(Lab(self.directory, self.lab.source).annotations, self.lab.annotations)

    def test_concurrent_review_exclusion_and_text_change_are_not_overwritten(self):
        snapshot = self.lab.rows()
        def generate(rows, *_):
            self.lab.annotate(dict(id=rows[0]['id'], text_hash=rows[0]['text_hash'], label='toxic'))
            self.lab.annotate(dict(id=rows[1]['id'], text_hash=rows[1]['text_hash'], label='', excluded=True))
            self.raw[2]['text_raw'] += ' mới bổ sung'
            return self.generate(rows)
        with patch('labeling.generate_suggestions', side_effect=generate):
            self.lab.suggest(snapshot, automatic=True)
        self.assertFalse(self.lab.annotation_job['error'])
        rows = self.lab.rows()
        self.assertEqual((rows[0]['label'], rows[0]['label_source']), ('toxic', 'manual'))
        self.assertEqual(rows[1]['quality'], 'excluded')
        self.assertEqual(rows[2]['label'], '')
        self.assertEqual(len(self.lab.dataset_rows(False)), len(self.raw)-2)


if __name__ == '__main__':
    unittest.main()
