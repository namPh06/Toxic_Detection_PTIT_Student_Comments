"""Reproducible group-held-out experiments and a report of measured results."""
import json
import platform
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dataset import LABELS, PREPROCESS_VERSION, atomic_json, fingerprint, summary


def split_dataset(rows):
    eligible = [r for r in rows if r['quality'] == 'ready' and r['label'] in LABELS]
    counts = Counter(r['label'] for r in eligible)
    if min(counts[x] for x in LABELS) < 10:
        raise ValueError('Cần ít nhất 10 mẫu sạch đã gán nhãn cho mỗi lớp. Đây chỉ là mức tối thiểu để chạy, chưa đủ để kết luận chất lượng.')
    import numpy as np
    from sklearn.model_selection import GroupShuffleSplit
    parents = {str(r['post_id']): str(r['post_id']) for r in rows}

    def root(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x

    first_post = {}
    for row in rows:
        if row['quality'] not in ('ready', 'duplicate'):
            continue
        post = str(row['post_id'])
        previous = first_post.setdefault(row['text_clean'], post)
        parents[root(post)] = root(previous)
    groups = np.array([root(str(r['post_id'])) for r in eligible])
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


def train_experiment(rows, output, notify=lambda message: None, epochs=12):
    import joblib
    import sklearn
    import torch
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC
    from neural import encode, predict_cnn, train_cnn

    eligible, split, groups = split_dataset(rows)
    texts = {name: [eligible[i]['text_clean'] for i in ids] for name, ids in split.items()}
    labels = {name: [LABELS.index(eligible[i]['label']) for i in ids] for name, ids in split.items()}
    output.mkdir(parents=True, exist_ok=False)
    result = dict(created_at=datetime.now(timezone.utc).isoformat(), fingerprint=fingerprint(rows),
                  preprocess_version=PREPROCESS_VERSION, seed=42, summary=summary(rows), models=[],
                  versions=dict(python=platform.python_version(), sklearn=sklearn.__version__, torch=torch.__version__),
                  split={name: dict(count=len(ids), groups=len({groups[i] for i in ids}),
                                     labels=dict(Counter(eligible[i]['label'] for i in ids)),
                                     automatic_labels=sum(eligible[i].get('label_source') == 'automatic' for i in ids)) for name, ids in split.items()},
                  settings=dict(ngram_range=[1, 2], max_features=20000, nb_alpha=1, svm_C=1,
                                cnn_embedding=64, cnn_filters=48, cnn_kernels=[2, 3, 4], cnn_max_length=128,
                                cnn_dropout=0.3, cnn_epochs=epochs, cnn_learning_rate=0.001, cnn_batch_size=32))
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

    for feature, vectorizer in [('BoW', CountVectorizer), ('TF-IDF', TfidfVectorizer)]:
        for algorithm, classifier in [('NB', MultinomialNB()), ('SVM', LinearSVC(class_weight='balanced', random_state=42, max_iter=10000))]:
            name = feature + '-' + algorithm
            notify('Đang huấn luyện ' + name)
            started = time.monotonic()
            model = Pipeline([('vectorizer', vectorizer(tokenizer=str.split, token_pattern=None, lowercase=False,
                                                        ngram_range=(1, 2), max_features=20000)), ('classifier', classifier)])
            model.fit(texts['train'], labels['train'])
            record(name, feature, algorithm, model.predict(texts['validation']), model.predict(texts['test']), time.monotonic() - started)
            joblib.dump(model, output / f'{name}.joblib')
    started = time.monotonic()
    model, vocabulary, history, best_epoch = train_cnn(texts['train'], labels['train'], texts['validation'], labels['validation'], notify, epochs)
    record('TextCNN', 'Word embeddings', 'TextCNN', predict_cnn(model, encode(texts['validation'], vocabulary)),
           predict_cnn(model, encode(texts['test'], vocabulary)), time.monotonic() - started)
    torch.save(model.state_dict(), output / 'TextCNN.pt')
    atomic_json(output / 'vocabulary.json', vocabulary)
    result['cnn_history'], result['cnn_best_epoch'] = history, best_epoch
    result['selected_model'] = max(result['models'], key=lambda m: m['validation']['f1_macro'])['name']
    atomic_json(output / 'metrics.json', result)
    (output / 'report.md').write_text(build_report(rows, result), encoding='utf-8')
    return result


def predict(text, directory, model_name):
    from dataset import clean_text
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError('Bình luận không còn token sau làm sạch.')
    if model_name == 'TextCNN':
        import torch
        from neural import TextCNN, encode, predict_cnn
        vocabulary = json.loads((directory / 'vocabulary.json').read_text(encoding='utf-8'))
        model = TextCNN(len(vocabulary) + 2)
        model.load_state_dict(torch.load(directory / 'TextCNN.pt', map_location='cpu', weights_only=True))
        value = predict_cnn(model, encode([cleaned], vocabulary))[0]
    elif model_name in ('BoW-NB', 'BoW-SVM', 'TF-IDF-NB', 'TF-IDF-SVM'):
        import joblib
        value = joblib.load(directory / f'{model_name}.joblib').predict([cleaned])[0]
    else:
        raise ValueError('Mô hình không hợp lệ.')
    return dict(label=LABELS[int(value)], text_clean=cleaned, model=model_name)


def build_report(rows, result=None):
    stats = summary(rows)
    status = 'Chưa có thực nghiệm: gán nhãn tự động toàn bộ hoặc gán nhãn thủ công rồi chạy huấn luyện. Nhãn máy không phải nhãn chuẩn do người đọc xác nhận.'
    if result:
        local_time = datetime.fromisoformat(result['created_at']).astimezone(timezone(timedelta(hours=7)))
        status = ('Kết quả dưới đây thuộc snapshot huấn luyện ' + local_time.strftime('%d/%m/%Y %H:%M (UTC+7)') + '. '
                  + ('Dữ liệu hiện tại đã thay đổi; cần chạy lại để cập nhật.' if result['fingerprint'] != fingerprint(rows) else 'Snapshot trùng với dữ liệu hiện tại.'))
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
        'Cả hai dùng unigram/bigram, tối đa 20.000 đặc trưng; từ vựng và IDF chỉ học trên train.',
        'Multinomial Naive Bayes dùng xác suất có điều kiện với giả định độc lập đặc trưng và làm trơn alpha=1. '
        'LinearSVC là SVM tuyến tính với C=1, class_weight=balanced để giảm tác động mất cân bằng lớp.',
        'Mô hình học sâu bổ sung: TextCNN theo hướng Kim (2014), embedding 64 chiều học từ đầu, '
        '3 cửa sổ convolution 2/3/4 token, mỗi cửa sổ 48 bộ lọc, ReLU, global max pooling, dropout 0,3 và lớp tuyến tính 2 nhãn. '
        'Adam, learning rate 0,001; batch 32; tối đa 12 epoch; chọn epoch bằng macro-F1 validation. '
        'Đây là baseline học sâu, không phải Transformer hay mô hình đã tiền huấn luyện.',
        '\n## 3. Thực nghiệm và kết quả',
        '\n### 3.1. Thu thập và tiền xử lý',
        f'Dữ liệu hiện tại: **{stats["total"]} bình luận**, **{stats["posts"]} bài**; '
        f'**{stats["usable"]} mẫu sạch duy nhất**, **{stats["labeled"]} mẫu sạch đã gán nhãn**. '
        f'Phân bố nhãn trong mẫu sạch: {json.dumps(stats["labels"], ensure_ascii=False)}. '
        f'Kiểm tra chất lượng: {json.dumps(stats["quality"], ensure_ascii=False)}.',
        f'Nguồn nhãn: {json.dumps(stats["label_sources"], ensure_ascii=False)}. Nhãn automatic được mô hình gán, chưa phải nhãn người đọc xác nhận.',
        'Quy trình: chuẩn hóa Unicode NFC, chữ thường, giải mã HTML; ẩn URL/email/số điện thoại bằng token; '
        'bỏ ký tự vô hình và dấu câu; chuẩn hóa một số teencode; tách token theo âm tiết/khoảng trắng và emoji; '
        'loại danh sách stop words ngắn. Giữ dấu tiếng Việt, từ phủ định, từ tục và emoji. '
        'Chưa ghép từ đa âm tiết bằng bộ phân đoạn tiếng Việt; bigram giúp biểu diễn các cụm gần nhau. '
        'Không xóa bản gốc. Văn bản trùng sau chuẩn hóa chỉ giữ một mẫu; nhãn mâu thuẫn bị loại khỏi train cho tới khi rà soát. '
        'Mẫu còn nội dung thu gọn được đánh dấu incomplete và không dùng huấn luyện; độ đầy đủ của bản crawl cũ thiếu thông tin này chưa được xác minh.',
        '\n### 3.2. Quy trình gán nhãn',
        'Người gán nhãn đọc văn bản gốc, chọn nhãn, ghi chú trường hợp khó hoặc loại dữ liệu không hợp lệ. '
        'Các trường hợp thiếu ngữ cảnh nên để trống để thảo luận. Nên có hai người gán độc lập một phần dữ liệu, '
        'thống nhất bất đồng và báo cáo Cohen kappa trước khi chốt bộ chuẩn. Hiện công cụ lưu một nhãn cuối cùng/mẫu; '
        'chưa có số liệu đồng thuận giữa người gán nhãn.',
        'Công cụ hỗ trợ gợi ý bằng dangvansam/vietnamese-toxicity, revision bac60f3e162d3a06003bf561a9f8365982ccc67a, '
        'chạy ONNX trên CPU tại máy người dùng, không gửi bình luận tới dịch vụ ngoài. Đầu vào giữ văn bản gốc, chỉ chuẩn hóa NFC/khoảng trắng. '
        'Điểm toxic là sigmoid chưa hiệu chỉnh trên PTIT, không phải độ chính xác. Điểm ≤ 0,2 gợi ý non-toxic; ≥ 0,8 gợi ý toxic; '
        'ở giữa hoặc văn bản vượt 512 token kể cả token đặc biệt thì không đề xuất nhãn. '
        '“Dùng gợi ý” chỉ điền lựa chọn; “Lưu đánh giá” mới xác nhận sau khi đọc. Mô hình nền ViSoBERT được công bố cho mục đích nghiên cứu.',
        'Chế độ “Làm sạch & gán nhãn toàn bộ” gán nhãn máy trực tiếp cho mọi mẫu sạch chưa có nhãn: điểm toxic ≥ 0,5 là toxic, còn lại là non-toxic. '
        'Giữ nhãn người đọc đã lưu. Mẫu có điểm giữa 0,2–0,8 hoặc bị cắt do quá dài vẫn có nhãn máy và cờ needs_review; '
        'mẫu trùng/rỗng/bị loại/chưa mở hết nội dung không vào dataset. Lưu nguồn automatic, mô hình, revision, điểm và ngưỡng; '
        'dataset_auto.csv/json và /api/dataset-auto.csv/json chứa các mẫu sạch đã có nhãn, gồm cả nhãn máy.',
        'Gợi ý, điểm, model/revision và dấu vân tay văn bản được lưu tách khỏi nhãn xác nhận. '
        'data/workspace.json là kho chính, ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử; '
        'annotations.json/imported.json cũ chỉ dùng làm nguồn chuyển đổi khi chưa có workspace. '
        'Nhãn có dấu vân tay không còn khớp nội dung phải được duyệt lại. '
        'Bản xuất /api/dataset.csv và /api/dataset.json chỉ chứa mẫu ready có nhãn xác nhận/nhập từ người gán, không chứa gợi ý chưa duyệt.',
        '\n### 3.3. Thiết kế đánh giá',
        'Chia theo nhóm bài viết độc lập, mục tiêu khoảng 60% train / 20% validation / 20% test theo số nhóm '
        '(tỷ lệ bình luận thực tế có thể khác). Các bài chứa bình luận trùng được nối cùng nhóm. '
        'Không có bài hoặc văn bản chuẩn hóa trùng giữa các tập. Seed 42; seed 43 cho validation. '
        'Chọn lần chia đầu tiên mà cả hai lớp xuất hiện trong mỗi tập; không chọn theo điểm mô hình. '
        'Tối thiểu 10 mẫu mỗi lớp và 5 nhóm độc lập chỉ là điều kiện chạy kỹ thuật; cần nhiều dữ liệu hơn cho kết luận đáng tin cậy.',
        'Bốn baseline dùng cùng các tập chia: BoW+NB, BoW+SVM, TF-IDF+NB, TF-IDF+SVM; TextCNN dùng cùng tập. '
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
                  f'Phân chia thực tế: {json.dumps(result["split"], ensure_ascii=False)}.',
                  '| Cấu hình | Val macro-F1 | Accuracy | Precision toxic | Recall toxic | F1 toxic | Macro-F1 | Giây |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for model in result['models']:
            m = model['test']
            lines.append(f'| {model["name"]} | {model["validation"]["f1_macro"]:.4f} | {m["accuracy"]:.4f} | {m["precision"]:.4f} | {m["recall"]:.4f} | {m["f1"]:.4f} | {m["f1_macro"]:.4f} | {model["seconds"]:.3f} |')
        lines += [f'Mô hình được chọn theo validation: **{result["selected_model"]}**. TextCNN lấy epoch {result["cnn_best_epoch"]}.']
        for feature in ('BoW', 'TF-IDF'):
            subset = [m for m in result['models'] if m['feature'] == feature]
            delta = subset[1]['test']['f1_macro'] - subset[0]['test']['f1_macro']
            lines.append(f'Với {feature}, chênh lệch test macro-F1 của SVM so với NB là {delta:+.4f}.')
        for algorithm in ('NB', 'SVM'):
            subset = [m for m in result['models'] if m['algorithm'] == algorithm]
            delta = subset[1]['test']['f1_macro'] - subset[0]['test']['f1_macro']
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
              'mỉa mai và hội thoại cần ngữ cảnh, ảnh/sticker bị bỏ qua, token hóa âm tiết, TextCNN cắt ở 128 token. '
              'Cần tăng số nhóm/bài và nhãn được kiểm tra chéo; mở rộng đánh giá sang dữ liệu ở thời điểm khác. '
              'Tránh điều chỉnh lặp lại dựa trên test. Bản gốc vẫn có thể chứa thông tin cá nhân; '
              'ẩn tên và định danh trước khi chia sẻ corpus, không chia sẻ chrome-profile.',
              '\n## Tài liệu tham khảo',
              '1. Scikit-learn: https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction',
              '2. Naive Bayes: https://scikit-learn.org/stable/modules/naive_bayes.html',
              '3. LinearSVC: https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html',
              '4. GroupShuffleSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html',
              '5. Kim, Y. (2014). Convolutional Neural Networks for Sentence Classification. EMNLP. https://aclanthology.org/D14-1181/',
              '6. PyTorch: https://docs.pytorch.org/docs/stable/nn.html',
              '7. Selenium: https://www.selenium.dev/documentation/webdriver/',
              '8. Model gợi ý: [dangvansam/vietnamese-toxicity](https://huggingface.co/dangvansam/vietnamese-toxicity), revision bac60f3e162d3a06003bf561a9f8365982ccc67a.',
              '9. Nguyen et al. (2023), [ViSoBERT](https://aclanthology.org/2023.emnlp-main.315/); [model card và phạm vi nghiên cứu](https://huggingface.co/uitnlp/visobert).']
    report = ''
    for index, line in enumerate(lines):
        separator = '\n' if index and line.startswith('|') and lines[index - 1].startswith('|') else '\n\n'
        report += (separator if index else '') + line
    return report + '\n'
