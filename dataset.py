"""Non-destructive preparation and human annotations for the PTIT corpus."""
import csv
import hashlib
import html
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from threading import RLock

LABELS = ('non-toxic', 'toxic')
LABEL_METADATA = ('model_score', 'label_model', 'label_revision', 'label_threshold', 'needs_review', 'review_reason')
# Keep function words that express permission, negation or relations in a comment.
STOP_WORDS = frozenset('các những'.split())
TEENCODE = {'ko': 'không', 'khum': 'không', 'hong': 'không',
            'hok': 'không', 'dc': 'được', 'đc': 'được', 'mn': 'mọi người',
            'mik': 'mình', 'mk': 'mình', 'bn': 'bạn', 'ntn': 'như thế nào'}
UI_ONLY = re.compile(r'^(?:thích|like|trả lời|reply|xem bản dịch|see translation|'
                     r'\d+\s*(?:phút|giờ|ngày|tuần|tháng|năm)(?: trước)?)$', re.I)
PREPROCESS_VERSION = 'ptit-v4-canonical-normalization'
TOKENIZER_VERSION = 'underthesea-9.5.0-word-v1'
MONEY_PATTERN = r'\d+(?:[.,]\d+)?(?:[-–—]\d+(?:[.,]\d+)?)?k'
MONEY_INPUT = re.compile(r'(?<!\w)(\d+(?:[.,]\d+)?(?:\s*[-–—]\s*\d+(?:[.,]\d+)?)?)\s*k\b')
EMOTICON = re.compile(r'[:;=]-?\)+|[:;=]-?\(+')
EMOJI_UNIT = r'[\u2600-\u27bf\U0001f000-\U0001faff][\ufe0e\ufe0f]?[\U0001f3fb-\U0001f3ff]?'
EMOJI_PATTERN = rf'(?:[\U0001f1e6-\U0001f1ff]{{2}}|{EMOJI_UNIT}(?:\u200d{EMOJI_UNIT})*)'
# Keep J-prefixed names/codes intact so a later pass cannot expand J-Hope to gì hope.
TOKEN_PATTERN = re.compile(rf'{EMOJI_PATTERN}|{MONEY_PATTERN}|\bj[.-]\w+(?:[.-]\w+)*\b|\w+|[^\w\s]')
PROTECTED_WORDS = re.compile(rf'\b(?:urltoken|emailtoken|phonetoken|emoticon_smile|emoticon_sad)\b|(?<!\w){MONEY_PATTERN}\b|{EMOJI_PATTERN}')
WORD_TOKENIZER_LOCK = RLock()
CONTEXT_NORMALIZATIONS = (
    (re.compile(r'\b(làm|nói|cái|kiểu|biết|còn|chắc)\s+j(?!\w|[.-]\w)'), r'\1 gì'),
    (re.compile(r'\b(đi|vừa)\s+hc(?!\w|[.-]\w)'), r'\1 học'),
    (re.compile(r'\bhc\s+(lại|phí|quân\s+sự)\b'), r'học \1'),
)
MASKED_CU = re.compile(r'(?<![\w./])c[ \t]*[.*_][ \t]*u(?!\w|[./]\w)')
REPEATED_LETTER = re.compile(r'([^\W\d_])\1{2,}')
# Reviewed words only: a global repeat replacement would corrupt account names.
ELONGATED_WORDS = frozenset('gấp vậy ngon chịu không kìa rồi tui đi tao ơi cái lắm nha đấy'.split())


@lru_cache(maxsize=8192)
def _word_tokens(text):
    from underthesea import word_tokenize

    tokens = []

    def segment(value):
        if value.strip():
            tokens.extend(word.replace(' ', '_') for word in
                          word_tokenize(value, use_token_normalize=False) if word.strip())

    # Underthesea can split joined emoji and money. Preserve these established
    # cleaning markers while segmenting all surrounding Vietnamese text.
    with WORD_TOKENIZER_LOCK:
        start = 0
        for match in PROTECTED_WORDS.finditer(text):
            segment(text[start:match.start()])
            tokens.append(match[0])
            start = match.end()
        segment(text[start:])
    return tuple(tokens)


def word_tokens(text):
    """Shared word units for features, TextCNN and inference; no fallback splitter."""
    if not text or not text.strip():
        return []
    return list(_word_tokens(text))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def row_id(row):
    key = json.dumps([str(row.get('post_id', '')), str(row.get('comment_id', ''))], ensure_ascii=False)
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def text_hash(value):
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()


