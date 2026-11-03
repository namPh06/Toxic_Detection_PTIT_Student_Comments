import json,hashlib
from pathlib import Path
from dataset import prepare,text_hash,atomic_json
from context_labeling import context_for
source=Path('data/progress.json'); content=source.read_bytes(); raw=json.loads(content.decode('utf-8-sig'))
ready=[r for r in prepare(raw['rows']) if r['quality']=='ready']
confirmed={}
for p in Path('data/manual_review').glob('*.json'):
 d=json.loads(p.read_text(encoding='utf-8'))
 for r in d.get('rows',[]):
  if r.get('human_verified') and r.get('reference_label') in ('toxic','non-toxic'):
   if r['id'] in confirmed and confirmed[r['id']]['reference_label']!=r['reference_label']: raise ValueError('Conflicting confirmed labels')
   confirmed[r['id']]=r
preds={r['id']:r for r in json.loads(Path('data/label_audit/full_corpus/machine_labels.json').read_text(encoding='utf-8'))['rows']}
semantic={}
for filename in ['context_diagnostic10.json','context_priority5.json']:
 for r in json.loads((Path('data/label_audit')/filename).read_text(encoding='utf-8'))['rows']: semantic[r['id']]=r
priority=[]; others=[]
for r in ready:
 if r['id'] in confirmed:
  assert confirmed[r['id']]['text_hash']==r['text_hash']; continue
 m=preds.get(r['id']); reasons=[]
 if not m or m['text_hash']!=r['text_hash']: reasons.append('Chưa có dự đoán khớp văn bản')
 elif m.get('needs_review'): reasons.append('Mô hình đánh dấu cần duyệt')
 s=semantic.get(r['id'])
 if s and (s.get('decision')=='uncertain' or s.get('error')): reasons.append('Bộ xét ngữ cảnh chưa kết luận')
 elif s and m and s.get('decision')!=m.get('label'): reasons.append('Hai mô hình bất đồng')
 context=context_for(r,raw['rows'],raw.get('posts',[]))
 if context['parent_status'] in ('missing_parent','cycle','depth_limit'): reasons.append('Thiếu hoặc không nối được đầy đủ bình luận cha')
 parent=chr(10).join(p['text_raw'] for p in context['parents']) or ('Không tìm thấy bình luận cha.' if context['parent_status']=='missing_parent' else 'Không có bình luận cha được ghi nhận.')
 entry=dict(id=r['id'],text_hash=r['text_hash'],comment=r['text_raw'],context=parent+chr(10)+'[Nội dung bài viết chưa có trong dữ liệu.]',reason='; '.join(reasons) if reasons else 'Chưa được người đọc xác nhận; điểm mô hình ngoài vùng chưa chắc chắn')
 (priority if reasons else others).append(entry)
result=dict(source_sha256=hashlib.sha256(content).hexdigest(),policy_version='ptit-v2-context-20261030',confirmed_excluded=len(confirmed),total_ready=len(ready),priority=priority,others=others)
assert len(priority)+len(others)+len(confirmed)==len(ready)
atomic_json(Path('outputs/label_review_20261030/review_manifest.json'),result)
print(json.dumps(dict(priority=len(priority),others=len(others),confirmed=len(confirmed),total=len(ready),max_comment=max(len(r['comment']) for r in priority+others)),ensure_ascii=True))
