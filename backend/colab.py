"""Portable ViSoBERT jobs. Never import executable model pickles from Colab."""
import hashlib
import io
import json
import math
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from backend.dataset import atomic_json, fingerprint, input_fingerprint, LABELS
from backend.features import feature_key, build_features

MAX_UPLOAD = 1_500_000_000
MODULES = ('teencode', 'dataset', 'features', 'experiments', 'improvements', 'transformer_model', 'colab')
MODEL_FILES = {'config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
               'special_tokens_map.json', 'sentencepiece.bpe.model', 'added_tokens.json', 'training.json'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')


def checked_archive(source):
    archive = ZipFile(source)
    names = archive.namelist()
    if len(names) != len(set(names)) or len(names) > 100:
        archive.close()
        raise ValueError('ZIP trùng tên tệp hoặc có quá nhiều tệp.')
    for item in archive.infolist():
        path = PurePosixPath(item.filename)
        if (path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename
                or item.is_dir() or item.file_size > MAX_UPLOAD
                or (item.external_attr >> 16) & 0o170000 == 0o120000):
            archive.close()
            raise ValueError('ZIP chứa đường dẫn hoặc tệp không hợp lệ.')
    if sum(i.file_size for i in archive.infolist()) > MAX_UPLOAD:
        archive.close()
        raise ValueError('ZIP giải nén vượt giới hạn 1,5 GB.')
    return archive


def notebook_bytes():
    cells = []
    def markdown(text):
        cells.append(dict(id=uuid.uuid4().hex[:8], cell_type='markdown', metadata={}, source=text.splitlines(True)))
    def code(text):
        cells.append(dict(id=uuid.uuid4().hex[:8], cell_type='code', metadata={}, execution_count=None, outputs=[], source=text.splitlines(True)))
    markdown('# Huấn luyện ViSoBERT trên Colab\nChọn **Runtime → Change runtime type → GPU** (A100 nếu tài khoản được cấp). Chạy lần lượt các ô. Gói chứa bình luận và nhãn; chỉ tải lên phiên Colab của bạn. NB/SVM tiếp tục chạy trên web.')
    code('%pip -q install "transformers>=4.48,<5" "scikit-learn>=1.6,<2" "underthesea==9.5.0" "sentencepiece>=0.2,<1"\n')
    code("import torch\nfrom packaging.version import Version\nassert Version(torch.__version__.split('+')[0]) >= Version('2.6'), 'Cần runtime Colab có PyTorch >= 2.6.'\nassert torch.cuda.is_available(), 'Hãy chọn GPU trong Runtime trước khi tiếp tục.'\nprint('GPU:', torch.cuda.get_device_name(0))\n")
    code("from google.colab import files\nfrom pathlib import Path, PurePosixPath\nfrom zipfile import ZipFile\nimport io, os, sys, tempfile\nuploaded = files.upload()\nassert len(uploaded) == 1, 'Chọn đúng một ZIP xuất từ web.'\nwork = Path(tempfile.mkdtemp(prefix='ptit-colab-'))\nwith ZipFile(io.BytesIO(next(iter(uploaded.values())))) as z:\n    names = z.namelist()\n    allowed = {'snapshot.json', 'PTIT_Colab.ipynb', 'backend/__init__.py', 'data/teencode_dictionary.json'} | {'backend/'+m+'.py' for m in ('teencode','dataset','features','experiments','improvements','transformer_model','colab')}\n    assert len(names) == len(set(names)) and set(names) <= allowed and 'snapshot.json' in names\n    assert sum(i.file_size for i in z.infolist()) < 100_000_000\n    z.extractall(work)\nos.chdir(work)\nsys.path.insert(0, str(work))\nprint('Đã nhận gói dữ liệu.')\n")
    markdown('## Huấn luyện\nGiữ mặc định để so sánh với lần chạy trên máy. Có thể chỉnh số epoch và batch bên dưới. Notebook giữ nguyên cách chia tập, chọn checkpoint và ngưỡng bằng validation. Ô này tải mô hình nền từ Hugging Face ở lần đầu.')
    code("from backend.colab import run_snapshot\nconfig = dict(epochs=4, batch_size=16, accumulation=1)\nresult_zip = run_snapshot(work, config=config)\nprint('Đã lưu:', result_zip)\n")
    markdown('## Tải kết quả\nTải ZIP rồi dùng nút **Nhập kết quả Colab** trên web. Nếu tải bị gián đoạn, chạy lại riêng ô này, không cần huấn luyện lại.')
    code('files.download(str(result_zip))\n')
    return encode(dict(nbformat=4, nbformat_minor=5, metadata=dict(colab=dict(name='PTIT_Colab.ipynb'),
                      kernelspec=dict(display_name='Python 3', language='python', name='python3')), cells=cells))


def export_package(lab):
    with lab.lock:
        if any(j['running'] for j in (lab.job, lab.feature_job, lab.annotation_job)):
            raise ValueError('Chờ tác vụ hiện tại hoàn tất trước khi xuất Colab.')
        rows = lab.experiment_rows()
        prepared = lab.features
        if not prepared or prepared['key'] != feature_key(rows):
            raise ValueError('Hãy trích xuất đặc trưng hiện tại trước khi xuất Colab.')
        snapshot = dict(schema_version=1, job_id=uuid.uuid4().hex, rows=rows,
                        key=prepared['key'], settings=prepared['settings'], split=prepared['split'],
                        feature_created_at=prepared['created_at'])
        snapshot['snapshot_sha256'] = hashlib.sha256(encode(snapshot)).hexdigest()
        destination = lab.directory / 'colab_jobs' / (snapshot['job_id'] + '.json')
        atomic_json(destination, {k: v for k, v in snapshot.items() if k != 'rows'})
    buffer = io.BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('snapshot.json', encode(snapshot))
        archive.writestr('PTIT_Colab.ipynb', notebook_bytes())
        archive.writestr('backend/__init__.py', '')
        archive.write(Path(__file__).resolve().parents[1] / 'data/teencode_dictionary.json', 'data/teencode_dictionary.json')
        for module in MODULES:
            archive.write(Path(__file__).parent / (module + '.py'), 'backend/' + module + '.py')
    return buffer.getvalue()


def run_snapshot(work, config=None, notify=print):
    from backend.improvements import train_improved
    import torch
    if not torch.cuda.is_available():
        raise ValueError('Phiên Colab chưa bật GPU.')
    work = Path(work)
    snapshot = json.loads((work / 'snapshot.json').read_text(encoding='utf-8'))
    checksum = snapshot.pop('snapshot_sha256')
    if hashlib.sha256(encode(snapshot)).hexdigest() != checksum:
        raise ValueError('Gói dữ liệu đã thay đổi.')
    prepared = build_features(snapshot['rows'], snapshot['settings'], notify)
    if prepared['key'] != snapshot['key'] or prepared['split'] != snapshot['split']:
        raise ValueError('Cách chia tập hoặc phiên bản xử lý khác với web. Xuất lại gói.')
    prepared['created_at'] = snapshot['feature_created_at']
    run = 'run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = work / 'data' / 'runs' / run
    train_improved(snapshot['rows'], output, notify=notify, prepared=prepared, algorithms=['ViSoBERT'], transformer_config=config)
    path = work / ('ptit-colab-result-' + snapshot['job_id'] + '.zip')
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('colab-result.json', encode(dict(schema_version=1, job_id=snapshot['job_id'], snapshot_sha256=checksum)))
        for name in ('metrics.json', 'split.json', 'ViSoBERT-predictions.json', 'ViSoBERT-validation-predictions.json', 'ViSoBERT-threshold.json'):
            archive.write(output / name, name)
        for file in (output / 'ViSoBERT').iterdir():
            if file.name in MODEL_FILES:
                archive.write(file, 'ViSoBERT/' + file.name)
    return path


def import_result(lab, source):
    """Validate without unpickling; recompute metrics from checked predictions."""
    from backend.experiments import metrics, publish_run, train_experiment
    from backend.improvements import choose_threshold
    import numpy as np
    try:
        archive = checked_archive(source)
    except (BadZipFile, OSError) as error:
        raise ValueError('Không đọc được ZIP kết quả Colab.') from error
    with archive:
        required = {'colab-result.json', 'metrics.json', 'split.json', 'ViSoBERT-predictions.json',
                    'ViSoBERT-validation-predictions.json', 'ViSoBERT-threshold.json',
                    'ViSoBERT/config.json', 'ViSoBERT/model.safetensors', 'ViSoBERT/tokenizer.json',
                    'ViSoBERT/tokenizer_config.json', 'ViSoBERT/training.json'}
        allowed = required | {'ViSoBERT/' + f for f in MODEL_FILES}
        if not required <= set(archive.namelist()) or not set(archive.namelist()) <= allowed:
            raise ValueError('ZIP thiếu mô hình hoặc chứa tệp ngoài định dạng Colab hỗ trợ.')
        def read(name):
            if archive.getinfo(name).file_size > 40_000_000:
                raise ValueError('Tệp JSON quá lớn.')
            return json.loads(archive.read(name))
        receipt = read('colab-result.json')
        job_id = receipt.get('job_id', '')
        if receipt.get('schema_version') != 1 or not re.fullmatch('[a-f0-9]{32}', job_id):
            raise ValueError('Mã gói Colab không hợp lệ.')
        job_file = lab.directory / 'colab_jobs' / (job_id + '.json')
        if not job_file.is_file():
            raise ValueError('Gói này chưa được xuất từ web trên máy này.')
        job = json.loads(job_file.read_text(encoding='utf-8'))
        if receipt.get('snapshot_sha256') != job['snapshot_sha256']:
            raise ValueError('Kết quả không khớp gói đã xuất.')
        with lab.lock:
            if any(j['running'] for j in (lab.job, lab.feature_job, lab.annotation_job)):
                raise ValueError('Chờ tác vụ hiện tại hoàn tất trước khi nhập kết quả.')
            rows = lab.experiment_rows()
            prepared = lab.features
            if (feature_key(rows) != job['key'] or not prepared or prepared['key'] != job['key']
                    or prepared['settings'] != job['settings'] or prepared['split'] != job['split']):
                raise ValueError('Dữ liệu hoặc cấu hình đã đổi. Trích xuất và xuất gói Colab mới.')
            remote = read('metrics.json')
            if (remote.get('fingerprint') != fingerprint(rows) or remote.get('input_fingerprint') != input_fingerprint(rows)
                    or [m['name'] for m in remote.get('models', [])] != ['ViSoBERT']):
                raise ValueError('Kết quả không thuộc dữ liệu và mô hình đã xuất.')
            expected_split = {part: [dict(id=prepared['rows'][i]['id'], post_id=prepared['rows'][i]['post_id'],
                                         group=prepared['groups'][i], label=prepared['rows'][i]['label'],
                                         label_source=prepared['rows'][i].get('label_source', 'legacy')) for i in ids]
                              for part, ids in prepared['split'].items()}
            if read('split.json') != expected_split:
                raise ValueError('Kết quả Colab đã dùng cách chia tập khác.')
            scores = {}
            for part, filename in [('validation', 'ViSoBERT-validation-predictions.json'), ('test', 'ViSoBERT-predictions.json')]:
                predictions = read(filename)
                expected = expected_split[part]
                if (len(predictions) != len(expected) or any(p['id'] != e['id'] or p['actual'] != e['label'] for p, e in zip(predictions, expected))):
                    raise ValueError('Dự đoán không khớp mẫu và nhãn đã xuất.')
                values = [p['score'] for p in predictions]
                if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                    raise ValueError('Điểm dự đoán không hợp lệ.')
                scores[part] = values
            choice = choose_threshold(prepared['labels']['validation'], scores['validation'])
            model = remote['models'][0]
            if model.get('threshold') != choice['threshold']:
                raise ValueError('Ngưỡng không được chọn đúng từ validation.')
            model.update(validation=choice['validation'], validation_default=choice['validation_default'],
                         test=metrics(prepared['labels']['test'], np.asarray(scores['test']) >= choice['threshold']),
                         test_default=metrics(prepared['labels']['test'], np.asarray(scores['test']) >= 0.5),
                         artifact=dict(kind='transformer', directory='ViSoBERT'), retained=False)
            config = read('ViSoBERT/config.json')
            if (config.get('model_type') != 'xlm-roberta' or config.get('auto_map')
                    or config.get('id2label') != {'0': 'non-toxic', '1': 'toxic'}):
                raise ValueError('Gói không phải kiến trúc ViSoBERT được hỗ trợ.')
            from backend.transformer_model import validate_config
            training = read('ViSoBERT/training.json')
            if not isinstance(training, dict) or not isinstance(training.get('config'), dict):
                raise ValueError('Thiếu cấu hình huấn luyện ViSoBERT trong kết quả.')
            training_config = validate_config(training['config'])
            source_info = training.get('source', {})
            if (not isinstance(source_info, dict) or source_info.get('model') != 'uitnlp/visobert'
                    or not isinstance(source_info.get('revision'), str) or not source_info['revision']
                    or training.get('device') != 'cuda' or training.get('fine_tuning') != 'full_encoder_and_head'
                    or type(training.get('best_epoch')) is not int
                    or not 1 <= training['best_epoch'] <= training_config['epochs']):
                raise ValueError('Thông tin nguồn hoặc checkpoint ViSoBERT không hợp lệ.')
            if type(model.get('seconds')) not in (int, float) or not math.isfinite(model['seconds']) or model['seconds'] < 0:
                raise ValueError('Thời gian huấn luyện không hợp lệ.')
            model.update(algorithm='ViSoBERT', feature='Pretrained transformer', parameters=training)
            lab.job = dict(running=True, error=False, message='Đang kiểm tra và nhập mô hình Colab…')
            output = lab.directory / 'runs' / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            try:
                result = train_experiment(rows, output, prepared=prepared, algorithms=[])
                result.update(models=[model], selected_model='ViSoBERT', requested_algorithms=['ViSoBERT'],
                              experiment_type='validation_search', protocol=dict(selection='validation_f1_macro',
                              threshold_selection='validation_f1_macro', labels_modified=False, context_added=False,
                              test_used_for_selection=False, limitation='Kết quả Colab dùng cùng tập chia đã xuất; test không dùng để chọn cấu hình. Cần dữ liệu độc lập cho kết luận tổng quát hóa cuối cùng.'),
                              colab_job=job_id, versions=remote['versions'])
                (output / 'ViSoBERT').mkdir()
                for name in archive.namelist():
                    if name.startswith('ViSoBERT/'):
                        with archive.open(name) as src, (output / name).open('wb') as dst:
                            shutil.copyfileobj(src, dst)
                training['config'] = training_config
                atomic_json(output / 'ViSoBERT' / 'training.json', training)
                # Check the returned weights and tokenizer before changing latest.json.
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                tokenizer = AutoTokenizer.from_pretrained(output / 'ViSoBERT', local_files_only=True, trust_remote_code=False)
                check_model = AutoModelForSequenceClassification.from_pretrained(
                    output / 'ViSoBERT', local_files_only=True, trust_remote_code=False, use_safetensors=True)
                check_model.eval()
                with torch.inference_mode():
                    logits = check_model(**tokenizer('Kiểm tra mô hình.', return_tensors='pt', truncation=True,
                                                     max_length=min(32, training_config['max_length']))).logits
                if logits.shape != (1, 2) or not torch.isfinite(logits).all():
                    raise ValueError('Mô hình Colab không trả về điểm phân loại hợp lệ.')
                del check_model, tokenizer
                for part, filename in [('validation', 'ViSoBERT-validation-predictions.json'), ('test', 'ViSoBERT-predictions.json')]:
                    predictions = [dict(id=e['id'], actual=e['label'], predicted=LABELS[int(s >= choice['threshold'])],
                                        score=s, threshold=choice['threshold']) for e, s in zip(expected_split[part], scores[part])]
                    atomic_json(output / filename, predictions)
                atomic_json(output / 'ViSoBERT-threshold.json', choice)
                result = publish_run(result, output, lab.directory, rows)
                lab.run = output.name
                lab.job.update(error=False, message='Đã nhập ViSoBERT từ Colab và giữ các mô hình cũ còn phù hợp.')
                return dict(imported=True, run=output.name, retained_models=result['retained_models'])
            except Exception:
                if output.exists():
                    shutil.rmtree(output)
                lab.job.update(error=True, message='Nhập Colab thất bại; kết quả hiện hành được giữ nguyên.')
                raise
            finally:
                lab.job['running'] = False
