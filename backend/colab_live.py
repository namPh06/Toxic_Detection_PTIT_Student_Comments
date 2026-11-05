"""Local Gradio connection and remote training orchestration; credentials stay in memory."""
import base64
import io
import json
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from backend.colab import MAX_UPLOAD, MODULES, encode, export_package, import_result
from backend.colab_worker import PROTOCOL
from backend.features import feature_key
from backend.transformer_model import validate_config


def validate_connection(body):
    if not isinstance(body, dict):
        raise ValueError('File kết nối phải là JSON object.')
    values = {key: body.get(key, '') for key in ('url', 'username', 'password')}
    if any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in values.values()):
        raise ValueError('Cần link Colab, tài khoản và mật khẩu trong file kết nối.')
    url = values['url'].strip().rstrip('/')
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or not re.fullmatch(r'[a-zA-Z0-9-]+\.gradio\.live', parsed.hostname or '')
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Dùng link HTTPS .gradio.live trong file kết nối do notebook tạo.')
    return dict(url=url, username=values['username'].strip(), password=values['password'])


def live_notebook_bytes():
    from backend.colab import notebook_bytes
    notebook = json.loads(notebook_bytes())
    sources = {'backend/__init__.py': ''}
    for module in (*MODULES, 'colab_worker'):
        sources['backend/' + module + '.py'] = (Path(__file__).parent / (module + '.py')).read_text(encoding='utf-8')
    payload = base64.b64encode(encode(sources)).decode('ascii')
    def cell(kind, source):
        import uuid
        result = dict(id=uuid.uuid4().hex[:8], cell_type=kind, metadata={}, source=source.splitlines(True))
        if kind == 'code':
            result.update(execution_count=None, outputs=[])
        return result
    notebook['metadata']['colab']['name'] = 'PTIT_Colab_Live.ipynb'
    notebook['cells'] = [
        cell('markdown', '# Kết nối GPU Colab với PTIT Comment Lab\nChọn **Runtime → Change runtime type → GPU** rồi chạy 3 ô bên dưới. Mở file kết nối JSON trên web máy tính. Sau đó bấm huấn luyện tại web; không cần chuyển ZIP thủ công. Giữ Colab và chương trình web hoạt động. File kết nối chứa mật khẩu, chỉ giữ cho riêng bạn.'),
        cell('code', '%pip -q install "gradio==5.49.1" "transformers>=4.48,<5" "scikit-learn>=1.6,<2" "underthesea==9.5.0" "sentencepiece>=0.2,<1"\n'),
        cell('code', "import base64, json, os, sys, tempfile\nfrom pathlib import Path\nimport torch\nfrom packaging.version import Version\nassert Version(torch.__version__.split('+')[0]) >= Version('2.6'), 'Cần PyTorch >= 2.6.'\nassert torch.cuda.is_available(), 'Hãy chọn runtime GPU.'\nif '_ptit_work' not in globals():\n    _ptit_work = Path(tempfile.mkdtemp(prefix='ptit-live-'))\n    _sources = json.loads(base64.b64decode('" + payload + "'))\n    for _name, _text in _sources.items():\n        _path = _ptit_work / _name\n        _path.parent.mkdir(parents=True, exist_ok=True)\n        _path.write_text(_text, encoding='utf-8')\n    os.chdir(_ptit_work)\n    sys.path.insert(0, str(_ptit_work))\n    for _name in list(sys.modules):\n        if _name == 'backend' or _name.startswith('backend.'):\n            del sys.modules[_name]\nfrom backend.colab_worker import TrainingService, build_service\nif '_ptit_service' not in globals():\n    _ptit_service = TrainingService(_ptit_work / 'gpu')\nprint('GPU:', torch.cuda.get_device_name(0))\n"),
        cell('code', "import secrets\nfrom google.colab import files\nif '_ptit_app' in globals():\n    _ptit_app.close()  # Chỉ mở lại kết nối, giữ lượt huấn luyện và kết quả.\nif '_ptit_password' not in globals():\n    _ptit_password = secrets.token_urlsafe(24)\n_ptit_app = build_service(_ptit_service)\n_, _, _ptit_url = _ptit_app.launch(share=True, auth=('ptit', _ptit_password), inline=False,\n    prevent_thread_lock=True, show_error=True, max_file_size='100mb',\n    blocked_paths=[str(_ptit_work / 'backend'), str(_ptit_service.root / 'jobs'), str(_ptit_work / 'ptit-colab-connection.json')])\nassert _ptit_url, 'Chưa tạo được link. Chạy lại riêng ô này.'\n_connection = dict(url=_ptit_url, username='ptit', password=_ptit_password)\n_connection_path = _ptit_work / 'ptit-colab-connection.json'\n_connection_path.write_text(json.dumps(_connection), encoding='utf-8')\nprint('Kết nối đã sẵn sàng. Mở file JSON trên web máy tính rồi bấm Kết nối GPU.')\nfiles.download(str(_connection_path))\n"),
        cell('markdown', '### Tùy chọn: khôi phục kết quả khi web bị đóng\nKhi web còn hoạt động, kết quả được nhận tự động; **không cần chạy lại ô này sau khi train**. Chỉ khi đã đóng chương trình web và mất thông tin kết nối, chạy ô dưới để tải ZIP kết quả hoàn tất gần nhất, rồi dùng **Nhập kết quả Colab** trên web. Trích xuất lại cùng cấu hình trước khi nhập. Chạy lại ô kết nối phía trên không huấn luyện lại.'),
        cell('code', "with _ptit_service.lock:\n    _completed = [job_id for job_id, job in _ptit_service.jobs.items() if job['state'] == 'complete']\nif _completed:\n    files.download(_ptit_service.result(_completed[-1]))\nelse:\n    print('Chưa có kết quả hoàn tất để tải dự phòng. Kết nối web và bấm Huấn luyện; web sẽ tự nhận kết quả, không cần chạy lại ô này.')\n")]
    return encode(notebook)


