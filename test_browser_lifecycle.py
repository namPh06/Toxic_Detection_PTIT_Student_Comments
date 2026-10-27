"""Browser lifecycle checks use fake drivers and never launch or contact Facebook."""
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, TimeoutException, WebDriverException

import app


class BrowserNavigationTests(unittest.TestCase):
    def test_renderer_crash_replaces_tab_and_retries_navigation(self):
        driver = Mock()
        with patch.object(app, '_navigate_once', side_effect=[WebDriverException('tab crashed'), None]) as navigate, \
                patch.object(app, 'replace_crashed_tab') as replace, patch.object(app.time, 'sleep'), patch.object(app, 'update'):
            app.navigate(driver, 'https://www.facebook.com/')
        self.assertEqual(navigate.call_count, 2)
        replace.assert_called_once_with(driver)

    def test_renderer_crash_retry_is_bounded(self):
        driver = Mock()
        with patch.object(app, '_navigate_once', side_effect=WebDriverException('tab crashed')) as navigate, \
                patch.object(app, 'replace_crashed_tab') as replace, patch.object(app.time, 'sleep'), patch.object(app, 'update'):
            with self.assertRaises(WebDriverException):
                app.navigate(driver, 'https://www.facebook.com/', attempts=3)
        self.assertEqual(navigate.call_count, 3)
        self.assertEqual(replace.call_count, 2)

    def test_closed_session_is_not_retried_as_a_renderer_crash(self):
        driver = Mock()
        with patch.object(app, '_navigate_once', side_effect=InvalidSessionIdException('browser closed')) as navigate, \
                patch.object(app, 'replace_crashed_tab') as replace:
            with self.assertRaises(InvalidSessionIdException):
                app.navigate(driver, 'https://www.facebook.com/')
        self.assertEqual(navigate.call_count, 1)
        replace.assert_not_called()

    def test_timeout_requires_reached_host_and_responding_renderer(self):
        driver = Mock(current_url='https://www.facebook.com/groups/ptit/')
        driver.get.side_effect = TimeoutException('slow resources')
        with patch.object(app, 'update'):
            app._navigate_once(driver, 'https://www.facebook.com/')
        driver.execute_script.assert_any_call('return document.readyState;')
        driver.current_url = 'about:blank'
        with self.assertRaises(RuntimeError):
            app._navigate_once(driver, 'https://www.facebook.com/')
        driver.current_url = 'https://www.facebook.com/'
        driver.execute_script.side_effect = InvalidSessionIdException('browser closed')
        with self.assertRaises(InvalidSessionIdException):
            app._navigate_once(driver, 'https://www.facebook.com/')

    def test_failed_replacement_does_not_close_existing_tab(self):
        driver = Mock(current_window_handle='old')
        driver.switch_to.new_window.side_effect = WebDriverException('cannot create new tab')
        with self.assertRaises(WebDriverException):
            app.replace_crashed_tab(driver)
        driver.close.assert_not_called()


