import json,hashlib,copy
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from dataset import prepare,atomic_json
out=Path('outputs/user_review_435_20261031');load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit=load(out/'workbook_audit.json');flags={r['id']:r for r in load(out/'needs_clarification.json')['rows']};workspace=Path('data/workspace.json');canonical=Path('data/manual_review/canonical_development_v32_20261031.json')
assert not audit['issues'] and len(audit['rows'])==435 and not audit['pending']
assert sha(workspace)==audit['workspace_sha256_before']
assert sha(audit['workbook'])==audit['workbook_sha256']
assert sha('data/progress.json')==audit['source_sha256']
reserved=set(map(str,load('outputs/label_review_20261031/review_manifest.json')['reserved_post_ids']))
source={r['id']:r for r in prepare(load('data/progress.json')['rows']) if r['quality']=='ready'}
w=load(workspace);old=copy.deepcopy(w);oldcanonical=load(canonical);now=datetime.now(timezone.utc).isoformat();policy='ptit-v3.2-friendly-banter-20261031'
records=[];development=[];validation=[]
for r in audit['rows']:
 assert r['id'] in source and source[r['id']]['text_hash']==r['text_hash']
 item=dict(id=r['id'],post_id=str(r['post_id']),comment_id=str(r['comment_id']),text_raw=r['comment'],text_hash=r['text_hash'],reference_label=r['label'],human_verified=True,review_method='user_filled_excel_ai_assisted',review_cell=r['review_cell'],annotation_note=r['note'],workbook_sha256=audit['workbook_sha256'],policy_version=policy,status='needs_policy_clarification' if r['id'] in flags else 'user_confirmed',training_eligible=r['id'] not in flags and str(r['post_id']) not in reserved)
 records.append(item)
 if str(r['post_id']) in reserved:validation.append(item);continue
 development.append(item)
 w['annotations'][r['id']]=dict(label=r['label'],note='Human-confirmed reference: Ra_soat_4275_cau.xlsx '+r['review_cell']+('. '+r['note'] if r['note'] else '')+(' | Pending policy clarification: '+flags[r['id']]['audit_reason'] if r['id'] in flags else ''),excluded=r['id'] in flags,text_hash=r['text_hash'],label_source='imported',human_verified=True,review_method='user_filled_excel_ai_assisted',policy_version=policy,updated_at=now,review_status=item['status'])
# Keep historical annotations untouched unless explicitly reviewed in this workbook.
changed={r['id'] for r in development}
assert all(w['annotations'][rid]==annotation for rid,annotation in old['annotations'].items() if rid not in changed)
assert not any(r['id'] in w['annotations'] and r['id'] not in old['annotations'] for r in validation)
canonical_rows=[]
for rid,a in w['annotations'].items():
 if a.get('excluded') or a.get('label') not in ['toxic','non-toxic'] or a.get('label_source','manual')=='automatic':continue
 r=source[rid];assert a['text_hash']==r['text_hash'];assert str(r['post_id']) not in reserved
 canonical_rows.append(dict(id=rid,post_id=str(r['post_id']),comment_id=str(r['comment_id']),text_raw=r['text_raw'],text_hash=r['text_hash'],reference_label=a['label'],human_verified=True,label_source=a.get('label_source','manual'),annotation_note=a.get('note','')))
assert len({r['id'] for r in canonical_rows})==len(canonical_rows)
for path,name in [(workspace,'workspace_before.json'),(canonical,'canonical_before.json')]:
 target=out/name
 if target.exists():raise ValueError('Backup already exists; do not apply twice')
 target.write_bytes(path.read_bytes())
atomic_json(out/'user_labels.json',dict(policy_version=policy,workbook_sha256=audit['workbook_sha256'],source_sha256=audit['source_sha256'],note='User labels after AI triage, not blind independent validation. Flagged choices retained but held out of training.',rows=records))
atomic_json(out/'reserved_post_user_labels.json',dict(role='reserved_validation_posts',blind=False,note='AI-assisted user review, kept out of training and retrieval; not a new blind accuracy test.',rows=validation))
atomic_json(workspace,w)
atomic_json(canonical,dict(policy_version=policy,role='development',source_sha256=audit['source_sha256'],workspace_sha256=sha(workspace),note='Canonical human development labels; exclude reserved posts, unresolved historical annotations and 5 policy clarification rows. User review after AI suggestions is not blind validation.',rows=canonical_rows))
report=dict(imported_user_labels=len(records),human_counts=dict(Counter(r['reference_label'] for r in records)),workspace_reviewed=len(development),reserved_kept_separate=len(validation),needs_clarification=len(flags),canonical_before=len(oldcanonical['rows']),canonical_after=len(canonical_rows),canonical_counts=dict(Counter(r['reference_label'] for r in canonical_rows)),workspace_annotations=len(w['annotations']),untouched_annotations_preserved=True,source_unchanged=sha('data/progress.json')==audit['source_sha256'],workbook_unchanged=sha(audit['workbook'])==audit['workbook_sha256'],no_training=True,blind_accuracy_measured=False)
atomic_json(out/'import_verification.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
