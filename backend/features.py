"""Train-only text features shared by the inspection page and experiments."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from backend.dataset import LABELS, PREPROCESS_VERSION, TOKENIZER_VERSION, fingerprint, input_fingerprint, word_tokens


def validate_settings(settings):
    methods = settings.get('methods', ['BoW', 'TF-IDF'])
    ngram = settings.get('ngram', 'both')
    maximum = settings.get('max_features', 20000)
    if (not isinstance(methods, list) or not methods or
            any(method not in ('BoW', 'TF-IDF') for method in methods) or len(set(methods)) != len(methods)):
        raise ValueError('Chọn ít nhất một phương pháp: BoW hoặc TF-IDF.')
    if ngram not in ('unigram', 'bigram', 'both'):
        raise ValueError('Chọn unigram, bigram hoặc kết hợp cả hai.')
    if type(maximum) is not int or not 1 <= maximum <= 100000:
        raise ValueError('Số đặc trưng tối đa phải là số nguyên từ 1 đến 100.000.')
    return dict(methods=[name for name in ('BoW', 'TF-IDF') if name in methods], ngram=ngram, max_features=maximum,
                char_features=False)


def feature_key(rows):
    # Post membership affects the split even when comment text/labels stay the same.
    content = ['word-features-only-v1', PREPROCESS_VERSION, TOKENIZER_VERSION, fingerprint(rows), input_fingerprint(rows),
               sorted((r['id'], str(r['post_id']), str(r.get('split_group', ''))) for r in rows)]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()


def build_features(rows, settings, notify=lambda message: None):
    from backend.experiments import split_dataset
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

    settings = validate_settings(settings)
    eligible, split, groups = split_dataset(rows)
    texts = {name: [eligible[i]['text_clean'] for i in ids] for name, ids in split.items()}
    labels = {name: [LABELS.index(eligible[i]['label']) for i in ids] for name, ids in split.items()}
    ngrams = {'unigram': (1, 1), 'bigram': (2, 2), 'both': (1, 2)}[settings['ngram']]
    features = {}
    for name in settings['methods']:
        vectorizer = (CountVectorizer if name == 'BoW' else TfidfVectorizer)(
            tokenizer=word_tokens, token_pattern=None, lowercase=False,
            ngram_range=ngrams, max_features=settings['max_features'])
        try:
            matrices = {'train': vectorizer.fit_transform(texts['train'])}
        except ValueError as error:
            raise ValueError('Không tạo được từ vựng. Thử unigram hoặc kết hợp cả hai; kiểm tra nội dung tập train.') from error
        matrices.update({part: vectorizer.transform(texts[part]) for part in ('validation', 'test')})
        features[name] = dict(vectorizer=vectorizer, matrices=matrices)
    return dict(schema_version=1, created_at=datetime.now(timezone.utc).isoformat(), key=feature_key(rows),
                fingerprint=fingerprint(rows), preprocess_version=PREPROCESS_VERSION, settings=settings,
                tokenizer='Underthesea', tokenizer_version=TOKENIZER_VERSION,
                rows=eligible, split=split, groups=groups, texts=texts, labels=labels, features=features)


def feature_summary(bundle):
    return dict(created_at=bundle['created_at'], settings=validate_settings(bundle['settings']),
                tokenizer=bundle.get('tokenizer', 'Khoảng trắng'), tokenizer_version=bundle.get('tokenizer_version'),
                split={name: dict(count=len(ids), labels=dict(Counter(bundle['rows'][i]['label'] for i in ids)),
                                      groups=len({bundle['groups'][i] for i in ids}))
                       for name, ids in bundle['split'].items()},
                methods={name: dict(dimensions=item['matrices']['train'].shape[1],
                                    matrices={part: list(matrix.shape) for part, matrix in item['matrices'].items()})
                         for name, item in bundle['features'].items()})


def preview_features(bundle, index=0, split='all'):
    if split not in ('all', 'train', 'validation', 'test') or type(index) is not int or index < 0:
        raise ValueError('Tập dữ liệu hoặc số thứ tự bình luận không hợp lệ.')
    positions = [(part, local, global_index) for part, ids in bundle['split'].items()
                 if split == 'all' or part == split for local, global_index in enumerate(ids)]
    index = min(index, len(positions) - 1)
    part, local, global_index = positions[index]
    row = bundle['rows'][global_index]
    terms = {}
    for name, item in bundle['features'].items():
        names = item['vectorizer'].get_feature_names_out()
        vector = item['matrices'][part].getrow(local)
        for column, value in zip(vector.indices, vector.data):
            term = names[column]
            terms.setdefault(term, dict(term=term, bow=None, tfidf=None))[
                'bow' if name == 'BoW' else 'tfidf'] = int(value) if name == 'BoW' else float(value)
    return dict(index=index, total=len(positions), split=part, text_clean=row['text_clean'],
                tokens=word_tokens(row['text_clean']),
                label=row['label'], id=row['id'], terms=[terms[key] for key in sorted(terms)[:200]],
                term_count=len(terms), created_at=bundle['created_at'])
