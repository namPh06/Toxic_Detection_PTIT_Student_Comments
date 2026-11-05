"""Authenticated Colab service. Uploaded packages supply data, never Python code."""
import hashlib
import json
import re
import shutil
import threading
import uuid
from pathlib import Path

from backend.colab import MODULES, checked_archive, encode, run_snapshot
from backend.dataset import atomic_json
from backend.transformer_model import compute_info, validate_config

PROTOCOL = 'ptit-colab-live-v1'


class TrainingService:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.session_id = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.jobs = {}

    def info(self):
        return dict(protocol=PROTOCOL, session_id=self.session_id, compute=compute_info())

    def start(self, package, config):
        config = validate_config(config)
        path = Path(package)
        if not path.is_file() or path.stat().st_size > 100_000_000:
            raise ValueError('Gói dữ liệu không hợp lệ hoặc vượt 100 MB.')
        with checked_archive(path) as archive:
            allowed = {'snapshot.json', 'PTIT_Colab.ipynb', 'backend/__init__.py'} | {'backend/' + m + '.py' for m in MODULES}
            if (not set(archive.namelist()) <= allowed or 'snapshot.json' not in archive.namelist()
                    or sum(i.file_size for i in archive.infolist()) > 100_000_000):
                raise ValueError('Chỉ nhận ZIP thực nghiệm xuất từ web PTIT.')
            snapshot = json.loads(archive.read('snapshot.json'))
        checksum = snapshot.pop('snapshot_sha256', None)
        job_id = snapshot.get('job_id', '')
        if (snapshot.get('schema_version') != 1 or not isinstance(job_id, str)
                or not re.fullmatch('[a-f0-9]{32}', job_id)
                or not isinstance(snapshot.get('rows'), list) or len(snapshot['rows']) > 20000
                or hashlib.sha256(encode(snapshot)).hexdigest() != checksum):
            raise ValueError('Snapshot dữ liệu không hợp lệ.')
        snapshot['snapshot_sha256'] = checksum
        with self.lock:
            existing = self.jobs.get(job_id)
            if existing:
                if existing['snapshot_sha256'] != checksum or existing['config'] != config:
                    raise ValueError('Mã gói đã dùng cho dữ liệu hoặc cấu hình khác.')
                return self.status(job_id)  # Retrying a lost reply must not train twice.
            if any(job['state'] == 'running' for job in self.jobs.values()):
                raise ValueError('GPU đang huấn luyện một gói khác. Chờ lượt hiện tại hoàn tất.')
            if compute_info()['device'] != 'cuda':
                raise ValueError('Phiên Colab chưa bật GPU.')
            work = self.root / 'jobs' / job_id
            work.mkdir(parents=True, exist_ok=True)
            atomic_json(work / 'snapshot.json', snapshot)
            job = dict(job_id=job_id, snapshot_sha256=checksum, config=config, state='running',
                       message='Đang chuẩn bị ViSoBERT trên GPU Colab…', error='', logs=[], result='')
            self.jobs[job_id] = job
            try:
                threading.Thread(target=self._run, args=(job_id, work, config), daemon=True).start()
            except Exception:
                self.jobs.pop(job_id)
                raise
            return self.status(job_id)

    def _run(self, job_id, work, config):
        def notify(message):
            with self.lock:
                job = self.jobs[job_id]
                job['message'] = str(message)[-1000:]
                job['logs'] = (job['logs'] + [job['message']])[-40:]
            print(message, flush=True)
        try:
            result = run_snapshot(work, config=config, notify=notify)
            destination = self.root / 'results' / (job_id + '.zip')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result, destination)
            with self.lock:
                self.jobs[job_id].update(state='complete', result=str(destination), message='Huấn luyện xong. Web đang nhận kết quả.')
        except Exception as error:
            with self.lock:
                self.jobs[job_id].update(state='failed', error=str(error)[-1500:], message='Huấn luyện trên Colab thất bại.')
        finally:
            # Free GPU memory between jobs, including when a training call fails.
            import gc
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass

    def status(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise ValueError('Không tìm thấy lượt huấn luyện trong phiên Colab này.')
            job = self.jobs[job_id]
            return {k: v for k, v in job.items() if k not in ('result', 'config')} | dict(
                session_id=self.session_id, result_bytes=Path(job['result']).stat().st_size if job['result'] else 0)

    def result(self, job_id):
        with self.lock:
            if self.status(job_id)['state'] != 'complete':
                raise ValueError('Lượt huấn luyện chưa có kết quả hoàn tất.')
            return self.jobs[job_id]['result']


def build_service(service):
    import gradio as gr
    with gr.Blocks(title='PTIT · GPU Colab', analytics_enabled=False) as app:
        gr.Markdown('## GPU Colab cho PTIT Comment Lab\nGiữ phiên này hoạt động. Dùng file kết nối trên web máy tính để bắt đầu huấn luyện.')
        info = gr.JSON(label='Trạng thái GPU')
        gr.Button('Kiểm tra GPU').click(service.info, outputs=info, api_name='info', queue=False)
        package = gr.File(label='Gói thực nghiệm', type='filepath', file_types=['.zip'])
        config = gr.JSON(value={}, label='Cấu hình ViSoBERT')
        status = gr.JSON(label='Tiến độ')
        gr.Button('Huấn luyện').click(service.start, inputs=[package, config], outputs=status, api_name='start', queue=False)
        job_id = gr.Textbox(label='Mã lượt huấn luyện')
        gr.Button('Xem tiến độ').click(service.status, inputs=job_id, outputs=status, api_name='status', queue=False)
        result = gr.File(label='Kết quả')
        gr.Button('Tải kết quả').click(service.result, inputs=job_id, outputs=result, api_name='result', queue=False)
    return app
