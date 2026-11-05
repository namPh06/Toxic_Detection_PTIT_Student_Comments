"""Uncertain AI labels use mocked Ollama replies and temporary workspaces only."""
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from backend.collection_filter import CollectionFilter, MODEL
from backend.dataset import parse_import
from backend.lab import Lab
from backend.shared_dataset import POLICY, export


class ContextualAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.rows = [dict(post_id='1', comment_id='1', text_raw='Cau noi gay tranh cai', text_complete=True),
                     dict(post_id='1', comment_id='2', text_raw='Cam on thong tin', text_complete=True)]
        self.lab = Lab(self.directory, lambda: self.rows)
        self.responses = []
        tags = patch('backend.collection_filter.request', return_value={'models': [{'name': MODEL, 'digest': 'test'}]})
        tags.start()
        self.addCleanup(tags.stop)
        replies = patch('backend.collection_filter.local_request', side_effect=self.request)
        self.request_mock = replies.start()
        self.addCleanup(replies.stop)

    def request(self, path, payload, **_):
        if path == '/api/generate':
            return {}
        return dict(done=True, message={'content': json.dumps(self.responses.pop(0))})

    def label_rows(self):
        self.responses = [dict(label='toxic', needs_review=True, evidence=['gay tranh cai'], reason='Missing context'),
                          dict(label='non-toxic', needs_review=False, evidence=[], reason='Clear information')]
        self.lab.suggest(self.lab.rows(), automatic=True)
        self.assertFalse(self.lab.annotation_job['error'], self.lab.annotation_job['message'])

    def test_uncertain_label_stays_usable_and_flag_survives_reload_and_json_import(self):
        self.label_rows()
        rows = Lab(self.directory, lambda: self.rows).dataset_rows()
        self.assertEqual([r['label'] for r in rows], ['toxic', 'non-toxic'])
        self.assertEqual([r['needs_review'] for r in rows], [True, False])
        self.assertTrue(all(not r['excluded'] and r['label_usable'] for r in rows))
        self.assertEqual(self.lab.status()['dataset_health']['needs_review'], 1)
        self.assertEqual(self.lab.annotations[rows[0]['id']]['note'], 'Missing context')
        content = (self.directory / 'dataset_auto.json').read_text(encoding='utf-8')
        imported = parse_import(content, 'dataset.json')
        self.assertEqual([r['needs_review'] for r in imported], [True, False])
        target = Lab(self.directory / 'imported', lambda: [])
        target.import_rows(dict(filename='dataset.json', content=content))
        self.assertEqual([r['needs_review'] for r in target.rows()], [True, False])
        chat = next(c.args[1] for c in self.request_mock.call_args_list if c.args[0] == '/api/chat')
        self.assertIn('needs_review', chat['format']['required'])
        self.assertEqual(chat['format']['properties']['label']['enum'], ['toxic', 'non-toxic'])

    def test_manual_confirmation_clears_flag_but_retains_ai_history(self):
        self.label_rows()
        row = self.lab.rows()[0]
        self.lab.annotate(dict(id=row['id'], text_hash=row['text_hash'], label=row['label'], note='Checked'))
        restored = Lab(self.directory, lambda: self.rows)
        confirmed = restored.rows()[0]
        self.assertEqual((confirmed['label'], confirmed['label_source']), ('toxic', 'manual'))
        self.assertFalse(confirmed['needs_review'])
        self.assertEqual(restored.status()['dataset_health']['needs_review'], 0)
        self.assertTrue(restored.annotations[row['id']]['history'][-1]['needs_review'])

    def test_shared_export_preserves_uncertainty_flags_and_count(self):
        self.label_rows()
        state = dict(label_policy_version=POLICY, annotations=self.lab.annotations, imported=[])
        with patch('backend.shared_dataset.source_rows', return_value=(self.rows, state)):
            result = export(self.directory)
        exported = json.loads((self.directory / 'shared_dataset.json').read_text(encoding='utf-8'))['rows']
        self.assertEqual([r['needs_review'] for r in exported], [True, False])
        self.assertEqual(result['pending_review'], 1)

    def test_legacy_unverified_source_does_not_imply_ai_uncertainty(self):
        self.rows[0].update(label='toxic', label_source='automatic', needs_review=True,
                            review_reason='unverified_v4_semantic')
        self.assertFalse(self.lab.rows()[0]['needs_review'])
        self.assertTrue(self.rows[0]['needs_review'])

    def test_collection_filter_still_abstains_without_provisional_labels(self):
        self.responses = [dict(label='uncertain', evidence=[], reason='Missing context')]
        gate = CollectionFilter('toxic')
        self.assertEqual(gate.evaluate(self.rows[0], {}, [])['label'], 'uncertain')
        self.assertNotIn('needs_review', gate.schema['required'])

    def test_ollama_connection_failure_stops_before_loading_or_saving(self):
        with patch('backend.collection_filter.request', side_effect=urllib.error.URLError('Connection refused')):
            with self.assertRaisesRegex(RuntimeError, 'Không kết nối được Ollama'):
                CollectionFilter('toxic', provisional_labels=True)
        self.request_mock.assert_not_called()
        self.assertFalse((self.directory / 'workspace.json').exists())

    def test_missing_ollama_model_has_a_distinct_error(self):
        with patch('backend.collection_filter.request', return_value={'models': []}):
            with self.assertRaisesRegex(RuntimeError, 'Chưa cài mô hình'):
                CollectionFilter('toxic', provisional_labels=True)
        self.request_mock.assert_not_called()

    def test_invalid_ai_replies_never_create_a_provisional_label(self):
        valid = dict(label='non-toxic', needs_review=True, evidence=[], reason='Missing context')
        missing = {k: v for k, v in valid.items() if k != 'needs_review'}
        for answer in (dict(valid, needs_review='true'), missing, dict(valid, label='uncertain'),
                       dict(valid, label='toxic', evidence=[])):
            with self.subTest(answer=answer):
                self.responses = [answer]
                gate = CollectionFilter('toxic', provisional_labels=True)
                self.assertEqual(gate.evaluate(self.rows[0], {}, [])['label'], 'uncertain')


if __name__ == '__main__':
    unittest.main()
