"""Local Selenium controller. Credentials stay in the browser, never read by this app."""
import json
import os
import queue
import threading
import time
import webbrowser
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dataset import atomic_json, csv_bytes, text_hash
from lab import Lab

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
COMMANDS = queue.Queue()
BROWSER_THREAD = None
STOP = threading.Event()
LOCK = threading.RLock()
STATE = dict(phase='idle', message='Dữ liệu đã sẵn sàng. Mở Chrome khi cần thu thập thêm.', ready=False, running=False, posts=0, comments=0, target=20, source='', results=[])
STATE['version'] = '3.0-comment-lab'
ROWS = {}
HELPERS = (ROOT / 'helpers.js').read_text(encoding='utf-8')
DOM = (ROOT / 'dom.js').read_text(encoding='utf-8')

def update(**values):
    with LOCK:
        STATE.update(values)

def payload():
    with LOCK:
        return dict(schema_version=1, source=STATE['source'], completeness='not_verified', posts=[dict(r) for r in STATE['results']], rows=[dict(r) for r in ROWS.values()])

def save():
    with LOCK:
        atomic_json(DATA / 'progress.json', payload())

def restore():
    file = DATA / 'progress.json'
    if file.exists():
        data = json.loads(file.read_text(encoding='utf-8'))
        for row in data.get('rows', []):
            ROWS[(row['post_id'], row['comment_id'])] = row
        results = data.get('posts', [])
        update(source=data.get('source', ''), results=results, posts=len(results), comments=len(ROWS))

def is_tab_crash(error):
    text = str(error).lower()
    return 'tab crashed' in text or 'target frame detached' in text

def replace_crashed_tab(driver):
    """Open a fresh tab and drop the crashed one; the Chrome process itself is still alive."""
    crashed = driver.current_window_handle
    driver.switch_to.new_window('tab')
    fresh = driver.current_window_handle
    try:
        driver.switch_to.window(crashed)
        driver.close()
    except Exception:
        pass
    driver.switch_to.window(fresh)
    return fresh

def navigate(driver, url, attempts=3):
    """A crashed renderer tab is replaced and retried instead of killing the whole session."""
    from selenium.common.exceptions import WebDriverException
    for attempt in range(attempts):
        try:
            return _navigate_once(driver, url)
        except WebDriverException as error:
            if not is_tab_crash(error) or attempt == attempts - 1:
                raise
            update(message=f'Tab Chrome bị crash khi tải trang, đang mở tab mới và thử lại ({attempt + 2}/{attempts})…')
            time.sleep(2)
            replace_crashed_tab(driver)

def _navigate_once(driver, url):
    """A slow image/feed must not destroy an otherwise usable browser session."""
    from selenium.common.exceptions import TimeoutException
    try:
        driver.get(url)
    except TimeoutException:
        # Facebook may keep loading resources long after its page is usable.
        # Continue only if the browser still responds and reached the requested host.
        driver.execute_script('window.stop();')
        current = urlparse(driver.current_url)
        expected = urlparse(url)
        if current.hostname != expected.hostname:
            raise RuntimeError('Trang tải quá lâu và chưa tới Facebook. Kiểm tra mạng rồi mở lại công cụ.')
        driver.execute_script('return document.readyState;')
        update(message='Facebook tải chậm; đã giữ phiên Chrome. Chờ trang hiển thị rồi tiếp tục.')

def check_browser(driver):
    """Recover a closed selected tab, but never reuse a dead browser session."""
    from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
    handles = driver.window_handles
    if not handles:
        raise InvalidSessionIdException('Chrome không còn cửa sổ nào. Bấm Mở Chrome thu thập để mở lại.')
    try:
        current = driver.current_window_handle
    except NoSuchWindowException:
        current = None
    if current not in handles:
        driver.switch_to.window(handles[-1])

