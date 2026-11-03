import json,zipfile,xml.etree.ElementTree as E,hashlib
from pathlib import Path
p=Path('outputs/assistant_review_20261031'); f=p/'Ket_qua_gan_nhan_va_ra_soat.xlsx'; ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
z=zipfile.ZipFile(f); shared=[''.join(e.itertext()) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
def value(c):
 if c is None:return ''
 if c.get('t')=='s':return shared[int(c.find('s:v',ns).text)]
 if c.get('t')=='inlineStr':return ''.join(c.find('s:is',ns).itertext())
 v=c.find('s:v',ns);return '' if v is None else v.text or ''
a=json.loads((p/'assistant_labels.json').read_text(encoding='utf-8'))['rows']; h=json.loads((p/'human_label_audit.json').read_text(encoding='utf-8'))['rows']; expected={r['id']:r for r in h if r['status']=='needs_confirmation'};expected.update({r['id']:r for r in a if r['status']=='needs_context'})
rows=[];seen=set();issues=[]
for row in E.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('s:sheetData/s:row',ns)[1:]:
 c={''.join(filter(str.isalpha,e.get('r'))):e for e in row.findall('s:c',ns)};i=value(c.get('G'));label=value(c.get('B')).strip().lower();ref=expected.get(i)
 if ref is None or i in seen:issues.append('Unknown/duplicate ID');continue
 seen.add(i)
 if value(c.get('H'))!=ref['text_hash'] or value(c.get('A')) not in (ref['comment'],"'"+ref['comment']):issues.append('Changed text/hash '+i)
 if label not in ('','t','n'):issues.append('Invalid label '+i)
 if any(e.find('s:f',ns) is not None for e in c.values()):issues.append('Formula '+i)
 rows.append(dict(id=i,text_hash=ref['text_hash'],text_raw=ref['comment'],post_id=ref['post_id'],comment_id=ref['comment_id'],label={'t':'toxic','n':'non-toxic','':''}.get(label,''),review_cell='Can_xem_lai!B'+row.get('r')))
assert seen==set(expected)
result=dict(workbook_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),rows=rows,issues=issues)
Path('outputs/assistant_review_20261031/latest_user_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(total=len(rows),filled=sum(bool(r['label']) for r in rows),toxic=sum(r['label']=='toxic' for r in rows),issues=issues)))
