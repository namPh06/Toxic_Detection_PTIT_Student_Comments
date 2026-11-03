"""Reconcile saved proposals and fill remaining READY rows, preserving human labels.

Local-only. All new annotations are automatic, unverified and require review.
"""
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib

from dataset import atomic_json, csv_bytes, prepare, text_hash
from word_preprocessing import word_text

POLICY = 'ptit-v3.2-friendly-banter-20261031'
OUT = Path('outputs/completed_labels_20261101')


def main():
    workspace_path = Path('data/workspace.json')
    raw_path = Path('data/progress.json')
    original = workspace_path.read_bytes()
    raw_bytes = raw_path.read_bytes()
    workspace = json.loads(original.decode('utf-8-sig'))
    raw = json.loads(raw_bytes.decode('utf-8-sig'))['rows']
    before = prepare(raw + workspace['imported'], workspace['annotations'])
    by_id = {r['id']: r for r in before}
    if OUT.exists():
        raise ValueError('Output already exists; inspect previous completion before rerunning')
    sources = [
        Path('outputs/assistant_review_20261031/assistant_labels.json'),
        Path('outputs/assistant_review_batch2_20261031/assistant_labels.json'),
        Path('outputs/remaining_semantic_review_20261031/assistant_labels.json')]
    choices, rejected, disagreements = {}, [], []
    source_hashes = {}
    # Priority is explicit; conflicting saved proposals fall back to the selected
    # fitted model and stay flagged. No historical human-labelled snapshots used.
    proposals = {}
    for path in sources:
        content = path.read_bytes()
        source_hashes[str(path)] = hashlib.sha256(content).hexdigest()
        payload = json.loads(content.decode('utf-8-sig'))
        for r in payload['rows']:
            current = by_id.get(r['id'])
            if not current or r.get('text_hash') != current['text_hash']:
                rejected.append(dict(id=r.get('id'), source=str(path), reason='missing_or_stale_text'))
                continue
            if r.get('policy_version', payload.get('policy_version')) != POLICY:
                rejected.append(dict(id=r['id'], source=str(path), reason='policy_mismatch'))
                continue
            if r.get('label') not in ('toxic', 'non-toxic'):
                continue
            proposals.setdefault(r['id'], []).append((r['label'], str(path)))
    model_dir = Path('outputs/safe_fallback_20261101')
    manifest = json.loads((model_dir / 'metrics.json').read_text(encoding='utf-8'))
    for name, digest in manifest['input_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('Fallback model inputs changed: ' + name)
    selected = manifest['selected_model']
    model_path = model_dir / (selected + '.joblib')
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    model = joblib.load(model_path)
    annotations = dict(workspace['annotations'])
    audit = []
    now = datetime.now(timezone.utc).isoformat()
    missing = [r for r in before if r['quality'] == 'ready' and not r['label']]
    for r in missing:
        options = proposals.get(r['id'], [])
        labels = {x[0] for x in options}
        if len(labels) == 1:
            label = options[0][0]
            origin = options[0][1]
            method = 'reconciled_assistant_proposal'
        else:
            label = 'toxic' if int(model.predict([word_text(r['text_raw'])])[0]) else 'non-toxic'
            origin = str(model_path)
            method = 'text_only_svm_fallback'
            if len(labels) > 1:
                disagreements.append(r['id'])
        # Semantic proposals and uncalibrated SVM decisions have no calibrated
        # toxicity probability. Do not invent a score or a threshold of 0.5.
        annotations[r['id']] = dict(
            label=label, label_source='automatic', text_hash=r['text_hash'],
            model_score=None, label_model='assistant_semantic_review' if method.startswith('reconciled') else selected,
            label_revision=POLICY if method.startswith('reconciled') else model_hash,
            label_threshold=None, needs_review=True,
            review_reason='unverified_reconciled_proposal' if method.startswith('reconciled') else 'unverified_text_only_fallback',
            human_verified=False, policy_version=POLICY, provenance=origin,
            labeling_method=method, updated_at=now,
            note='Machine proposal only; not human gold, not an independent evaluation answer.',
            excluded=False)
        audit.append(dict(id=r['id'], text_hash=r['text_hash'], comment=r['text_raw'],
                          label=label, method=method, provenance=origin,
                          historical_candidates=[dict(label=a, source=b) for a, b in options],
                          needs_review=True, human_verified=False))
    after = prepare(raw + workspace['imported'], annotations)
    old_human = {k: v for k, v in workspace['annotations'].items() if v.get('label_source') != 'automatic'}
    assert all(annotations[k] == v for k, v in old_human.items())
    assert not any(r['quality'] == 'ready' and not r['label'] for r in after)
    if Counter(r['quality'] for r in before) != Counter(r['quality'] for r in after):
        raise ValueError('New annotations changed duplicate/conflict quality; inspect before committing')
    ready = [r for r in after if r['quality'] == 'ready']
    counts = Counter(r['label'] for r in ready)
    human_counts = Counter(r['label'] for r in ready if r['label_source'] != 'automatic')
    machine_counts = Counter(r['label'] for r in ready if r['label_source'] == 'automatic')
    total, toxic = len(ready), counts['toxic']
    targets = [dict(target_toxic_percent=int(q * 100),
                    additional_verified_toxic_if_only_adding_toxic=max(0, math.ceil((q * total - toxic) / (1 - q))))
               for q in (0.20, 0.25, 0.30, 0.50)]
    human_total = sum(human_counts.values())
    human_targets = [dict(target_toxic_percent=int(q * 100),
                         additional_verified_toxic_if_only_adding_toxic=max(0, math.ceil((q * human_total - human_counts['toxic']) / (1 - q))))
                    for q in (0.20, 0.25, 0.30, 0.50)]
    OUT.mkdir(parents=True)
    # Backup is written before the single atomic workspace mutation.
    (OUT / 'workspace_before.json').write_bytes(original)
    atomic_json(OUT / 'new_annotations_audit.json', dict(rows=audit))
    atomic_json(OUT / 'rejected_proposals.json', dict(rows=rejected, conflicting_ids=disagreements))
    atomic_json(OUT / 'dataset_auto.json', dict(label_policy='includes_unverified_automatic', rows=ready))
    (OUT / 'dataset_auto.csv').write_bytes(csv_bytes(ready))
    report = dict(policy_version=POLICY, source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        workspace_before_sha256=hashlib.sha256(original).hexdigest(),
        historical_source_hashes=source_hashes, fallback_model_sha256=model_hash,
        total_raw=len(raw), total_ready=total, labels=dict(counts),
        human_labels=dict(human_counts), automatic_labels=dict(machine_counts),
        toxic_percent=100 * toxic / total,
        human_toxic_percent=100 * human_counts['toxic'] / human_total,
        new_machine_labels=len(audit), methods=dict(Counter(r['method'] for r in audit)),
        remaining_ready_unlabeled=0, excluded_quality=dict(Counter(r['quality'] for r in after if r['quality'] != 'ready')),
        hypothetical_all_labels_targets=targets, human_only_targets=human_targets,
        target_note='Arithmetic scenarios, not assignment requirements or a guarantee of model quality. Assumes all added examples are distinct, valid, verified toxic.',
        limitations=['Machine labels are unverified; overall toxic ratio is provisional.',
                     'Historical semantic proposals predate the new post-context collection.',
                     'Text-only SVM fallback has low toxic recall; predictions may be wrong.',
                     'No class ratio is a mandated minimum in debai.jpg.',
                     'Old preprocessing/model manifests containing workspace hash become stale after this authorized annotation update.'])
    if workspace_path.read_bytes() != original or raw_path.read_bytes() != raw_bytes:
        raise RuntimeError('Inputs changed before commit')
    atomic_json(workspace_path, dict(workspace, annotations=annotations))
    saved = json.loads(workspace_path.read_text(encoding='utf-8'))
    assert all(saved['annotations'][k] == v for k, v in old_human.items())
    assert raw_path.read_bytes() == raw_bytes
    report['workspace_after_sha256'] = hashlib.sha256(workspace_path.read_bytes()).hexdigest()
    report['verification'] = dict(human_annotations_unchanged=True, raw_source_unchanged=True,
                                  quality_counts_unchanged=True, ready_coverage_complete=True)
    atomic_json(OUT / 'summary.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
