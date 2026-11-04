"""Artifact-backed evidence and persistent, single-worker system report videos."""
import hashlib
import json
import math
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = 'system-report-1'
NAMES = ('BoW-NB', 'BoW-SVM', 'TF-IDF-NB', 'TF-IDF-SVM', 'ViSoBERT')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def display_text(text):
    """Mask identifiers in visuals; inference always receives the original input."""
    text = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[ẩn liên hệ]', text)
    return re.sub(r'(?<!\w)(?:\+?84|0)[\d .-]{8,12}(?!\w)', '[ẩn số]', text)


def evidence_for_linear(model, text, threshold):
    import numpy as np
    from dataset import clean_text
    pipeline = getattr(model, 'estimator', model)
    vectorizer, classifier = pipeline.named_steps['vectorizer'], pipeline.named_steps['classifier']
    cleaned = clean_text(text)
    x = vectorizer.transform([cleaned]).tocsr()
    names = vectorizer.get_feature_names_out()
    nb = hasattr(classifier, 'feature_log_prob_')
    if list(classifier.classes_) != [0, 1]:
        raise ValueError('Thứ tự lớp artifact phải là non-toxic, toxic.')
    terms = []
    if nb:
        contributions = x.data[:, None] * classifier.feature_log_prob_[:, x.indices].T
        base = classifier.class_log_prior_
        totals = np.asarray(base + contributions.sum(axis=0))
        prob = float(np.exp(totals[1] - np.logaddexp(totals[0], totals[1])))
        score = prob
        rank = np.argsort(-np.abs(contributions[:, 1] - contributions[:, 0]))
    else:
        contributions = x.data * classifier.coef_[0, x.indices]
        base = [float(classifier.intercept_[0])]
        totals = [float(base[0] + contributions.sum())]
        score = totals[0]
        rank = np.argsort(-np.abs(contributions))
    expected = float(model.decision_function([cleaned])[0])
    if not math.isclose(score, expected, abs_tol=1e-7, rel_tol=1e-6):
        raise ValueError('Phép tính minh họa không khớp artifact.')
    for k in rank[:4 if nb else 5]:
        index = int(x.indices[k])
        terms.append(dict(term=display_text(str(names[index])), index=index, value=float(x.data[k]),
                          weight=classifier.feature_log_prob_[:, index].tolist() if nb else float(classifier.coef_[0, index]),
                          contribution=contributions[k].tolist() if nb else float(contributions[k])))
    branches = getattr(vectorizer, 'transformer_list', [('word', vectorizer)])
    vocab = []
    for name, v in branches:
        local = v.transform([cleaned]).tocsr()
        feature_names = v.get_feature_names_out()
        analyzer = v.build_analyzer()(cleaned)
        from collections import Counter
        counts = Counter(analyzer)
        vocab.append(dict(branch=name, dimensions=len(v.vocabulary_), analyzer=v.analyzer,
                          ngram_range=list(v.ngram_range), norm=getattr(v, 'norm', None),
                          features=[dict(term=display_text(str(feature_names[i])), count=counts[feature_names[i]],
                                         value=float(value), idf=float(v.idf_[i]) if hasattr(v, 'idf_') else None)
                                    for i, value in zip(local.indices[:7], local.data[:7])]))
    shown = np.asarray([v['contribution'] for v in terms]).sum(axis=0) if terms else np.zeros(2 if nb else 1)
    remainder = np.asarray(totals) - np.asarray(base) - shown
    return dict(kind='nb' if nb else 'svm', score=score, threshold=float(threshold),
                prediction='toxic' if score >= threshold else 'non-toxic', base=np.asarray(base).tolist(),
                totals=np.asarray(totals).tolist(), remainder=np.asarray(remainder).reshape(-1).tolist(), terms=terms,
                shown_sum=np.asarray(shown).reshape(-1).tolist(), remaining_count=int(x.nnz-len(terms)),
                alpha=float(classifier.alpha) if nb else None,
                dimensions=x.shape[1], nonzero=x.nnz, branches=vocab)