def scope_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not (parsed.hostname == 'facebook.com' or (parsed.hostname or '').endswith('.facebook.com')):
        return False
    parts = parsed.path.strip('/').split('/')
    return bool(parts[0]) and not any(x in parts for x in ('posts', 'permalink', 'login', 'checkpoint', 'watch', 'reel', 'reels')) and (parts[0] != 'groups' or len(parts) >= 2)

def run_batch(driver):
    target = STATE['target']
    source = driver.current_url
    if not scope_url(source):
        update(message='Hãy vào trang nhóm hoặc fanpage trong Chrome của công cụ, rồi bấm Bắt đầu.', phase='ready', running=False)
        return
    with LOCK:
        previous_source = STATE['source']
        if previous_source != source:
            STATE['results'] = []
        STATE.update(source=source, running=True, phase='discovering', posts=0)
    feed_handle = driver.current_window_handle
    posts = {}
    stale = 0
    try:
        for _ in range(max(60, target * 3)):
            if STOP.is_set():
                break
            driver.execute_script(HELPERS)
            result = driver.execute_script(DOM, 'feed', '')
            if not result.get('blocked') and not any(p['id'] not in posts for p in result.get('posts', [])):
                # Facebook can populate the timestamp href only after pointer hover.
                from selenium.webdriver.common.action_chains import ActionChains
                for element in driver.execute_script(DOM, 'feed_hover', ''):
                    if STOP.is_set():
                        break
                    try:
                        ActionChains(driver).move_to_element(element).perform()
                        STOP.wait(0.3)
                    except Exception:
                        continue
                result = driver.execute_script(DOM, 'feed', '')
            if result.get('blocked'):
                raise RuntimeError('Facebook yêu cầu đăng nhập/xác minh hoặc đang hạn chế. Đã dừng.')
            before = len(posts)
            for post in result.get('posts', []):
                posts.setdefault(post['id'], post)
            diag = result.get('diagnostics', {})
            update(message=f'Tìm được {min(len(posts),target)}/{target} bài · đọc {diag.get("anchors",0)} link, {diag.get("articles",0)} khối bài, {diag.get("candidates",0)} permalink nhận diện.')
            if len(posts) >= target:
                break
            step = driver.execute_script(DOM, 'feed_scroll', '')
            if step.get('blocked'):
                raise RuntimeError('Facebook yêu cầu đăng nhập/xác minh hoặc đang hạn chế. Đã dừng.')
            stale = stale + 1 if len(posts) == before and not step.get('moved') else 0
            if stale >= 5:
                break
            if STOP.wait(2.5):
                break
        chosen = list(posts.values())[:target]
        if not chosen and not STOP.is_set():
            raise RuntimeError('Không nhận diện được link bài trong nhóm/trang. Chưa thu thập bài nào.')
        for index, post in enumerate(chosen, 1):
            if STOP.is_set():
                break
            reason = 'time_limit'
            post_error = None
            update(phase='collecting', message=f'Bài {index}/{len(chosen)}: đang tải bình luận…')
            try:
                driver.switch_to.new_window('tab')
                navigate(driver, post['url'])
                if STOP.wait(3):
                    reason = 'user_stop'
                else:
                    started = time.monotonic()
                    stale = 0
                    missing = 0
                    while not STOP.is_set() and time.monotonic() - started < 180:
                        driver.execute_script(HELPERS)
                        result = driver.execute_script(DOM, 'read', post['id'])
                        if result.get('blocked'):
                            raise RuntimeError('Gặp đăng nhập/xác minh/hạn chế. Dừng toàn phiên, dữ liệu được giữ.')
                        if result.get('wrong_source'):
                            raise RuntimeError('Nguồn bài thay đổi. Dừng để tránh gán nhầm dữ liệu.')
                        if result.get('missing_scope'):
                            missing += 1
                            if missing >= 5:
                                reason = 'unrecognized_scope'
                                break
                            if STOP.wait(2.5):
                                break
                            continue
                        missing = 0
                        before = len(ROWS)
                        with LOCK:
                            for item in result.get('rows', []):
                                key = (post['id'], item['comment_id'])
                                if key in ROWS:
                                    old = ROWS[key]
                                    if len(item['text_raw']) > len(old['text_raw']) or (old.get('text_complete') is False and item.get('text_complete') is True):
                                        if item['text_raw'] != old['text_raw'] and old.get('label'):
                                            old['invalidated_raw_label'] = dict(label=old['label'], text_hash=text_hash(old['text_raw']))
                                            old['label'] = ''
                                        old['text_raw'] = item['text_raw']
                                        old['text_complete'] = item.get('text_complete')
                                    elif item['text_raw'] == old['text_raw'] and item.get('text_complete') is True:
                                        old['text_complete'] = True
                                    continue
                                if len(ROWS) >= 10000:
                                    break
                                ROWS[key] = dict(item, post_id=post['id'], post_url=post['url'], label='', annotation_note='', collection_method='selenium_auto', collected_at=datetime.now(timezone.utc).isoformat(), comment_filter='unknown')
                            STATE['comments'] = len(ROWS)
                        save()
                        if len(ROWS) >= 10000:
                            reason = 'dataset_limit'
                            STOP.set()
                            break
                        if STOP.is_set():
                            break
                        step = driver.execute_script(DOM, 'advance', post['id'])
                        if step.get('blocked') or step.get('wrong_source'):
                            raise RuntimeError('Gặp hạn chế hoặc đổi bài khi tải. Đã dừng.')
                        if step.get('missing_scope'):
                            if STOP.wait(2.5):
                                break
                            continue
                        stale = stale + 1 if len(ROWS) == before and not step.get('moved') and not step.get('clicked') else 0
                        if stale >= 5:
                            reason = 'no_progress'
                            break
                        update(message=f'Bài {index}/{len(chosen)} · {len(ROWS)} bình luận trong bộ dữ liệu. Đang tự cuộn/tải thêm…')
                        if STOP.wait(2.5):
                            break
                    if STOP.is_set() and reason != 'dataset_limit':
                        reason = 'user_stop'
            except Exception as error:
                reason, post_error = 'crawl_error', error
            finally:
                try:
                    if driver.current_window_handle != feed_handle:
                        driver.close()
                except Exception as error:
                    reason, post_error = 'crawl_error', post_error or error
                try:
                    driver.switch_to.window(feed_handle)
                except Exception as error:
                    reason, post_error = 'crawl_error', post_error or error
            with LOCK:
                STATE['results'] = [r for r in STATE['results'] if r['post_id'] != post['id']]
                result = dict(post_id=post['id'], url=post['url'], reason=reason, count=sum(r['post_id'] == post['id'] for r in ROWS.values()), completeness='not_verified')
                if post_error:
                    result['error'] = str(post_error).split('Stacktrace:')[0].strip()[:500]
                STATE['results'].append(result)
            update(posts=index)
            save()
            if post_error:
                raise post_error
            if STOP.wait(2):
                break
        update(phase='ready', message='Đã dừng theo yêu cầu.' if STOP.is_set() else f'Đã xử lý {STATE["posts"]}/{len(chosen)} bài. Không xác nhận đã lấy đủ bình luận.')
    except Exception as error:
        update(phase='error', message=str(error))
        save()
    finally:
        update(running=False)

