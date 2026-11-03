"""Offline experiment: grouped validation and a fixed post-level holdout, never writes workspace."""
import json, hashlib
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import joblib

OUT=Path('data/label_audit/learned_review');OUT.mkdir(parents=True,exist_ok=True)

def metrics(y,p):
 return dict(n=len(y),accuracy=accuracy_score(y,p),precision=precision_score(y,p,zero_division=0),recall=recall_score(y,p,zero_division=0),macro_f1=f1_score(y,p,average='macro',zero_division=0),confusion_matrix=confusion_matrix(y,p,labels=[0,1]).tolist())

def make_model(c,balanced):
 return Pipeline([('text',FeatureUnion([('char',TfidfVectorizer(analyzer='char',ngram_range=(2,5),min_df=2,sublinear_tf=True,max_features=40000)),('word',TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,max_features=15000))])),('classifier',LogisticRegression(C=c,class_weight='balanced' if balanced else None,max_iter=1500,random_state=430))])

def main():
 ref=json.loads(Path('data/manual_review/excel_review_20261030.json').read_text(encoding='utf-8'));rows=sorted(ref['rows'],key=lambda r:r['id'])
 from review_round import assert_training_posts_allowed
 assert_training_posts_allowed(rows)
 pred={r['id']:r for r in json.loads(Path('data/label_audit/full_corpus/predictions.json').read_text(encoding='utf-8-sig'))}
 manifest=json.loads(Path('outputs/label_review_20261030/review_manifest.json').read_text(encoding='utf-8'))
 contexts={r['id']:r['context'] for r in manifest['priority']}
 y=np.array([int(r['reference_label']=='toxic') for r in rows]);groups=np.array([r['post_id'] for r in rows]);scores=np.array([pred[r['id']]['model_score'] for r in rows])
 assert all(pred[r['id']]['text_hash']==r['text_hash'] for r in rows)
 text=np.array([r['text_raw'] for r in rows]);ctx=np.array([r['text_raw']+' [PARENT_CONTEXT] '+contexts[r['id']] for r in rows])
 dev,test=next(StratifiedGroupKFold(n_splits=4,shuffle=True,random_state=430).split(text,y,groups))
 assert not set(groups[dev]) & set(groups[test])
 folds=list(StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=431).split(text[dev],y[dev],groups[dev]))
 trials=[]
 for use_context in [False,True]:
  x=ctx if use_context else text
  for c in [0.5,2,8]:
   for balanced in [False,True]:
    oof=np.zeros(len(dev))
    for tr,va in folds:
     model=make_model(c,balanced);model.fit(x[dev[tr]],y[dev[tr]]);oof[va]=model.predict_proba(x[dev[va]])[:,1]
    for threshold in [0.3,0.4,0.5,0.6,0.7]:
     trials.append(dict(context=use_context,C=c,balanced=balanced,threshold=threshold,macro_f1=f1_score(y[dev],oof>=threshold,average='macro',zero_division=0)))
 best=max(trials,key=lambda r:r['macro_f1']);x=ctx if best['context'] else text
 model=make_model(best['C'],best['balanced']);model.fit(x[dev],y[dev]);p=model.predict_proba(x[test])[:,1]
 # Threshold-only baseline is selected on development labels, never on holdout.
 threshold=max(np.arange(.05,1,.025),key=lambda t:f1_score(y[dev],scores[dev]>=t,average='macro',zero_division=0))
 result=dict(scope='450 difficult user-reviewed comments; not representative overall corpus accuracy',reference_sha256=hashlib.sha256(Path('data/manual_review/excel_review_20261030.json').read_bytes()).hexdigest(),split='fixed seed 430; post-group holdout; inner grouped CV seed 431',dev_n=len(dev),holdout_n=len(test),dev_toxic=int(y[dev].sum()),holdout_toxic=int(y[test].sum()),selected=best,original=metrics(y[test],scores[test]>=.5),threshold_baseline=dict(threshold=float(threshold),metrics=metrics(y[test],scores[test]>=threshold)),candidate=metrics(y[test],p>=best['threshold']),holdout_ids=[rows[i]['id'] for i in test],development_ids=[rows[i]['id'] for i in dev],trials=trials)
 result['promote']=result['candidate']['macro_f1']>max(result['original']['macro_f1'],result['threshold_baseline']['metrics']['macro_f1']) and result['candidate']['recall']>=result['original']['recall']
 joblib.dump(model,OUT/'candidate.joblib');(OUT/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ('trials','holdout_ids','development_ids')}))

if __name__=='__main__':main()
