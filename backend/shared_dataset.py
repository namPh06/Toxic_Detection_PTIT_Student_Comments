"""Version and verify the Git-shared corpus. No model calls or training here."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from backend.dataset import LABELS, atomic_json, csv_bytes, prepare, row_id, summary, text_hash
from backend.post_context import canonical_post_id

POLICY = 'ptit-v4-abuse-context-20261102'
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def reviewed(row):
    return (row.get('label_source') == 'manual' and row.get('human_verified') is True
            and row.get('label_policy_version') == POLICY
            and not row.get('annotation_stale') and row.get('label') in LABELS)


def usable_label(row):
    """Use any saved label, including AI, on a valid current clean comment."""
    return (row['quality'] == 'ready' and row['label'] in LABELS
            and not row.get('annotation_stale') and not row.get('excluded'))


def approval_token(row):
    fields = ('text_hash', 'label', 'post_id', 'parent_comment_id', 'post_text_raw', 'parent_context')
    return text_hash(json.dumps({k: row.get(k) for k in fields}, ensure_ascii=False, sort_keys=True))


def apply_approval(directory, rows, approval=None, imported=None):
    """Keep historical review metadata; reviews no longer gate label usage."""
    if approval is None or imported is None:
        state = load(directory / 'workspace.json') if (directory / 'workspace.json').exists() else {}
        if approval is None:
            approval = state.get('dataset_approval', {})
        if imported is None:
            imported = state.get('imported', [])
    valid = (approval.get('method') == 'owner_batch_acceptance'
             and approval.get('label_policy_version') == POLICY
             and approval.get('policy_sha256') == digest(directory.parent / 'docs' / 'QUY_TAC_GAN_NHAN.md')
             and approval.get('source_sha256') == digest(directory / 'progress.json')
             and approval.get('imported_sha256') == text_hash(json.dumps(imported, ensure_ascii=False, sort_keys=True))
             and approval.get('context_sha256') == {
                 name: digest(directory / name) for name in ('post_context.json', 'parent_context.json')})
    tokens = approval.get('rows', {}) if valid else {}
    result = []
    for row in rows:
        usable = usable_label(row)
        method = ('individual_review' if reviewed(row) else
                  'owner_batch_acceptance' if tokens.get(row['id']) == approval_token(row) else '') if usable else ''
        # Legacy unverified flags record provenance, not AI uncertainty.
        needs_review = bool(row.get('needs_review')) and row.get('review_reason') not in (
            'unverified_reconciled_proposal', 'unverified_text_only_fallback', 'unverified_collection_filter', 'unverified_v4_semantic')
        result.append(dict(row, label_usable=usable, needs_review=needs_review,
                           label_approved=bool(method), label_approval_method=method))
    return result


def approve_current(directory):
    """Record the owner's explicit acceptance of the current labelled snapshot."""
    before = digest(directory / 'workspace.json')
    raw, state = source_rows(directory)
    if state.get('label_policy_version') != POLICY:
        raise ValueError('Phiên bản tiêu chí trong workspace không khớp; không phê duyệt.')
    rows = [r for r in prepare(raw, state['annotations'])
            if r['quality'] == 'ready' and r['label'] in LABELS and not r['annotation_stale']]
    if not rows:
        raise ValueError('Không có mẫu sạch đã gán nhãn để phê duyệt.')
    state['dataset_approval'] = dict(
        method='owner_batch_acceptance', approved_at=datetime.now(timezone.utc).isoformat(),
        statement='Người phụ trách phê duyệt bộ nhãn hiện có với sự hỗ trợ của AI; không xác nhận từng mẫu được gán tay.',
        label_policy_version=POLICY, policy_sha256=digest(directory.parent / 'docs' / 'QUY_TAC_GAN_NHAN.md'),
        source_sha256=digest(directory / 'progress.json'),
        imported_sha256=text_hash(json.dumps(state['imported'], ensure_ascii=False, sort_keys=True)),
        context_sha256={name: digest(directory / name) for name in ('post_context.json', 'parent_context.json')},
        labels=dict(Counter(r['label'] for r in rows)), rows={r['id']: approval_token(r) for r in rows})
    if digest(directory / 'workspace.json') != before:
        raise ValueError('Workspace vừa thay đổi; không ghi đè phê duyệt.')
    atomic_json(directory / 'workspace.json', state)
    return dict(label_approved=len(rows), labels=state['dataset_approval']['labels'])


