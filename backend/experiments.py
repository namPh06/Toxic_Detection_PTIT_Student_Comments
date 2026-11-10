"""Reproducible group-held-out experiments and measured model results."""
import json
import platform
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from backend.dataset import LABELS, PREPROCESS_VERSION, TOKENIZER_VERSION, atomic_json, fingerprint, input_fingerprint, summary

MODEL_NAMES = ('BoW-NB', 'BoW-SVM', 'TF-IDF-NB', 'TF-IDF-SVM', 'ViSoBERT')


def active_result(result):
    """Present only supported models, without mutating historical run files."""
    if not result:
        return None
    import copy
    result = copy.deepcopy(result)
    result['models'] = [m for m in result['models'] if m['name'] in MODEL_NAMES]
    if not result['models']:
        return None
    names = {m['name'] for m in result['models']}
    if result.get('selected_model') not in names:
        result['selected_model'] = max(result['models'], key=lambda m: m['validation']['f1_macro'])['name']
    for key in ('trained_models', 'retained_models'):
        if key in result:
            result[key] = [name for name in result[key] if name in names]
    if 'requested_algorithms' in result:
        result['requested_algorithms'] = [a for a in result['requested_algorithms'] if a in ('NB', 'SVM', 'ViSoBERT')]
    return result


def split_dataset(rows):
    eligible = [r for r in rows if r['quality'] == 'ready' and r['label'] in LABELS]
    counts = Counter(r['label'] for r in eligible)
    if min(counts[x] for x in LABELS) < 10:
        raise ValueError('Cần ít nhất 10 mẫu sạch đã gán nhãn cho mỗi lớp. Đây chỉ là mức tối thiểu để chạy, chưa đủ để kết luận chất lượng.')
    import numpy as np
    from sklearn.model_selection import GroupShuffleSplit
    group_key = lambda r: str(r.get('split_group') or r['post_id'])
    parents = {group_key(r): group_key(r) for r in rows}

    def root(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x

    first_post = {}
    for row in rows:
        if row['quality'] not in ('ready', 'duplicate'):
            continue
        post = group_key(row)
        previous = first_post.setdefault(row['text_clean'], post)
        parents[root(post)] = root(previous)
    groups = np.array([root(group_key(r)) for r in eligible])
    labels = np.array([LABELS.index(r['label']) for r in eligible])
    if any(r.get('dataset_partition') for r in eligible):
        if any(r.get('dataset_partition') not in ('train', 'validation', 'test') for r in eligible):
            raise ValueError('Bộ chia cố định thiếu phân vùng cho một số mẫu.')
        split = {name: [i for i, r in enumerate(eligible) if r['dataset_partition'] == name]
                 for name in ('train', 'validation', 'test')}
        memberships = [{groups[i] for i in ids} for ids in split.values()]
        if any(memberships[i] & memberships[j] for i in range(3) for j in range(i)):
            raise ValueError('Bộ chia cố định có nhóm bài hoặc nội dung trùng giữa các tập.')
        if any(len(set(labels[ids])) != 2 for ids in split.values()):
            raise ValueError('Mỗi tập cố định phải có đủ hai nhãn.')
        return eligible, split, groups.tolist()
    if len(set(groups)) < 5:
        raise ValueError('Cần ít nhất 5 nhóm bài độc lập đã gán nhãn. Các bài có bình luận trùng được nối cùng nhóm để tránh rò rỉ dữ liệu.')
    indexes = np.arange(len(eligible))
    for train_val, test in GroupShuffleSplit(n_splits=100, test_size=0.2, random_state=42).split(indexes, labels, groups):
        if len(set(labels[test])) != 2 or len(set(groups[train_val])) < 3:
            continue
        for train_local, val_local in GroupShuffleSplit(n_splits=50, test_size=0.25, random_state=43).split(train_val, labels[train_val], groups[train_val]):
            train, val = train_val[train_local], train_val[val_local]
            if all(len(set(labels[part])) == 2 for part in (train, val)):
                return eligible, {'train': train.tolist(), 'validation': val.tolist(), 'test': test.tolist()}, groups.tolist()
    raise ValueError('Không chia được train/validation/test độc lập theo bài mà mỗi tập đều có 2 lớp. Hãy gán nhãn thêm ở nhiều bài khác nhau.')


def metrics(y_true, y_pred):
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', pos_label=1, zero_division=0)
    _, _, macro, _ = precision_recall_fscore_support(y_true, y_pred, average='macro', zero_division=0)
    return dict(accuracy=float(accuracy_score(y_true, y_pred)), precision=float(precision), recall=float(recall),
                f1=float(f1), f1_macro=float(macro), confusion_matrix=confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
                per_class=classification_report(y_true, y_pred, labels=[0, 1], target_names=LABELS, output_dict=True, zero_division=0))


def validate_algorithms(algorithms=None, include_visobert=False, optimized=False):
    selected = (['NB', 'SVM'] + (['ViSoBERT'] if include_visobert else [])
                if algorithms is None else algorithms)
    allowed = ('NB', 'SVM', 'ViSoBERT') if optimized else ('NB', 'SVM')
    if (not isinstance(selected, list) or not selected or any(a not in allowed for a in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError('Chọn ít nhất một mô hình hợp lệ; không chọn trùng mô hình.')
    return [a for a in allowed if a in selected]


def train_experiment(rows, output, notify=lambda message: None, prepared=None, algorithms=None):
    import joblib
    import sklearn
    import torch
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC
    from backend.features import build_features, feature_key

    # An empty internal baseline list supports a ViSoBERT-only optimized run.
    algorithms = validate_algorithms(algorithms) if algorithms != [] else []
    prepared = prepared if prepared is not None else build_features(rows, {})
    if prepared['key'] != feature_key(rows):
        raise ValueError('Bộ đặc trưng thuộc dữ liệu cũ. Hãy trích xuất lại trước khi huấn luyện.')
    eligible, split, groups = prepared['rows'], prepared['split'], prepared['groups']
    texts, labels = prepared['texts'], prepared['labels']
    ngrams = {'unigram': [1, 1], 'bigram': [2, 2], 'both': [1, 2]}[prepared['settings']['ngram']]
    output.mkdir(parents=True, exist_ok=False)
    result = dict(created_at=datetime.now(timezone.utc).isoformat(), fingerprint=fingerprint(rows),
                  input_fingerprint=input_fingerprint(rows), preprocess_version=PREPROCESS_VERSION, tokenizer='Underthesea',
                  tokenizer_version=TOKENIZER_VERSION, seed=42, summary=summary(rows), models=[],
                  versions=dict(python=platform.python_version(), sklearn=sklearn.__version__, torch=torch.__version__),
                  split={name: dict(count=len(ids), groups=len({groups[i] for i in ids}),
                                     labels=dict(Counter(eligible[i]['label'] for i in ids)),
                                     automatic_labels=sum(eligible[i].get('label_source') == 'automatic' for i in ids)) for name, ids in split.items()},
                  feature_created_at=prepared['created_at'],
                  settings=dict(ngram_range=ngrams, max_features=prepared['settings']['max_features'],
                                char_features=prepared['settings'].get('char_features', False),
                                feature_methods=prepared['settings']['methods'], nb_alpha=1, svm_C=1))
    manifest = {name: [dict(id=eligible[i]['id'], post_id=eligible[i]['post_id'], group=groups[i], label=eligible[i]['label'], label_source=eligible[i].get('label_source', 'legacy'))
                       for i in ids] for name, ids in split.items()}
    atomic_json(output / 'split.json', manifest)
    atomic_json(output / 'dataset.json', eligible)

    def record(name, feature, algorithm, val_pred, test_pred, elapsed):
        evaluation = metrics(labels['test'], test_pred)
        result['models'].append(dict(name=name, feature=feature, algorithm=algorithm, seconds=round(elapsed, 3),
                                     validation=metrics(labels['validation'], val_pred), test=evaluation))
        predictions = [dict(id=eligible[i]['id'], actual=LABELS[actual], predicted=LABELS[int(predicted)])
                       for i, actual, predicted in zip(split['test'], labels['test'], test_pred)]
        atomic_json(output / f'{name}-predictions.json', predictions)

    for feature, data in prepared['features'].items():
        for algorithm, classifier in [('NB', MultinomialNB()), ('SVM', LinearSVC(class_weight='balanced', random_state=42, max_iter=10000))]:
            if algorithm not in algorithms:
                continue
            name = feature + '-' + algorithm
            notify('Đang huấn luyện ' + name)
            started = time.monotonic()
            classifier.fit(data['matrices']['train'], labels['train'])
            model = Pipeline([('vectorizer', data['vectorizer']), ('classifier', classifier)])
            record(name, feature, algorithm, classifier.predict(data['matrices']['validation']),
                   classifier.predict(data['matrices']['test']), time.monotonic() - started)
            joblib.dump(model, output / f'{name}.joblib')
    result['selected_model'] = max(result['models'], key=lambda m: m['validation']['f1_macro'])['name'] if result['models'] else ''
    result['trained_models'] = [m['name'] for m in result['models']]
    atomic_json(output / 'metrics.json', result)
    return result


def retain_models(result, output, previous):
    """Keep completed models only when labels, raw input and fixed split match."""
    import copy
    import shutil
    output, previous = Path(output), Path(previous) if previous else None
    result['trained_models'] = [m['name'] for m in result['models']]
    result['retained_models'] = []
    if not previous or previous == output or not (previous / 'metrics.json').exists():
        return result
    old = json.loads((previous / 'metrics.json').read_text(encoding='utf-8'))
    compatible = (old['fingerprint'] == result['fingerprint'] and old.get('tokenizer_version') == result.get('tokenizer_version')
                  and old.get('preprocess_version') == result.get('preprocess_version')
                  and (previous / 'split.json').read_bytes() == (output / 'split.json').read_bytes())
    if not compatible:
        return result
    old_rows = json.loads((previous / 'dataset.json').read_text(encoding='utf-8'))
    new_rows = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))
    if input_fingerprint(old_rows) != input_fingerprint(new_rows):
        return result

    def carry(source, target):
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.hardlink_to(source)
        except OSError:
            shutil.copy2(source, target)

    names = {m['name'] for m in result['models']}
    for entry in old['models']:
        if entry['name'] in names or entry['name'] not in MODEL_NAMES:
            continue
        model = copy.deepcopy(entry)
        name = model['name']
        settings = model.get('training_settings', old['settings'])
        if model['algorithm'] in ('NB', 'SVM'):
            if (model['feature'] not in result['settings']['feature_methods'] or
                    any(settings.get(key) != result['settings'].get(key) for key in ('ngram_range', 'max_features')) or
                    settings.get('char_features', False) != result['settings'].get('char_features', False)):
                continue
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            continue
        artifact = model.get('artifact', {})
        files = [f'{name}-predictions.json', f'{name}-validation-predictions.json', f'{name}-threshold.json']
        if artifact.get('kind') == 'transformer':
            if not all((previous / 'ViSoBERT' / f).is_file() for f in ('config.json', 'training.json', 'model.safetensors', 'tokenizer.json')):
                continue
            files += [str(p.relative_to(previous)) for p in (previous / 'ViSoBERT').rglob('*') if p.is_file()]
        else:
            if not (previous / f'{name}.joblib').is_file():
                continue
            files += [f'{name}.joblib']
        if not (previous / f'{name}-predictions.json').is_file():
            continue
        for filename in files:
            if (previous / filename).is_file():
                carry(previous / filename, output / filename)
        model['source_run'] = model.get('source_run', previous.name)
        model['training_settings'] = settings
        model['retained'] = True
        result['models'].append(model)
        result['retained_models'].append(name)
    if result['retained_models']:
        if old.get('experiment_type') == 'validation_search':
            result.setdefault('experiment_type', old['experiment_type'])
            result.setdefault('protocol', old['protocol'])
        result['selected_model'] = max(result['models'], key=lambda m: m['validation']['f1_macro'])['name']
        result['versions'] = dict(old['versions'], **result['versions'])
    result['models'].sort(key=lambda model: MODEL_NAMES.index(model['name']))
    atomic_json(output / 'metrics.json', result)
    return result


def publish_run(result, output, directory, rows):
    """Serialize CLI/web publication and merge the latest completed model set."""
    import os
    import re
    output, directory = Path(output), Path(directory)
    with (directory / '.publish.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            latest = directory / 'latest.json'
            run = json.loads(latest.read_text(encoding='utf-8')).get('run', '') if latest.exists() else ''
            previous = directory / 'runs' / run if re.fullmatch(r'run-\d{8}T\d{12}Z', run) else None
            result = retain_models(result, output, previous)
            atomic_json(output / 'metrics.json', result)
            atomic_json(latest, dict(run=output.name))
            return result
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def predict(text, directory, model_name):
    from backend import improvements  # Register the module name used by older joblib models.
    from backend.dataset import clean_text
    metadata = json.loads((directory / 'metrics.json').read_text(encoding='utf-8'))
    if metadata.get('tokenizer_version') != TOKENIZER_VERSION:
        raise ValueError('Mô hình dùng cách tách từ cũ. Hãy trích xuất lại đặc trưng bằng Underthesea và huấn luyện lại.')
    if metadata.get('preprocess_version') != PREPROCESS_VERSION:
        raise ValueError('Chuẩn hóa teencode đã đổi. Hãy trích xuất lại đặc trưng và huấn luyện lại mô hình.')
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError('Bình luận không còn token sau làm sạch.')
    entry = next((item for item in metadata['models'] if item['name'] == model_name), None)
    if not entry or model_name not in MODEL_NAMES:
        raise ValueError('Mô hình không hợp lệ.')
    artifact = entry.get('artifact') if entry else None
    score = None
    if artifact:
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+', model_name):
            raise ValueError('Mô hình không hợp lệ.')
        if artifact['kind'] == 'sklearn':
            import joblib
            model = joblib.load(directory / artifact['file'])
            score = float(model.decision_function([cleaned])[0])
        elif artifact['kind'] == 'transformer':
            from backend.transformer_model import predict_transformer
            score = float(predict_transformer(directory / 'ViSoBERT', [text])[0])
        else:
            raise ValueError('Định dạng mô hình không được hỗ trợ.')
        value = int(score >= entry['threshold'])
    elif model_name in ('BoW-NB', 'BoW-SVM', 'TF-IDF-NB', 'TF-IDF-SVM'):
        import joblib
        value = joblib.load(directory / f'{model_name}.joblib').predict([cleaned])[0]
    else:
        raise ValueError('Mô hình không hợp lệ.')
    answer = dict(label=LABELS[int(value)], text_clean=cleaned, model=model_name)
    if score is not None:
        answer.update(score=score, threshold=entry['threshold'])
    return answer
