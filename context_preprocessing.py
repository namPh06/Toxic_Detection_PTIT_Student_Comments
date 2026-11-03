"""Conservative, offline preprocessing of post/parent/target context.

Run: .venv/Scripts/python.exe context_preprocessing.py
This produces a separate artifact and never changes corpus labels or deployed models.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from dataset import atomic_json, row_id, text_hash

VERSION = 'ptit-context-preserve-v1-20261101'


def normalize(text):
    """Keep case, negation, stop words, profanity, punctuation and emoji joins."""
    text = unicodedata.normalize('NFC', str(text or ''))
    # Remove transport artifacts, but preserve U+200D (emoji ZWJ) and variation selectors.
    text = text.replace('\ufeff', '').replace('\u200b', '')
    return re.sub(r'\s+', ' ', text).strip()


@lru_cache(maxsize=20000)
def segment(text):
    from pyvi import ViTokenizer
    # Segment word spans only. Pyvi never receives punctuation/emoticon/emoji spans.
    return re.sub(r'\w+(?:[ \t]+\w+)*',
                  lambda m: ViTokenizer.tokenize(m.group()), text)


def field(text):
    normalized = normalize(text)
    segmented = segment(normalized) if normalized else ''
    return dict(text_raw=str(text or ''), text_normalized=normalized,
                text_word=segmented, word_tokens=re.findall(r'\w+|[^\w\s]+', segmented))


def prepare_row(row):
    context = row.get('context', {})
    post = field(context.get('post_text', ''))
    parents = [dict(comment_id=str(p['comment_id']), **field(p.get('text_raw', '')),
                    text_complete=p.get('text_complete')) for p in context.get('parents', [])]
    target = field(row.get('text_raw', ''))
    gaps, warnings = [], []
    if not post['text_normalized']:
        gaps.append('post_text_unavailable')
    if context.get('post_text_complete') is False:
        gaps.append('post_text_incomplete')
    parent_status = context.get('parent_status', 'unknown')
    if parent_status not in ('available', 'no_parent'):
        gaps.append('parent_' + parent_status)
    if context.get('parent_chain_verified') is False:
        gaps.append('parent_ancestors_unverified')
    if any(p['text_complete'] is False for p in parents):
        gaps.append('parent_text_incomplete')
    if row.get('text_complete') is False:
        warnings.append('target_text_incomplete')
    elif row.get('text_complete') is not True:
        warnings.append('target_completeness_unknown')
    if row.get('comment_filter', 'unknown') == 'unknown':
        warnings.append('comment_filter_unknown')
    if any(p['text_complete'] is None for p in parents):
        warnings.append('parent_completeness_unknown')
    if not target['text_normalized']:
        warnings.append('empty_target')
    # Structured fields are the authoritative model input; labels never enter this object.
    fields = dict(post=post, parents=parents, target=target)
    sections = ['[BAI_VIET]\n' + (post['text_normalized'] or '[THIEU_VAN_BAN]')]
    sections += [f'[BINH_LUAN_CHA {i}]\n' + (p['text_normalized'] or '[KHONG_CO_VAN_BAN]')
                 for i, p in enumerate(parents, 1)]
    sections.append('[BINH_LUAN_CAN_XET]\n' + target['text_normalized'])
    model_text = '\n\n'.join(sections)
    result = dict(id=row_id(row), post_id=str(row['post_id']), comment_id=str(row['comment_id']),
                  canonical_post_id=str(context.get('canonical_post_id') or row['post_id']),
                  text_hash=text_hash(row.get('text_raw', '')),
                  context_source_hash=context.get('context_hash'), fields=fields,
                  model_text=model_text, context_gaps=gaps, source_warnings=warnings,
                  target_usable=bool(target['text_normalized']) and row.get('text_complete') is not False,
                  target_text_group=text_hash(target['text_normalized'].casefold()))
    result['model_input_hash'] = text_hash(json.dumps(fields, ensure_ascii=False, sort_keys=True))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/progress_with_context.json'))
    parser.add_argument('--reference', type=Path,
                        default=Path('data/manual_review/canonical_development_v32_20261031.json'))
    parser.add_argument('--output', type=Path, default=Path('outputs/context_preprocessing_20261101'))
    args = parser.parse_args()
    # All generated artifacts stay outside production data and require a fresh directory.
    out = args.output.resolve()
    if out == Path('data').resolve() or Path('data').resolve() in out.parents:
        parser.error('Output must be outside data/')
    protected = [args.source, args.reference, Path('data/progress.json'), Path('data/workspace.json')]
    contents = {p: p.read_bytes() for p in protected}
    source = json.loads(contents[args.source].decode('utf-8-sig'))
    reference = json.loads(contents[args.reference].decode('utf-8-sig'))
    references = {}
    for r in reference['rows']:
        if r['id'] in references or not r.get('human_verified'):
            raise ValueError('Reference labels must be unique and human confirmed')
        if r.get('reference_label') not in ('toxic', 'non-toxic'):
            raise ValueError('Invalid reference label')
        references[r['id']] = r
    prepared = [prepare_row(r) for r in source['rows']]
    if len({r['id'] for r in prepared}) != len(prepared):
        raise ValueError('Duplicate post/comment identity')
    matched = set()
    for r in prepared:
        ref = references.get(r['id'])
        if ref:
            if ref['text_hash'] != r['text_hash']:
                raise ValueError('Reference text changed')
            r['supervision'] = dict(label=ref['reference_label'], human_verified=True,
                                    scope='development', source=str(args.reference),
                                    policy_version=reference['policy_version'])
            matched.add(r['id'])
        else:
            r['supervision'] = None
    if matched != set(references):
        raise ValueError('Some reference comments are missing from the context source')
    summary = dict(rows=len(prepared), canonical_post_groups=len({r['canonical_post_id'] for r in prepared}),
                   rows_with_post_text=sum(bool(r['fields']['post']['text_normalized']) for r in prepared),
                   rows_with_parent=sum(bool(r['fields']['parents']) for r in prepared),
                   rows_with_context_gaps=sum(bool(r['context_gaps']) for r in prepared),
                   context_gaps=dict(Counter(g for r in prepared for g in r['context_gaps'])),
                   source_warnings=dict(Counter(g for r in prepared for g in r['source_warnings'])),
                   target_usable=sum(r['target_usable'] for r in prepared),
                   human_development_labels=dict(Counter(r['supervision']['label'] for r in prepared if r['supervision'])),
                   labels_changed=False, model_trained=False)
    manifest = dict(version=VERSION, pyvi_version=version('pyvi'), summary=summary,
                    input_hashes={str(p): hashlib.sha256(b).hexdigest() for p, b in contents.items()},
                    settings=dict(remove_stopwords=False, expand_teencode=False,
                                  preserve_punctuation=True, preserve_emoji_zwj=True,
                                  truncate=False, deduplicate=False),
                    limitations=['Media text has not been transcribed.',
                                 'No recorded parent ID does not prove the comment has no conversational context.',
                                 'No context gaps does not guarantee complete context or a correct label.',
                                 'Word segmentation does not infer sarcasm, friendship or toxicity.',
                                 'human development labels are not an independent blind test.'])
    if any(p.read_bytes() != content for p, content in contents.items()):
        raise RuntimeError('An input changed during preprocessing')
    out.mkdir(parents=True, exist_ok=False)
    atomic_json(out / 'dataset.json', dict(preprocess_version=VERSION, rows=prepared))
    atomic_json(out / 'manifest.json', manifest)
    atomic_json(out / 'context_gaps.json', dict(rows=[dict(id=r['id'], post_id=r['post_id'],
                comment_id=r['comment_id'], comment=r['fields']['target']['text_raw'],
                context_gaps=r['context_gaps']) for r in prepared if r['context_gaps']]))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
