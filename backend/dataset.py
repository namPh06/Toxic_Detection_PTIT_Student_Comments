"""Non-destructive preparation and human annotations for the PTIT corpus."""
import csv
import hashlib
import html
import io
import json
import re
import tempfile
import time
from pathlib import Path
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache

LABELS = ('non-toxic', 'toxic')
LABEL_METADATA = ('model_score', 'label_model', 'label_revision', 'label_threshold', 'needs_review', 'review_reason')
STOP_WORDS = frozenset(('các', 'những'))
TEENCODE = {'ko': 'không', 'khum': 'không', 'hong': 'không',
            'hok': 'không', 'đc': 'được', 'mn': 'mọi người',
            'mik': 'mình', 'ntn': 'như thế nào', 'khg': 'không', 'k0': 'không'}
UI_ONLY = re.compile(r'^(?:thích|like|trả lời|reply|xem bản dịch|see translation|'
                     r'\d+\s*(?:phút|giờ|ngày|tuần|tháng|năm)(?: trước)?)$', re.I)
PREPROCESS_VERSION = 'ptit-v4-contextual-dc-20261105'
TOKENIZER_VERSION = 'underthesea-9.5.0-v1'


def word_tokens(text):
    """Segment cleaned Vietnamese text consistently for all model features."""
    return list(_word_tokens_cached(text))


@lru_cache(maxsize=20000)
def _word_tokens_cached(text):
    from underthesea import word_tokenize

    return tuple(word_tokenize(text, format='text').split())


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Separate writers must never share a temporary file. Windows readers may
    # briefly deny replacement; retry without removing the last valid dataset.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
        temp = path.parent / Path(handle.name).name
        try:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        except BaseException:
            handle.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        for attempt in range(8):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(0.05 * 2 ** attempt, 0.5))
    finally:
        temp.unlink(missing_ok=True)


def row_id(row):
    key = json.dumps([str(row.get('post_id', '')), str(row.get('comment_id', ''))], ensure_ascii=False)
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def text_hash(value):
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()


def input_fingerprint(rows):
    """Bind raw model inputs too: transformer input preserves punctuation."""
    return text_hash(json.dumps(sorted((r['id'], r.get('text_raw', '')) for r in rows), ensure_ascii=False))


