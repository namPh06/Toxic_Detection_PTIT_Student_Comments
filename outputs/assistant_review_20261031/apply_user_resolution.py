import json,hashlib,socket
from pathlib import Path
from datetime import datetime,timezone
from lab import Lab
from dataset import atomic_json,prepare
p=Path('outputs/assistant_review_20261031'); r=json.loads((p/'latest_user_review.json').read_text(encoding='utf-8')); assert not r['issues']
f=p/'Ket_qua_gan_nhan_va_ra_soat.xlsx'; assert hashlib.sha256(f.read_bytes()).hexdigest()==r['workbook_sha256']
rawpath=Path('data/progress.json'); raw=rawpath.read_bytes(); assert hashlib.sha256(raw).hexdigest()=='e478f195be50d8fd842f22e49c2b4d19f54563d3c00d4b30a6b180f1f006df00'
s=socket.socket(); assert s.connect_ex(('127.0.0.1',8767))!=0,'Running application; use live API';s.close()
wp=Path('data/workspace.json'); before=wp.read_bytes(); backup=p/'workspace_before_user_resolution.json'; assert not backup.exists(),'Resolution already applied; inspect history';backup.write_bytes(before)
lab=Lab(Path('data'),lambda:json.loads(raw)['rows']); annotations=dict(lab.annotations); previous=json.loads(before)['annotations']; idx={x['id']:x for x in lab.rows()}; resolved=[]; validation=[];changes=0
for row in r['rows']:
 if not row['label']:continue
 assert idx[row['id']]['text_hash']==row['text_hash']
 entry=dict(row,human_verified=True,review_method='user_excel_after_assistant_proposal',policy_version='ptit-v3.2-friendly-banter-20261031',workbook_sha256=r['workbook_sha256'],rationale='User selected t/n; no per-comment friendly-banter rationale supplied')
 if row['id'] not in previous:
  validation.append(entry);continue
 old=previous[row['id']];changes+=old['label']!=row['label']; annotations[row['id']]=dict(old,label=row['label'],label_source='manual',updated_at=datetime.now(timezone.utc).isoformat(),note=old.get('note','')+' | User reconfirmed '+row['review_cell']+'; see user_resolutions_20261031.json')
 entry['previous_label']=old['label']; resolved.append(entry)
assert len(resolved)==82 and len(validation)==11 and changes==15
assert wp.read_bytes()==before
lab.save_workspace(annotations,lab.imported,lab.suggestions)
atomic_json(p/'user_resolutions_20261031.json',dict(rows=resolved,validation_rows=validation,pending=[x for x in r['rows'] if not x['label']],policy_version='ptit-v3.2-friendly-banter-20261031'))
now=json.loads(wp.read_text(encoding='utf-8')); changed={x['id'] for x in resolved};assert all(now['annotations'][i]==v for i,v in previous.items() if i not in changed)
assert all(now['annotations'][x['id']]['label']==x['label'] for x in resolved)
assert len(now['annotations'])==536 and sum(x['label']=='toxic' for x in now['annotations'].values())==85
assert rawpath.read_bytes()==raw and hashlib.sha256(f.read_bytes()).hexdigest()==r['workbook_sha256']
report=dict(human_workspace=536,toxic=85,non_toxic=451,reconfirmed=82,changed_labels=15,human_validation_kept_separate=11,pending=1,source_unchanged=True,workbook_unchanged=True,untouched_labels_preserved=True)
atomic_json(p/'user_resolution_verification.json',report);print(json.dumps(report))
