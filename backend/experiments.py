"""Reproducible group-held-out experiments and a report of measured results."""
import json
import platform
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
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
    (output / 'report.md').write_text(build_report(rows, result), encoding='utf-8')
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
            (output / 'report.md').write_text(build_report(rows, result), encoding='utf-8')
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


def build_report(rows, result=None, experiment_fingerprint=None, experiment_input_fingerprint=None):
    result = active_result(result)
    stats = summary(rows)
    status = 'Chưa có thực nghiệm: gán nhãn tự động toàn bộ hoặc gán nhãn thủ công rồi chạy huấn luyện. Nhãn máy không phải nhãn chuẩn do người đọc xác nhận.'
    if result:
        local_time = datetime.fromisoformat(result['created_at']).astimezone(timezone(timedelta(hours=7)))
        status = ('Kết quả dưới đây thuộc snapshot huấn luyện ' + local_time.strftime('%d/%m/%Y %H:%M (UTC+7)') + '. '
                  + ('Dữ liệu hoặc cách tách từ hiện tại đã thay đổi; cần chạy lại để cập nhật.'
                     if result['fingerprint'] != (experiment_fingerprint or fingerprint(rows)) or result.get('tokenizer_version') != TOKENIZER_VERSION
                     or result.get('preprocess_version') != PREPROCESS_VERSION
                     or (result.get('input_fingerprint') and result['input_fingerprint'] != (experiment_input_fingerprint or input_fingerprint(rows)))
                     else 'Snapshot trùng với dữ liệu và cách tách từ hiện tại.'))
    lines = [
        '# Phân loại bình luận toxic và non-toxic trong các nhóm Facebook liên quan đến sinh viên PTIT',
        '\n## 1. Giới thiệu bài toán',
        'Mục tiêu: hỗ trợ nhận diện bình luận độc hại trong ngữ cảnh cộng đồng sinh viên. '
        'Đầu vào là văn bản bình luận; đầu ra là toxic hoặc non-toxic. Đây là công cụ hỗ trợ nghiên cứu, '
        'không tự động kết luận tư cách sinh viên hay áp dụng chế tài với người viết.',
        'Nguồn dữ liệu: bình luận văn bản do Selenium thu thập từ các nhóm/trang người dùng có quyền truy cập. '
        'Không suy ra mọi người bình luận đều là sinh viên PTIT. Không khẳng định đã thu thập đầy đủ; '
        'bộ lọc Facebook, bình luận ẩn, ảnh/sticker và thay đổi giao diện có thể tạo thiên lệch mẫu.',
        '\n## 2. Cơ sở lý thuyết',
        'Toxic: công kích cá nhân/nhóm, lăng mạ, đe dọa, quấy rối hoặc miệt thị. Non-toxic: hỏi đáp, '
        'trao đổi thông tin, phản biện lịch sự và ý kiến tiêu cực không công kích. Từ tục trong trích dẫn '
        'hoặc đùa thân mật cần xét ngữ cảnh, không dùng từ khóa đơn lẻ làm nhãn chuẩn.',
        'BoW biểu diễn số lần xuất hiện token/ngram. TF-IDF giảm trọng số token phổ biến và tăng trọng số '
        'token đặc trưng. Với cấu hình mặc định: idf(t)=log((1+n)/(1+df(t)))+1, sau đó chuẩn hóa L2. '
        'Mặc định dùng unigram/bigram từ, tối đa 20.000 đặc trưng cho nhánh từ. Khi bật char_features, '
        'ghép thêm nhánh char_wb 3–5 ký tự, tối đa 20.000 đặc trưng riêng; tổng hai nhánh có thể tới 40.000. '
        'Có thể chọn lại cấu hình trên trang Trích xuất đặc trưng. '
        'Từ vựng và IDF chỉ học trên train; NB/SVM dùng lại ma trận đã trích xuất.',
        'Multinomial Naive Bayes dùng xác suất có điều kiện với giả định độc lập đặc trưng và làm trơn alpha=1. '
        'LinearSVC là SVM tuyến tính, cấu hình ban đầu C=1, class_weight=balanced. '
        'Khi tối ưu, alpha/C/trọng số lớp được chọn bằng validation; bảng cấu hình thực tế bên dưới ghi giá trị cuối cùng.',
        'Mô hình học sâu bổ sung: ViSoBERT, encoder Transformer tiền huấn luyện cho văn bản mạng xã hội tiếng Việt. '
        'Dùng tokenizer riêng và tinh chỉnh bộ phân loại trên nhãn train; chọn checkpoint và ngưỡng bằng validation.',
        '\n## 3. Thực nghiệm và kết quả',
        '\n### 3.1. Thu thập và tiền xử lý',
        f'Dữ liệu hiện tại: **{stats["total"]} bình luận**, **{stats["posts"]} bài**; '
        f'**{stats["usable"]} mẫu sạch duy nhất**, **{stats["labeled"]} mẫu sạch đã gán nhãn**. '
        f'Phân bố nhãn trong mẫu sạch: {json.dumps(stats["labels"], ensure_ascii=False)}. '
        f'Kiểm tra chất lượng: {json.dumps(stats["quality"], ensure_ascii=False)}.',
        f'Nguồn nhãn: {json.dumps(stats["label_sources"], ensure_ascii=False)}. '
        f'Số mẫu sạch có nhãn dùng được: {sum(r["quality"] == "ready" and r["label"] in LABELS for r in rows)}. '
        'Nhãn máy đã lưu được dùng trực tiếp, không yêu cầu duyệt. Nguồn automatic và xác nhận riêng được giữ để truy vết.',
        'Quy trình: chuẩn hóa Unicode NFC, chữ thường, giải mã HTML; ẩn URL/email/số điện thoại bằng token; '
        'bỏ ký tự vô hình trong chữ và dấu câu; chuẩn hóa một số teencode; '
        'chỉ loại stop words các/những. Giữ dấu tiếng Việt, từ phủ định, được/thì/mà, từ tục và emoji. '
        'Giữ k/cc khi mơ hồ; dạng tiền 10-50 k thành 10-50k; ko đc thành không được. '
        'Biểu cảm :))/=))) thành emoticon_smile, :(( thành emoticon_sad; không dùng biểu cảm làm nhãn. '
        f'Phiên bản tiền xử lý hiện tại: {PREPROCESS_VERSION}. '
        f'Tách từ bằng Underthesea trước trích xuất đặc trưng, phiên bản {TOKENIZER_VERSION}. '
        'Từ đa âm tiết được nối bằng dấu gạch dưới (sinh viên → sinh_viên); unigram là một từ, bigram là hai từ liền nhau. '
        'Giữ nguyên token ẩn thông tin, biểu cảm, emoji ghép và dạng tiền. NB/SVM và dự đoán baseline dùng cùng bộ tách từ; ViSoBERT dùng tokenizer riêng. '
        'Không xóa bản gốc. Văn bản trùng sau chuẩn hóa chỉ giữ một mẫu; nhãn mâu thuẫn bị loại khỏi train cho tới khi rà soát. '
        'Mẫu còn nội dung thu gọn được đánh dấu incomplete và không dùng huấn luyện; độ đầy đủ của bản crawl cũ thiếu thông tin này chưa được xác minh.',
        '\n### 3.2. Quy trình gán nhãn',
        'Người gán nhãn đọc văn bản gốc, chọn nhãn, ghi chú trường hợp khó hoặc loại dữ liệu không hợp lệ. '
        'Các trường hợp thiếu ngữ cảnh nên để trống để thảo luận. Nên có hai người gán độc lập một phần dữ liệu, '
        'thống nhất bất đồng và báo cáo Cohen kappa trước khi chốt bộ chuẩn. Hiện công cụ lưu một nhãn cuối cùng/mẫu; '
        'chưa có số liệu đồng thuận giữa người gán nhãn.',
        'Bộ nhãn hiện hành có hỗ trợ Qwen3 4B Instruct qua Ollama tại máy. Tác vụ đọc quy tắc v4, '
        'bình luận gốc, ngữ cảnh bài viết và chuỗi bình luận cha có sẵn. “Làm sạch dữ liệu” và '
        '“Gán nhãn tự động” là hai thao tác riêng; tác vụ tự động chỉ xử lý mẫu sạch chưa có nhãn, '
        'giữ nguyên nhãn, ghi chú và quyết định để trống do người đọc đã lưu.',
        'Mẫu sạch có nhãn toxic/non-toxic đã lưu được đưa vào trích xuất đặc trưng và huấn luyện, '
        'kể cả nhãn máy chưa có xác nhận riêng. Không có bước duyệt bắt buộc. Người dùng có thể sửa nhãn '
        'hoặc loại mẫu tại bảng dữ liệu; sửa nhãn làm đặc trưng/kết quả cũ hết hiệu lực. '
        'human_verified chỉ thể hiện xác nhận riêng đã được lưu; thông tin phê duyệt cũ được giữ như lịch sử, '
        'không quyết định quyền sử dụng nhãn. Nhãn không khớp nội dung gốc hiện tại vẫn bị loại.',
        'Gợi ý, điểm, model/revision và dấu vân tay văn bản được lưu tách khỏi nhãn xác nhận. '
        'data/workspace.json là kho chính, ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử; '
        'annotations.json/imported.json cũ chỉ dùng làm nguồn chuyển đổi khi chưa có workspace. '
        'Nhãn có dấu vân tay không còn khớp nội dung phải được duyệt lại. '
        'Bản xuất /api/dataset.csv và /api/dataset.json chứa mẫu ready có nhãn đã lưu, bao gồm nhãn máy, '
        'kèm nguồn nhãn và label_usable; gợi ý chưa lưu nhãn không được đưa vào dataset.',
        '\n### 3.3. Thiết kế đánh giá',
        'Chia theo nhóm bài viết độc lập, mục tiêu khoảng 60% train / 20% validation / 20% test theo số nhóm '
        '(tỷ lệ bình luận thực tế có thể khác). Các bài chứa bình luận trùng được nối cùng nhóm. '
        'Không có bài hoặc văn bản chuẩn hóa trùng giữa các tập. Seed 42; seed 43 cho validation. '
        'Chọn lần chia đầu tiên mà cả hai lớp xuất hiện trong mỗi tập; không chọn theo điểm mô hình. '
        'Tối thiểu 10 mẫu mỗi lớp và 5 nhóm độc lập chỉ là điều kiện chạy kỹ thuật; cần nhiều dữ liệu hơn cho kết luận đáng tin cậy.',
        'Mỗi phương pháp đặc trưng được chọn được dùng cho hai baseline NB và SVM; ViSoBERT dùng cùng các tập chia. '
        'Chọn mô hình theo macro-F1 validation, không chọn theo test. Test được dùng để so sánh cuối cùng. '
        'Không cân bằng mẫu hoặc học từ vựng trên toàn bộ dữ liệu trước khi chia.',
        'Nhãn validation/test cần được người đọc gán độc lập, không xem gợi ý tự động, rồi kiểm tra chéo và khóa trước đánh giá. '
        'Việc này phải thực hiện bằng quy trình nhóm/bản xuất riêng; giao diện chưa tự che gợi ý hay khóa bộ test. '
        'Cần công bố phần dữ liệu có hỗ trợ tự động và quy trình duyệt; chưa có bằng chứng về độ chính xác của mô hình gợi ý trên corpus PTIT.',
        'Accuracy=(TP+TN)/N; Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2PR/(P+R). '
        'Lớp dương là toxic. Macro-F1 là trung bình F1 hai lớp. Confusion matrix: hàng là nhãn tham chiếu trong dataset, '
        'cột là dự đoán, thứ tự [non-toxic, toxic], tức [[TN, FP], [FN, TP]]. Mẫu số bằng 0 được ghi 0.',
        '\n### 3.4. Kết quả', status,
    ]
    if result:
        if result['summary'].get('label_sources', {}).get('automatic', 0):
            lines += ['**Lần huấn luyện này dùng nhãn tự động.** Nếu validation/test có nhãn máy, các chỉ số đo mức khớp với nhãn máy, chưa đo độ chính xác thực trên PTIT. Xem automatic_labels trong thống kê từng tập.']
        lines += [f'Snapshot: {result["fingerprint"]}. Phiên bản thư viện: {json.dumps(result["versions"])}.',
                  f'Bộ tách từ của lần chạy: {result.get("tokenizer", "Khoảng trắng")}; phiên bản: {result.get("tokenizer_version", "cũ")}.',
                  f'Cấu hình thực tế: {json.dumps(result["settings"], ensure_ascii=False)}.',
                  f'Phân chia thực tế: {json.dumps(result["split"], ensure_ascii=False)}.',
                  '| Cấu hình | Val macro-F1 | Accuracy | Precision toxic | Recall toxic | F1 toxic | Macro-F1 | Giây |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for model in result['models']:
            m = model['test']
            lines.append(f'| {model["name"]} | {model["validation"]["f1_macro"]:.4f} | {m["accuracy"]:.4f} | {m["precision"]:.4f} | {m["recall"]:.4f} | {m["f1"]:.4f} | {m["f1_macro"]:.4f} | {model["seconds"]:.3f} |')
        lines += [f'Mô hình được chọn theo validation: **{result["selected_model"]}**.']
        if result.get('retained_models'):
            lines += ['Lượt này chạy lại: ' + ', '.join(result['trained_models']) + '. Giữ kết quả đã hoàn tất: '
                      + ', '.join(result['retained_models']) + '. Chỉ giữ lại khi snapshot và bộ chia trùng nhau.']
        lines += ['Thiết bị huấn luyện: ' + ', '.join(f'{m["name"]}: {m.get("device", m.get("parameters", {}).get("device", "cpu"))}' for m in result['models']) + '.']
        if result.get('experiment_type') == 'validation_search':
            lines += ['### Tối ưu tham số và ngưỡng',
                      'Cột Giây của mô hình tối ưu gồm thời gian tìm kiếm tham số trong nhóm; '
                      'không dùng để so trực tiếp tốc độ huấn luyện một cấu hình hay tốc độ dự đoán.',
                      'Giữ nguyên nhãn, không bổ sung ngữ cảnh. Mỗi mô hình chỉ giữ một kết quả cuối cùng. '
                      'NB/SVM dùng đúng ma trận và từ vựng đã tạo ở bước trích xuất, không fit lại vectorizer. '
                      'NB thử alpha 0,1/0,3/1/3; SVM thử C 0,03/0,1/0,3/1/3, có/không class_weight balanced. '
                      'Unigram/bigram, phương pháp và số đặc trưng tối đa do bước trích xuất quyết định. '
                      'Từ vựng và IDF chỉ fit train. search.json lưu các lượt chọn tham số phân loại.',
                      'Sau khi chốt tham số bằng ngưỡng mặc định, chọn ngưỡng macro-F1 trên validation, '
                      'không dùng test. Điểm SVM là decision score, không phải xác suất/độ tin cậy đã hiệu chỉnh. '
                      'Các xác suất NB/ViSoBERT cũng chưa được kiểm định hiệu chỉnh. '
                      'Ngưỡng chỉ thay đổi quyết định, không tự cải thiện khả năng xếp hạng của mô hình.',
                      '| Cấu hình | Ngưỡng | Val macro-F1 mặc định → tối ưu | Test precision mặc định → tối ưu | Test recall mặc định → tối ưu |',
                      '|---|---:|---:|---:|---:|']
            for model in result['models']:
                if 'threshold' not in model:
                    continue
                before, after = model['test_default'], model['test']
                lines.append(f'| {model["name"]} | {model["threshold"]:.5f} | '
                             f'{model["validation_default"]["f1_macro"]:.4f} → {model["validation"]["f1_macro"]:.4f} | '
                             f'{before["precision"]:.4f} → {after["precision"]:.4f} | '
                             f'{before["recall"]:.4f} → {after["recall"]:.4f} |')
            lines += [result['protocol']['limitation'] + ' Điểm validation sau tìm kiếm có thể lạc quan; '
                      'các kết quả test ở đây mang tính so sánh trên bộ tham chiếu hiện tại.']
        transformer = next((m for m in result['models'] if m['algorithm'] == 'ViSoBERT'), None)
        if transformer:
            p = transformer['parameters']
            lines += [f'ViSoBERT dùng {p["source"]["model"]}, revision {p["source"]["revision"]}; '
                      f'chiến lược {p["fine_tuning"]}, thiết bị {p["device"]}, checkpoint epoch {p["best_epoch"]}. '
                      'Chuẩn hóa Unicode/URL/email, giữ dấu câu và emoji; dùng tokenizer tiền huấn luyện, '
                      'không tách từ Underthesea. Bộ phân loại được học trên nhãn train, '
                      'chọn checkpoint và ngưỡng bằng validation.']
        for feature in ('BoW', 'TF-IDF'):
            subset = {m['algorithm']: m for m in result['models'] if m['feature'] == feature}
            if set(subset) != {'NB', 'SVM'}:
                continue
            delta = subset['SVM']['test']['f1_macro'] - subset['NB']['test']['f1_macro']
            lines.append(f'Với {feature}, chênh lệch test macro-F1 của SVM so với NB là {delta:+.4f}.')
        for algorithm in ('NB', 'SVM'):
            subset = {m['feature']: m for m in result['models'] if m['algorithm'] == algorithm}
            if set(subset) != {'BoW', 'TF-IDF'}:
                continue
            delta = subset['TF-IDF']['test']['f1_macro'] - subset['BoW']['test']['f1_macro']
            lines.append(f'Với {algorithm}, chênh lệch test macro-F1 của TF-IDF so với BoW là {delta:+.4f}.')
        for model in result['models']:
            lines.append(f'- {model["name"]}: confusion matrix `{model["test"]["confusion_matrix"]}`.')
        lines += ['Các chênh lệch trên chỉ mô tả một lần chia; chưa chứng minh ý nghĩa thống kê. '
                  'Xem *-predictions.json cùng dataset.json trong thư mục run để phân tích các lỗi FP/FN.']
    else:
        lines += ['Chưa có Accuracy/Precision/Recall/F1/confusion matrix để báo cáo. Không dùng nhãn tự suy đoán '
                  'hoặc dữ liệu kiểm thử phần mềm làm kết quả trên sinh viên PTIT. Hoàn thành gán nhãn, chạy huấn luyện rồi xuất lại báo cáo.']
    lines += ['\n## 4. Kết luận và hạn chế',
              'Hệ thống cung cấp luồng thu thập → làm sạch → gán nhãn → trích chọn đặc trưng → huấn luyện → '
              'đánh giá → dự đoán. Hạn chế: số bài ít, thiên lệch chọn nhóm, chưa xác minh danh tính sinh viên, '
              'mỉa mai và hội thoại cần ngữ cảnh, ảnh/sticker bị bỏ qua, tách từ có thể sai với tiếng lóng, ViSoBERT giới hạn độ dài đầu vào theo cấu hình đã lưu. '
              'Cần tăng số nhóm/bài và nhãn được kiểm tra chéo; mở rộng đánh giá sang dữ liệu ở thời điểm khác. '
              'Tránh điều chỉnh lặp lại dựa trên test. Bản gốc vẫn có thể chứa thông tin cá nhân; '
              'ẩn tên và định danh trước khi chia sẻ corpus, không chia sẻ chrome-profile.',
              '\n## Tài liệu tham khảo',
              '1. Scikit-learn: https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction',
              '2. Naive Bayes: https://scikit-learn.org/stable/modules/naive_bayes.html',
              '3. LinearSVC: https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html',
              '4. GroupShuffleSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html',
              '5. PyTorch: https://docs.pytorch.org/docs/stable/nn.html',
              '6. Selenium: https://www.selenium.dev/documentation/webdriver/',
              '7. Model gợi ý: [dangvansam/vietnamese-toxicity](https://huggingface.co/dangvansam/vietnamese-toxicity), revision bac60f3e162d3a06003bf561a9f8365982ccc67a.',
              '8. Nguyen et al. (2023), [ViSoBERT](https://aclanthology.org/2023.emnlp-main.315/); [model card và phạm vi nghiên cứu](https://huggingface.co/uitnlp/visobert).',
              '9. Underthesea: https://github.com/undertheseanlp/underthesea',
              ]
    report = ''
    for index, line in enumerate(lines):
        separator = '\n' if index and line.startswith('|') and lines[index - 1].startswith('|') else '\n\n'
        report += (separator if index else '') + line
    return report + '\n'