def boundary(raw, previous=()):
    """Keep historical reservations and join aliases/duplicates transitively."""
    by_post = defaultdict(list)
    for row in raw:
        by_post[str(row['post_id'])].append(row)
    aliases = {p: canonical_post_id(p, rows) for p, rows in by_post.items()}
    parents = {p: p for p in aliases.values()}

    def root(p):
        while parents[p] != p:
            parents[p] = parents[parents[p]]
            p = parents[p]
        return p

    def join(a, b):
        a, b = root(a), root(b)
        parents[max(a, b)] = min(a, b)

    old = {r['id']: r for r in previous}
    first = {}
    reserved = set()
    # Keep old connections even if some bridging comments were later removed.
    for row in prepare(raw):
        post = aliases[str(row['post_id'])]
        keys = [('text', row['text_clean'])]
        prior = old.get(row['id'])
        if prior:
            keys.append(('historical_group', prior['group']))
            if prior['partition'] == 'reserved':
                reserved.add(post)
        for kind, value in keys:
            if value:
                join(post, first.setdefault((kind, value), post))
    reserved = {root(p) for p in reserved}
    return [dict(id=row_id(r), post_id=str(r['post_id']), canonical_post_id=aliases[str(r['post_id'])], group=root(aliases[str(r['post_id'])]),
                 partition='reserved' if root(aliases[str(r['post_id'])]) in reserved else 'development_pool')
            for r in raw]


def source_rows(directory):
    state = load(directory / 'workspace.json')
    return load(directory / 'progress.json')['rows'] + state['imported'], state


SPLIT_NAMES = ('train', 'validation', 'test')


def fixed_rows(directory):
    """Read all three fixed files together; never silently randomize a partial set."""
    paths = [directory / (name + '.json') for name in SPLIT_NAMES]
    if not any(path.exists() for path in paths):
        return None
    if not all(path.exists() for path in paths):
        raise ValueError('Thiếu file train.json, validation.json hoặc test.json; hãy khôi phục đủ ba tập.')
    result = {}
    for name, path in zip(SPLIT_NAMES, paths):
        payload = load(path)
        if payload.get('partition') != name or not payload.get('rows'):
            raise ValueError(f'File {path.name} không đúng phân vùng hoặc không có mẫu.')
        for row in payload['rows']:
            if row['id'] in result:
                raise ValueError('Trùng ID trong ba tập cố định: ' + row['id'])
            result[row['id']] = (name, row)
    return result


def refresh_fixed_rows(directory, rows):
    """Refresh saved labels/clean text without adding or moving any members."""
    fixed = fixed_rows(directory)
    if fixed is None:
        return
    actual = {r['id']: r for r in rows}
    for key, (_, previous) in fixed.items():
        if key not in actual or actual[key]['text_hash'] != previous['text_hash'] or not usable_label(actual[key]):
            raise ValueError('Mẫu cố định bị đổi nội dung hoặc không còn hợp lệ: ' + key)
    for name in SPLIT_NAMES:
        path = directory / (name + '.json')
        payload = load(path)
        payload['rows'] = [actual[r['id']] for r in payload['rows']]
        if payload != load(path):
            atomic_json(path, payload)


