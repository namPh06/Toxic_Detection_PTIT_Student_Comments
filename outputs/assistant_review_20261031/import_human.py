import json,hashlib,socket
from pathlib import Path
from lab import Lab
from dataset import prepare
p=Path('data/workspace.json'); before=p.read_bytes()
assert hashlib.sha256(before).hexdigest()=='e21fe9eb49a62a89271b3b3f1af79641aa47a015d0fe759069f8e87de5a4d43f'
s=socket.socket(); assert s.connect_ex(('127.0.0.1',8767))!=0; s.close()
raw=json.loads(Path('data/progress.json').read_text(encoding='utf-8'))
assert hashlib.sha256(Path('data/progress.json').read_bytes()).hexdigest()=='e478f195be50d8fd842f22e49c2b4d19f54563d3c00d4b30a6b180f1f006df00'
backup=Path('outputs/assistant_review_20261031/workspace_before_import.json'); assert not backup.exists(); backup.write_bytes(before)
ref=json.loads(Path('data/manual_review/round2_development_20261031.json').read_text(encoding='utf-8'))
rows=[dict(r,label=r['reference_label'],label_source='manual',annotation_note='User Excel '+r['review_cell']+'; round2 20261031') for r in ref['rows']]
lab=Lab(Path('data'),lambda:raw['rows'])
assert p.read_bytes()==before
result=lab.import_rows(dict(filename='human_round2.json',content=json.dumps(dict(rows=rows))))
assert result==dict(added=0,labels_updated=60),result
old=json.loads(before)
assert all(lab.annotations[k]==v for k,v in old['annotations'].items())
human=[r for r in lab.rows() if r['label'] in ('toxic','non-toxic') and r['label_source']!='automatic' and r['quality']=='ready']
assert len(human)==536
Path('outputs/assistant_review_20261031/human_snapshot.json').write_text(json.dumps(dict(rows=human),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(result=result,total=len(human),toxic=sum(r['label']=='toxic' for r in human)),ensure_ascii=True))