def worker():
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        options = webdriver.ChromeOptions()
        options.page_load_strategy = 'eager'
        options.add_argument('--start-maximized')
        options.add_argument('--user-data-dir=' + str(ROOT / 'chrome-profile'))
        # Resolve explicitly, ignoring obsolete chromedriver.exe on PATH.
        os.environ.pop('SE_CHROMEDRIVER', None)
        candidates = [Path(os.environ.get(v, d)) / 'Google/Chrome/Application/chrome.exe' for v, d in (('PROGRAMFILES', r'C:\Program Files'), ('PROGRAMFILES(X86)', r'C:\Program Files (x86)'), ('LOCALAPPDATA', ''))]
        chrome = next((c for c in candidates if c.exists()), candidates[0])
        args = ['--browser', 'chrome', '--skip-driver-in-path', '--cache-path', str(ROOT / 'driver-cache')]
        if chrome.exists():
            options.binary_location = str(chrome)
            args.extend(['--browser-path', str(chrome)])
        update(message='Đang tìm/tải ChromeDriver phù hợp với Chrome. Cần Internet lần đầu…')
        resolved = SeleniumManager().binary_paths(args)
        if not options.binary_location and resolved.get('browser_path'):
            options.binary_location = resolved['browser_path']
        driver = webdriver.Chrome(service=Service(executable_path=resolved['driver_path']), options=options)
        driver.set_page_load_timeout(35)
        navigate(driver, 'https://www.facebook.com/')
        check_browser(driver)
        update(ready=True, phase='ready', message='Tự đăng nhập và vào nhóm/trang trong Chrome vừa mở. Sau đó bấm Bắt đầu.')
        while True:
            try:
                command = COMMANDS.get(timeout=1)
            except queue.Empty:
                check_browser(driver)
                continue
            if command == 'quit':
                break
            if command == 'start':
                try:
                    check_browser(driver)
                    if STATE.get('requested_source'):
                        navigate(driver, STATE['requested_source'])
                    run_batch(driver)
                    check_browser(driver)
                except Exception as error:
                    check_browser(driver)
                    summary = str(error).split('Stacktrace:')[0].strip()[:500]
                    update(phase='error', running=False, message=f'Lỗi thu thập/lưu dữ liệu: {summary}. Bình luận đã đọc vẫn được giữ trong phiên; tải bản sao trước khi đóng công cụ. Chrome vẫn mở để thử lại.')
    except Exception as error:
        from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
        summary = str(error).split('Stacktrace:')[0].strip()[:700]
        if isinstance(error, (InvalidSessionIdException, NoSuchWindowException)):
            message = 'Phiên Chrome đã đóng hoặc mất kết nối. Bấm Mở Chrome thu thập để mở lại; dữ liệu và nhãn đã lưu vẫn được giữ.'
        elif is_tab_crash(error):
            message = 'Tab Chrome bị crash. Hãy tắt máy chủ cũ bằng Ctrl+C rồi chạy MO_CONG_CU.cmd từ thư mục project để mở công cụ trong phiên Windows bình thường.'
        else:
            message = f'Không mở/điều khiển được Chrome: {summary}. Bạn vẫn có thể làm sạch, gán nhãn và huấn luyện.'
        update(ready=False, running=False, phase='error', message=message)
        try:
            DATA.mkdir(exist_ok=True)
            (DATA / 'startup-error.txt').write_text(str(error), encoding='utf-8')
        except OSError:
            pass
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        finally:
            update(ready=False, running=False)


