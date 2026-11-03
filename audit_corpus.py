"""Run local inference over every eligible comment, without treating it as gold.

Artifacts are separate from workspace labels. No external inference calls.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from dataset import LABELS, atomic_json, prepare, summary, text_hash
from labeling import BATCH_SIZE, FILES, MODEL_ID, REVISION, automatic_annotation, generate_suggestions, valid_file


def audit(source, output, cache, notify=print):
    started = time.monotonic()
    content = source.read_bytes()
    source_hash = hashlib.sha256(content).hexdigest()
    raw = json.loads(content.decode('utf-8-sig'))
    prepared = prepare(raw['rows'])
    ready = [r for r in prepared if r['quality'] == 'ready']
    if not ready or len({r['id'] for r in prepared}) != len(prepared):
        raise ValueError('Empty dataset or duplicate comment IDs; resolve before inference')
    # Audit every eligible text even when the source carries an existing label.
    candidates = [dict(r, label='') for r in ready]
    predictions = generate_suggestions(candidates, cache, notify)
    if len(predictions) != len(candidates) or len({p['id'] for p in predictions}) != len(candidates):
        raise ValueError('Missing or duplicate predictions')
    by_id = {p['id']: p for p in predictions}
    audited, blind = [], []
    for row in candidates:
        item = by_id[row['id']]
        if item['text_hash'] != text_hash(row['text_raw']):
            raise ValueError('Prediction does not match original text')
        annotation = automatic_annotation(item, row['text_raw'])
        if annotation['label'] not in LABELS:
            raise ValueError('Invalid automatic label')
        audited.append(dict(id=row['id'], post_id=row['post_id'], text_raw=row['text_raw'],
                            text_complete=row.get('text_complete'), **annotation))
        blind.append(dict(id=row['id'], post_id=row['post_id'], text_raw=row['text_raw'],
                          text_hash=row['text_hash'], reference_label='', human_verified=False))
    # Never publish a completed audit for a source that changed while it was running.
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Source changed during inference; rerun against a stable snapshot')
    queue = [r for r in audited if r['needs_review']]
    result = dict(created_at=datetime.now(timezone.utc).isoformat(), source_sha256=source_hash,
                  model=MODEL_ID, revision=REVISION, threshold=0.5, inference_batch_size=BATCH_SIZE,
                  assets_verified=all(valid_file(cache / name, *spec) for name,spec in FILES.items()),
                  source_summary=summary(prepared), inferred=len(predictions),
                  machine_labels=dict(Counter(r['label'] for r in audited)),
                  review_needed=len(queue), review_reasons=dict(Counter(r['review_reason'] for r in queue)),
                  unknown_completeness=sum(r['text_complete'] is None for r in audited),
                  reference_labels_available=0, accuracy=None,
                  status='INFERENCE_COMPLETE_ACCURACY_UNVERIFIED',
                  warning='These are model predictions, not independent reference labels. Unflagged can also be wrong.',
                  seconds=round(time.monotonic()-started, 2))
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'predictions.json', predictions)
    atomic_json(output / 'machine_labels.json', dict(label_policy='unverified_machine_predictions', rows=audited))
    atomic_json(output / 'review_queue.json', dict(label_policy='unverified_machine_predictions', rows=queue))
    atomic_json(output / 'human_review_blind.json', dict(reference_type='full corpus independent review pending', rows=blind))
    atomic_json(output / 'excluded.json', dict(rows=[r for r in prepared if r['quality'] != 'ready']))
    # Write summary last, after the complete set of artifacts.
    atomic_json(output / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/progress.json'))
    parser.add_argument('--output', type=Path, default=Path('data/label_audit/full_corpus'))
    parser.add_argument('--cache', type=Path, default=Path('models/vietnamese-toxicity'))
    args = parser.parse_args()
    print(json.dumps(audit(args.source, args.output, args.cache), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