class BrowserLifecycleTests(unittest.TestCase):
    def test_closed_active_tab_switches_to_remaining_tab(self):
        driver = Mock(window_handles=['first', 'remaining'])
        type(driver).current_window_handle = PropertyMock(side_effect=NoSuchWindowException('tab closed'))
        app.check_browser(driver)
        driver.switch_to.window.assert_called_once_with('remaining')
        driver.close.assert_not_called()

    def test_missing_active_handle_switches_to_remaining_tab(self):
        driver = Mock(window_handles=['remaining'], current_window_handle='closed')
        app.check_browser(driver)
        driver.switch_to.window.assert_called_once_with('remaining')

    def test_no_remaining_windows_is_a_dead_session(self):
        driver = Mock(window_handles=[])
        with self.assertRaises(InvalidSessionIdException):
            app.check_browser(driver)

    def run_worker(self, commands, *, handles=None, startup_error=None, batch_error=None, quit_error=None, log_error=None):
        driver = Mock(current_window_handle='tab')
        type(driver).window_handles = PropertyMock(side_effect=handles or [['tab']] * 10)
        driver.quit.side_effect = quit_error
        command_queue = Mock()
        command_queue.get.side_effect = commands
        state = dict(app.STATE, phase='opening', ready=False, running=False, requested_source='')
        rows = {('p', 'c'): dict(post_id='p', comment_id='c', text_raw='Bình luận đã giữ', label='')}
        with tempfile.TemporaryDirectory() as directory, \
                patch.multiple(app, STATE=state, COMMANDS=command_queue, DATA=Path(directory), ROWS=rows), \
                patch('selenium.webdriver.Chrome', return_value=driver), \
                patch('selenium.webdriver.common.selenium_manager.SeleniumManager.binary_paths', return_value={'driver_path': 'fake-driver.exe'}), \
                patch.object(app, 'navigate', side_effect=startup_error), \
                patch.object(app, 'run_batch', side_effect=batch_error) as batch:
            if log_error:
                with patch.object(Path, 'write_text', side_effect=log_error):
                    app.worker()
            else:
                app.worker()
            self.assertEqual(app.payload()['rows'], list(rows.values()))
        return state, driver, command_queue, batch

    def test_idle_browser_close_exits_worker_and_allows_reopen(self):
        state, driver, commands, _ = self.run_worker([queue.Empty()], handles=[['tab'], []])
        self.assertFalse(state['ready'])
        self.assertFalse(state['running'])
        self.assertEqual(state['phase'], 'error')
        commands.get.assert_called_once_with(timeout=1)
        driver.quit.assert_called_once()

    def test_session_lost_inside_batch_is_detected_even_when_batch_returns(self):
        state, driver, commands, batch = self.run_worker(['start'], handles=[['tab'], ['tab'], [], []])
        batch.assert_called_once_with(driver)
        self.assertEqual(commands.get.call_count, 1)
        self.assertFalse(state['ready'])
        self.assertFalse(state['running'])
        self.assertEqual(state['phase'], 'error')

    def test_dead_session_error_is_not_reported_as_an_open_browser(self):
        state, _, commands, _ = self.run_worker(['start'], handles=[['tab'], ['tab'], []], batch_error=InvalidSessionIdException('browser closed'))
        self.assertEqual(commands.get.call_count, 1)
        self.assertFalse(state['ready'])
        self.assertNotIn('Chrome vẫn mở', state['message'])

    def test_logging_and_quit_failures_do_not_strand_opening_state(self):
        state, driver, _, _ = self.run_worker([], startup_error=InvalidSessionIdException('browser closed'),
                                              quit_error=InvalidSessionIdException('already closed'), log_error=OSError('disk full'))
        self.assertFalse(state['ready'])
        self.assertFalse(state['running'])
        self.assertEqual(state['phase'], 'error')
        self.assertIn('mở lại', state['message'])
        driver.quit.assert_called_once()

    def test_recoverable_batch_error_keeps_worker_available_for_next_command(self):
        state, driver, commands, batch = self.run_worker(['start', 'quit'], batch_error=OSError('disk full'))
        batch.assert_called_once_with(driver)
        self.assertEqual(commands.get.call_count, 2)
        self.assertIn('disk full', state['message'])
        self.assertFalse(state['ready'])
        driver.quit.assert_called_once()

    def test_reopen_waits_for_previous_worker_to_finish_quitting(self):
        handler = app.Handler.__new__(app.Handler)
        handler.path = '/api/browser'
        previous = Mock()
        previous.is_alive.return_value = True
        state = dict(app.STATE, phase='error', ready=False, running=False)
        with patch.multiple(app, STATE=state, BROWSER_THREAD=previous), patch.object(app.threading, 'Thread') as factory:
            with self.assertRaises(ValueError):
                handler.post_route({})
        factory.assert_not_called()

    def test_reopen_discards_old_commands_before_new_worker_starts(self):
        handler = app.Handler.__new__(app.Handler)
        handler.path = '/api/browser'
        previous = Mock()
        previous.is_alive.return_value = False
        commands = queue.Queue()
        commands.put('start')
        commands.put('quit')
        state = dict(app.STATE, phase='error', ready=False, running=False)
        replacement = Mock()
        replacement.start.side_effect = lambda: self.assertTrue(commands.empty())
        with patch.multiple(app, STATE=state, BROWSER_THREAD=previous, COMMANDS=commands), \
                patch.object(app.threading, 'Thread', return_value=replacement):
            handler.post_route({})
            replacement.start.assert_called_once()
            self.assertIs(app.BROWSER_THREAD, replacement)
        self.assertEqual(state['phase'], 'opening')

    def test_thread_start_failure_does_not_block_next_open(self):
        handler = app.Handler.__new__(app.Handler)
        handler.path = '/api/browser'
        state = dict(app.STATE, phase='error', ready=False, running=False)
        replacement = Mock()
        replacement.start.side_effect = [RuntimeError('cannot start thread'), None]
        with patch.multiple(app, STATE=state, BROWSER_THREAD=None, COMMANDS=queue.Queue()), \
                patch.object(app.threading, 'Thread', return_value=replacement):
            with self.assertRaises(RuntimeError):
                handler.post_route({})
            self.assertEqual(state['phase'], 'error')
            self.assertFalse(state['ready'])
            self.assertIsNone(app.BROWSER_THREAD)
            handler.post_route({})
            self.assertEqual(state['phase'], 'opening')


if __name__ == '__main__':
    unittest.main()
