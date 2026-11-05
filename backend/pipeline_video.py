"""Bounded background MP4 rendering from server-created prediction snapshots."""
import copy
import hashlib
import json
import threading
from pathlib import Path

_lock = threading.Lock()
_jobs = {}
_folder = Path(__file__).resolve().parents[1] / 'outputs' / 'pipeline_videos'


def start(trace):
    snapshot = copy.deepcopy(trace)
    snapshot['renderer_version'] = 1
    key = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    with _lock:
        if key in _jobs and _jobs[key]['state'] != 'error':
            return dict(_jobs[key])
        if any(j['state'] == 'running' for j in _jobs.values()):
            raise ValueError('Đang dựng một video. Chờ video hiện tại hoàn tất rồi thử lại.')
        _jobs[key] = dict(id=key, state='running', progress=0)
        threading.Thread(target=_render, args=(key, snapshot), daemon=True).start()
        return dict(_jobs[key])


def _render(key, trace):
    temporary = _folder / (key + '.partial.mp4')
    try:
        from backend.animation_renderer import render_trace_video
        _folder.mkdir(parents=True, exist_ok=True)
        def progress(value):
            with _lock:
                _jobs[key]['progress'] = value
        render_trace_video(trace, temporary, progress)
        temporary.replace(_folder / (key + '.mp4'))
        with _lock:
            _jobs[key].update(state='done', progress=100)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        with _lock:
            _jobs[key].update(state='error', error=str(exc))


def status(key):
    with _lock:
        if key not in _jobs:
            raise ValueError('Không tìm thấy lượt dựng video.')
        return dict(_jobs[key])


def video_path(key):
    if status(key)['state'] != 'done':
        raise ValueError('Video chưa hoàn tất.')
    return _folder / (key + '.mp4')
