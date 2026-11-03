"""Read-only diagnostic of frozen local predictions against current human labels."""
import json,hashlib,math
from pathlib import Path
from collections import Counter
import numpy as np,joblib
from dataset import prepare,atomic_json
from labeling import automatic_annotation,MODEL_ID,REVISION,valid_file,FILES
from hybrid_labeling import metrics
out=Path('outputs/label_evaluation_v32_20261031');load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source_sha=sha('data/progress.json');workspace_sha=sha('data/workspace.json');canonical_path=Path('data/manual_review/canonical_development_v32_20261031.json');canonical=load(canonical_path)
assert canonical['source_sha256']==source_sha and canonical['workspace_sha256']==workspace_sha
raw=load('data/progress.json');source={r['id']:r for r in prepare(raw['rows']) if r['quality']=='ready'};preds=load('data/label_audit/full_corpus/predictions.json');pred={r['id']:r for r in preds};assert len(pred)==len(source)==5111
manifest=load('outputs/label_review_20261031/review_manifest.json');reserved=set(map(str,manifest['reserved_post_ids']))
dev=canonical['rows'];assert all(str(r['post_id']) not in reserved for r in dev)
prior=load('outputs/assistant_review_20261031/user_resolutions_20261031.json')['validation_rows'];recent=load('outputs/user_review_435_20261031/reserved_post_user_labels.json')['rows']
hold=[]
for r in prior+recent:
 label=r.get('reference_label',r.get('label'));assert r['human_verified'] is True and label in ['toxic','non-toxic'] and str(r['post_id']) in reserved
 hold.append(dict(r,reference_label=label,text_raw=r.get('text_raw',r.get('comment'))))
assert len({r['id'] for r in hold})==len(hold)
allrows=dev+hold;assert len({r['id'] for r in allrows})==len(allrows)
old=load('outputs/label_review_20261030/review_manifest.json');contexts={r['id']:r['context'] for r in old['priority']+old['others']}
parents={(str(r.get('post_id')),str(r.get('comment_id'))):r.get('text_raw','') for r in raw['rows']}
for r in source.values():
 if r['id'] not in contexts:contexts[r['id']]='Bình luận cha: '+parents.get((str(r['post_id']),str(r.get('parent_comment_id'))),'[Không có bình luận cha được ghi nhận]')+'; [Nội dung bài gốc chưa được thu thập]' 
frozen=load('outputs/label_review_20261031/frozen_predictions.json');candidate_path=Path('data/label_audit/hybrid_v31/candidate.joblib');assert sha(candidate_path)==frozen['model_sha256'];assert not {str(source[i]['post_id']) for i in frozen['training_ids']} & reserved
candidate=joblib.load(candidate_path)
# Candidate was previously fitted; no fitting, parameter search or threshold tuning here.
x=np.array([dict(text_raw=r['text_raw'],context=contexts[r['id']],score=pred[r['id']]['model_score']) for r in hold],dtype=object);prob=candidate.predict_proba(x)[:,1]
hybrid={r['id']:float(p) for r,p in zip(hold,prob)}
rows=[]
for r in allrows:
 p=pred[r['id']];s=source[r['id']];assert r['human_verified'] is True and r['text_hash']==s['text_hash']==p['text_hash'];assert r['text_raw']==s['text_raw'];assert p['model']==MODEL_ID and p['revision']==REVISION
 ann=automatic_annotation(p,s['text_raw']);guess=ann['label'];row=dict(id=r['id'],post_id=str(r['post_id']),text_hash=r['text_hash'],comment=r['text_raw'],context=contexts[r['id']],reference_label=r['reference_label'],predicted_label=guess,model_score=p['model_score'],needs_review=ann['needs_review'],review_reason=ann['review_reason'],correct=guess==r['reference_label'],partition='reserved_post_diagnostic' if str(r['post_id']) in reserved else 'development_diagnostic',human_verified=True)
 if r['id'] in hybrid:row.update(old_candidate_score=hybrid[r['id']],old_candidate_label='toxic' if hybrid[r['id']]>=frozen['threshold'] else 'non-toxic')
 rows.append(row)
def wilson(k,n):
 if not n:return None
 z=1.95996398454;d=1+z*z/n;mid=(k/n+z*z/(2*n))/d;half=z*math.sqrt((k/n*(1-k/n)+z*z/(4*n))/n)/d;return [mid-half,mid+half]
def summarize(rs,field='predicted_label'):
 y=np.array([r['reference_label']=='toxic' for r in rs]);p=np.array([r[field]=='toxic' for r in rs]);m=metrics(y,p);m.update(toxic_support=int(y.sum()),non_toxic_support=int((~y).sum()),correct=int((y==p).sum()),accuracy_wilson95=wilson(int((y==p).sum()),len(rs)),toxic_recall_wilson95=wilson(int((y&p).sum()),int(y.sum())))
 if field=='predicted_label':
  flagged=[r for r in rs if r['needs_review']];unflagged=[r for r in rs if not r['needs_review']];errors=[r for r in rs if not r['correct']];m['review_routing']=dict(flagged=len(flagged),unflagged=len(unflagged),errors_flagged=sum(r['needs_review'] for r in errors),errors_unflagged=sum(not r['needs_review'] for r in errors),unflagged_accuracy=None if not unflagged else sum(r['correct'] for r in unflagged)/len(unflagged))
 return m
holdrows=[r for r in rows if r['partition']=='reserved_post_diagnostic'];devrows=[r for r in rows if r['partition']=='development_diagnostic'];frozen_ids={r['id'] for r in frozen['rows']};subset=[r for r in holdrows if r['id'] in frozen_ids]
for r in subset:
 f=next(f for f in frozen['rows'] if f['id']==r['id']);assert abs(r['old_candidate_score']-f['candidate_score'])<1e-10
model_assets={name:valid_file(Path('models/vietnamese-toxicity')/name,size,digest) for name,(size,digest) in FILES.items()}
report=dict(policy_version='ptit-v3.2-friendly-banter-20261031',method='Frozen predictions and previously trained candidate, no fit or threshold tuning; only user-confirmed labels',source_sha256=source_sha,workspace_sha256=workspace_sha,canonical_sha256=sha(canonical_path),baseline_predictions_sha256=sha('data/label_audit/full_corpus/predictions.json'),candidate_sha256=sha(candidate_path),model_assets=model_assets,total_human=len(rows),development=summarize(devrows),reserved_posts=summarize(holdrows),all_human_diagnostic=summarize(rows),old_candidate_reserved=summarize(holdrows,'old_candidate_label'),frozen_200_human_labeled=len(subset),frozen_200_unlabeled=200-len(subset),no_training_post_overlap=True,no_source_or_workspace_changes=sha('data/progress.json')==source_sha and sha('data/workspace.json')==workspace_sha,new_training=False,deployment_approved=False,limitations=['Human rows selected for difficult cases; not representative corpus accuracy.','Human labels were reviewed with AI assistance, not a fresh blind independent test.','Only part of the fixed 200-row validation sample has human labels. Do not fill others with AI labels.','Reserved diagnostic has small toxic support.','Old candidate uses v3.1 training, evaluated diagnostically against current v3.2 labels.'])
atomic_json(out/'evaluation.json',report);atomic_json(out/'predictions_vs_human.json',dict(rows=rows));atomic_json(out/'errors.json',dict(rows=[r for r in rows if not r['correct']]))
print(json.dumps(report,ensure_ascii=False,indent=2))
