"""Read t/n Excel reviews without changing the workbook or assigning labels to blanks."""
import hashlib
import json
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from dataset import prepare, text_hash

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def read_review(workbook, manifest, source):
    content=Path(workbook).read_bytes()
    raw=Path(source).read_bytes()
    control=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    if hashlib.sha256(raw).hexdigest()!=control['source_sha256']:
        raise ValueError('Source changed since export; reconcile before import')
    prepared=prepare(json.loads(raw.decode('utf-8-sig'))['rows'])
    current={r['id']:r for r in prepared if r['quality']=='ready'}
    expected={r['id']:r for r in control['priority']+control['others']}
    worksheets=control.get('worksheets', {'Can_duyet':'priority','Chua_xac_nhan':'others'})
    if not isinstance(worksheets,dict) or set(worksheets.values())!={'priority','others'} or len(worksheets)!=2:
        raise ValueError('Invalid review worksheet configuration')
    sheet_ids={name:{r['id'] for r in control[partition]} for name,partition in worksheets.items()}
    if len(expected)!=len(control['priority'])+len(control['others']):
        raise ValueError('Duplicate manifest IDs')
    labeled=[]; seen=set(); counts={}; issues=[]; pending_notes=[]
    with zipfile.ZipFile(Path(workbook)) as archive:
        shared=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared=[''.join(t.text or '' for t in e.iter('{'+NS['s']+'}t')) for e in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        relations={r.get('Id'):r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets=ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS)
        def value(c):
            if c is None: return ''
            if c.get('t')=='s': return shared[int(c.find('s:v',NS).text)]
            if c.get('t')=='inlineStr': return ''.join(t.text or '' for t in c.iter('{'+NS['s']+'}t'))
            v=c.find('s:v',NS); return '' if v is None else v.text or ''
        for sheet in sheets:
            name=sheet.get('name')
            if name not in worksheets: continue
            target=relations[sheet.get('{'+NS['r']+'}id')]
            location=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows=ET.fromstring(archive.read(location)).findall('s:sheetData/s:row',NS)
            tally={'toxic':0,'non-toxic':0,'blank':0,'invalid':0}
            for row in rows:
                if row.get('r')=='1': continue
                cells={''.join(filter(str.isalpha,c.get('r'))):c for c in row.findall('s:c',NS)}
                if not any(value(c) for c in cells.values()): continue
                id_=value(cells.get('E')); digest=value(cells.get('F')); text=value(cells.get('A'))
                where=name+'!'+row.get('r')
                if id_ not in expected or id_ not in current or id_ in seen:
                    issues.append(dict(cell=where,reason='Missing, unknown or duplicate ID')); continue
                seen.add(id_); ref=expected[id_]; original=current[id_]
                if id_ not in sheet_ids[name]:
                    issues.append(dict(cell=where,reason='Review row moved to a different partition'));continue
                if digest!=ref['text_hash'] or digest!=original['text_hash'] or text not in (ref['comment'],"'"+ref['comment']):
                    issues.append(dict(cell=where,reason='Comment or identity hash changed'));continue
                if any(c.find('s:f',NS) is not None for c in cells.values()):
                    issues.append(dict(cell=where,reason='Formula not allowed in review row'));continue
                if control.get('check_context') and value(cells.get('C')) not in (ref['context'],"'"+ref['context']):
                    issues.append(dict(cell=where,reason='Review context changed'));continue
                note=value(cells.get('D')).strip() if control.get('review_note_column')=='D' else ''
                if len(note)>2000:
                    issues.append(dict(cell=where,reason='Review note exceeds 2000 characters'));continue
                label=value(cells.get('B')).strip().lower()
                if label not in ('','t','n'):
                    tally['invalid']+=1;issues.append(dict(cell=where+' B',reason='Only t/n or blank allowed',value=label));continue
                if not label:
                    tally['blank']+=1
                    if note: pending_notes.append(dict(id=id_,review_cell=name+'!B'+row.get('r'),note=note))
                    continue
                label='toxic' if label=='t' else 'non-toxic';tally[label]+=1
                labeled.append(dict(id=id_,post_id=original['post_id'],comment_id=original['comment_id'],text_raw=original['text_raw'],text_hash=digest,reference_label=label,human_verified=True,review_method='user_filled_excel',review_cell=name+'!B'+row.get('r'),**({'annotation_note':note} if note else {})))
            counts[name]=tally
    if set(counts)!=set(worksheets): issues.append(dict(reason='Missing review worksheet'))
    if seen!=set(expected): issues.append(dict(reason='Missing workbook IDs',count=len(set(expected)-seen)))
    return dict(workbook_sha256=hashlib.sha256(content).hexdigest(),source_sha256=hashlib.sha256(raw).hexdigest(),policy_version=control['policy_version'],counts=counts,checked_ids=len(seen),issues=issues,rows=labeled,pending_notes=pending_notes)
