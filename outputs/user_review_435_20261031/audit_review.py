import json,hashlib,zipfile,posixpath,xml.etree.ElementTree as E
from pathlib import Path
from collections import Counter
from dataset import prepare
base=Path('outputs/remaining_semantic_review_20261031');out=Path('outputs/user_review_435_20261031')
wb=base/'Ra_soat_4275_cau.xlsx';ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ai=load(base/'assistant_labels.json')['rows'];queue=load(base/'review_queue.json')['rows'];source={r['id']:r for r in prepare(load('data/progress.json')['rows']) if r['quality']=='ready'}
assert sha('data/progress.json')==load(base/'verification.json')['source_sha256']
expected={'Can_bo_sung_435':{r['id']:r for r in queue},'AI_4275':{r['id']:r for r in ai}}
issues=[];filled=[];pending=[];counts={}
with zipfile.ZipFile(wb) as z:
 shared=[]
 if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(t.text or '' for t in e.iter('{'+ns['s']+'}t')) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
 rel={r.get('Id'):r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
 def val(c):
  if c is None:return ''
  if c.get('t')=='s':return shared[int(c.find('s:v',ns).text)]
  if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter('{'+ns['s']+'}t'))
  v=c.find('s:v',ns);return '' if v is None else v.text or ''
 for sh in E.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',ns):
  name=sh.get('name')
  if name not in expected:continue
  target=rel[sh.get('{'+ns['r']+'}id')];loc=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
  seen=set();tally=Counter()
  for row in E.fromstring(z.read(loc)).findall('s:sheetData/s:row',ns):
   if row.get('r')=='1':continue
   cells={''.join(filter(str.isalpha,c.get('r'))):c for c in row.findall('s:c',ns)}
   if not any(val(c) for c in cells.values()):continue
   rid=val(cells.get('E'));where=name+'!B'+row.get('r');ref=expected[name].get(rid);original=source.get(rid)
   if not ref or not original or rid in seen:issues.append({'cell':where,'reason':'unknown/duplicate ID'});continue
   seen.add(rid)
   if val(cells.get('F'))!=ref['text_hash'] or val(cells.get('F'))!=original['text_hash'] or val(cells.get('A')) not in [ref['comment'],"'"+ref['comment']]:issues.append({'cell':where,'reason':'text/hash changed'});continue
   if any(c.find('s:f',ns) is not None for c in cells.values()):issues.append({'cell':where,'reason':'formula present'});continue
   label=val(cells.get('B')).strip().lower();note=val(cells.get('D')).strip()
   if label not in ['','t','n']:issues.append({'cell':where,'reason':'invalid label','value':label});continue
   tally[label or 'blank']+=1
   item=dict(id=rid,post_id=original['post_id'],comment_id=original['comment_id'],text_hash=ref['text_hash'],comment=ref['comment'],context=ref.get('context',''),review_cell=where,note=note,label={'t':'toxic','n':'non-toxic','':''}[label])
   if label:filled.append(item)
   elif name=='Can_bo_sung_435':pending.append(item)
  if seen!=set(expected[name]):issues.append({'sheet':name,'reason':'missing IDs','count':len(set(expected[name])-seen)})
  counts[name]=dict(tally)
 if set(counts)!=set(expected):issues.append({'reason':'missing sheet'})
byid={}
for r in filled:
 if r['id'] in byid and byid[r['id']]['label']!=r['label']:issues.append({'id':r['id'],'reason':'conflicting labels between sheets'})
 else:byid[r['id']]=r
result=dict(workbook=str(wb),workbook_sha256=sha(wb),source_sha256=sha('data/progress.json'),workspace_sha256_before=sha('data/workspace.json'),counts=counts,issues=issues,rows=list(byid.values()),pending=pending)
(out/'workbook_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','pending']},ensure_ascii=False));print('UNIQUE FILLED',len(byid),'PENDING',len(pending))