def training_rows(directory, rows):
    """Labels can evolve without changing the frozen group boundary."""
    manifest = load(directory / 'shared_manifest.json')
    if text_hash(json.dumps(manifest['groups'], sort_keys=True)) != manifest['groups_sha256']:
        raise ValueError('Manifest chia nhóm đã thay đổi ngoài công cụ xuất dữ liệu; cần kiểm tra lại.')
    if manifest['label_policy_version'] != POLICY:
        raise ValueError('Chính sách nhãn đã đổi; cần xuất lại bộ dữ liệu dùng chung.')
    if manifest['source_sha256'] != digest(directory / 'progress.json'):
        raise ValueError('Dữ liệu crawl đã đổi; chạy python -m backend.shared_dataset --export trước khi huấn luyện.')
    state = load(directory / 'workspace.json')
    if manifest['imported_sha256'] != text_hash(json.dumps(state['imported'], ensure_ascii=False, sort_keys=True)):
        raise ValueError('Dữ liệu nhập đã đổi; chạy python -m backend.shared_dataset --export trước khi huấn luyện.')
    policy = directory.parent / 'docs' / 'QUY_TAC_GAN_NHAN.md'
    if manifest['policy_sha256'] != digest(policy):
        raise ValueError('Tiêu chí gán nhãn đã đổi; cần rà soát nhãn và cập nhật phiên bản chính sách.')
    by_id = {r['id']: r for r in manifest['groups']}
    if {r['id'] for r in rows} != set(by_id):
        raise ValueError('Dữ liệu không khớp manifest chia nhóm; cần xuất lại.')
    fixed = fixed_rows(directory)
    if manifest.get('fixed_split_files') and fixed is None:
        raise ValueError('Thiếu ba file dữ liệu cố định; không tự chia lại ngẫu nhiên.')
    assignments = {key: {'partition': name, 'text_hash': row['text_hash']}
                   for key, (name, row) in (fixed or {}).items()}
    if fixed is not None:
        actual = {r['id']: r for r in rows}
        if any(key not in actual or actual[key]['text_hash'] != value['text_hash']
               for key, value in assignments.items()):
            raise ValueError('Nội dung bộ chia cố định đã thay đổi; cần rà soát trước khi dùng.')
        if any(not usable_label(actual[key]) for key in assignments):
            raise ValueError('Bộ chia cố định có mẫu không còn đủ điều kiện; cần rà soát trước khi dùng.')
        if any(actual[key]['label'] != saved['label'] or actual[key]['text_clean'] != saved['text_clean']
               for key, (_, saved) in fixed.items()):
            raise ValueError('Nhãn hoặc chuẩn hóa của ba tập chưa đồng bộ; chạy python -m backend.shared_dataset --export.')
        # Preserve source order for existing feature/run fingerprints, but read saved split rows.
        rows = [fixed[r['id']][1] for r in rows if r['id'] in fixed]
    return [dict(r, split_group=by_id[r['id']]['group'],
                 **({'dataset_partition': assignments[r['id']]['partition']} if fixed else {}))
            for r in apply_approval(directory, rows, state.get('dataset_approval', {}), state['imported'])
            if usable_label(r) and by_id[r['id']]['partition'] == 'development_pool'
            and (not fixed or r['id'] in assignments)]


def export(directory):
    raw, state = source_rows(directory)
    if state.get('label_policy_version') != POLICY:
        raise ValueError('Workspace chưa theo v4; chạy --migrate-legacy một lần trước.')
    if len({row_id(r) for r in raw}) != len(raw):
        raise ValueError('Trùng ID trong dữ liệu nguồn; không xuất bản.')
    old_path = directory / 'shared_manifest.json'
    historical = directory.parent / 'outputs/history.zip'
    if old_path.exists():
        previous = load(old_path)['groups']
    elif historical.exists():
        with ZipFile(historical) as archive:
            previous = json.loads(archive.read('outputs/safe_fallback_20261101/partitions.json'))['rows']
    else:
        previous = []
    groups = boundary(raw, previous)
    rows = apply_approval(directory, prepare(raw, state['annotations']), state.get('dataset_approval', {}), state['imported'])
    for r in rows:
        r['human_verified'] = reviewed(r)
    refresh_fixed_rows(directory, rows)
    atomic_json(directory / 'shared_dataset.json', dict(schema_version=1, label_policy_version=POLICY,
                                                       label_policy='includes_automatic', rows=rows))
    csv_path = directory / 'shared_dataset.csv'
    temp = csv_path.with_suffix('.csv.tmp')
    temp.write_bytes(csv_bytes(rows))
    temp.replace(csv_path)
    manifest = dict(schema_version=1, label_policy_version=POLICY, label_usage_policy='includes_automatic',
                    policy_sha256=digest(directory.parent / 'docs' / 'QUY_TAC_GAN_NHAN.md'),
                    source_sha256=digest(directory / 'progress.json'),
                    workspace_sha256=digest(directory / 'workspace.json'),
                    imported_sha256=text_hash(json.dumps(state['imported'], ensure_ascii=False, sort_keys=True)),
                    context_sha256={name: digest(directory / name) for name in ('post_context.json', 'parent_context.json')},
                    exports={name: digest(directory / name) for name in ('shared_dataset.json', 'shared_dataset.csv')},
                    summary=summary(rows), human_reviewed=sum(reviewed(r) for r in rows if r['quality'] == 'ready'),
                    label_approved=sum(r['label_approved'] for r in rows),
                    usable_labels=sum(usable_label(r) for r in rows),
                    pending_review=sum(bool(r.get('needs_review')) for r in rows if r['quality'] == 'ready'),
                    reservation_scope='Historical diagnostic groups; not an independent blind test.', groups=groups)
    manifest['groups_sha256'] = text_hash(json.dumps(groups, sort_keys=True))
    if fixed_rows(directory) is not None:
        manifest['fixed_split_files'] = [name + '.json' for name in SPLIT_NAMES]
    atomic_json(old_path, manifest)
    return {k: manifest[k] for k in ('summary', 'human_reviewed', 'usable_labels', 'pending_review')}


