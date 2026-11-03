"""Crawler persistence tests use fake drivers; no Facebook requests or real data writes."""
import json
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch

import app


class CrawlerIntegrityTests(unittest.TestCase):
    def run_fixture(self, batches, *, step_error=None, open_error=None, stop_after_read=False, save_error=None, initial_rows=None):
        source = 'https://www.facebook.com/groups/ptit/'
        state = dict(app.STATE, source=source, target=1, results=[])
        rows, snapshots = dict(initial_rows or {}), []
        driver = Mock(current_url=source, current_window_handle='feed')
        driver.switch_to.new_window.side_effect = open_error or (lambda _kind: setattr(driver, 'current_window_handle', 'post'))
        driver.switch_to.window.side_effect = lambda handle: setattr(driver, 'current_window_handle', handle)
        stop = Mock()
        stop.wait.return_value = False
        reads = 0
        stop.is_set.side_effect = lambda: stop_after_read and reads > 0

        def script(_script, action=None, _expected=None):
            nonlocal reads
            if action == 'feed':
                return dict(posts=[dict(id='1', url=source + 'posts/1/')])
            if action == 'read':
                batch = batches[min(reads, len(batches) - 1)]
                reads += 1
                return dict(rows=batch)
            if action == 'advance' and step_error:
                raise step_error
            return dict(moved=False)

        driver.execute_script.side_effect = script
        def save():
            if save_error:
                raise save_error
            snapshots.append(json.loads(json.dumps(app.payload())))

        with patch.multiple(app, STATE=state, ROWS=rows, STOP=stop), patch.object(app, 'save', side_effect=save):
            if save_error:
                with self.assertRaises(type(save_error)):
                    app.run_batch(driver)
                self.assertEqual(app.payload()['rows'], list(rows.values()))
            else:
                app.run_batch(driver)
        return state, rows, snapshots, driver

    def test_expanded_comment_replaces_partial_text_even_when_shorter(self):
        partial = dict(comment_id='a', text_raw='Nội dung...', text_complete=False)
        complete = dict(comment_id='a', text_raw='Nội dung', text_complete=True)
        state, rows, _, _ = self.run_fixture([[partial], [complete]])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[('1', 'a')]['text_raw'], 'Nội dung')
        self.assertTrue(rows[('1', 'a')]['text_complete'])
        self.assertEqual(state['results'][0]['reason'], 'no_progress')

    def test_collapsed_copy_does_not_downgrade_saved_complete_text(self):
        complete = dict(comment_id='a', text_raw='Nội dung bình luận đầy đủ', text_complete=True)
        partial = dict(comment_id='a', text_raw='Nội dung...', text_complete=False)
        _, rows, _, _ = self.run_fixture([[complete], [partial]])
        self.assertEqual(rows[('1', 'a')]['text_raw'], complete['text_raw'])
        self.assertTrue(rows[('1', 'a')]['text_complete'])

    def test_raw_legacy_label_invalidated_only_when_text_changes(self):
        prior = dict(post_id='1', comment_id='a', text_raw='Nội dung...', text_complete=False, label='non-toxic')
        complete = dict(comment_id='a', text_raw='Nội dung', text_complete=True)
        _, rows, snapshots, _ = self.run_fixture([[complete]], initial_rows={('1', 'a'): dict(prior)})
        self.assertEqual(rows[('1', 'a')]['label'], '')
        self.assertEqual(rows[('1', 'a')]['invalidated_raw_label'], dict(label='non-toxic', text_hash=app.text_hash(prior['text_raw'])))
        self.assertEqual(snapshots[-1]['rows'][0]['invalidated_raw_label'], rows[('1', 'a')]['invalidated_raw_label'])
        _, unchanged, _, _ = self.run_fixture([[dict(complete, text_raw=prior['text_raw'])]], initial_rows={('1', 'a'): dict(prior)})
        self.assertEqual(unchanged[('1', 'a')]['label'], 'non-toxic')
        self.assertNotIn('invalidated_raw_label', unchanged[('1', 'a')])

    def test_crawl_error_keeps_collected_rows_and_records_failed_post(self):
        row = dict(comment_id='a', text_raw='Bình luận đã đọc', text_complete=True)
        state, rows, snapshots, driver = self.run_fixture([[row]], step_error=RuntimeError('tab crashed'))
        self.assertEqual(state['phase'], 'error')
        self.assertFalse(state['running'])
        self.assertEqual(state['results'][0]['reason'], 'crawl_error')
        self.assertEqual(state['results'][0]['error'], 'tab crashed')
        self.assertEqual(state['results'][0]['count'], 1)
        self.assertEqual(snapshots[-1]['rows'], list(rows.values()))
        driver.close.assert_called_once()
        self.assertEqual(driver.current_window_handle, 'feed')

    def test_open_failure_does_not_close_the_feed(self):
        state, _, _, driver = self.run_fixture([[]], open_error=RuntimeError('cannot create tab'))
        driver.close.assert_not_called()
        self.assertEqual(state['results'][0]['reason'], 'crawl_error')
        self.assertFalse(state['running'])

    def test_save_failure_preserves_collected_rows_for_download(self):
        row = dict(comment_id='a', text_raw='Bình luận chưa ghi được xuống đĩa', text_complete=True)
        state, rows, snapshots, driver = self.run_fixture([[row]], save_error=OSError('disk full'))
        self.assertEqual(rows[('1', 'a')]['text_raw'], row['text_raw'])
        self.assertEqual(state['phase'], 'error')
        self.assertFalse(state['running'])
        self.assertEqual(state['results'][0]['reason'], 'crawl_error')
        self.assertEqual(state['results'][0]['error'], 'disk full')
        self.assertEqual(snapshots, [])
        self.assertEqual(driver.current_window_handle, 'feed')

    def test_stop_keeps_partial_row_and_honest_completion_status(self):
        row = dict(comment_id='a', text_raw='Chưa mở hết...', text_complete=False)
        state, rows, snapshots, _ = self.run_fixture([[row]], stop_after_read=True)
        self.assertEqual(state['results'][0]['reason'], 'user_stop')
        self.assertFalse(rows[('1', 'a')]['text_complete'])
        self.assertEqual(snapshots[-1]['completeness'], 'not_verified')
        self.assertFalse(state['running'])

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for JS helper checks')
    def test_group_aliases_require_matching_facebook_group_metadata(self):
        script = r"""
const assert = require('node:assert/strict');
const H = require('./helpers.js');
const group = {__typename:'Group', id:'450310163844833', url:'https://www.facebook.com/groups/2k5ptit/'};
const unrelated = {__typename:'Group', id:'999', url:'https://www.facebook.com/groups/another/'};
const scripts = ['invalid JSON', JSON.stringify({data:[group, unrelated]})];
assert.deepEqual([...H.groupAliases('450310163844833', scripts)].sort(), ['2k5ptit','450310163844833']);
assert.deepEqual([...H.groupAliases('2k5ptit', scripts)].sort(), ['2k5ptit','450310163844833']);
assert.deepEqual([...H.groupAliases('unknown', scripts)], ['unknown']);
for (const url of ['https://evil.test/groups/2k5ptit/', 'https://facebook.com.evil.test/groups/2k5ptit/', 'http://facebook.com/groups/2k5ptit/', 'https://facebook.com/groups/2k5ptit/posts/1/']) {
  assert.deepEqual([...H.groupAliases(group.id, [JSON.stringify({...group, url})])], [group.id], url);
}
assert.deepEqual([...H.groupAliases(group.id, [JSON.stringify({...group, __typename:'User'})])], [group.id]);
"""
        result = subprocess.run(['node', '-e', script], cwd=app.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for JS helper checks')
    def test_comment_urls_and_fallback_expansion_identity(self):
        script = r"""
const assert = require('node:assert/strict');
let H = require('./helpers.js');
for (const url of ['https://evil.test/?comment_id=123', 'https://facebook.com.evil.test/?comment_id=123', 'http://facebook.com/?comment_id=123', 'javascript:alert(1)', 'https://facebook.com/?comment_id=a%20b']) {
  assert.equal(H.commentInfo(url).id, '', url);
}
assert.deepEqual(H.commentInfo('https://www.facebook.com/groups/g/posts/1/?comment_id=2&reply_comment_id=3'), {id:'3',parent:'2'});
const node = {}, id = H.fallbackCommentId(node, '1', 'Student', 'Nội dung...', false);
delete require.cache[require.resolve('./helpers.js')];
H = require('./helpers.js');
assert.equal(H.fallbackCommentId(node, '1', 'Student', 'Nội dung đầy đủ', true), id);
assert.equal(H.fallbackCommentId(node, '1', 'Student', 'Nội dung đầy đủ', true), id);
assert.notEqual(H.fallbackCommentId(node, '1', 'Student', 'Một bình luận khác', true), id);
assert.notEqual(H.fallbackCommentId(node, '2', 'Student', 'Nội dung đầy đủ', true), id);
console.log('Comment URL validation and fallback identity checks passed');
"""
        result = subprocess.run(['node', '-e', script], cwd=app.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
