import json,hashlib,zipfile,xml.etree.ElementTree as E,posixpath,shutil
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from dataset import atomic_json
out=Path('outputs/user_corrections_5_20261031');book=Path('outputs/remaining_semantic_review_20261031/Ra_soat_4275_cau.xlsx');load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def read(path):
 with zipfile.ZipFile(path) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(t.text or '' for t in e.iter('{'+ns['s']+'}t')) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
  rel={r.get('Id'):r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))};result={};features={}
  for sh in E.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',ns):
   target=rel[sh.get('{'+ns['r']+'}id')];loc=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target);root=E.fromstring(z.read(loc));cells={}
   for c in root.findall('s:sheetData/s:row/s:c',ns):
    v=c.find('s:v',ns);value='' if v is None else v.text or ''
    if c.get('t')=='s':value=shared[int(value)]
    if c.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.iter('{'+ns['s']+'}t'))
    f=c.find('s:f',ns)
    if value or f is not None:cells[c.get('r')]=(value,None if f is None else f.text)
   result[sh.get('name')]=cells
   features[sh.get('name')]={'tables':len(root.findall('s:tableParts/s:tablePart',ns)),'validation':[(x.get('sqref'),x.get('type'),x.findtext('s:formula1',default='',namespaces=ns)) for x in root.findall('s:dataValidations/s:dataValidation',ns)],'panes':[dict(x.attrib) for x in root.findall('s:sheetViews/s:sheetView/s:pane',ns)]}
 return result,features
# Restore native sheet view metadata unsupported by artifact export (scroll position).
with zipfile.ZipFile(out/'workbook_before.xlsx') as original,zipfile.ZipFile(out/'corrected.xlsx') as exported:
 payload={i.filename:(i,exported.read(i.filename)) for i in exported.infolist()}
 for name in list(payload):
  if name.startswith('xl/worksheets/sheet') and name.endswith('.xml') and name in original.namelist():
   import re
   oldxml=original.read(name);info,newxml=payload[name]
   pattern=rb'<(?:\w+:)?sheetViews\b[\s\S]*?</(?:\w+:)?sheetViews>'
   match=re.search(pattern,oldxml)
   if match and re.search(pattern,newxml):newxml=re.sub(pattern,lambda _:E.tostring(E.fromstring(oldxml).find('s:sheetViews',ns),encoding='utf-8'),newxml,count=1)
   payload[name]=(info,newxml)
with zipfile.ZipFile(out/'native_preserved.xlsx','w',zipfile.ZIP_DEFLATED) as z:
 for info,data in payload.values():z.writestr(info,data)
shutil.copyfile(out/'native_preserved.xlsx',out/'corrected.xlsx')
before,bf=read(out/'workbook_before.xlsx');after,af=read(out/'corrected.xlsx');assert list(before)==list(after)
changes=[]
for sh in before:
 for cell in set(before[sh])|set(after[sh]):
  if before[sh].get(cell)!=after[sh].get(cell):changes.append((sh,cell,before[sh].get(cell),after[sh].get(cell)))
expected={'B68','B81','B85','B113','B122'}
assert len(changes)==5 and {c[1] for c in changes}==expected and all(c[0]=='Can_bo_sung_435' and c[2]==('n',None) and c[3]==('t',None) for c in changes),changes
assert bf==af,{'before':bf,'after':af}
assert sha(book)==sha(out/'workbook_before.xlsx'),'Workbook changed externally; do not overwrite'
paths=['data/workspace.json','data/manual_review/canonical_development_v32_20261031.json','outputs/user_review_435_20261031/user_labels.json','outputs/user_review_435_20261031/needs_clarification.json']
for i,p in enumerate(paths):
 dest=out/(str(i)+'_'+Path(p).name)
 if dest.exists():
  assert sha(dest)==sha(p),'Data changed since backup; stop'
 else:shutil.copyfile(p,dest)
w=load(paths[0]);canonical=load(paths[1]);labels=load(paths[2]);flags=load(paths[3]);assert len(flags['rows'])==5
now=datetime.now(timezone.utc).isoformat();byid={r['id']:r for r in labels['rows']};existing={r['id'] for r in canonical['rows']};resolved=[]
for r in flags['rows']:
 rid=r['id'];a=w['annotations'][rid];assert a['text_hash']==r['text_hash'] and a['label']=='non-toxic' and a['excluded']
 a.update(label='toxic',excluded=False,review_status='user_confirmed',human_verified=True,updated_at=now,note='Human-confirmed correction in chat 31/10/2026: all five flagged comments are toxic. Ra_soat_4275_cau.xlsx '+r['review_cell'])
 item=byid[rid];item.update(reference_label='toxic',status='user_confirmed',training_eligible=True,review_method='user_filled_excel_then_chat_correction',annotation_note='User corrected n to t in chat 31/10/2026')
 assert rid not in existing
 canonical['rows'].append(dict(id=rid,post_id=item['post_id'],comment_id=item['comment_id'],text_raw=item['text_raw'],text_hash=item['text_hash'],reference_label='toxic',human_verified=True,label_source='imported',annotation_note=a['note']))
 resolved.append(dict(id=rid,text_hash=r['text_hash'],review_cell=r['review_cell'],previous_label='non-toxic',reference_label='toxic',human_verified=True,reason='Explicit user correction in chat',updated_at=now))
try:shutil.copyfile(out/'corrected.xlsx',book)
except PermissionError:
 book=out/'Ra_soat_4275_cau_da_sua.xlsx';shutil.copyfile(out/'corrected.xlsx',book)
labels['workbook_sha256']=sha(book)
for r in labels['rows']:r['workbook_sha256']=sha(book)
labels['latest_correction']='All five flagged comments corrected to toxic in chat 31/10/2026'
atomic_json(Path(paths[0]),w);canonical['workspace_sha256']=sha(paths[0]);canonical['note']='Canonical human development labels; reserved posts excluded. Five pending policy rows resolved as toxic by user in chat 31/10/2026. AI-assisted human labels are not blind validation.';atomic_json(Path(paths[1]),canonical);atomic_json(Path(paths[2]),labels)
atomic_json(Path(paths[3]),dict(policy_version=flags['policy_version'],rows=[],resolved_in=str(out/'corrections.json')))
atomic_json(out/'corrections.json',dict(rows=resolved,workbook_sha256=sha(book)))
report=dict(workbook_output=str(book),corrected=5,remaining_clarifications=0,user_435_counts=dict(Counter(r['reference_label'] for r in labels['rows'])),canonical_rows=len(canonical['rows']),canonical_counts=dict(Counter(r['reference_label'] for r in canonical['rows'])),excel_changes=changes,excel_other_values_unchanged=True,excel_tables_validation_panes_preserved=True,workspace_sha256=sha(paths[0]),source_sha256=sha('data/progress.json'),workbook_sha256=sha(book),new_training=False)
atomic_json(out/'verification.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
