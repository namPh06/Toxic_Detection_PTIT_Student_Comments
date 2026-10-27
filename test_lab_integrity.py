"""Workspace and review integrity checks with temporary data and no model/network calls."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from dataset import csv_bytes, row_id, text_hash
from lab import Lab


def suggestion(row):
    return dict(id=row['id'], text_hash=row['text_hash'], suggested_label='toxic', model_score=0.95,
                model='synthetic-test-model', revision='test-revision', truncated=False,
                abstain_reason='', created_at='2026-01-01T00:00:00+00:00')


class LabIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'data'
        self.source_rows = [dict(post_id='post-1', comment_id=str(i), text_raw=text, label='', text_complete=True)
                            for i, text in enumerate(['Cho mình hỏi lịch thi lập trình.', 'Bài giảng hôm nay dễ hiểu.',
                                                      'Cần tìm nhóm làm bài tập lớn.', 'Thư viện mở cửa lúc mấy giờ?'])]
        self.source = lambda: copy.deepcopy(self.source_rows)
        self.lab = Lab(self.directory, self.source)

    def review(self, index, label='non-toxic', excluded=False, note=''):
        row = self.lab.rows()[index]
        return self.lab.annotate(dict(id=row['id'], text_hash=row['text_hash'], label=label, excluded=excluded, note=note))

    def import_data(self, rows):
        return self.lab.import_rows(dict(filename='fixture.json', content=json.dumps(rows, ensure_ascii=False)))

    def state(self):
        return copy.deepcopy((self.lab.annotations, self.lab.imported, self.lab.suggestions))

    def assert_workspace_unchanged(self, before, disk):
        self.assertEqual(self.state(), before)
        self.assertEqual((self.directory / 'workspace.json').read_bytes(), disk)
        restored = Lab(self.directory, self.source)
        self.assertEqual((restored.annotations, restored.imported, restored.suggestions), before)

    def test_import_commit_failure_preserves_rows_labels_and_previous_file(self):
        self.review(0, excluded=True, note='Đã đọc và loại mẫu.')
        before, disk = self.state(), (self.directory / 'workspace.json').read_bytes()
        incoming = [dict(self.source_rows[1], label='toxic'),
                    dict(post_id='new-post', comment_id='new-comment', text_raw='Nội dung nhập mới.', label='non-toxic')]
        with patch('pathlib.Path.replace', side_effect=OSError('simulated atomic replace failure')):
            with self.assertRaises(OSError):
                self.import_data(incoming)
        self.assert_workspace_unchanged(before, disk)
        self.assertEqual(len(self.lab.rows()), len(self.source_rows))

    def test_import_reviews_changed_text_without_using_stale_label(self):
        self.review(0, label='toxic', note='Ghi chú cũ')
        self.source_rows[0]['text_raw'] = 'Nội dung mới sau khi mở hết bình luận'
        self.assertTrue(self.lab.rows()[0]['annotation_stale'])
        self.import_data([dict(self.source_rows[0], label='non-toxic')])
        row = self.lab.rows()[0]
        self.assertFalse(row['annotation_stale'])
        self.assertEqual(row['label'], 'non-toxic')
        self.assertEqual(row['label_source'], 'imported')

    def test_formula_guarded_csv_can_be_reimported_without_changing_raw_text(self):
        self.source_rows[0]['text_raw'] = '@bạn lịch thi xem ở đâu?'
        self.review(0)
        content = csv_bytes(self.lab.rows()).decode('utf-8-sig')
        self.assertIn("'@bạn", content)
        self.lab.import_rows(dict(filename='roundtrip.csv', content=content))
        self.assertEqual(self.lab.rows()[0]['text_raw'], self.source_rows[0]['text_raw'])
        self.assertEqual(self.lab.rows()[0]['label'], 'non-toxic')

    def test_annotation_commit_failure_keeps_previous_review(self):
        self.review(0, label='non-toxic', note='Nhãn đã duyệt.')
        before, disk = self.state(), (self.directory / 'workspace.json').read_bytes()
        with patch('pathlib.Path.replace', side_effect=OSError('simulated atomic replace failure')):
            with self.assertRaises(OSError):
                self.review(0, label='toxic', excluded=True, note='Không được lưu.')
        self.assert_workspace_unchanged(before, disk)
        self.assertEqual(self.lab.dataset_rows()[0]['label'], 'non-toxic')

    def test_changed_text_invalidates_review_until_explicit_rereview(self):
        self.review(0, label='toxic')
        original = self.lab.rows()[0]
        self.source_rows[0]['text_raw'] += ' Nội dung được thu thập bổ sung.'
        changed = self.lab.rows()[0]
        self.assertTrue(changed['annotation_stale'])
        self.assertEqual(changed['label'], '')
        self.assertEqual(changed['previous_label'], 'toxic')
        with self.assertRaises(ValueError):
            self.lab.dataset_rows()
        before, disk = self.state(), (self.directory / 'workspace.json').read_bytes()
        with self.assertRaises(ValueError):
            self.lab.annotate(dict(id=original['id'], text_hash=original['text_hash'], label='non-toxic'))
        self.assert_workspace_unchanged(before, disk)
        self.review(0, label='non-toxic')
        reviewed = self.lab.dataset_rows()[0]
        self.assertFalse(reviewed['annotation_stale'])
        self.assertNotIn('previous_label', reviewed)
        self.assertEqual(reviewed['label'], 'non-toxic')
        self.assertEqual(self.lab.annotations[reviewed['id']]['text_hash'], text_hash(self.source_rows[0]['text_raw']))

    def test_reimport_preserves_manual_exclusion_note_and_review_provenance(self):
        self.review(0, label='toxic', excluded=True, note='Loại mẫu đã kiểm tra.')
        self.review(1, label='', excluded=True, note='Giữ nguyên lý do loại.')
        existing = copy.deepcopy(self.lab.annotations[row_id(self.source_rows[0])])
        result = self.import_data([dict(self.source_rows[0], label='toxic', excluded=False, annotation_note='Ghi đè'),
                                   dict(self.source_rows[1], label='non-toxic', excluded=False, annotation_note='Ghi đè')])
        self.assertEqual(result, dict(added=0, labels_updated=1))
        self.assertEqual(self.lab.annotations[row_id(self.source_rows[0])], existing)
        self.assertTrue(all(row['quality'] == 'excluded' for row in self.lab.rows()[:2]))
        self.assertEqual(self.lab.rows()[1]['annotation_note'], 'Giữ nguyên lý do loại.')
        with self.assertRaises(ValueError):
            self.lab.dataset_rows()

    def test_suggestions_remain_outside_dataset_until_human_review(self):
        raw_before = copy.deepcopy(self.source_rows)
        with patch('labeling.generate_suggestions', side_effect=lambda rows, *_: [suggestion(row) for row in rows]):
            self.lab.suggest(self.lab.rows())
        self.assertFalse(self.lab.annotation_job['error'])
        self.assertTrue(all(row['suggestion'] and row['label'] == '' for row in self.lab.rows()))
        with self.assertRaises(ValueError):
            self.lab.dataset_rows()
        expected = self.lab.rows()[0]['suggestion']
        self.review(0, label='non-toxic', note='Người đọc sửa gợi ý.')
        exported = self.lab.dataset_rows()
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]['label'], 'non-toxic')
        self.assertIsNone(exported[0]['suggestion'])
        self.assertEqual(exported[0]['label_source'], 'manual')
        self.assertEqual(self.lab.annotations[exported[0]['id']]['suggestion_at_review'], expected)
        self.assertEqual(self.source_rows, raw_before)
        self.assertEqual(Lab(self.directory, self.source).dataset_rows()[0]['label'], 'non-toxic')

    def test_worker_discards_predictions_after_concurrent_review_text_change_or_exclusion(self):
        snapshot = self.lab.rows()
        entered, release = threading.Event(), threading.Event()

        def delayed_generate(rows, *_):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test did not release worker')
            return [suggestion(row) for row in rows]

        self.lab.annotation_job['running'] = True
        with patch('labeling.generate_suggestions', side_effect=delayed_generate):
            worker = threading.Thread(target=self.lab.suggest, args=(snapshot,), daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(5), 'worker did not enter mocked inference')
                self.review(0, label='non-toxic')
                self.source_rows[1]['text_raw'] += ' Nội dung mới.'
                self.review(2, label='', excluded=True)
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(self.lab.annotation_job['running'])
        self.assertFalse(self.lab.annotation_job['error'])
        self.assertEqual(set(self.lab.suggestions), {snapshot[3]['id']})
        self.assertEqual(self.lab.rows()[0]['label'], 'non-toxic')
        self.assertIsNone(self.lab.rows()[1]['suggestion'])
        self.assertEqual(self.lab.rows()[2]['quality'], 'excluded')
        self.assertEqual(len(self.lab.dataset_rows()), 1)
        self.assertEqual(Lab(self.directory, self.source).suggestions, self.lab.suggestions)

    def test_inference_or_suggestion_commit_failure_preserves_workspace(self):
        self.review(0)
        with patch('labeling.generate_suggestions', side_effect=lambda rows, *_: [suggestion(row) for row in rows]):
            self.lab.suggest(self.lab.rows()[1:2])
        before, disk = self.state(), (self.directory / 'workspace.json').read_bytes()
        for failure in ('inference', 'commit'):
            with self.subTest(failure=failure):
                self.lab.annotation_job['running'] = True
                prediction = (lambda rows, *_: [suggestion(row) for row in rows]) if failure == 'commit' else RuntimeError('simulated inference failure')
                with patch('labeling.generate_suggestions', side_effect=prediction), \
                        patch('lab.atomic_json', side_effect=OSError('simulated storage failure')):
                    self.lab.suggest(self.lab.rows()[2:])
                self.assertTrue(self.lab.annotation_job['error'])
                self.assertFalse(self.lab.annotation_job['running'])
                self.assert_workspace_unchanged(before, disk)


if __name__ == '__main__':
    unittest.main()