class GradioPeer:
    def __init__(self, connection):
        self.temp = tempfile.TemporaryDirectory(prefix='ptit-colab-client-')
        try:
            from gradio_client import Client
            self.client = Client(connection['url'], auth=(connection['username'], connection['password']),
                                 verbose=False, download_files=self.temp.name, httpx_kwargs={'timeout': 60})
        except ImportError:
            self.temp.cleanup()
            raise ValueError('Thiếu thư viện kết nối. Cài requirements.txt rồi khởi động lại web.') from None
        except Exception:
            self.temp.cleanup()
            raise ValueError('Không kết nối được Colab. Kiểm tra link, mật khẩu và phiên GPU.') from None

    def call(self, api_name, *args):
        try:
            return self.client.predict(*args, api_name='/' + api_name)
        except Exception:
            raise ValueError('Mất kết nối Colab. Giữ phiên GPU mở rồi bấm Nối lại / nhận kết quả.') from None

    def info(self):
        return self.call('info')

    def start(self, package, config):
        from gradio_client import handle_file
        with tempfile.TemporaryDirectory(prefix='input-', dir=self.temp.name) as directory:
            path = Path(directory) / 'input.zip'
            path.write_bytes(package)
            return self.call('start', handle_file(str(path)), config)

    def status(self, job_id):
        return self.call('status', job_id)

    def result(self, job_id):
        path = Path(self.call('result', job_id)).resolve()
        if (not path.is_relative_to(Path(self.temp.name).resolve()) or not path.is_file()
                or not 0 < path.stat().st_size <= MAX_UPLOAD):
            raise ValueError('Kết quả tải về không phải ZIP Colab hợp lệ.')
        return path

    def close(self):
        self.client.close()
        self.temp.cleanup()