LAB = Lab(DATA, lambda: payload()['rows'])

class LocalHTTPServer(ThreadingHTTPServer):
    # Windows otherwise lets two app instances bind the same port and write one workspace.
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, content, kind, code=200, filename=None):
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def json(self, body, code=200):
        self.send(json.dumps(body, ensure_ascii=False).encode(), 'application/json;charset=utf-8', code)

    def valid_host(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send(b'Forbidden host', 'text/plain', 403)
            return False
        return True

    def do_GET(self):
        if not self.valid_host():
            return
        try:
            self.get_route()
        except ConnectionError:
            return
        except (ValueError, TypeError) as error:
            self.json(dict(error=str(error)), 400)
        except Exception as error:
            self.json(dict(error=f'Không đọc được dữ liệu: {error}'), 500)

    def get_route(self):
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        static = {
            '/': ('index.html', 'text/html'),
            '/ui.js': ('ui.js', 'text/javascript'),
            '/style.css': ('style.css', 'text/css'),
            '/assets/fonts/be-vietnam-pro-400.ttf': ('assets/fonts/be-vietnam-pro-400.ttf', 'font/ttf'),
            '/assets/fonts/be-vietnam-pro-500.ttf': ('assets/fonts/be-vietnam-pro-500.ttf', 'font/ttf'),
            '/assets/fonts/be-vietnam-pro-600.ttf': ('assets/fonts/be-vietnam-pro-600.ttf', 'font/ttf'),
            '/assets/fonts/be-vietnam-pro-700.ttf': ('assets/fonts/be-vietnam-pro-700.ttf', 'font/ttf'),
        }
        if path in static:
            filename, kind = static[path]
            self.send((ROOT / filename).read_bytes(), kind + ';charset=utf-8')
        elif path == '/favicon.ico':
            self.send(b'', 'image/x-icon', 204)
        elif path == '/status':
            with LOCK:
                body = json.dumps(STATE, ensure_ascii=False).encode()
            self.send(body, 'application/json;charset=utf-8')
        elif path == '/download':
            self.send(json.dumps(payload(), ensure_ascii=False, indent=2).encode(), 'application/json;charset=utf-8', filename='ptit_selenium_comments.json')
        elif path == '/api/status':
            self.json(LAB.status())
        elif path == '/api/rows':
            rows = LAB.rows()
            search = query.get('q', [''])[0].casefold()
            label = query.get('label', ['all'])[0]
            quality = query.get('quality', ['all'])[0]
            rows = [r for r in rows if (not search or search in str(r.get('text_raw', '')).casefold())
                    and (label == 'all' or r['label'] == ('' if label == 'unlabeled' else label))
                    and (quality == 'all' or r['quality'] == quality)]
            page = max(1, int(query.get('page', ['1'])[0]))
            self.json(dict(total=len(rows), page=page, rows=rows[(page - 1) * 25:page * 25]))
        elif path in ('/api/export.csv', '/api/export.json'):
            rows = LAB.rows()
            if path.endswith('.csv'):
                self.send(csv_bytes(rows), 'text/csv;charset=utf-8', filename='ptit_cleaned.csv')
            else:
                self.send(json.dumps(dict(rows=rows), ensure_ascii=False, indent=2).encode(), 'application/json;charset=utf-8', filename='ptit_cleaned.json')
        elif path in ('/api/dataset.csv', '/api/dataset.json'):
            rows = LAB.dataset_rows()
            if path.endswith('.csv'):
                self.send(csv_bytes(rows), 'text/csv;charset=utf-8', filename='ptit_reviewed_dataset.csv')
            else:
                self.send(json.dumps(dict(schema_version=2, label_policy='reviewed_only', rows=rows), ensure_ascii=False, indent=2).encode(),
                          'application/json;charset=utf-8', filename='ptit_reviewed_dataset.json')
        elif path in ('/api/dataset-auto.csv', '/api/dataset-auto.json'):
            rows = LAB.dataset_rows(reviewed_only=False)
            if path.endswith('.csv'):
                self.send(csv_bytes(rows), 'text/csv;charset=utf-8', filename='ptit_dataset_auto.csv')
            else:
                self.send(json.dumps(dict(schema_version=2, label_policy='includes_automatic', rows=rows), ensure_ascii=False, indent=2).encode(),
                          'application/json;charset=utf-8', filename='ptit_dataset_auto.json')
        elif path == '/api/report':
            self.send(LAB.report().encode(), 'text/markdown;charset=utf-8', filename='bao_cao_ptit.md')
        elif path == '/api/results.json':
            self.send(json.dumps(LAB.result(), ensure_ascii=False, indent=2).encode(), 'application/json;charset=utf-8', filename='metrics.json')
        else:
            self.send(b'Not found', 'text/plain', 404)

    def do_POST(self):
        # Browser pages from another origin cannot start automation on this local service.
        if not self.valid_host():
            return
        if self.headers.get('Origin') != f'http://127.0.0.1:{self.server.server_port}':
            self.send(b'Forbidden', 'text/plain', 403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 15_000_000 or self.headers.get_content_type() != 'application/json':
                raise ValueError('Yêu cầu JSON, tối đa 15 MB.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Yêu cầu phải là JSON object.')
            answer = self.post_route(body)
            if answer is not None:
                self.json(answer)
        except ConnectionError:
            return
        except (ValueError, TypeError, KeyError) as error:
            self.json(dict(error=str(error)), 400)
        except Exception as error:
            self.json(dict(error=f'Không thực hiện được: {error}'), 500)

    def post_route(self, body):
        if self.path == '/start':
            target, source = body.get('target'), body.get('source', '')
            if type(target) is not int or not 1 <= target <= 500:
                raise ValueError('Số bài phải là số nguyên từ 1 đến 500.')
            if not isinstance(source, str) or len(source) > 2000 or (source and not scope_url(source)):
                raise ValueError('Nhập URL https của nhóm/fanpage Facebook, hoặc để trống để dùng tab hiện tại.')
            with LOCK:
                if not STATE['ready'] or STATE['running']:
                    self.send(b'Not ready', 'text/plain', 409)
                    return
                STATE['target'] = target
                STATE['requested_source'] = source
                STATE['running'] = True
                STATE['message'] = 'Đang bắt đầu…'
                STOP.clear()
                COMMANDS.put('start')
        elif self.path == '/stop':
            STOP.set()
        elif self.path == '/api/browser':
            global BROWSER_THREAD
            with LOCK:
                if STATE['ready'] or STATE['phase'] == 'opening' or (BROWSER_THREAD and BROWSER_THREAD.is_alive()):
                    raise ValueError('Chrome đã mở hoặc đang khởi động.')
                while True:
                    try:
                        COMMANDS.get_nowait()
                    except queue.Empty:
                        break
                STATE.update(phase='opening', message='Đang mở Chrome riêng…')
                BROWSER_THREAD = threading.Thread(target=worker, daemon=True)
                try:
                    BROWSER_THREAD.start()
                except Exception:
                    BROWSER_THREAD = None
                    STATE.update(phase='error', ready=False, running=False, message='Không khởi động được phiên Chrome. Bấm Mở Chrome thu thập để thử lại.')
                    raise
        elif self.path == '/api/annotate':
            return LAB.annotate(body)
        elif self.path == '/api/annotate-bulk':
            return LAB.annotate_many(body.get('rows'))
        elif self.path == '/api/suggest':
            return LAB.start_suggestions()
        elif self.path == '/api/auto-label':
            return LAB.start_suggestions(automatic=True)
        elif self.path == '/api/import':
            return LAB.import_rows(body)
        elif self.path == '/api/clean':
            return LAB.save_cleaned()
        elif self.path == '/api/train':
            return LAB.start_training()
        elif self.path == '/api/predict':
            return LAB.predict(body)
        else:
            self.send(b'Not found', 'text/plain', 404)
            return
        return {}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PTIT Comment Lab')
    parser.add_argument('--no-browser', action='store_true', help='Do not open the dashboard automatically')
    args = parser.parse_args()
    try:
        server = LocalHTTPServer(('127.0.0.1', 8767), Handler)
    except OSError:
        print('Cong 8767 dang bi chiem. Hay dong cua so MO_CONG_CU.cmd cu (Ctrl+C), roi mo lai. Dong tab web khong tat chuong trinh cu.')
        raise SystemExit(1)
    restore()
    if not args.no_browser:
        webbrowser.open('http://127.0.0.1:8767/')
    print('PTIT Comment Lab: http://127.0.0.1:8767/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        STOP.set()
        COMMANDS.put('quit')
    finally:
        server.server_close()
