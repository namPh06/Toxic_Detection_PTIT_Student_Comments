"""Read-only visualization of the artifacts used by a prediction."""
import json
from dataset import PREPROCESS_VERSION, word_tokens


def build_trace(text, directory, answer):
    metadata = json.loads((directory / 'metrics.json').read_text(encoding='utf-8'))
    name = answer['model']
    entry = next(m for m in metadata['models'] if m['name'] == name)
    artifact = entry.get('artifact') or {}
    stages = [dict(title='Bình luận gốc', content=text)]
    features = []
    warning = ''
    if metadata.get('preprocess_version') != PREPROCESS_VERSION:
        warning = 'Phiên bản chuẩn hóa của run khác phiên bản hiện tại; nên huấn luyện lại trước khi báo cáo.'
    if name == 'ViSoBERT':
        from transformer_model import normalize_input
        from transformers import AutoTokenizer
        folder = directory / 'ViSoBERT'
        config = json.loads((folder / 'training.json').read_text(encoding='utf-8'))['config']
        tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
        normalized = normalize_input(text)
        ids = tokenizer(normalized, truncation=True, max_length=config['max_length'])['input_ids']
        stages += [dict(title='Chuẩn hóa Unicode', content=normalized),
                   dict(title='Tokenizer ViSoBERT', content=json.dumps(dict(tokens=tokenizer.convert_ids_to_tokens(ids), ids=ids), ensure_ascii=False)),
                   dict(title='Encoder và đầu phân loại', content='Dùng trọng số ViSoBERT đã lưu. Không suy diễn mức đóng góp của từng token.')]
    else:
        cleaned = answer['text_clean']
        tokens = word_tokens(cleaned)
        stages += [dict(title='Làm sạch và chuẩn hóa', content=cleaned),
                   dict(title='Tách từ Underthesea', content=' | '.join(tokens))]
        import joblib
        model = joblib.load(directory / artifact.get('file', f'{name}.joblib'))
        pipeline = getattr(model, 'estimator', model)
        vectorizer = pipeline.named_steps['vectorizer']
        vector = vectorizer.transform([cleaned]).tocsr()
        names = vectorizer.get_feature_names_out()
        features = sorted([dict(term=str(names[i]), value=float(v)) for i, v in zip(vector.indices, vector.data)], key=lambda f: abs(f['value']), reverse=True)[:20]
        stages.append(dict(title='Đặc trưng ' + ('TF-IDF' if 'TF-IDF' in name else 'BoW'), content=f'{vector.shape[1]} chiều; {vector.nnz} đặc trưng khác 0. Giá trị bên dưới là trọng số đầu vào, không phải độ độc hại.\n' + '\n'.join(f"{f['term']}: {f['value']:.5g}" for f in features)))
    score = answer.get('score')
    detail = f'Mô hình: {name}'
    if score is not None:
        detail += f"\nĐiểm đầu ra: {score:.6g}\nNgưỡng: {answer['threshold']:.6g}\nĐiểm >= ngưỡng → toxic. Điểm này không phải độ chính xác của nhãn."
    else:
        detail += '\nArtifact cũ: dùng quyết định predict của mô hình đã lưu.'
    stages += [dict(title='Quyết định của mô hình', content=detail), dict(title='Kết luận', content=answer['label'].upper() + '\nKết quả tự động có thể sai; đây là minh họa đường dự đoán, không phải nhãn chuẩn.')]
    return dict(run=metadata.get('created_at', directory.name), model=name, preprocess_version=metadata.get('preprocess_version'), warning=warning, stages=stages, features=features)
