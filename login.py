"""Open the project's Chrome profile for sign-in completed by the user."""
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def open_login():
    # Reusing a running WebDriver profile would reopen the same automated browser.
    try:
        port = int((ROOT / 'chrome-profile' / 'DevToolsActivePort').read_text().splitlines()[0])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid local port')
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=2):
            pass
    except (OSError, ValueError, IndexError, urllib.error.URLError):
        pass
    else:
        raise RuntimeError('Hay dong cua so Chrome thu thap cua tool truoc, roi chay lai DANG_NHAP_FACEBOOK.cmd.')

    candidates = [Path(os.environ.get(v, d)) / 'Google/Chrome/Application/chrome.exe'
                  for v, d in (('PROGRAMFILES', r'C:\Program Files'),
                               ('PROGRAMFILES(X86)', r'C:\Program Files (x86)'), ('LOCALAPPDATA', ''))]
    chrome = next((path for path in candidates if path.is_file()), None)
    if chrome is None:
        raise RuntimeError('Khong tim thay Google Chrome. Hay cai Chrome roi thu lai.')
    subprocess.Popen([str(chrome), '--user-data-dir=' + str(ROOT / 'chrome-profile'),
                      '--disable-background-mode', 'https://www.facebook.com/'])
    print('Da mo Chrome de dang nhap thu cong trong ho so cua project.')
    print('1. Tu dang nhap Facebook va hoan tat xac minh neu duoc yeu cau.')
    print('2. Dang nhap xong, dong cua so Chrome nay.')
    print('3. Quay lai tool, bam Mo Chrome thu thap, roi mo nhom can lay du lieu.')


if __name__ == '__main__':
    try:
        open_login()
    except (OSError, RuntimeError) as error:
        print(str(error))
        raise SystemExit(1)