def check(directory):
    manifest = load(directory / 'shared_manifest.json')
    expected = dict(manifest['exports'], **manifest['context_sha256'])
    expected.update({'progress.json': manifest['source_sha256'], 'workspace.json': manifest['workspace_sha256']})
    stale = [name for name, value in expected.items() if digest(directory / name) != value]
    if digest(directory.parent / 'docs' / 'QUY_TAC_GAN_NHAN.md') != manifest['policy_sha256']:
        stale.append('QUY_TAC_GAN_NHAN.md')
    if stale:
        raise ValueError('Bản chia sẻ chưa đồng bộ: ' + ', '.join(stale) + '. Chạy --export trước khi commit/push.')
    raw, state = source_rows(directory)
    rows = apply_approval(directory, prepare(raw, state['annotations']), state.get('dataset_approval', {}), state['imported'])
    training_rows(directory, rows)  # Validate group membership, not training readiness.
    actual = load(directory / 'shared_dataset.json')['rows']
    if [(r['id'], r['text_hash'], r['label'], r['quality'], reviewed(r), usable_label(r)) for r in rows] != [
            (r['id'], r['text_hash'], r['label'], r['quality'], reviewed(r), r.get('label_usable', usable_label(r))) for r in actual]:
        raise ValueError('Dataset xuất khác workspace; chạy --export.')
    return dict(valid=True, total=len(rows), ready=sum(r['quality'] == 'ready' for r in rows),
                human_reviewed=manifest['human_reviewed'], usable_labels=sum(usable_label(r) for r in rows),
                pending_review=sum(bool(r.get('needs_review')) for r in rows if r['quality'] == 'ready'))


def migrate(directory):
    """One-time migration: archive legacy reviews, retain only proven v4 reviews."""
    raw, old = source_rows(directory)
    if old.get('label_policy_version') == POLICY:
        return export(directory)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive = directory / 'label_history' / stamp
    archive.mkdir(parents=True, exist_ok=False)
    (archive / 'workspace_before.json').write_bytes((directory / 'workspace.json').read_bytes())
    atomic_json(archive / 'source_reference.json', dict(source_sha256=digest(directory / 'progress.json'),
                policy=POLICY, note='Full legacy decisions retained in workspace_before.json; older-policy reviews require v4 confirmation.'))
    annotations, carried = {}, 0
    for r in raw:
        key = row_id(r)
        prior = old['annotations'].get(key, {})
        if (prior.get('label_policy_version') == POLICY and prior.get('text_hash') == text_hash(r['text_raw'])):
            annotations[key] = prior
            carried += 1
        elif r.get('label') in LABELS:
            annotations[key] = dict(label=r['label'], text_hash=text_hash(r['text_raw']),
                label_source='automatic', label_policy_version=POLICY, human_verified=False,
                needs_review=True, review_reason=r.get('review_reason') or 'unverified_v4_semantic',
                note=r.get('annotation_note', ''), excluded=bool(r.get('excluded', False)),
                **{k: r[k] for k in ('label_model', 'label_revision', 'model_score', 'label_threshold') if k in r})
    state = dict(schema_version=1, label_policy_version=POLICY, annotations=annotations,
                 imported=old['imported'], suggestions={}, legacy_archive=str(archive.relative_to(directory)).replace('\\', '/'))
    atomic_json(directory / 'workspace.json', state)
    result = export(directory)
    atomic_json(archive / 'migration.json', dict(archived_annotations=len(old['annotations']),
                carried_current_policy=carried, result=result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--export', action='store_true', help='Refresh JSON/CSV, checksums and safe grouping before commit.')
    action.add_argument('--check', action='store_true', help='Verify a pulled release without changing data.')
    action.add_argument('--approve-current', action='store_true', help='Record explicit owner acceptance of current labels without changing their origin.')
    action.add_argument('--migrate-legacy', action='store_true', help='Archive old workspace and initialize current-policy machine labels once.')
    args = parser.parse_args()
    try:
        if args.approve_current:
            approve_current(ROOT / 'data')
        result = migrate(ROOT / 'data') if args.migrate_legacy else export(ROOT / 'data') if args.export or args.approve_current else check(ROOT / 'data')
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