def normalize_social_text(text):
    text = MASKED_CU.sub('cu', text)

    def shorten(match):
        token = match[0]
        candidate = REPEATED_LETTER.sub(r'\1', token)
        if candidate != token and candidate in ELONGATED_WORDS:
            return candidate
        return token

    return re.sub(r'\w+', shorten, text)


def clean_text(value):
    text = unicodedata.normalize('NFC', html.unescape(str(value or ''))).lower()
    text = re.sub(r'<(?:/?(?:div|span|p|br|a|b|i|strong))\b[^>]*>', ' ', text)
    text = re.sub(r'[\u200b\u200c\ufeff]', '', text)
    # Remove hidden joiners inside words, but preserve joined emoji such as 👩‍💻.
    text = re.sub(r'(?<=\w)\u200d|\u200d(?=\w)', '', text)
    text = re.sub(r'(?:https?://|www\.)\S+', ' urltoken ', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', ' emailtoken ', text)
    text = re.sub(r'(?<!\w)(?:\+84|0)(?:[ .-]?\d){9,10}(?!\w)', ' phonetoken ', text)
    text = MONEY_INPUT.sub(lambda m: re.sub(r'\s+', '', m[1]).replace('–', '-').replace('—', '-') + 'k', text)
    text = EMOTICON.sub(lambda m: ' emoticon_smile ' if m[0].endswith(')') else ' emoticon_sad ', text)
    text = normalize_social_text(text)
    tokens = TOKEN_PATTERN.findall(text)
    # Keep negation, accents, profanity and emoji: they can change the target label.
    tokens = [expanded for t in tokens for expanded in TEENCODE.get(t, t).split()
              if expanded not in STOP_WORDS and not all(unicodedata.category(c)[0] == 'P' or
                                                       unicodedata.category(c) == 'Cf' for c in expanded)]
    # A leftover symbol such as '=' is not a meaningful comment on its own.
    if not any(re.search(r'\w', t) or re.fullmatch(EMOJI_PATTERN, t) for t in tokens):
        return ''
    text = ' '.join(tokens).strip()
    # Apply phrase rules after shortening and punctuation removal, in the same pass.
    for pattern, replacement in CONTEXT_NORMALIZATIONS:
        text = pattern.sub(replacement, text)
    return text


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
        for key in LABEL_METADATA:
            row[key] = (annotation.get(key) if annotation else row.get(key)) if row['label_source'] == 'automatic' else None
        row['annotation_note'] = annotation.get('note', row.get('annotation_note', ''))
        row['excluded'] = annotation.get('excluded', row.get('excluded', False))
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
            keeper = next((r for r in duplicates if r['label']), duplicates[0])
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
    tokenized = [word_tokens(r['text_clean']) for r in usable]
    terms = Counter(t for tokens in tokenized for t in tokens if len(t) > 1)
    lengths = [len(tokens) for tokens in tokenized]
    return dict(total=len(rows), usable=len(usable), quality=dict(quality), labels=dict(labels),
                labeled=sum(labels[x] for x in LABELS), label_sources=dict(sources), posts=len({r.get('post_id') for r in rows}),
                avg_tokens=round(sum(lengths) / max(1, len(lengths)), 1),
                top_terms=terms.most_common(12), preprocess_version=PREPROCESS_VERSION,
                tokenizer='Underthesea', tokenizer_version=TOKENIZER_VERSION)


def fingerprint(rows):
    relevant = [(r['id'], r['text_clean'], r['label'], r['quality'], r.get('label_source', '')) for r in rows]
    return hashlib.sha256(json.dumps(sorted(relevant), ensure_ascii=False).encode()).hexdigest()


def csv_bytes(rows):
    output = io.StringIO(newline='')
    columns = ['id', 'post_id', 'comment_id', 'post_url', 'parent_comment_id', 'text_raw', 'text_clean',
               'text_hash', 'label', 'label_source', 'quality', 'excluded', 'text_complete',
               'annotation_stale', 'previous_label', 'annotation_note', 'identifier_quality',
               'collection_method', 'collected_at', *LABEL_METADATA]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
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
            raise ValueError(f'Dòng {index + 1}: nguồn nhãn chưa được duyệt; không nhập nhãn tự động thành nhãn chuẩn.')
        automatic = label and row.get('label_source') == 'automatic'
        label_metadata = {}
        if automatic:
            if row.get('text_hash') != text_hash(row['text_raw']):
                raise ValueError(f'Dòng {index + 1}: nhãn tự động phải có hash đúng với nội dung.')
            for name in ('model_score', 'label_threshold'):
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
