"""Evaluate fixed model predictions against separate, hash-matched review labels.

References: {"reference_type": "...", "rows": [{"id": "...", "text_hash": "...",
"reference_label": "toxic|non-toxic|uncertain", "human_verified": true|false}]}.
This utility never writes training annotations or tunes thresholds.
"""
import argparse
import json
import math
from pathlib import Path
from dataset import prepare, text_hash
from experiments import metrics
from labeling import automatic_annotation


def evaluate(reference, predictions, threshold=0.5):
    if not 0 < threshold < 1:
        raise ValueError('threshold must be between 0 and 1')
    items = reference['rows']
    if not items or not predictions:
        raise ValueError('Reference and predictions must not be empty')
    predicted = {r['id']: r for r in predictions}
    if len(predicted) != len(predictions) or len({r['id'] for r in items}) != len(items):
        raise ValueError('Duplicate IDs')
    actual, guesses, review_actual, review_guesses, errors = [], [], [], [], []
    review_count = excluded = 0
    verified = True
    for row in items:
        if row['reference_label'] not in ('toxic', 'non-toxic', 'uncertain'):
            raise ValueError('Invalid reference label')
        if 'text_raw' in row and text_hash(row['text_raw']) != row['text_hash']:
            raise ValueError('Reference text hash mismatch: ' + row['id'])
        item = predicted.get(row['id'])
        if not item or item['text_hash'] != row['text_hash']:
            raise ValueError('Missing prediction or mismatched text hash: ' + row['id'])
        score = item['model_score']
        if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Invalid score')
        decision = automatic_annotation(item, row.get('text_raw'))
        if row['reference_label'] == 'uncertain':
            excluded += 1
            continue
        verified = verified and row.get('human_verified') is True
        truth, guess = int(row['reference_label'] == 'toxic'), int(score >= threshold)
        actual.append(truth)
        guesses.append(guess)
        if decision['needs_review']:
            review_count += 1
        else:
            review_actual.append(truth)
            review_guesses.append(guess)
        if truth != guess:
            errors.append(dict(id=row['id'], reference_label=row['reference_label'],
                               predicted_label='toxic' if guess else 'non-toxic',
                               model_score=score, needs_review=decision['needs_review'],
                               review_reason=decision['review_reason']))
    if not actual:
        raise ValueError('No resolved reference labels')
    return dict(reference_type=reference.get('reference_type', 'unspecified'),
                human_verified=verified,
                interpretation='human-reviewed reference' if verified else 'provisional AI agreement; NOT human gold accuracy',
                threshold=threshold, total=len(items), evaluated=len(actual), uncertain_excluded=excluded,
                metrics=metrics(actual, guesses), errors=errors,
                review_routing=dict(flagged_resolved=review_count,
                                    errors_flagged=sum(r['needs_review'] for r in errors),
                                    unflagged_resolved=len(review_actual),
                                    unflagged_errors=sum(a != b for a,b in zip(review_actual,review_guesses))))


def full_corpus_acceptance(reference, predictions, corpus):
    """A full-corpus claim needs complete, human-verified references, not self-labels."""
    expected = {r['id']: r['text_hash'] for r in prepare(corpus['rows']) if r['quality'] == 'ready'}
    rows = reference['rows']
    refs = {r['id']: r for r in rows}
    preds = {r['id']: r for r in predictions}
    problems = []
    if not expected:
        problems.append('empty_corpus')
    if len(refs) != len(rows) or len(preds) != len(predictions):
        problems.append('duplicate_ids')
    missing_refs = len(expected.keys() - refs.keys())
    missing_predictions = len(expected.keys() - preds.keys())
    if missing_refs or set(refs) != set(expected):
        problems.append('reference_coverage_mismatch')
    if missing_predictions or set(preds) != set(expected):
        problems.append('prediction_coverage_mismatch')
    unresolved = unverified = mismatches = errors = evaluated = 0
    for identity, digest in expected.items():
        ref, pred = refs.get(identity), preds.get(identity)
        if ref is None or pred is None:
            continue
        if ref.get('reference_label') not in ('toxic', 'non-toxic'):
            unresolved += 1
        if ref.get('human_verified') is not True:
            unverified += 1
        valid_hash = ref.get('text_hash') == digest and pred.get('text_hash') == digest
        if 'text_raw' in ref:
            valid_hash = valid_hash and text_hash(ref['text_raw']) == digest
        if not valid_hash:
            mismatches += 1
        score = pred.get('model_score')
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            problems.append('invalid_prediction_score')
            continue
        if ref.get('reference_label') in ('toxic', 'non-toxic'):
            evaluated += 1
            errors += ref['reference_label'] != ('toxic' if score >= 0.5 else 'non-toxic')
    for count, name in [(unresolved,'unresolved_reference_labels'), (unverified,'references_not_human_verified'),
                        (mismatches,'text_hash_mismatch'), (errors,'prediction_errors')]:
        if count:
            problems.append(name)
    return dict(passed=not problems, corpus_size=len(expected), missing_references=missing_refs,
                missing_predictions=missing_predictions, unresolved=unresolved, unverified=unverified,
                hash_mismatches=mismatches, evaluated_references=evaluated,
                errors=errors if evaluated else None, reasons=sorted(set(problems)),
                scope='Only agreement with this fixed reference corpus, never a guarantee on future text.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--predictions', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--require-perfect', action='store_true', help='Fail unless the entire corpus has verified references and zero errors')
    parser.add_argument('--corpus', type=Path, help='Original progress.json for full coverage checking')
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding='utf-8-sig'))
    predictions = json.loads(args.predictions.read_text(encoding='utf-8-sig'))
    if args.require_perfect:
        if args.corpus is None:
            parser.error('--require-perfect needs --corpus')
        corpus = json.loads(args.corpus.read_text(encoding='utf-8-sig'))
        result = dict(full_corpus_acceptance=full_corpus_acceptance(reference, predictions, corpus))
        if result['full_corpus_acceptance']['passed']:
            result['evaluation'] = evaluate(reference, predictions)
    else:
        result = evaluate(reference, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    if args.require_perfect and not result['full_corpus_acceptance']['passed']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