def build_evidence(directory, progress=lambda value: None):
    import joblib
    from dataset import clean_text, word_tokens, PREPROCESS_VERSION, TOKENIZER_VERSION
    directory = Path(directory)
    metrics = read(directory / 'metrics.json')
    if (metrics.get('preprocess_version') != PREPROCESS_VERSION or
            metrics.get('tokenizer_version') != TOKENIZER_VERSION):
        raise ValueError('Cần trích xuất và huấn luyện lại trước khi tạo video với chuẩn hóa mới.')
    entries = {e['name']: e for e in metrics['models']}
    if any(name not in entries for name in NAMES):
        raise ValueError('Video toàn hệ thống cần đủ năm mô hình trong cùng run.')
    rows = read(directory / 'dataset.json')
    if any(r['text_clean'] != clean_text(r['text_raw']) for r in rows):
        raise ValueError('Snapshot văn bản sạch không khớp bộ chuẩn hóa của video.')
    # Deterministic selection by ID/length, independent of model predictions.
    candidates = [r for r in rows if 25 <= len(r['text_raw']) <= 115
                  and not re.search(r'https?://|\d{5}|@', r['text_raw'])
                  and not re.search(r'\b[A-ZĐ][a-zà-ỹ]+\s+[A-ZĐ][a-zà-ỹ]+', r['text_raw'])]
    examples = []
    for label in ('non-toxic', 'toxic'):
        # Choose an information question with teencode and an explicit insult, then
        # break ties by ID. No model score is consulted in example selection.
        pool = [r for r in candidates if r['label'] == label and
                (re.search(r'\b(ngu|cút|óc chó|vô học)\b', r['text_raw'], re.I) if label == 'toxic'
                 else re.search(r'^cho mình hỏi', r['text_raw'], re.I) and re.search(r'\b(ko|đc|khum)\b', r['text_raw'], re.I))]
        if not pool:
            pool = [r for r in candidates if r['label'] == label]
        row = sorted(pool, key=lambda r: r['id'])[0]
        text = row['text_raw']
        examples.append(dict(id=row['id'], text=text, display=display_text(text), label=label,
                             label_source=row.get('label_source'), text_hash=hashlib.sha256(text.encode()).hexdigest(),
                             cleaned=display_text(clean_text(text)), tokens=word_tokens(clean_text(text)), models={}))
    for i, name in enumerate(NAMES[:4]):
        entry = entries[name]
        model = joblib.load(directory / entry['artifact']['file'])
        for example in examples:
            example['models'][name] = evidence_for_linear(model, example['text'], entry['threshold'])
        progress(3 + i * 2)
    progress(12)
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from transformer_model import normalize_input
    folder = directory / 'ViSoBERT'
    training = read(folder / 'training.json')
    tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(folder, local_files_only=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device).eval()
    for example in examples:
        normalized = normalize_input(example['text'])
        encoded = tokenizer(normalized, truncation=True, max_length=training['config']['max_length'], return_tensors='pt')
        inputs = {k: v.to(device) for k, v in encoded.items()}
        with torch.inference_mode():
            result = model(**inputs, output_hidden_states=True)
            embedding = model.get_input_embeddings()(inputs['input_ids'])[0, :6, :8].cpu().tolist()
            # Independently reconstruct the actual XLM-R classification head.
            pooled = result.hidden_states[-1][:, 0, :]
            reconstructed = model.classifier.out_proj(torch.tanh(model.classifier.dense(pooled)))
            if not torch.allclose(reconstructed, result.logits, atol=1e-5, rtol=1e-5):
                raise ValueError('Đầu phân loại ViSoBERT không khớp phép tính minh họa.')
        logits = result.logits[0].float().cpu()
        probability = float(torch.softmax(logits, dim=-1)[1])
        threshold = entries['ViSoBERT']['threshold']
        ids = encoded['input_ids'][0].tolist()
        example['models']['ViSoBERT'] = dict(kind='transformer', score=probability, threshold=threshold,
            prediction='toxic' if probability >= threshold else 'non-toxic', normalized=display_text(normalized),
            tokens=tokenizer.convert_ids_to_tokens(ids), ids=ids, mask=encoded['attention_mask'][0].tolist(),
            original_tokens=len(tokenizer(normalized)['input_ids']), max_length=training['config']['max_length'],
            embedding=embedding, logits=logits.tolist(), layers=model.config.num_hidden_layers,
            hidden_size=model.config.hidden_size, heads=model.config.num_attention_heads,
            hidden_norms=[float(h[0].float().norm(dim=-1).mean().cpu()) for h in result.hidden_states])
    del model
    if device.type == 'cuda':
        torch.cuda.empty_cache()
    progress(20)
    return dict(version=VERSION, run=directory.name, created_at=datetime.now(timezone.utc).isoformat(),
                fingerprint=metrics['fingerprint'], input_fingerprint=metrics.get('input_fingerprint'),
                preprocess_version=metrics['preprocess_version'], tokenizer_version=metrics['tokenizer_version'],
                metrics=metrics, examples=examples,
                note='Chọn câu hỏi có teencode và công kích rõ theo nội dung, sau đó theo ID; không dùng điểm dự đoán. Nhãn dataset không phải chuẩn độc lập.')


