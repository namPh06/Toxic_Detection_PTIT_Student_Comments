"""Join collected post context without changing comments or their labels."""
import argparse
import base64
import hashlib
import json
from collections import Counter
from pathlib import Path

from backend.dataset import atomic_json


def load_context(path):
    if not path.exists():
        return {}
    return {str(p['post_id']): p for p in json.loads(path.read_text(encoding='utf-8'))['posts']}


def enrich_posts(posts, contexts):
    return [dict(p, **{k: v for k, v in contexts.get(str(p['post_id']), {}).items()
                      if k not in ('post_id', 'url')}) for p in posts]


def canonical_post_id(post_id, rows):
    """Facebook opaque permalink aliases can share one underlying post ID."""
    ids = set()
    for row in rows:
        try:
            decoded = base64.b64decode(row['comment_id'], validate=True).decode()
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded.startswith('comment:') and '_' in decoded:
            value = decoded.split(':', 1)[1].split('_', 1)[0]
            if value.isdigit():
                ids.add(value)
    return next(iter(ids)) if len(ids) == 1 else str(post_id)


def build_context_rows(rows, posts, context_rows=()):
    index = {(str(r['post_id']), str(r['comment_id'])): r for r in context_rows
             if r.get('identity_verified')}
    index.update({(str(r['post_id']), str(r['comment_id'])): r for r in rows})
    post_index = {str(p['post_id']): p for p in posts}
    result = []
    for row in rows:
        pid = str(row['post_id'])
        post = post_index.get(pid, {})
        parents, seen, current = [], {str(row['comment_id'])}, row
        parent_chain_verified = True
        status = 'no_parent'
        while current.get('parent_comment_id'):
            parent_id = str(current['parent_comment_id'])
            if parent_id in seen:
                status = 'cycle'
                break
            seen.add(parent_id)
            parent = index.get((pid, parent_id))
            if parent is None:
                status = 'missing_parent'
                break
            parents.append(dict(comment_id=parent_id, text_raw=parent['text_raw'],
                                text_complete=parent.get('text_complete')))
            if parent.get('context_only'):
                parent_chain_verified = False
            if not parent['text_raw']:
                status = 'parent_without_text'
                break
            current, status = parent, 'available'
        text = post.get('post_text_raw', '')
        context = dict(post_text=text, post_text_available=bool(text),
                       post_status=post.get('status', 'not_collected'),
                       post_text_complete=post.get('text_complete'),
                       media_text_extracted=post.get('media_text_extracted', False),
                       parents=list(reversed(parents)), parent_status=status,
                       parent_chain_verified=parent_chain_verified,
                       canonical_post_id=post.get('canonical_post_id', pid),
                       collected_at=post.get('collected_at'))
        context['context_hash'] = hashlib.sha256(json.dumps(context, ensure_ascii=False,
                                                          sort_keys=True).encode()).hexdigest()
        result.append(dict(row, context=context))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/progress.json'))
    parser.add_argument('--context', type=Path, default=Path('data/post_context.json'))
    parser.add_argument('--parents', type=Path, default=Path('data/parent_context.json'))
    parser.add_argument('--output', type=Path, default=Path('data/progress_with_context.json'))
    args = parser.parse_args()
    protected = {args.source.resolve(), args.context.resolve(), args.parents.resolve(),
                 Path('data/workspace.json').resolve(), Path('data/annotations.json').resolve()}
    if args.output.resolve() in protected:
        parser.error('Output must be a separate file')
    source = args.source.read_bytes()
    data = json.loads(source.decode('utf-8-sig'))
    contexts = load_context(args.context)
    posts = enrich_posts(data['posts'], contexts)
    grouped = {}
    for row in data['rows']:
        grouped.setdefault(str(row['post_id']), []).append(row)
    for post in posts:
        post['canonical_post_id'] = canonical_post_id(post['post_id'], grouped.get(str(post['post_id']), []))
    extra = json.loads(args.parents.read_text(encoding='utf-8'))['rows'] if args.parents.exists() else []
    rows = build_context_rows(data['rows'], posts, extra)
    output = dict(data, posts=posts, rows=rows,
                  context_source_sha256=hashlib.sha256(source).hexdigest(),
                  context_completeness='not_verified',
                  context_summary=dict(post_status=dict(Counter(p.get('status', 'not_collected') for p in posts)),
                                       parent_status=dict(Counter(r['context']['parent_status'] for r in rows)),
                                       rows_with_post_text=sum(r['context']['post_text_available'] for r in rows)))
    if args.source.read_bytes() != source:
        raise RuntimeError('Source changed during export')
    atomic_json(args.output, output)
    print(json.dumps(output['context_summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
