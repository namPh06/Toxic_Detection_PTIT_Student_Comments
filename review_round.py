"""Prepare a blind human-review round; keep validation labels out of training exports."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from collections import Counter
import joblib
import numpy as np
from dataset import atomic_json, prepare, text_hash
from review_excel import read_review

OUT = Path('outputs/label_review_20261031')
SOURCE = Path('data/progress.json')
WORKSPACE = Path('data/workspace.json')
POLICY = 'ptit-v3.1-school-feedback-20261030'
SEED = 'ptit-review-round2-20261031-v1'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def order(row, purpose):
    return text_hash(SEED + ':' + purpose + ':' + row['id'])


def prepare_round():
    manifest_path = OUT / 'review_manifest.json'
    if manifest_path.exists():
        raise ValueError('Round already exists; do not resample or overwrite human review files')
    source_sha = sha(SOURCE)
    workspace_sha = sha(WORKSPACE)
    raw = load(SOURCE)
    all_prepared = prepare(raw['rows'])
    rows = [r for r in all_prepared if r['quality'] == 'ready']
    annotations = load(WORKSPACE)['annotations']
    human = {i:a for i,a in annotations.items()
             if a.get('label') in ('toxic','non-toxic') and a.get('label_source','manual') != 'automatic'}
    # Exclude posts of every human-annotated original, including duplicate aliases.
    used_posts = {str(r['post_id']) for r in all_prepared if r['id'] in human}
    index = {r['id']:r for r in rows}
    for i,a in human.items():
        if i not in index or a['text_hash'] != index[i]['text_hash']:
            raise ValueError('Human annotations require reconciliation before sampling')
    fresh = [r for r in rows if str(r['post_id']) not in used_posts]
    if len(fresh) < 200:
        raise ValueError('Insufficient new-post rows for the fixed review protocol')
    # Uniform row sampling by a predetermined SHA256 ordering, without label/score access.
    validation = sorted(fresh, key=lambda r:order(r,'validation'))[:200]
    reserved_posts = {str(r['post_id']) for r in validation}
    old_manifest = load('outputs/label_review_20261030/review_manifest.json')
    context_index = {r['id']:r for r in old_manifest['priority']+old_manifest['others']}
    predictions_path = Path('data/label_audit/full_corpus/predictions.json')
    predictions = {r['id']:r for r in load(predictions_path)}
    for r in rows:
        if predictions[r['id']]['text_hash'] != r['text_hash']:
            raise ValueError('Stale baseline prediction')
    candidate_path = Path('data/label_audit/hybrid_v31/candidate.joblib')
    candidate_eval_path = Path('data/label_audit/hybrid_v31/evaluation.json')
    candidate_eval = load(candidate_eval_path)
    training_posts = {str(index[i]['post_id']) for i in candidate_eval['development_ids']}
    assert not training_posts & reserved_posts
    candidate = joblib.load(candidate_path)
    def features(rs):
        return np.array([dict(text_raw=r['text_raw'],context=context_index[r['id']]['context'],
                              score=predictions[r['id']]['model_score']) for r in rs], dtype=object)
    # Additional development examples come from already-used posts only.
    pool = [r for r in rows if r['id'] not in human and str(r['post_id']) in used_posts]
    probs = candidate.predict_proba(features(pool))[:,1]
    scores = {r['id']:float(p) for r,p in zip(pool,probs)}
    threshold = candidate_eval['selected']['threshold']
    selected = []
    selection_reason = {}
    def take(candidates, count, reason):
        chosen = [r for r in candidates if r['id'] not in selection_reason][:count]
        selected.extend(chosen)
        selection_reason.update({r['id']:reason for r in chosen})
    school = re.compile(r'trường|học phí|csvc|cơ sở vật chất|giảng viên|giáo viên|đào tạo|giảng dạy|bưu chính|ptit',re.I)
    take(sorted([r for r in pool if school.search(r['text_raw'])], key=lambda r:order(r,'school')),
         20, 'school_feedback_boundary_candidate_not_a_label')
    take(sorted([r for r in pool if (scores[r['id']] >= threshold) != (predictions[r['id']]['model_score'] >= .5)],
                key=lambda r:order(r,'disagreement')), 20, 'model_disagreement_candidate_not_a_label')
    take(sorted(pool,key=lambda r:(abs(scores[r['id']]-threshold),order(r,'boundary'))),
         60-len(selected), 'candidate_boundary_not_calibrated_confidence')
    assert len(selected) == 60
    assert not {str(r['post_id']) for r in selected} & reserved_posts
    def entry(r, role):
        original = context_index[r['id']]
        return dict(id=r['id'],post_id=str(r['post_id']),comment_id=str(r['comment_id']),
                    text_hash=r['text_hash'],comment=r['text_raw'],context=original['context'],
                    post_url=r.get('post_url',''),role=role,
                    selection_reason=selection_reason.get(r['id'],'uniform_hash_sample_new_posts'))
    manifest = dict(schema_version=2,policy_version=POLICY,source_sha256=source_sha,
                    workspace_sha256_at_export=workspace_sha,seed=SEED,
                    worksheets={'Bo_sung_60':'priority','Kiem_chung_200':'others'},
                    check_context=True,review_note_column='D',
                    total_ready=len(rows),human_confirmed_excluded=len(human),
                    fresh_pool_rows=len(fresh),fresh_pool_posts=len({r['post_id'] for r in fresh}),
                    historical_human_posts=sorted(used_posts),reserved_post_ids=sorted(reserved_posts),
                    validation_scope='Uniform comment sample from posts without previous human labels, not all 5111 comments',
                    validation_protocol='Reserve every selected post from future training and retrieval; never use validation labels to tune thresholds/prompts. Freeze candidate before opening labels. Unresolved rows remain unresolved.',
                    priority=[entry(r,'development') for r in selected],
                    others=[entry(r,'validation') for r in validation])
    probs = candidate.predict_proba(features(validation))[:,1]
    frozen = dict(policy_version=POLICY,source_sha256=source_sha,seed=SEED,
                  status='frozen_before_new_human_labels',deployment_approved=False,
                  model_sha256=sha(candidate_path),candidate_evaluation_sha256=sha(candidate_eval_path),
                  baseline_predictions_sha256=sha(predictions_path),threshold=threshold,
                  training_ids=candidate_eval['development_ids'],
                  rows=[dict(id=r['id'],text_hash=r['text_hash'],
                             baseline_score=predictions[r['id']]['model_score'],
                             baseline_label='toxic' if predictions[r['id']]['model_score']>=.5 else 'non-toxic',
                             candidate_score=float(p),candidate_label='toxic' if p>=threshold else 'non-toxic')
                        for r,p in zip(validation,probs)])
    assert sha(SOURCE)==source_sha and sha(WORKSPACE)==workspace_sha
    OUT.mkdir(parents=True,exist_ok=True)
    atomic_json(OUT/'frozen_predictions.json',frozen)
    manifest['frozen_predictions_sha256']=sha(OUT/'frozen_predictions.json')
    atomic_json(manifest_path,manifest)
    return dict(development=len(selected),validation=len(validation),reserved_posts=len(reserved_posts),
                selection_reasons=dict(Counter(selection_reason.values())),
                fresh_pool_rows=len(fresh),fresh_pool_posts=manifest['fresh_pool_posts'])


def inspect_round(workbook=None):
    result=read_review(workbook or OUT/'Gan_nhan_bo_sung_va_kiem_chung.xlsx',OUT/'review_manifest.json',SOURCE)
    if result['issues']:
        raise ValueError(json.dumps(result['issues'],ensure_ascii=True))
    return result


def assert_training_posts_allowed(rows):
    """Fail closed if reserved validation posts enter training or retrieval examples."""
    path=OUT/'review_manifest.json'
    if not path.exists():
        return
    manifest=load(path)
    if sha(SOURCE)!=manifest['source_sha256']:
        raise ValueError('Source changed; reconcile validation reservation before training')
    reserved=set(manifest['reserved_post_ids'])
    if any(str(r['post_id']) in reserved for r in rows):
        raise ValueError('Reserved validation post cannot be used for training or retrieval')


def export_development(workbook=None):
    result=inspect_round(workbook)
    rows=[r for r in result['rows'] if r['review_cell'].startswith('Bo_sung_60!')]
    if not rows:
        raise ValueError('No human development labels; blanks are never non-toxic')
    assert_training_posts_allowed(rows)
    # Validation labels deliberately remain inside the workbook, outside manual_review glob.
    output=Path('data/manual_review/round2_development_20261031.json')
    if output.exists():
        raise ValueError('Development export already exists; reconcile changes explicitly')
    atomic_json(output,dict(policy_version=POLICY,source_sha256=result['source_sha256'],
                           workbook_sha256=result['workbook_sha256'],role='development',rows=rows))
    return dict(exported_development=len(rows),validation_imported=0)


def evaluate_frozen(workbook=None):
    output=OUT/'frozen_evaluation.json'
    if output.exists():
        raise ValueError('Validation already opened; further runs are historical diagnostics')
    manifest=load(OUT/'review_manifest.json')
    if sha(OUT/'frozen_predictions.json')!=manifest['frozen_predictions_sha256']:
        raise ValueError('Frozen predictions changed')
    result=inspect_round(workbook)
    gold={r['id']:r for r in result['rows'] if r['review_cell'].startswith('Kiem_chung_200!')}
    if set(gold)!={r['id'] for r in manifest['others']}:
        raise ValueError('Validation incomplete: every one of 200 rows needs t/n; unresolved rows cannot be dropped')
    frozen=load(OUT/'frozen_predictions.json')
    from hybrid_labeling import metrics
    rows=frozen['rows']
    if len(rows)!=200 or {r['id'] for r in rows}!=set(gold):
        raise ValueError('Prediction/gold coverage differs')
    if any(r['text_hash']!=gold[r['id']]['text_hash'] for r in rows):
        raise ValueError('Prediction/gold text differs')
    y=np.array([gold[r['id']]['reference_label']=='toxic' for r in rows])
    report=dict(policy_version=POLICY,scope=manifest['validation_scope'],
                workbook_sha256=result['workbook_sha256'],frozen_predictions_sha256=manifest['frozen_predictions_sha256'],
                toxic_count=int(y.sum()),non_toxic_count=int((~y).sum()),
                baseline=metrics(y,np.array([r['baseline_label']=='toxic' for r in rows])),
                candidate=metrics(y,np.array([r['candidate_label']=='toxic' for r in rows])),
                deployment_approved=False,
                limitations='One annotator, new-post subset. Report toxic support; no claim of 100 percent or automatic deployment. After opening, this set is historical and cannot validate later tuning.')
    atomic_json(output,report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','check','export-development','evaluate-frozen'])
    p.add_argument('--workbook',type=Path)
    args=p.parse_args()
    if args.action=='prepare': result=prepare_round()
    elif args.action=='check':
        full=inspect_round(args.workbook)
        result={k:v for k,v in full.items() if k!='rows'}
    elif args.action=='export-development': result=export_development(args.workbook)
    else: result=evaluate_frozen(args.workbook)
    print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__': main()