class ColabConnection:
    def __init__(self, lab):
        self.lab = lab
        self.peer = None
        self.info = None
        self.url = ''
        self.connected = False
        self.pending = None
        self.message = 'Chưa kết nối GPU Colab.'

    def status(self):
        with self.lab.lock:
            return dict(connected=self.connected, gpu=(self.info or {}).get('compute', {}).get('name', ''),
                        url=self.url, message=self.message, retryable=bool(self.pending and not self.lab.job['running']))

    @staticmethod
    def check_info(info):
        if (not isinstance(info, dict) or info.get('protocol') != PROTOCOL
                or not re.fullmatch('[a-f0-9]{32}', str(info.get('session_id', '')))
                or info.get('compute', {}).get('device') != 'cuda'):
            raise ValueError('Link này không phải notebook GPU PTIT tương thích. Tải notebook kết nối mới từ web.')

    def connect(self, body):
        connection = validate_connection(body)
        # Do not hold the dataset lock during a network request.
        with self.lab.lock:
            if self.lab.job['running']:
                raise ValueError('Chờ lượt huấn luyện hiện tại hoàn tất trước khi đổi kết nối.')
        peer = GradioPeer(connection)
        try:
            info = peer.info()
            self.check_info(info)
            with self.lab.lock:
                if self.lab.job['running']:
                    raise ValueError('Huấn luyện đã bắt đầu. Chờ hoàn tất trước khi đổi kết nối.')
                old = self.peer
                if self.pending and self.pending['session_id'] != info['session_id']:
                    self.pending = None  # A fresh runtime cannot recover a previous runtime's GPU job.
                self.peer, self.info, self.url = peer, info, connection['url']
                self.connected = True
                self.message = 'Đã kết nối GPU Colab · ' + str(info['compute'].get('name', 'GPU'))
            if old:
                old.close()
        except Exception:
            peer.close()
            raise
        return self.status()

    def disconnect(self):
        with self.lab.lock:
            if self.lab.job['running']:
                raise ValueError('Chờ huấn luyện hoàn tất trước khi ngắt kết nối.')
            old = self.peer
            self.peer = self.info = self.pending = None
            self.connected, self.url, self.message = False, '', 'Đã ngắt kết nối GPU Colab.'
        if old:
            old.close()
        return self.status()

    def _idle(self):
        if any(job['running'] for job in (self.lab.job, self.lab.feature_job, self.lab.annotation_job)):
            raise ValueError('Chờ tác vụ hiện tại hoàn tất.')

    def start_training(self, body):
        from backend.experiments import validate_algorithms
        algorithms = validate_algorithms(body.get('algorithms'), optimized=True)
        if 'ViSoBERT' not in algorithms:
            raise ValueError('Chọn ViSoBERT để huấn luyện trên Colab.')
        config = validate_config(body.get('transformer_config', dict(batch_size=16, accumulation=1)))
        with self.lab.lock:
            self._idle()
            if not self.connected or not self.peer:
                raise ValueError('Kết nối GPU Colab trước khi huấn luyện.')
            if self.pending:
                raise ValueError('Còn lượt Colab chờ nhận. Bấm Nối lại / nhận kết quả trước.')
            package = export_package(self.lab)
            with ZipFile(io.BytesIO(package)) as archive:
                snapshot = json.loads(archive.read('snapshot.json'))
            self.pending = dict(package=package, snapshot=snapshot, config=config,
                                algorithms=algorithms, baselines_done=False, prepared=self.lab.features,
                                rows=self.lab.experiment_rows(), session_id=self.info['session_id'])
            return self._launch()

    def retry(self):
        with self.lab.lock:
            self._idle()
            if not self.pending or not self.peer:
                raise ValueError('Không có lượt Colab đang chờ nhận.')
            self._current(self.pending)
            return self._launch()

    def _current(self, pending):
        features = self.lab.features
        if (not features or feature_key(self.lab.experiment_rows()) != pending['snapshot']['key']
                or features['settings'] != pending['prepared']['settings']
                or features['split'] != pending['prepared']['split']):
            raise ValueError('Dữ liệu hoặc đặc trưng đã đổi. Ngắt kết nối rồi tạo lượt huấn luyện mới.')

    def _launch(self):
        self.lab.job = dict(running=True, error=False, message='Đang gửi dữ liệu và kết nối GPU Colab…')
        try:
            threading.Thread(target=self._execute, args=(self.pending, self.peer), daemon=True).start()
        except Exception:
            self.lab.job.update(running=False, error=True, message='Không khởi động được lượt Colab. Bấm nối lại.')
            raise
        return dict(started=True)

    def _execute(self, pending, peer):
        def notify(message):
            with self.lab.lock:
                self.lab.job['message'] = str(message)
        try:
            info = peer.info()
            self.check_info(info)
            if info['session_id'] != pending['session_id']:
                raise ValueError('Phiên Colab đã đổi. Kết nối lại bằng file JSON mới.')
            response = peer.start(pending['package'], pending['config'])
            job_id = pending['snapshot']['job_id']
            self._check_job(response, pending)
            local_algorithms = [a for a in pending['algorithms'] if a != 'ViSoBERT']
            if local_algorithms and not pending['baselines_done']:
                from backend.improvements import train_improved
                from backend.experiments import publish_run
                run = 'run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                output = self.lab.directory / 'runs' / run
                result = train_improved(pending['rows'], output, notify=notify,
                                        prepared=pending['prepared'], algorithms=local_algorithms)
                with self.lab.lock:
                    self._current(pending)
                    publish_run(result, output, self.lab.directory, pending['rows'])
                    self.lab.run = run
                    pending['baselines_done'] = True
            deadline = time.monotonic() + 6 * 60 * 60
            while True:
                response = peer.status(job_id)
                self._check_job(response, pending)
                notify('Colab · ' + str(response.get('message', 'Đang huấn luyện…'))[-1500:])
                if response['state'] == 'failed':
                    with self.lab.lock:
                        self.pending = None
                    raise ValueError('Huấn luyện trên Colab thất bại: ' + str(response.get('error', 'Kiểm tra notebook.'))[-1500:])
                if response['state'] == 'complete':
                    if not 0 < response.get('result_bytes', 0) <= MAX_UPLOAD:
                        raise ValueError('ZIP kết quả Colab vượt giới hạn hoặc bị rỗng.')
                    break
                if time.monotonic() > deadline:
                    raise ValueError('Chờ Colab quá 6 giờ. Bấm nối lại để kiểm tra lượt đang chạy.')
                time.sleep(2)
            notify('Đang nhận và kiểm tra mô hình Colab. Giữ chương trình web mở…')
            path = peer.result(job_id)
            with self.lab.lock:
                self._current(pending)
                # The RLock makes this handover atomic to other local jobs.
                self.lab.job['running'] = False
                try:
                    with path.open('rb') as source:
                        import_result(self.lab, source)
                finally:
                    # import_result releases its own busy flag. Keep this worker's
                    # ownership until cleanup and final status are finished.
                    self.lab.job['running'] = True
                self.pending = None
                self.connected = True
                self.message = 'Đã nhận ViSoBERT từ GPU Colab. Có thể huấn luyện lượt tiếp theo.'
                self.lab.job.update(error=False, message='Đã huấn luyện và nhận ViSoBERT từ Colab; kết quả đã sẵn sàng để so sánh và dự đoán.')
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass  # Cache cleanup cannot invalidate a published model.
        except Exception as error:
            with self.lab.lock:
                self.connected = False
                self.message = str(error)
                self.lab.job.update(error=True, message=str(error))
        finally:
            with self.lab.lock:
                self.lab.job['running'] = False

    @staticmethod
    def _check_job(response, pending):
        if (not isinstance(response, dict) or response.get('job_id') != pending['snapshot']['job_id']
                or response.get('snapshot_sha256') != pending['snapshot']['snapshot_sha256']
                or response.get('session_id') != pending['session_id']
                or response.get('state') not in ('running', 'complete', 'failed')):
            raise ValueError('Phản hồi Colab không khớp lượt dữ liệu đã gửi.')
