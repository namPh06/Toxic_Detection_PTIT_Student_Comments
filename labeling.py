"""Local toxicity inference; automatic labels retain their machine provenance."""
import hashlib
import math
import tempfile
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dataset import text_hash

MODEL_ID = 'dangvansam/vietnamese-toxicity'
REVISION = 'bac60f3e162d3a06003bf561a9f8365982ccc67a'
MAX_TOKENS = 512
BATCH_SIZE = 16
LOW_THRESHOLD, HIGH_THRESHOLD = 0.2, 0.8
FILES = {
    'model.onnx': (98385294, 'c6b21c36d89d4a3a9b295a06062a22a9605f942446d50a27d5cfee73b97db01a'),
    'tokenizer.json': (1802897, '3feb78081252fc85422f95a0a0284b6a03cc3522d0dbbcb2c86f2c15c3e5f0c8'),
}


def valid_file(path, expected_size, expected_hash):
    if not path.is_file() or path.stat().st_size != expected_size:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest() == expected_hash


def ensure_model(cache_dir, notify=lambda message: None):
    """Download only fixed public model assets, never texts; reuse verified cache offline."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for filename, (size, digest) in FILES.items():
        destination = cache_dir / filename
        if valid_file(destination, size, digest):
            continue
        notify(f'Đang tải mô hình gợi ý: {filename} ({size / 1_000_000:.1f} MB)…')
        url = f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{filename}'
        temporary = None
        try:
            started, received, next_notice = time.monotonic(), 0, 16 * 1024 * 1024
            with urllib.request.urlopen(url, timeout=30) as response:
                if not response.geturl().startswith('https://'):
                    raise ValueError('Máy chủ tải mô hình chuyển tới địa chỉ không an toàn.')
                with tempfile.NamedTemporaryFile(dir=cache_dir, prefix=filename + '.', suffix='.tmp', delete=False) as stream:
                    temporary = Path(stream.name)
                    while chunk := response.read(1024 * 1024):
                        received += len(chunk)
                        if received > size or time.monotonic() - started > 300:
                            raise ValueError('Tải mô hình vượt kích thước hoặc thời gian cho phép. Hãy thử lại.')
                        stream.write(chunk)
                        if received >= next_notice:
                            notify(f'Đang tải {filename}: {received / size:.0%}…')
                            next_notice += 16 * 1024 * 1024
            if not valid_file(temporary, size, digest):
                raise ValueError(f'Tệp {filename} không khớp SHA-256 của phiên bản mô hình đã chốt.')
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return cache_dir


def suggestion_from_logit(logit, truncated):
    if not math.isfinite(logit):
        raise ValueError('Mô hình trả điểm không hữu hạn; không lưu gợi ý.')
    # One output is a toxicity logit, not a two-class softmax or calibrated confidence.
    score = 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))
    label = 'toxic' if score >= HIGH_THRESHOLD else 'non-toxic' if score <= LOW_THRESHOLD else ''
    reason = 'truncated' if truncated else 'uncertain' if not label else ''
    return ('' if truncated else label), score, reason


def automatic_annotation(item):
    score = item['model_score']
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError('Điểm mô hình không hợp lệ; không lưu nhãn tự động.')
    reason = 'truncated' if item.get('truncated') else 'uncertain' if LOW_THRESHOLD < score < HIGH_THRESHOLD else ''
    return dict(label='toxic' if score >= 0.5 else 'non-toxic', label_source='automatic',
                text_hash=item['text_hash'], model_score=score, label_model=item['model'],
                label_revision=item['revision'], label_threshold=0.5,
                needs_review=bool(reason), review_reason=reason,
                updated_at=datetime.now(timezone.utc).isoformat())


def generate_suggestions(rows, cache_dir, notify=lambda message: None):
    """Suggest only for usable unlabelled rows. The caller saves a separate review queue."""
    candidates, seen = [], set()
    for row in rows:
        if row.get('quality') != 'ready' or row.get('label') or row.get('excluded') or row.get('text_complete') is False:
            continue
        if not isinstance(row.get('id'), str) or not row['id'] or row['id'] in seen:
            raise ValueError('Mẫu gợi ý thiếu mã hoặc trùng mã bình luận.')
        if not isinstance(row.get('text_raw'), str) or not 1 <= len(row['text_raw'].strip()) <= 20000:
            raise ValueError('Mẫu gợi ý cần văn bản từ 1 đến 20.000 ký tự.')
        seen.add(row['id'])
        candidates.append(row)
    if not candidates:
        return []
    try:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as error:
        raise RuntimeError('Thiếu thư viện gợi ý nhãn. Cài lại requirements.txt rồi mở lại ứng dụng.') from error

    directory = ensure_model(cache_dir, notify)
    notify('Đang nạp mô hình gợi ý trên CPU…')
    options = ort.SessionOptions()
    options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
    session = ort.InferenceSession(str(directory / 'model.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
    inputs, outputs = session.get_inputs(), session.get_outputs()
    names = {item.name for item in inputs}
    if not {'input_ids', 'attention_mask'} <= names <= {'input_ids', 'attention_mask', 'token_type_ids'}:
        raise ValueError('Tên đầu vào ONNX không đúng với mô hình gợi ý đã chốt.')
    if any(item.type != 'tensor(int64)' or len(item.shape) != 2 for item in inputs):
        raise ValueError('Kiểu dữ liệu đầu vào ONNX không hợp lệ.')
    if len(outputs) != 1 or outputs[0].name != 'logits' or outputs[0].type != 'tensor(float)':
        raise ValueError('Đầu ra ONNX phải là một tensor logits float.')
    tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
    if tokenizer.token_to_id('<pad>') != 1 or tokenizer.token_to_id('</s>') != 2:
        raise ValueError('Token đặc biệt không đúng với mô hình đã chốt.')
    tokenizer.no_padding()
    tokenizer.no_truncation()
    suggestions = []
    for offset in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[offset:offset + BATCH_SIZE]
        texts = [' '.join(unicodedata.normalize('NFC', row['text_raw']).split()) for row in batch]
        encodings = tokenizer.encode_batch(texts)
        truncated = [len(item.ids) > MAX_TOKENS for item in encodings]
        if any(truncated):
            tokenizer.enable_truncation(max_length=MAX_TOKENS)
            encodings = tokenizer.encode_batch(texts)
            tokenizer.no_truncation()
        width = max(len(item.ids) for item in encodings)
        ids = np.full((len(batch), width), 1, dtype=np.int64)
        attention = np.zeros_like(ids)
        for i, encoded in enumerate(encodings):
            ids[i, :len(encoded.ids)] = encoded.ids
            attention[i, :len(encoded.ids)] = encoded.attention_mask
        feed = dict(input_ids=ids, attention_mask=attention)
        if 'token_type_ids' in names:
            feed['token_type_ids'] = np.zeros_like(ids)
        logits = np.asarray(session.run(['logits'], feed)[0])
        if logits.shape != (len(batch), 1) or not np.isfinite(logits).all():
            raise ValueError('Mô hình phải trả một logit hữu hạn cho từng bình luận.')
        for row, logit, cut in zip(batch, logits[:, 0], truncated):
            label, score, reason = suggestion_from_logit(float(logit), cut)
            suggestions.append(dict(id=row['id'], text_hash=text_hash(row['text_raw']), suggested_label=label,
                                    model_score=score, model=MODEL_ID, revision=REVISION, truncated=cut,
                                    abstain_reason=reason, created_at=datetime.now(timezone.utc).isoformat()))
        notify(f'Đã tạo gợi ý {min(offset + BATCH_SIZE, len(candidates))}/{len(candidates)} bình luận. Chờ người đọc duyệt.')
    return suggestions
