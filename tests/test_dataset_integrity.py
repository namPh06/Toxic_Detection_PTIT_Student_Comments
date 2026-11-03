"""Integrity regressions use synthetic comments and never write the real dataset."""
import json
import unittest

from dataset import clean_text, csv_bytes, parse_import, prepare, row_id, text_hash


def sample(**values):
    return dict(dict(post_id='1', comment_id='2', text_raw='Nội dung đầy đủ', label='non-toxic'), **values)


class DatasetIntegrityTests(unittest.TestCase):
    def test_import_rejects_non_identifier_json_values(self):
        for name in ('post_id', 'comment_id'):
            for invalid in (None, True, False, [], {}, 1.5, ''):
                with self.subTest(name=name, value=invalid), self.assertRaises(ValueError):
                    parse_import(json.dumps([sample(**{name: invalid})]), 'input.json')
        self.assertEqual(parse_import(json.dumps([sample(post_id=1)]), 'input.json')[0]['post_id'], '1')

    def test_excluded_and_incomplete_survive_json_and_csv_roundtrip(self):
        originals = [sample(excluded=True), sample(comment_id='3', text_complete=False),
                     sample(comment_id='4', text_raw='Nội dung khác', text_complete=True)]
        exported = prepare(originals)
        for filename, content in [('input.json', json.dumps(dict(rows=exported))),
                                  ('input.csv', csv_bytes(exported).decode('utf-8-sig'))]:
            with self.subTest(filename=filename):
                rows = prepare(parse_import(content, filename))
                self.assertEqual([r['quality'] for r in rows], ['excluded', 'incomplete', 'ready'])
                self.assertEqual([r.get('text_complete') for r in rows], [None, False, True])
                self.assertEqual([r['text_raw'] for r in rows], [r['text_raw'] for r in originals])

    def test_flags_require_booleans_and_legacy_completeness_stays_unknown(self):
        for name in ('excluded', 'text_complete'):
            for invalid in (0, 1, 'false', [], {}):
                with self.subTest(name=name, value=invalid), self.assertRaises(ValueError):
                    parse_import(json.dumps([sample(**{name: invalid})]), 'input.json')
        self.assertIsNone(parse_import(json.dumps([sample()]), 'input.json')[0]['text_complete'])
        self.assertNotIn('text_complete', prepare([sample()])[0])

    def test_changed_text_invalidates_annotation_without_erasing_review(self):
        original = sample(text_raw='Bình luận đang thu gọn…', label='')
        annotation = {row_id(original): dict(label='non-toxic', text_hash=text_hash(original['text_raw']), note='Đã đọc')}
        unchanged = prepare([original], annotation)[0]
        self.assertEqual(unchanged['label'], 'non-toxic')
        self.assertFalse(unchanged['annotation_stale'])
        updated = dict(original, text_raw='Bình luận đang thu gọn… đồ ngu', text_hash='forged', annotation_stale=False)
        row = prepare([updated], annotation)[0]
        self.assertEqual(row['label'], '')
        self.assertEqual(row['previous_label'], 'non-toxic')
        self.assertTrue(row['annotation_stale'])
        self.assertEqual(row['label_source'], '')
        self.assertEqual(row['text_hash'], text_hash(updated['text_raw']))
        self.assertEqual(annotation[row_id(original)]['label'], 'non-toxic')
        self.assertEqual(row['annotation_note'], 'Đã đọc')

    def test_stale_export_does_not_promote_previous_label_on_import(self):
        original = sample(label='')
        rows = prepare([original], {row_id(original): dict(label='toxic', text_hash=text_hash('Old text'))})
        for filename, content in [('input.json', json.dumps(rows)), ('input.csv', csv_bytes(rows).decode('utf-8-sig'))]:
            self.assertEqual(prepare(parse_import(content, filename))[0]['label'], '')
        with self.assertRaises(ValueError):
            parse_import(json.dumps([sample(label_source='automatic')]), 'input.json')

    def test_exports_keep_source_context_and_import_marks_label_origin(self):
        original = sample(post_url='https://www.facebook.com/groups/ptit/posts/1/', parent_comment_id='parent',
                          identifier_quality='facebook_comment_id', collection_method='selenium_auto',
                          collected_at='2026-10-26T00:00:00+00:00')
        for filename, content in [('input.json', json.dumps(prepare([original]))),
                                  ('input.csv', csv_bytes(prepare([original])).decode('utf-8-sig'))]:
            row = parse_import(content, filename)[0]
            for key in ('post_url', 'parent_comment_id', 'identifier_quality', 'collection_method', 'collected_at'):
                self.assertEqual(row[key], original[key])
            self.assertEqual(row['label_source'], 'imported')

    def test_cleaning_keeps_negation_and_never_mutates_source(self):
        examples = ['Không phải đồ ngu', 'Chưa từng xúc phạm bạn', 'Đừng chửi người khác 😡', 'ko đồng ý', 'Xin chào!']
        rows = [sample(comment_id=str(i), text_raw=text) for i, text in enumerate(examples)]
        before = json.dumps(rows)
        prepare(rows)
        self.assertEqual(json.dumps(rows), before)
        for text in examples:
            cleaned = clean_text(text)
            self.assertEqual(clean_text(cleaned), cleaned)
        self.assertNotEqual(clean_text('đồ ngu'), clean_text('không phải đồ ngu'))

    def test_reprepare_clears_derived_duplicate_references(self):
        source = [sample(), sample(comment_id='3', label='')]
        prepared = prepare(source)
        self.assertIn('duplicate_of', prepared[1])
        reviewed = prepare(prepared, {row_id(source[0]): dict(excluded=True)})
        self.assertEqual(reviewed[1]['quality'], 'ready')
        self.assertNotIn('duplicate_of', reviewed[1])

    def test_bom_json_and_note_validation(self):
        self.assertEqual(len(parse_import('\ufeff' + json.dumps([sample()]), 'input.json')), 1)
        for note in (None, {}, 'x' * 2001):
            with self.subTest(note=type(note).__name__), self.assertRaises(ValueError):
                parse_import(json.dumps([sample(annotation_note=note)]), 'input.json')


if __name__ == '__main__':
    unittest.main()
