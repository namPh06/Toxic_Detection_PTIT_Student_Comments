"""Manual sign-in launcher checks; never launch a browser or read account cookies."""
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import dang_nhap


class ManualLoginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Project with spaces'
        (self.root / 'chrome-profile').mkdir(parents=True)
        self.chrome = self.root / 'Programs' / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
        self.chrome.parent.mkdir(parents=True)
        self.chrome.touch()
        self.addCleanup(patch.stopall)
        patch.object(dang_nhap, 'ROOT', self.root).start()
        patch.dict(dang_nhap.os.environ, {'PROGRAMFILES': str(self.root / 'Programs')}).start()
        self.launch = patch.object(dang_nhap.subprocess, 'Popen').start()
        self.request = patch.object(dang_nhap.urllib.request, 'urlopen').start()

    def test_manual_launch_uses_same_profile_without_webdriver_or_debug_flags(self):
        dang_nhap.open_login()
        self.launch.assert_called_once_with([
            str(self.chrome), '--user-data-dir=' + str(self.root / 'chrome-profile'),
            '--disable-background-mode', 'https://www.facebook.com/'])
        self.request.assert_not_called()
        self.assertEqual(list((self.root / 'chrome-profile').iterdir()), [])

    def test_active_automation_profile_refuses_to_launch(self):
        (self.root / 'chrome-profile' / 'DevToolsActivePort').write_text('54321\n/devtools/browser/test')
        self.request.return_value.__enter__.return_value = Mock()
        with self.assertRaisesRegex(RuntimeError, 'dong cua so Chrome'):
            dang_nhap.open_login()
        self.launch.assert_not_called()
        self.request.assert_called_once_with('http://127.0.0.1:54321/json/version', timeout=2)

    def test_stale_or_invalid_debug_file_does_not_block_manual_login(self):
        port_file = self.root / 'chrome-profile' / 'DevToolsActivePort'
        self.request.side_effect = urllib.error.URLError('closed')
        for contents in ('54321\n/stale', 'not-a-port', '', '70000'):
            with self.subTest(contents=contents):
                self.launch.reset_mock()
                port_file.write_text(contents)
                dang_nhap.open_login()
                self.launch.assert_called_once()
                self.assertEqual(port_file.read_text(), contents)

    def test_missing_chrome_does_not_launch(self):
        with patch.object(Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'Khong tim thay Google Chrome'):
                dang_nhap.open_login()
        self.launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