def normalize_teencode(value):
    """A separate view, never overwrite raw input; leave unknown meanings intact."""
    text = unicodedata.normalize('NFC', str(value or ''))
    # Narrow local cues only. In particular m is never inferred as mình/mày.
    patterns = (
        (r'\b(?P<prefix>quên\s+)mk(?=\s+(?:đăng nhập|tài khoản)\b)', r'\g<prefix>mật khẩu'),
        (r'\bmk(?=\s+(?:đang học|đi học)\b)', 'mình'),
        (r'\bbn(?=\s+(?:tiền|tín chỉ)\b)', 'bao nhiêu'),
        (r'\bbn(?=\s+có đi học\b)', 'bạn'),
        (r'\b(?P<prefix>làm\s+)dc(?=\s+bài\b)', r'\g<prefix>được'),
        (r'\b(?P<prefix>(?:xin|tìm)\s+)dc(?=\s+việc\b)', r'\g<prefix>được'),
        (r'\b(?P<prefix>(?:đổi|học|thi|đăng ký|đăng kí|nhận|vào|ra)\s+)dc(?=\s|[?.!,]|$)', r'\g<prefix>được'),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return re.sub(r'\b\w+\b', lambda m: TEENCODE.get(m[0].lower(), m[0]), text)


def clean_text(value, *, remove_stopwords=True):
    text = normalize_teencode(html.unescape(str(value or ''))).lower()
    text = re.sub(r'<(?:/?(?:div|span|p|br|a|b|i|strong))\b[^>]*>', ' ', text)
    text = re.sub(r'[\u200b\u200c\ufeff]', '', text)
    text = re.sub(r'(?<=\w)\u200d(?=\w)', '', text)
    text = re.sub(r'(?:https?://|www\.)\S+', ' urltoken ', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', ' emailtoken ', text)
    text = re.sub(r'(?<!\w)(?:\+84|0)(?:[ .-]?\d){9,10}(?!\w)', ' phonetoken ', text)
    # Keep ambiguous standalone k; only attach it to an explicit amount.
    text = re.sub(r'(?<=\d)\s+k\b', 'k', text)
    text = re.sub(r'[:=]-?\){2,}', ' emoticon_smile ', text)
    text = re.sub(r'[:=]-?\({2,}', ' emoticon_sad ', text)
    # Preserve emoji modifiers, variation selectors and joined emoji sequences.
    modifier = r'[\ufe0e\ufe0f\U0001f3fb-\U0001f3ff]?'
    tokens = re.findall(r'[0-9#*]\ufe0f?\u20e3|[\U0001f1e6-\U0001f1ff]{2}|\w+(?:\+\+|#)?|'
                        rf'[^\w\s\u200d]{modifier}(?:\u200d[^\w\s]{modifier})*', text)
    # Keep negation, accents, profanity and emoji: they can change the target label.
    tokens = [expanded for t in tokens for expanded in TEENCODE.get(t, t).split()
              if (not remove_stopwords or expanded not in STOP_WORDS) and not all(unicodedata.category(c).startswith('P') for c in expanded)]
    return ' '.join(tokens).strip()


def prepare(rows, annotations=None):
    annotations = annotations or {}
    prepared = []
    by_text = defaultdict(list)
    for original in rows:
        row = dict(original)
        row.pop('duplicate_of', None)
        row['id'] = row_id(row)
        row['text_hash'] = text_hash(row.get('text_raw', ''))
        annotation = annotations.get(row['id'], {})
        raw_label = row.get('label', '')
        row['label'] = annotation.get('label', raw_label if raw_label in LABELS else '')
        row['annotation_stale'] = bool(annotation.get('text_hash') and annotation['text_hash'] != row['text_hash'])
        row.pop('previous_label', None)
        if row['annotation_stale']:
            row['previous_label'] = row['label']
            row['label'] = ''
        row['label_source'] = (annotation.get('label_source', 'manual') if annotation else row.get('label_source', 'legacy')) if row['label'] else ''
        row['label_policy_version'] = annotation.get('label_policy_version', row.get('label_policy_version', ''))
        row['human_verified'] = bool(annotation.get('human_verified', row.get('human_verified', False))) and not row['annotation_stale']
        for key in LABEL_METADATA:
            row[key] = (annotation.get(key) if annotation else row.get(key)) if row['label_source'] == 'automatic' else None
        row['annotation_note'] = annotation.get('note', row.get('annotation_note', ''))
        row['excluded'] = annotation.get('excluded', row.get('excluded', False))
        row['text_normalized'] = normalize_teencode(row.get('text_raw', ''))
        row['text_clean'] = clean_text(row.get('text_raw', ''))
        raw = str(row.get('text_raw', '')).strip()
        if row['excluded']:
            row['quality'] = 'excluded'
        elif row.get('text_complete') is False:
            row['quality'] = 'incomplete'
        elif not row['text_clean'] or UI_ONLY.fullmatch(raw):
            row['quality'] = 'empty_or_ui'
        else:
            row['quality'] = 'ready'
            by_text[row['text_clean']].append(row)
        prepared.append(row)
    for duplicates in by_text.values():
        labels = {r['label'] for r in duplicates if r['label']}
        if len(labels) > 1:
            for row in duplicates:
                row['quality'] = 'conflict'
        else:
            # Prefer the annotated copy; unlabelled duplicates never override a reviewed label.
            keeper = next((r for r in duplicates if r['label'] and r['human_verified']
                           and r['label_source'] == 'manual'),
                          next((r for r in duplicates if r['label']), duplicates[0]))
            for row in duplicates:
                if row is not keeper:
                    row['quality'] = 'duplicate'
                    row['duplicate_of'] = keeper['id']
    return prepared


def summary(rows):
    quality = Counter(r['quality'] for r in rows)
    usable = [r for r in rows if r['quality'] == 'ready']
    labels = Counter(r['label'] or 'unlabeled' for r in usable)
    sources = Counter(r['label_source'] for r in usable if r['label'] in LABELS)
    terms = Counter(t for r in usable for t in r['text_clean'].split() if len(t) > 1)
    lengths = [len(r['text_clean'].split()) for r in usable]
    return dict(total=len(rows), usable=len(usable), quality=dict(quality), labels=dict(labels),
                labeled=sum(labels[x] for x in LABELS), label_sources=dict(sources), posts=len({r.get('post_id') for r in rows}),
                avg_tokens=round(sum(lengths) / max(1, len(lengths)), 1),
                top_terms=terms.most_common(12), preprocess_version=PREPROCESS_VERSION)


def fingerprint(rows):
    relevant = [(r['id'], r['text_clean'], r['label'], r['quality'], r.get('label_source', '')) for r in rows]
    return hashlib.sha256(json.dumps(sorted(relevant), ensure_ascii=False).encode()).hexdigest()


def csv_bytes(rows):
    output = io.StringIO(newline='')
    columns = ['id', 'post_id', 'comment_id', 'post_url', 'parent_comment_id', 'text_raw', 'text_normalized', 'text_clean',
               'text_hash', 'label', 'label_source', 'quality', 'excluded', 'text_complete',
               'annotation_stale', 'previous_label', 'annotation_note', 'identifier_quality',
               'collection_method', 'collected_at', 'collection_filter', 'filter_policy_hash', 'filter_reason', 'filter_evidence', 'post_text_raw', 'parent_context', 'label_policy_version', 'human_verified', 'label_usable', 'label_approved', 'label_approval_method', *LABEL_METADATA]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        row = dict(row)
        for key in ('parent_context', 'filter_evidence'):
            if isinstance(row.get(key), (list, dict)):
                row[key] = json.dumps(row[key], ensure_ascii=False)
        safe = {k: ("'" + str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v)
                for k, v in row.items() if k in columns}
        writer.writerow(safe)
    return output.getvalue().encode('utf-8-sig')


def parse_import(content, filename):
    if not isinstance(content, str) or not isinstance(filename, str):
        raise ValueError('Tệp nhập không hợp lệ.')
    is_csv = filename.lower().endswith('.csv')
    if is_csv:
        rows = list(csv.DictReader(io.StringIO(content.lstrip('\ufeff'))))
    else:
        data = json.loads(content.lstrip('\ufeff'))
        rows = data.get('rows') if isinstance(data, dict) else data
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError('Tệp cần có từ 1 đến 10.000 dòng.')
    result = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get('text_raw'), str) or len(row['text_raw']) > 20000:
            raise ValueError(f'Dòng {index + 1}: cần text_raw là chuỗi, tối đa 20.000 ký tự.')
        # Undo only our CSV formula guard, proven by the original content hash.
        if is_csv and row['text_raw'].startswith("'") and text_hash(row['text_raw'][1:]) == row.get('text_hash'):
            row['text_raw'] = row['text_raw'][1:]
        label = str(row.get('label', '')).strip().lower()
        if label not in ('', *LABELS):
            raise ValueError(f'Dòng {index + 1}: label phải trống, toxic hoặc non-toxic.')
        if any(type(row.get(key)) not in (str, int) for key in ('post_id', 'comment_id')):
            raise ValueError(f'Dòng {index + 1}: post_id và comment_id phải là chuỗi hoặc số nguyên.')
        post = str(row['post_id']).strip()
        comment = str(row['comment_id']).strip()
        if not post or not comment or max(len(post), len(comment)) > 200:
            raise ValueError(f'Dòng {index + 1}: cần post_id và comment_id (tối đa 200 ký tự) để chia tập theo bài.')
        identity = (post, comment)
        if identity in seen:
            raise ValueError(f'Dòng {index + 1}: trùng post_id/comment_id trong tệp.')
        seen.add(identity)
        flags = {}
        for name in ('excluded', 'text_complete'):
            flag = row.get(name)
            if flag is None or flag == '':
                flags[name] = False if name == 'excluded' else None
            elif type(flag) is bool:
                flags[name] = flag
            elif is_csv and isinstance(flag, str) and flag.strip().lower() in ('true', 'false'):
                flags[name] = flag.strip().lower() == 'true'
            else:
                raise ValueError(f'Dòng {index + 1}: {name} phải là true/false hoặc để trống.')
        if label and row.get('label_source', '') not in ('', 'manual', 'imported', 'legacy', 'automatic'):
            raise ValueError(f'Dòng {index + 1}: nguồn nhãn không hợp lệ.')
        automatic = label and row.get('label_source') == 'automatic'
        label_metadata = {}
        if automatic:
            if row.get('text_hash') != text_hash(row['text_raw']):
                raise ValueError(f'Dòng {index + 1}: nhãn tự động phải có hash đúng với nội dung.')
            # Reconciled semantic decisions and SVM labels have no calibrated
            # probability. Preserve missing scores rather than inventing one.
            unscored = (row.get('model_score') in (None, '') and row.get('label_threshold') in (None, '')
                        and row.get('review_reason') in ('unverified_reconciled_proposal', 'unverified_text_only_fallback', 'unverified_collection_filter', 'unverified_v4_semantic'))
            for name in ('model_score', 'label_threshold'):
                if unscored:
                    label_metadata[name] = None
                    continue
                value = row.get(name)
                if is_csv:
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        raise ValueError(f'Dòng {index + 1}: thiếu {name} hợp lệ.')
                if type(value) not in (int, float) or not 0 <= value <= 1:
                    raise ValueError(f'Dòng {index + 1}: {name} phải từ 0 đến 1.')
                label_metadata[name] = value
            for name in ('label_model', 'label_revision', 'review_reason'):
                value = row.get(name, '')
                if not isinstance(value, str) or len(value) > 200 or (name != 'review_reason' and not value):
                    raise ValueError(f'Dòng {index + 1}: {name} không hợp lệ.')
                label_metadata[name] = value
            flag = row.get('needs_review')
            if is_csv and isinstance(flag, str) and flag.lower() in ('true', 'false'):
                flag = flag.lower() == 'true'
            if type(flag) is not bool:
                raise ValueError(f'Dòng {index + 1}: needs_review phải là true/false.')
            label_metadata['needs_review'] = flag
        note = row.get('annotation_note', '')
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError(f'Dòng {index + 1}: annotation_note phải là chuỗi, tối đa 2.000 ký tự.')
        metadata = {}
        for name, limit in (('post_url', 2000), ('parent_comment_id', 200), ('identifier_quality', 200),
                            ('collection_method', 200), ('collected_at', 200)):
            value = row.get(name, '')
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f'Dòng {index + 1}: {name} phải là chuỗi, tối đa {limit} ký tự.')
            metadata[name] = value
        metadata['collection_method'] = metadata['collection_method'] or 'import'
        metadata['collected_at'] = metadata['collected_at'] or datetime.now(timezone.utc).isoformat()
        result.append(dict(post_id=post, comment_id=comment, text_raw=row['text_raw'], label=label,
                           label_source=('automatic' if automatic else 'imported') if label else '', **flags,
                           annotation_note=note, **metadata, **label_metadata))
    return result
