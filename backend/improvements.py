"""Bounded validation-only model search, thresholds, and optional ViSoBERT."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from backend.dataset import LABELS, atomic_json, fingerprint, input_fingerprint
from backend.experiments import build_report, metrics, publish_run, train_experiment, validate_algorithms

# Existing joblib models refer to improvements.ThresholdClassifier.
if __name__ != '__main__':
    sys.modules.setdefault('improvements', sys.modules[__name__])


def choose_threshold(labels, scores, default=0.5):
    """Maximize validation macro-F1; break ties towards the default threshold."""
    y, scores = np.asarray(labels, dtype=int), np.asarray(scores, dtype=float)
    if y.ndim != 1 or scores.shape != y.shape or not len(y) or not np.isfinite(scores).all():
        raise ValueError('Điểm validation không hợp lệ.')
    if set(y.tolist()) != {0, 1}:
        raise ValueError('Validation phải có cả hai lớp để chọn ngưỡng.')
    thresholds = np.unique(np.r_[scores, default, np.nextafter(scores.max(), np.inf)])
    order = np.argsort(scores, kind='stable')
    sorted_scores, sorted_y = scores[order], y[order]
    positions = np.searchsorted(sorted_scores, thresholds, side='left')
    cumulative = np.r_[0, np.cumsum(sorted_y)]
    fn = cumulative[positions]
    tn = positions - fn
    tp, fp = y.sum() - fn, len(y) - positions - (y.sum() - fn)
    positive = np.divide(2*tp, 2*tp+fp+fn, out=np.zeros_like(tp, dtype=float), where=2*tp+fp+fn != 0)
    negative = np.divide(2*tn, 2*tn+fp+fn, out=np.zeros_like(tn, dtype=float), where=2*tn+fp+fn != 0)
    macro = (positive + negative) / 2
    tied = np.flatnonzero(np.isclose(macro, macro.max(), rtol=0, atol=1e-12))
    index = min(tied, key=lambda i: (abs(thresholds[i] - default), thresholds[i]))
    threshold = float(thresholds[index])
    return dict(threshold=threshold, default_threshold=default, selection_split='validation',
                objective='f1_macro', validation=metrics(y, scores >= threshold),
                validation_default=metrics(y, scores >= default),
                curve=[dict(threshold=float(t), f1_macro=float(f), precision=float(p/(p+q)) if p+q else 0.,
                            recall=float(p/y.sum())) for t, f, p, q in zip(thresholds, macro, tp, fp)])


def decision_scores(model, texts):
    if hasattr(model, 'decision_function'):
        return np.asarray(model.decision_function(texts), dtype=float)
    return np.asarray(model.predict_proba(texts)[:, 1], dtype=float)


class ThresholdClassifier:
    """Persist a fitted sklearn pipeline together with its validation threshold."""
    def __init__(self, estimator, threshold):
        self.estimator, self.threshold = estimator, float(threshold)

    def decision_function(self, texts):
        return decision_scores(self.estimator, texts)

    def predict(self, texts):
        return (self.decision_function(texts) >= self.threshold).astype(int)


def search_baselines(features, train_labels, validation_labels, notify=print, algorithms=None):
    """Choose classifier parameters on the already extracted train/validation matrices."""
    from sklearn.metrics import f1_score
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.pipeline import FeatureUnion
    from sklearn.svm import LinearSVC
    selected = ['NB', 'SVM'] if algorithms is None else algorithms
    winners, trials = {}, []
    if not any(a in selected for a in ('NB', 'SVM')):
        return winners, trials
    for method, data in features.items():
        vectorizer = data['vectorizer']
        train_x, val_x = data['matrices']['train'], data['matrices']['validation']
        for algorithm in ('NB', 'SVM'):
            if algorithm not in selected:
                continue
            name = f'{method}-{algorithm}'
            settings = ([dict(alpha=a) for a in (0.1, 0.3, 1.0, 3.0)] if algorithm == 'NB' else
                        [dict(C=c, class_weight=w) for c in (0.03, 0.1, 0.3, 1.0, 3.0) for w in (None, 'balanced')])
            notify(f'Chọn tham số {name} trên đặc trưng đã trích xuất')
            for params in settings:
                started = time.monotonic()
                classifier = (MultinomialNB(**params) if algorithm == 'NB' else
                              LinearSVC(**params, random_state=42, max_iter=20000))
                classifier.fit(train_x, train_labels)
                score = float(f1_score(validation_labels, classifier.predict(val_x), average='macro', zero_division=0))
                if isinstance(vectorizer, FeatureUnion):
                    branches = dict(vectorizer.transformer_list)
                    word, char = branches['word'], branches['char']
                    config = dict(ngram_range=list(word.ngram_range), max_features=word.max_features,
                                  char_features=True, char_ngram_range=list(char.ngram_range),
                                  char_max_features=char.max_features, **params)
                else:
                    config = dict(ngram_range=list(vectorizer.ngram_range), max_features=vectorizer.max_features,
                                  char_features=False, **params)
                trials.append(dict(name=name, parameters=config, validation_f1_macro=score,
                                   seconds=round(time.monotonic()-started, 3)))
                if name not in winners or score > winners[name]['score']:
                    winners[name] = dict(score=score, parameters=config, feature=method, algorithm=algorithm,
                                         estimator=Pipeline([('vectorizer', vectorizer), ('classifier', classifier)]))
    if not winners:
        raise ValueError('Không tìm được cấu hình; kiểm tra độ dài và từ vựng tập train.')
    return winners, trials


def train_improved(rows, output, notify=print, prepared=None, include_visobert=False,
                   transformer_config=None, algorithms=None):
    import joblib
    from backend.features import build_features

    algorithms = validate_algorithms(algorithms, include_visobert, optimized=True)
    output = Path(output)
    if prepared is None:
        prepared = build_features(rows, dict(ngram='both'), notify)
    # Initialize the shared snapshot; each selected family records one final model.
    result = train_experiment(rows, output, notify, prepared=prepared,
                              algorithms=[])
    result['requested_algorithms'] = algorithms
    result['experiment_type'] = 'validation_search'
    result['input_fingerprint'] = input_fingerprint(rows)
    result['protocol'] = dict(selection='validation_f1_macro', threshold_selection='validation_f1_macro',
                              labels_modified=False, context_added=False, test_used_for_selection=False,
                              limitation='Test đã được xem ở các thực nghiệm trước; cần dữ liệu độc lập cho kết luận tổng quát hóa cuối cùng.')
    texts, labels, split = prepared['texts'], prepared['labels'], prepared['split']
    eligible = prepared['rows']
    started = time.monotonic()
    winners, trials = search_baselines(prepared['features'], labels['train'], labels['validation'], notify, algorithms)
    atomic_json(output / 'search.json', dict(selection_split='validation', trials=trials))

    def record(name, feature, algorithm, val_scores, test_scores, default, parameters, artifact, seconds):
        choice = choose_threshold(labels['validation'], val_scores, default)
        threshold = choice['threshold']
        model = dict(name=name, feature=feature, algorithm=algorithm, validation=choice['validation'],
                     test=metrics(labels['test'], np.asarray(test_scores) >= threshold),
                     validation_default=choice['validation_default'],
                     test_default=metrics(labels['test'], np.asarray(test_scores) >= default),
                     threshold=threshold, default_threshold=default, parameters=parameters, artifact=artifact,
                     selection_split='validation', seconds=round(seconds, 3))
        result['models'].append(model)
        atomic_json(output / f'{name}-threshold.json', choice)
        for part, scores in [('validation', val_scores), ('test', test_scores)]:
            predictions = [dict(id=eligible[i]['id'], actual=LABELS[int(actual)],
                                predicted=LABELS[int(score >= threshold)], score=float(score), threshold=threshold)
                           for i, actual, score in zip(split[part], labels[part], scores)]
            suffix = 'predictions' if part == 'test' else 'validation-predictions'
            atomic_json(output / f'{name}-{suffix}.json', predictions)
        return threshold

    search_seconds = time.monotonic() - started
    for name, winner in winners.items():
        estimator = winner['estimator']
        val_scores = decision_scores(estimator, texts['validation'])
        # Test is transformed only after this family's hyperparameters are fixed.
        test_scores = decision_scores(estimator, texts['test'])
        family_seconds = sum(t['seconds'] for t in trials if t['name'] == name)
        threshold = record(name, winner['feature'], winner['algorithm'], val_scores, test_scores,
                           0.0 if winner['algorithm'] == 'SVM' else 0.5, winner['parameters'],
                           dict(kind='sklearn', file=name+'.joblib'), family_seconds)
        joblib.dump(ThresholdClassifier(estimator, threshold), output / f'{name}.joblib')
    result['search_seconds'] = round(search_seconds, 3)

    if 'ViSoBERT' in algorithms:
        from backend.transformer_model import train_transformer, score_transformer
        raw = {part: [eligible[i]['text_raw'] for i in ids] for part, ids in split.items()}
        model, tokenizer, transformer = train_transformer(raw['train'], labels['train'], raw['validation'], labels['validation'],
                                                          output.parent.parent.parent / 'models' / 'visobert-base',
                                                          output / 'ViSoBERT', notify, transformer_config)
        val_scores = score_transformer(model, tokenizer, raw['validation'], transformer['config']['max_length'])
        test_scores = score_transformer(model, tokenizer, raw['test'], transformer['config']['max_length'])
        record('ViSoBERT', 'Pretrained transformer', 'ViSoBERT', val_scores, test_scores, 0.5,
               transformer, dict(kind='transformer', directory='ViSoBERT'), transformer['seconds'])
        result['versions']['transformers'] = __import__('transformers').__version__
    result['selected_model'] = max(result['models'], key=lambda m: m['validation']['f1_macro'])['name']
    result['trained_models'] = [m['name'] for m in result['models']]
    atomic_json(output / 'metrics.json', result)
    (output / 'report.md').write_text(build_report(rows, result), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-visobert', action='store_true')
    parser.add_argument('--download-visobert', action='store_true')
    parser.add_argument('--visobert-epochs', type=int, default=4)
    parser.add_argument('--algorithms', nargs='+', choices=['NB', 'SVM', 'ViSoBERT'],
                        help='Only train the selected algorithms; retain compatible previous models.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.download_visobert:
        from backend.transformer_model import download_base
        print(download_base(root / 'models' / 'visobert-base'), flush=True)
        return
    from app import LAB, restore
    import joblib
    restore()
    notify = lambda message: print(message, flush=True)
    rows = LAB.experiment_rows()
    feature_path = root / 'data' / 'features.joblib'
    if not feature_path.is_file():
        raise ValueError('Hãy trích xuất đặc trưng trên web trước khi chạy huấn luyện từ dòng lệnh.')
    prepared = joblib.load(feature_path)
    run = 'run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = root / 'data' / 'runs' / run
    result = train_improved(rows, output, notify, prepared=prepared, include_visobert=args.include_visobert,
                            transformer_config=dict(epochs=args.visobert_epochs), algorithms=args.algorithms)
    current = LAB.experiment_rows()
    if fingerprint(rows) != fingerprint(current) or input_fingerprint(rows) != input_fingerprint(current):
        raise ValueError('Dữ liệu đã thay đổi trong lúc huấn luyện; giữ kết quả cũ và không cập nhật latest.')
    result = publish_run(result, output, root / 'data', rows)
    (root / 'docs' / 'Report.md').write_text(build_report(LAB.rows(), result,
        experiment_fingerprint=fingerprint(current), experiment_input_fingerprint=input_fingerprint(current)), encoding='utf-8')
    print(json.dumps(dict(run=run, selected=result['selected_model'], models=len(result['models'])), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    # Keep persisted class references importable when the CLI is __main__.
    from backend.improvements import main as run_main
    run_main()
