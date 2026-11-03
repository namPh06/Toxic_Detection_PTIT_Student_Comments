"""Offline grouped development CV and provisional text-only fallback labels.

Never changes workspace annotations or production models. Run with a fresh --output.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from context_preprocessing import normalize
from dataset import atomic_json, prepare, row_id, text_hash
from experiments import metrics
from word_preprocessing import word_text

POLICY = 'ptit-v3.2-friendly-banter-20261031'


def grouped_partition(rows, legacy, reserved):
    """Union canonical posts and exact duplicate representations BEFORE reservation."""
    parent = {r['canonical_post_id']: r['canonical_post_id'] for r in rows}

    def root(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def union(a, b):
        a, b = root(a), root(b)
        parent[max(a, b)] = min(a, b)

    seen = {}
    for r in rows:
        old = legacy[r['id']]
        # All nonempty conservative normalized targets are compared, including
        # common short comments. This may reserve large groups; never split them
        # silently to obtain more convenient evaluation counts.
        keys = [('normalized', normalize(r['fields']['target']['text_raw']).casefold())]
        if old['quality'] in ('ready', 'duplicate'):
            keys += [('legacy', old['text_clean']),
                     ('legacy_word', word_text(old['text_raw']))]
        for kind, value in keys:
            if value:
                first = seen.setdefault((kind, value), r['canonical_post_id'])
                union(first, r['canonical_post_id'])
    groups = {r['id']: root(r['canonical_post_id']) for r in rows}
    reserved_groups = {groups[r['id']] for r in rows if r['post_id'] in reserved}
    return groups, reserved_groups


def make_model(feature, algorithm):
    vectorizer = CountVectorizer if feature == 'BoW' else TfidfVectorizer
    return Pipeline([
        ('vectorizer', vectorizer(tokenizer=str.split, token_pattern=None,
                                 lowercase=False, ngram_range=(1, 2), max_features=20000)),
        ('classifier', MultinomialNB(alpha=1) if algorithm == 'NB' else
         LinearSVC(C=1, class_weight='balanced', random_state=42, max_iter=10000))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('outputs/safe_fallback_20261101'))
    args = parser.parse_args()
    paths = [Path(p) for p in [
        'data/progress.json', 'data/workspace.json',
        'data/manual_review/canonical_development_v32_20261031.json',
        'outputs/context_preprocessing_20261101/dataset.json',
        'outputs/context_preprocessing_20261101/manifest.json',
        'outputs/label_review_20261031/review_manifest.json']]
    protected = {p: p.read_bytes() for p in paths}
    load = lambda p: json.loads(protected[Path(p)].decode('utf-8-sig'))
    raw = load(paths[0])['rows']
    reference = load(paths[2])
    if reference['policy_version'] != POLICY:
        raise ValueError('Unexpected reference policy')
    rows = load(paths[3])['rows']
    source_manifest = load(paths[4])
    for name, digest in source_manifest['input_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('Stale context preprocessing input: ' + name)
    if len(rows) != len(raw) or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Corpus identities are not one-to-one')
    raw_by_id = {row_id(r): r for r in raw}
    refs = {r['id']: r for r in reference['rows']}
    for r in rows:
        if r['fields']['target']['text_raw'] != raw_by_id[r['id']]['text_raw']:
            raise ValueError('Target text changed')
        ref = refs.get(r['id'])
        if ref and (not ref['human_verified'] or ref['text_hash'] != text_hash(raw_by_id[r['id']]['text_raw'])):
            raise ValueError('Invalid human reference')
    legacy = {r['id']: r for r in prepare(raw)}
    reserved = set(map(str, load(paths[5])['reserved_post_ids']))
    groups, reserved_groups = grouped_partition(rows, legacy, reserved)
    dev = [r for r in rows if r['id'] in refs and groups[r['id']] not in reserved_groups]
    removed = [r for r in rows if r['id'] in refs and groups[r['id']] in reserved_groups]
    y = np.array([int(refs[r['id']]['reference_label'] == 'toxic') for r in dev])
    x = np.array([word_text(r['fields']['target']['text_raw']) for r in dev])
    g = np.array([groups[r['id']] for r in dev])
    if len(set(g)) < 5 or min(Counter(y).get(k, 0) for k in (0, 1)) < 5:
        raise ValueError('Too few independent development groups/classes after reservation')
    folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42).split(x, y, g))
    manifest = []
    for a, b in folds:
        if len(set(y[a])) != 2 or len(set(y[b])) != 2:
            raise ValueError('Both classes required in every fold')
        assert not set(g[a]) & set(g[b])
        assert not set(g[a]) & reserved_groups
        assert not set(g[b]) & reserved_groups
        assert not set(x[a]) & set(x[b])
        manifest.append(dict(train_ids=[dev[i]['id'] for i in a],
                             validation_ids=[dev[i]['id'] for i in b],
                             train_labels=dict(Counter(refs[dev[i]['id']]['reference_label'] for i in a)),
                             validation_labels=dict(Counter(refs[dev[i]['id']]['reference_label'] for i in b))))
    out = args.output.resolve()
    if Path('data').resolve() == out or Path('data').resolve() in out.parents:
        raise ValueError('Output must be outside data/')
    out.mkdir(parents=True, exist_ok=False)
    partition = [dict(id=r['id'], post_id=r['post_id'], canonical_post_id=r['canonical_post_id'],
                      group=groups[r['id']], partition='reserved' if groups[r['id']] in reserved_groups else 'development_pool',
                      human_label_available=r['id'] in refs) for r in rows]
    atomic_json(out / 'partitions.json', dict(rows=partition,
                excluded_development_ids=[r['id'] for r in removed],
                reservation_rule='Entire transitive duplicate/canonical group is reserved if any member post was reserved.',
                reserved_scope='Previously used diagnostic reservation, not a fresh blind test'))
    atomic_json(out / 'folds.json', manifest)
    candidates, models, oof = [], {}, {}
    for feature in ('BoW', 'TF-IDF'):
        for algorithm in ('NB', 'SVM'):
            name = feature + '-' + algorithm
            pred = np.full(len(y), -1)
            scores = []
            for a, b in folds:
                model = make_model(feature, algorithm)
                model.fit(x[a], y[a])
                pred[b] = model.predict(x[b])
                scores.append(metrics(y[b], pred[b]))
            assert np.all(pred >= 0)
            candidates.append(dict(name=name, fold_metrics=scores,
                                   mean_macro_f1=float(np.mean([s['f1_macro'] for s in scores])),
                                   oof=metrics(y, pred)))
            oof[name] = {r['id']: int(p) for r, p in zip(dev, pred)}
            model = make_model(feature, algorithm)
            model.fit(x, y)
            joblib.dump(model, out / (name + '.joblib'))
            models[name] = model
            atomic_json(out / (name + '-oof.json'), [dict(id=r['id'], actual=refs[r['id']]['reference_label'],
                        predicted='toxic' if p else 'non-toxic') for r, p in zip(dev, pred)])
            print(name, candidates[-1]['oof']['f1_macro'], flush=True)
    selected = max(candidates, key=lambda m: m['mean_macro_f1'])['name']
    # Missing/incomplete context OR unknown target completeness can require review.
    # Source-wide collection warnings alone do not imply semantic ambiguity.
    targets = [r for r in rows if r['context_gaps'] and r['target_usable']]
    fallback = []
    for r in targets:
        existing = refs.get(r['id'])
        split = 'reserved' if groups[r['id']] in reserved_groups else 'development_pool'
        predictions = {}
        for name, model in models.items():
            p = oof[name].get(r['id'])
            method = 'out_of_fold' if p is not None else 'fit_development_only'
            if p is None:
                p = int(model.predict([word_text(r['fields']['target']['text_raw'])])[0])
            predictions[name] = dict(label='toxic' if p else 'non-toxic', method=method)
        fallback.append(dict(id=r['id'], comment=r['fields']['target']['text_raw'],
            group=groups[r['id']], partition=split, context_gaps=r['context_gaps'],
            human_reference_label=existing['reference_label'] if existing else None,
            proposed_label=predictions[selected]['label'] if not existing else None,
            selected_model=selected, candidates=predictions, human_verified=False,
            label_source='automatic_text_only_fallback', needs_review=True,
            policy_version=POLICY, text_hash=r['text_hash'],
            score=None, score_note='No calibrated correctness probability; labels are provisional.',
            action='preserve_human_label' if existing else 'review_proposal_only'))
    atomic_json(out / 'fallback_review.json', dict(rows=fallback,
        scope='Candidates only; never use as gold test labels. Missing-context flags do not prove semantic ambiguity.'))
    assert all(p.read_bytes() == b for p, b in protected.items())
    result = dict(policy=POLICY, seed=42, scope='Grouped development CV, not blind test',
        partitions_sha256=hashlib.sha256((out / 'partitions.json').read_bytes()).hexdigest(),
        input_hashes={str(p): hashlib.sha256(b).hexdigest() for p, b in protected.items()},
        development_rows=len(dev), development_labels=dict(Counter(refs[r['id']]['reference_label'] for r in dev)),
        development_groups=len(set(g)), excluded_human_rows=len(removed),
        reserved_groups=len(reserved_groups), reserved_rows=sum(p['partition'] == 'reserved' for p in partition),
        selected_model=selected, models=candidates, fallback_rows=len(fallback),
        new_proposals=sum(r['proposed_label'] is not None for r in fallback),
        human_labels_preserved=sum(r['human_reference_label'] is not None for r in fallback),
        production_model_changed=False, workspace_changed=False,
        limitations=['Exact duplicates including short generic text may join large groups.',
                      'CV model selection is not independent final evaluation.',
                      'Text-only models do not recover missing context or prove semantic correctness.',
                      'Fallback proposals do not become human training/evaluation labels.'])
    atomic_json(out / 'metrics.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('models', 'input_hashes')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