class ReportStore:
    def __init__(self, data=ROOT / 'data', folder=ROOT / 'outputs/system_report_videos'):
        self.data, self.folder = Path(data), Path(folder)
        self.lock = threading.RLock()
        self.pending = None
        self.worker = None
        self.current = None
        self.wanted = None

    def identity(self, run):
        if not re.fullmatch(r'run-[A-Za-z0-9]+', run):
            raise ValueError('Run không hợp lệ.')
        directory = self.data / 'runs' / run
        metrics = read(directory / 'metrics.json')
        # Includes all fitted files, not just reported metrics: weight replacement invalidates cache.
        files = [(str(p.relative_to(directory)), p.stat().st_size, p.stat().st_mtime_ns)
                 for p in sorted(directory.rglob('*')) if p.is_file() and p.suffix in ('.json', '.joblib', '.bin', '.safetensors')]
        renderer_hash = hashlib.sha256(b''.join((ROOT / name).read_bytes() for name in
            ('system_report_video.py', 'report_animation.py', 'animation_renderer.py'))).hexdigest()
        return hashlib.sha256(json.dumps([VERSION, renderer_hash, run, metrics, files], sort_keys=True).encode()).hexdigest()

    def ready(self, key):
        if not re.fullmatch(r'[a-f0-9]{64}', str(key)):
            return None
        path = self.folder / (key + '.json')
        video = self.folder / (key + '.mp4')
        if path.exists() and video.exists() and video.stat().st_size > 1024:
            manifest = read(path)
            return dict(id=key, run=manifest['run'], chapters=manifest['chapters'], duration=manifest['duration'])
        return None

    def enqueue(self, run=None, retry=False):
        run = run or read(self.data / 'latest.json')['run']
        key = self.identity(run)
        with self.lock:
            self.wanted = key
            cached = self.ready(key)
            if cached:
                atomic(self.folder / 'latest-ready.json', cached)
                if not self.worker or not self.worker.is_alive():
                    self.current = dict(id=key, run=run, state='done', progress=100)
                return self.status()
            if self.current and self.current['id'] == key and self.current['state'] in ('queued', 'running', 'error') and not retry:
                return self.status()
            self.pending = (run, key)
            if not self.worker or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._work, daemon=True)
                self.worker.start()
            return self.status()

    def _work(self):
        while True:
            with self.lock:
                if not self.pending:
                    self.worker = None
                    return
                run, key = self.pending
                self.pending = None
                self.current = dict(id=key, run=run, state='running', progress=0)
            temporary = self.folder / (key + '.partial.mp4')
            try:
                self.folder.mkdir(parents=True, exist_ok=True)
                def progress(value):
                    with self.lock:
                        self.current['progress'] = value
                evidence = build_evidence(self.data / 'runs' / run, progress)
                from report_animation import render_report, chapters
                evidence['chapters'] = chapters(evidence)
                evidence['duration'] = sum(c['duration'] for c in evidence['chapters'])
                render_report(evidence, temporary, progress)
                import imageio.v2 as imageio
                with imageio.get_reader(str(temporary)) as reader:
                    metadata = reader.get_meta_data()
                    if metadata['size'] != (1280, 720) or abs(metadata['duration'] - evidence['duration']) > 1:
                        raise ValueError('Video xuất ra không khớp kích thước/thời lượng.')
                temporary.replace(self.folder / (key + '.mp4'))
                atomic(self.folder / (key + '.json'), evidence)
                with self.lock:
                    if key == self.wanted:
                        atomic(self.folder / 'latest-ready.json', self.ready(key))
                    self.current.update(state='done', progress=100)
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                with self.lock:
                    self.current.update(state='error', error=str(exc))

    def status(self):
        with self.lock:
            pointer = self.folder / 'latest-ready.json'
            ready = self.ready(read(pointer)['id']) if pointer.exists() else None
            return dict(job=dict(self.current) if self.current else None, ready=ready,
                        updating=bool(self.pending or (self.current and self.current['state'] == 'running')),
                        stale=bool(ready and self.wanted and ready['id'] != self.wanted))

    def video_path(self, key):
        if not self.ready(key):
            raise ValueError('Video báo cáo chưa sẵn sàng.')
        return self.folder / (key + '.mp4')


STORE = ReportStore()
