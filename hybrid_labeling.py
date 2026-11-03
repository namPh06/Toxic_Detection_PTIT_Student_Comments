"""V3.1 offline hybrid experiment. Frozen historical holdout; never edits labels/workspace."""
import hashlib,json
from pathlib import Path
import joblib
import numpy as np
from scipy.sparse import hstack,csr_matrix
from sklearn.base import BaseEstimator,TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,confusion_matrix

POLICY='ptit-v3.1-school-feedback-20261030'
OUT=Path('data/label_audit/hybrid_v31')
class HybridFeatures(BaseEstimator,TransformerMixin):
 def __init__(self,context=True,score_weight=1):self.context=context;self.score_weight=score_weight
 def strings(self,x):return [r['text_raw']+(' [PARENT] '+r['context'] if self.context else '') for r in x]
 def fit(self,x,y=None):
  self.char=TfidfVectorizer(analyzer='char',ngram_range=(2,5),min_df=2,sublinear_tf=True,max_features=40000)
  self.word=TfidfVectorizer(ngram_range=(1,2),min_df=1,sublinear_tf=True,max_features=15000)
  text=self.strings(x);self.char.fit(text);self.word.fit(text);return self
 def transform(self,x):
  text=self.strings(x);s=np.clip([r['score'] for r in x],.001,.999)
  # Fixed scaling, not fitted on held-out labels or texts.
  extra=csr_matrix((self.score_weight*np.log(s/(1-s))/5).reshape(-1,1))
  return hstack([self.char.transform(text),self.word.transform(text),extra]).tocsr()

def model(c,context,weight):return Pipeline([('features',HybridFeatures(context,weight)),('classifier',LogisticRegression(C=c,class_weight='balanced',max_iter=1500,random_state=431))])
def metrics(y,p):return dict(n=len(y),accuracy=accuracy_score(y,p),precision=precision_score(y,p,zero_division=0),recall=recall_score(y,p,zero_division=0),macro_f1=f1_score(y,p,average='macro',zero_division=0),confusion_matrix=confusion_matrix(y,p,labels=[0,1]).tolist())
def run():
 OUT.mkdir(parents=True,exist_ok=True)
 refpath=Path('data/manual_review/excel_review_20261030.json');refbytes=refpath.read_bytes();rows=json.loads(refbytes)['rows']
 old=json.loads(Path('data/label_audit/learned_review/evaluation.json').read_text(encoding='utf-8'))
 preds={r['id']:r for r in json.loads(Path('data/label_audit/full_corpus/predictions.json').read_text(encoding='utf-8-sig'))}
 manifest=json.loads(Path('outputs/label_review_20261030/review_manifest.json').read_text(encoding='utf-8'));contexts={r['id']:r['context'] for r in manifest['priority']}
 idx={r['id']:r for r in rows};dev=[idx[i] for i in old['development_ids']];test=[idx[i] for i in old['holdout_ids']]
 from review_round import assert_training_posts_allowed
 assert_training_posts_allowed(dev)
 assert len(dev)+len(test)==len(rows)==450
 assert not {r['post_id'] for r in dev}&{r['post_id'] for r in test}
 for r in rows:assert r['human_verified'] is True and r['text_hash']==preds[r['id']]['text_hash']
 def features(rs):return np.array([dict(text_raw=r['text_raw'],context=contexts[r['id']],score=preds[r['id']]['model_score']) for r in rs],dtype=object)
 x=features(dev);y=np.array([r['reference_label']=='toxic' for r in dev]);groups=np.array([r['post_id'] for r in dev]);folds=list(StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=431).split(x,y,groups))
 minimum_recall=recall_score(y,np.array([r['score'] for r in x])>=.5)
 trials=[]
 for context in [False,True]:
  for weight in [0,1,3]:
   for c in [.5,2,8]:
    oof=np.zeros(len(dev))
    for tr,va in folds:
     assert not set(groups[tr])&set(groups[va])
     m=model(c,context,weight);m.fit(x[tr],y[tr]);oof[va]=m.predict_proba(x[va])[:,1]
    for threshold in [.15,.2,.25,.3,.35,.4,.45,.5,.6,.7]:
     met=metrics(y,oof>=threshold);trials.append(dict(C=c,context=context,score_weight=weight,threshold=threshold,metrics=met))
 eligible=[t for t in trials if t['metrics']['recall']>=minimum_recall]
 best=max(eligible,key=lambda t:(t['metrics']['macro_f1'],t['metrics']['precision']))
 m=model(best['C'],best['context'],best['score_weight']);m.fit(x,y)
 xt=features(test);yt=np.array([r['reference_label']=='toxic' for r in test]);prob=m.predict_proba(xt)[:,1];guess=prob>=best['threshold']
 baseline=metrics(yt,np.array([r['score'] for r in xt])>=.5);candidate=metrics(yt,guess)
 result=dict(policy_version=POLICY,reference_sha256=hashlib.sha256(refbytes).hexdigest(),source_sha256=hashlib.sha256(Path('data/progress.json').read_bytes()).hexdigest(),scope='450 selected difficult comments; historical holdout previously inspected, not fresh independent validation',split_origin='Frozen IDs from learned_review/evaluation.json; never regenerated after label changes',development_ids=old['development_ids'],holdout_ids=old['holdout_ids'],development_n=len(dev),holdout_n=len(test),development_toxic=int(y.sum()),holdout_toxic=int(yt.sum()),minimum_development_recall=float(minimum_recall),selected=best,baseline=baseline,candidate=candidate,trials=trials)
 result['improved_on_historical_holdout']=candidate['macro_f1']>baseline['macro_f1'] and candidate['recall']>=baseline['recall'] and candidate['precision']>=baseline['precision']
 result['deployment_approved']=False;result['deployment_reason']='Requires fresh independent representative validation; no production change.'
 result['predictions']=[dict(id=r['id'],text_hash=r['text_hash'],reference_label=r['reference_label'],predicted_label='toxic' if g else 'non-toxic',score=float(p)) for r,g,p in zip(test,guess,prob)]
 assert refpath.read_bytes()==refbytes
 joblib.dump(m,OUT/'candidate.joblib');(OUT/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ['development_ids','holdout_ids','trials','predictions']}),flush=True)
 return result
if __name__=='__main__':run()
