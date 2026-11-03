"""Commit complete v4 results only after validating snapshot and provenance."""
import json, hashlib
from pathlib import Path
from collections import Counter
from dataset import prepare, atomic_json, csv_bytes, text_hash, LABELS, summary
from relabel_v4 import ROOT, OUT, POLICY, MODEL, load, now

def main():
 snap=load(OUT/'snapshot.json'); status=load(OUT/'status.json')
 if not status.get('classification_complete'):raise ValueError('Classification is not complete')
 decisions={d['id']:d for d in map(json.loads,(OUT/'decisions.jsonl').read_text(encoding='utf-8').splitlines())}
 assert set(decisions)=={r['id'] for r in snap['rows']}
 if (OUT/'applied.json').exists():return
 for name,digest in snap['input_hashes'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed during classification: '+name)
 failed=sum(d.get('method')=='inference_failure' for d in decisions.values())
 if failed>max(3,len(decisions)//100):raise ValueError('Too many invalid model answers; refusing to apply')
 ws=load(OUT/'before_workspace.json'); raw=load(OUT/'before_progress.json'); annotations={}; audit=[]
 for r in snap['rows']:
  d=decisions[r['id']]; assert d['text_hash']==r['text_hash']; label=d['label'] if d['label'] in LABELS else ''
  annotations[r['id']]=dict(label=label,excluded=not bool(label),text_hash=r['text_hash'],label_source='automatic',note=('v4: '+d['reason'])[:2000],updated_at=now(),label_model='ollama/'+MODEL,label_revision=POLICY,model_score=None,label_threshold=None,needs_review=bool(label),review_reason='unverified_v4_semantic',human_verified=False)
  audit.append(dict(id=r['id'],text_raw=r['text_raw'],old_label=r['label'],old_source=r['label_source'],new_label=label or 'uncertain',reason=d['reason'],evidence=d['evidence']))
 context_rows={(str(r['post_id']),str(r['comment_id'])):r for r in snap['rows']}
 for r in load(OUT/'before_parent_context.json').get('rows',[]):
  if r.get('identity_verified') and r.get('text_raw'):context_rows.setdefault((str(r['post_id']),str(r['comment_id'])),r)
 def updated(r):
  from dataset import row_id
  a=annotations[row_id(r)];r=dict(r);p=snap['posts'].get(str(r['post_id']),{})
  r['post_text_raw']=r.get('post_text_raw') or p.get('post_text_raw') or p.get('text_raw') or ''
  if not r.get('parent_context'):
   parents=[];current=r;seen=set()
   for _ in range(8):
    key=(str(r['post_id']),str(current.get('parent_comment_id') or ''))
    if key in seen or key not in context_rows:break
    seen.add(key);current=context_rows[key];parents.insert(0,dict(comment_id=current['comment_id'],text_raw=current['text_raw'],context_only=True))
   r['parent_context']=parents
  return dict(r,label=a['label'],excluded=a['excluded'],label_source='automatic' if a['label'] else '',label_revision=POLICY,label_model=a['label_model'],model_score=None,label_threshold=None,needs_review=a['needs_review'],review_reason=a['review_reason'],annotation_note=a['note'],human_verified=False)
 raw['rows']=[updated(r) for r in raw['rows']]; imported=[updated(r) for r in ws.get('imported',[])]
 rows=prepare(raw['rows']+imported,annotations)
 usable=[r for r in rows if r['quality']=='ready' and r['label'] in LABELS]
 excluded=[r for r in rows if r['quality']!='ready']
 assert len(rows)==len(snap['rows']) and len(usable)+len(excluded)==len(rows)
 assert all(r['label_source']=='automatic' and r['label_revision']==POLICY and not r['excluded'] for r in usable)
 # Write reviewable products before replacing active workspace.
 for name,content in [('dataset_v4',usable),('excluded_v4',excluded)]:
  atomic_json(OUT/(name+'.json'),dict(policy_version=POLICY,human_verified=False,rows=content)); (OUT/(name+'.csv')).write_bytes(csv_bytes(content))
 atomic_json(OUT/'audit.json',dict(policy_version=POLICY,rows=audit))
 # Uncertain/conflicting/invalid rows leave active sources; originals stay in snapshot/archive.
 active_ids={r['id'] for r in rows if r['label'] in LABELS and r['quality'] in ('ready','duplicate')}
 from dataset import row_id
 raw['rows']=[r for r in raw['rows'] if row_id(r) in active_ids];raw['label_policy_version']=POLICY
 imported=[r for r in imported if row_id(r) in active_ids]
 annotations={k:v for k,v in annotations.items() if k in active_ids}
 active_rows=prepare(raw['rows']+imported,annotations)
 assert {r['id'] for r in active_rows}==active_ids
 atomic_json(ROOT/'data/progress.json',raw)
 atomic_json(ROOT/'data/workspace.json',dict(schema_version=1,annotations=annotations,imported=imported,suggestions={}))
 atomic_json(ROOT/'data/processed.json',dict(policy_version=POLICY,rows=active_rows)); (ROOT/'data/processed.csv').write_bytes(csv_bytes(active_rows))
 atomic_json(ROOT/'data/dataset_auto.json',dict(policy_version=POLICY,label_policy='includes_automatic',human_verified=False,rows=usable)); (ROOT/'data/dataset_auto.csv').write_bytes(csv_bytes(usable))
 # This contextual crawl derivative must carry the same labels.
 p=ROOT/'data/progress_with_context.json'
 if p.exists():
  old=load(p); (OUT/'before_progress_with_context.json').write_bytes(p.read_bytes())
  from dataset import row_id
  if isinstance(old,dict) and isinstance(old.get('rows'),list):
   old['rows']=[updated(r) for r in old['rows'] if row_id(r) in active_ids];old['policy_version']=POLICY;atomic_json(p,old)
 stats=summary(rows);counts=Counter(r['label'] for r in usable)
 result=dict(completed_at=now(),policy_version=POLICY,total=len(rows),active=len(active_rows),removed_from_active=len(rows)-len(active_rows),usable=len(usable),labels=dict(counts),quality=stats['quality'],changed=sum(a['old_label']!=a['new_label'] and a['new_label']!='uncertain' for a in audit),human_verified=False)
 atomic_json(OUT/'applied.json',result)
 (OUT/'KET_QUA.md').write_text('# Kết quả gán lại v4\n\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n\nNhãn được mô hình cục bộ gán tự động, chưa phải bộ nhãn chuẩn do người duyệt. Tệp dataset_v4 chỉ chứa mẫu dùng được; excluded_v4 lưu các mẫu bị loại và lý do. Mô hình NB/SVM và đánh giá cũ cần chạy lại với ranh giới chia tập mới.\n',encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
