"""Context-aware local automatic annotations using the current collection policy."""
from collection_filter import CollectionFilter, MODEL
from dataset import text_hash
from datetime import datetime, timezone
import json

def generate_annotations(rows, all_rows, directory, notify=lambda message: None):
    gate = CollectionFilter('toxic')
    def read(name):
        p = directory / name
        return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
    posts = {}
    for name in ('progress.json', 'post_context.json'):
        for p in read(name).get('posts', []):
            posts[str(p.get('post_id', p.get('id', '')))] = p
    lookup = {(str(r['post_id']), str(r['comment_id'])): r for r in all_rows}
    for r in read('parent_context.json').get('rows', []):
        if r.get('identity_verified') and r.get('text_raw'):
            lookup.setdefault((str(r['post_id']), str(r['comment_id'])), r)
    for i, row in enumerate(rows, 1):
        post = dict(posts.get(str(row['post_id']), {}))
        post['post_text_raw'] = row.get('post_text_raw') or post.get('post_text_raw') or post.get('text_raw') or ''
        parents = list(row.get('parent_context') or [])
        if not parents:
            current, seen = row, set()
            for _ in range(8):
                key = (str(row['post_id']), str(current.get('parent_comment_id') or ''))
                if key in seen or key not in lookup: break
                seen.add(key); current = lookup[key]
                parents.insert(0, dict(text_raw=current['text_raw'], comment_id=current['comment_id']))
        post['parent_missing'] = bool(row.get('parent_comment_id') and not parents)
        decision = gate.evaluate(row, post, parents)
        label = decision['label'] if decision['label'] in ('toxic','non-toxic') else ''
        annotation = dict(label=label, excluded=not bool(label), label_source='automatic',
            text_hash=row['text_hash'], model_score=None, label_model=MODEL,
            label_revision=text_hash(gate.policy), label_threshold=None, needs_review=bool(label),
            review_reason='unverified_v4_semantic', note=decision['reason'],
            updated_at=datetime.now(timezone.utc).isoformat())
        notify(f'Qwen: đã xét {i}/{len(rows)} bình luận; lưu từng kết quả, loại câu chưa rõ khỏi dataset.')
        yield row, annotation
