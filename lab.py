"""Local dataset workspace; annotations never overwrite crawl output."""
import json
import re
import threading
from datetime import datetime, timezone

from dataset import LABELS, LABEL_METADATA, PREPROCESS_VERSION, TOKENIZER_VERSION, atomic_json, csv_bytes, fingerprint, input_fingerprint, parse_import, prepare, row_id, summary, text_hash
from experiments import active_result, build_report, predict, publish_run, split_dataset, train_experiment, validate_algorithms
from features import build_features, feature_key, feature_summary, preview_features, validate_settings
from shared_dataset import POLICY, apply_approval, digest, reviewed, training_rows, usable_label


class Lab:
    def __init__(self, directory, source):
        self.directory, self.source = directory, source
        self.lock = threading.RLock()
        state = self.read('workspace.json', None)
        if state is not None and (not isinstance(state, dict) or state.get('schema_version') != 1):
            raise ValueError('Định dạng data/workspace.json không hợp lệ; hãy khôi phục bản sao lưu.')
        self.annotations = state['annotations'] if state is not None else self.read('annotations.json', {})
        self.imported = state['imported'] if state is not None else self.read('imported.json', [])
        self.suggestions = state.get('suggestions', {}) if state is not None else {}
        self.workspace_extra = {k: v for k, v in (state or {}).items()
                                if k not in ('schema_version', 'annotations', 'imported', 'suggestions')}
        self.workspace_digest = digest(self.directory / 'workspace.json')
        if not isinstance(self.annotations, dict) or not isinstance(self.imported, list) or not isinstance(self.suggestions, dict):
            raise ValueError('Kho nhãn/dữ liệu nhập không hợp lệ; không ghi đè dữ liệu.')
        self.job = dict(running=False, message='Chưa chạy huấn luyện.', error=False)
        self.feature_job = dict(running=False, message='Chưa trích xuất đặc trưng.', error=False)
        # Rebuild local features from the shared, reviewed data; never trust old caches.
        self.features = None
        self.annotation_job = dict(running=False, message='Gán nhãn tự động hoặc sửa nhãn trực tiếp. Nhãn đã lưu dùng được ngay, không cần duyệt.', error=False)
        if self.suggestions:
            self.annotation_job['message'] = f'Đã lưu kết quả mô hình cho {len(self.suggestions)} bình luận. Có thể gán nhãn toàn bộ hoặc xem từng mẫu.'
        self.split_check = None
        self.run = self.read('latest.json', {}).get('run', '')
        if not re.fullmatch(r'run-\d{8}T\d{12}Z', self.run):
            self.run = ''

    def read(self, name, default):
        path = self.directory / name
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

    def rows(self):
        with self.lock:
            rows = apply_approval(self.directory, prepare(self.source() + list(self.imported), self.annotations),
                                  self.workspace_extra.get('dataset_approval', {}), self.imported)
            for row in rows:
                suggestion = self.suggestions.get(row['id'])
                row['suggestion'] = (dict(suggestion) if suggestion and suggestion['text_hash'] == row['text_hash']
                                     and row['quality'] == 'ready' and not row['label'] else None)
            return rows

    def save_workspace(self, annotations, imported, suggestions):
        if digest(self.directory / 'workspace.json') != self.workspace_digest:
            raise ValueError('Workspace đã được thay đổi ở nơi khác (có thể vừa git pull). Khởi động lại ứng dụng trước khi lưu để tránh mất nhãn.')
        # All replacement paths (manual, import, model) retain prior decisions.
        annotations = dict(annotations)
        for key, value in annotations.items():
            previous = self.annotations.get(key)
            if previous and value != previous:
                history = list(previous.get('history', [])) + [
                    {k: v for k, v in previous.items() if k != 'history'}]
                annotations[key] = dict(value, history=history)
        # One atomic file prevents half-imported rows/labels after a write failure.
        atomic_json(self.directory / 'workspace.json', dict(schema_version=1, annotations=annotations,
                                                            imported=imported, suggestions=suggestions, **self.workspace_extra))
        self.workspace_digest = digest(self.directory / 'workspace.json')
        self.annotations, self.imported, self.suggestions = annotations, imported, suggestions

    def experiment_rows(self, rows=None):
        rows = self.rows() if rows is None else rows
        if (self.directory / 'shared_manifest.json').exists():
            return training_rows(self.directory, rows)
        # The real corpus must never bypass a missing release boundary.
        if (self.directory / 'progress.json').exists():
            raise ValueError('Thiếu manifest chia nhóm; chạy shared_dataset.py --export trước.')
        return rows  # Independent synthetic/import-only workspaces.

    def result(self):
        with self.lock:
            latest = self.read('latest.json', {}).get('run', '')
            if re.fullmatch(r'run-\d{8}T\d{12}Z', latest):
                self.run = latest
            return active_result(self.read(f'runs/{self.run}/metrics.json', None)) if self.run else None

    @staticmethod
    def result_stale(result, rows):
        return bool(result and (result['fingerprint'] != fingerprint(rows) or
                    result.get('preprocess_version') != PREPROCESS_VERSION or
                    result.get('tokenizer_version') != TOKENIZER_VERSION or
                    (result.get('input_fingerprint') and result['input_fingerprint'] != input_fingerprint(rows))))

    def status(self):
        from transformer_model import compute_info
        with self.lock:
            rows = self.rows()
            result = self.result()
            job = dict(self.job)
            annotation_job = dict(self.annotation_job)
        stats = summary(rows)
        with self.lock:
            experiment = []
            try:
                experiment = self.experiment_rows(rows)
                split_dataset(experiment)
                training_ready, training_message = True, 'Đủ điều kiện kỹ thuật để chia tập; chưa phải chứng nhận chất lượng nhãn.'
            except (ValueError, OSError, KeyError) as error:
                training_ready, training_message = False, str(error)
        automatic = stats['label_sources'].get('automatic', 0)
        shared = (self.directory / 'shared_manifest.json').exists()
        confirmed = sum(r['label_approved'] for r in rows) if shared else stats['labeled'] - automatic
        health = dict(reviewed=confirmed, automatic=automatic,
                      usable_labels=sum(usable_label(r) for r in rows),
                      unlabeled=stats['usable'] - stats['labeled'],
                      individually_reviewed=sum(reviewed(r) for r in rows if r['quality'] == 'ready'),
                      approval_method=self.workspace_extra.get('dataset_approval', {}).get('method', ''),
                      needs_review=0,
                      suggested=sum(bool(r['suggestion'] and r['suggestion']['suggested_label']) for r in rows),
                      abstained=sum(bool(r['suggestion'] and not r['suggestion']['suggested_label']) for r in rows),
                      stale_annotations=sum(r['annotation_stale'] for r in rows), incomplete=stats['quality'].get('incomplete', 0),
                      unknown_completeness=sum(r.get('text_complete') is None for r in rows),
                      automatic_candidates=sum(self.can_auto_label(r) for r in rows),
                      training_ready=training_ready, training_message=training_message)
        return dict(summary=stats, job=job, annotation_job=annotation_job, dataset_health=health, result=result, compute=compute_info(),
                    experiment_summary=summary(experiment),
                    features=self.feature_status(rows),
                    stale=self.result_stale(result, experiment))

    def feature_status(self, rows=None):
        with self.lock:
            bundle = self.features
            try:
                stale = bool(bundle and bundle['key'] != feature_key(self.experiment_rows(rows)))
            except (ValueError, OSError, KeyError):
                stale = bool(bundle)
            return dict(job=dict(self.feature_job), ready=bool(bundle and not stale), stale=stale,
                        result=feature_summary(bundle) if bundle else None)

    def feature_preview(self, index=0, split='all'):
        with self.lock:
            if not self.features or self.features['key'] != feature_key(self.experiment_rows()):
                raise ValueError('Chưa có đặc trưng phù hợp với dữ liệu hiện tại. Hãy trích xuất lại.')
            return preview_features(self.features, index, split)

    def start_features(self, body):
        settings = validate_settings(body)
        with self.lock:
            if self.feature_job['running'] or self.job['running'] or self.annotation_job['running']:
                raise ValueError('Chờ tác vụ trích xuất, huấn luyện hoặc gán nhãn hiện tại hoàn tất.')
            rows = self.experiment_rows()
            split_dataset(rows)
            self.feature_job = dict(running=True, error=False, message='Đang chia tập và trích xuất đặc trưng…')
            try:
                threading.Thread(target=self.extract_features, args=(rows, settings), daemon=True).start()
            except Exception:
                self.feature_job.update(running=False, error=True, message='Không khởi động được bước trích xuất. Hãy thử lại.')
                raise
        return dict(started=True)

    def extract_features(self, rows, settings):
        temp = self.directory / 'features.joblib.tmp'
        try:
            import joblib
            def notify(message):
                with self.lock:
                    self.feature_job['message'] = message
            bundle = build_features(rows, settings, notify)
            with self.lock:
                if bundle['key'] != feature_key(self.experiment_rows()):
                    raise ValueError('Dữ liệu đã thay đổi trong lúc trích xuất. Hãy chạy lại.')
                self.directory.mkdir(parents=True, exist_ok=True)
                joblib.dump(bundle, temp)
                temp.replace(self.directory / 'features.joblib')
                self.features = bundle
                self.feature_job.update(message='Đã lưu bộ đặc trưng cho dữ liệu sạch có nhãn.', error=False)
        except Exception as error:
            with self.lock:
                self.feature_job.update(error=True, message=f'Trích xuất thất bại: {error}')
        finally:
            try:
                temp.unlink(missing_ok=True)
            finally:
                with self.lock:
                    self.feature_job['running'] = False

    def annotate(self, body):
        self.annotate_many([body])
        return dict(saved=True)

    def annotate_many(self, items):
        if not isinstance(items, list) or not 1 <= len(items) <= 20000:
            raise ValueError('Cần từ 1 đến 20.000 đánh giá để lưu.')
        with self.lock:
            rows = {r['id']: r for r in self.rows()}
            annotations = dict(self.annotations)
            seen = set()
            for body in items:
                if not isinstance(body, dict) or not isinstance(body.get('id'), str) or body['id'] in seen:
                    raise ValueError('Đánh giá không hợp lệ hoặc trùng mã bình luận.')
                seen.add(body['id'])
                row = rows.get(body['id'])
                if row is None:
                    raise ValueError('Không tìm thấy bình luận.')
                if body.get('text_hash') != row['text_hash']:
                    raise ValueError('Nội dung bình luận đã thay đổi. Tải lại danh sách và đọc lại trước khi lưu nhãn.')
                label, note, excluded = body.get('label'), body.get('note', ''), body.get('excluded', False)
                if label not in ('', *LABELS) or not isinstance(note, str) or len(note) > 2000 or type(excluded) is not bool:
                    raise ValueError('Nhãn, ghi chú hoặc trạng thái loại mẫu không hợp lệ.')
                annotations[body['id']] = dict(label=label, note=note, excluded=excluded,
                                               text_hash=row['text_hash'], label_source='manual',
                                               label_policy_version=POLICY, human_verified=bool(label),
                                               updated_at=datetime.now(timezone.utc).isoformat())
                if row['suggestion']:
                    annotations[body['id']]['suggestion_at_review'] = row['suggestion']
            self.save_workspace(annotations, self.imported, self.suggestions)
        return dict(saved=len(items))

    def import_rows(self, body):
        incoming = parse_import(body.get('content'), body.get('filename'))
        with self.lock:
            all_rows = self.source() + list(self.imported)
            existing = {row_id(r): r for r in all_rows}
            annotations, added, updated = dict(self.annotations), [], 0
            # Existing IDs may add labels only if their original text is identical.
            for row in incoming:
                key = row_id(row)
                if key in existing:
                    if row['text_raw'] != existing[key]['text_raw']:
                        raise ValueError('Mã bình luận đã tồn tại nhưng nội dung khác; không ghi đè dữ liệu.')
                    prior = annotations.get(key, {})
                    current = prior.get('label', existing[key].get('label', ''))
                    if prior.get('text_hash') and prior['text_hash'] != text_hash(existing[key]['text_raw']):
                        current = ''
                    source = prior.get('label_source', existing[key].get('label_source', 'legacy'))
                    replacing_automatic = source == 'automatic' and row['label_source'] != 'automatic'
                    if row['label'] and current and row['label'] != current and not replacing_automatic:
                        raise ValueError('Nhãn nhập xung đột với nhãn đã lưu. Hãy sửa trong màn hình gán nhãn.')
                    if row['label'] and (not current or replacing_automatic):
                        annotations[key] = dict(label=row['label'], note=prior.get('note', existing[key].get('annotation_note', '')) or row['annotation_note'],
                                                excluded=prior.get('excluded', existing[key].get('excluded', False)) or row['excluded'],
                                                text_hash=text_hash(existing[key]['text_raw']), label_source=row['label_source'],
                                                updated_at=datetime.now(timezone.utc).isoformat(),
                                                **{k:row[k] for k in LABEL_METADATA if k in row})
                        updated += 1
                else:
                    added.append(row)
            if len(all_rows) + len(added) > 20000:
                raise ValueError('Workspace hỗ trợ tối đa 20.000 mẫu; hãy chia nhỏ bộ dữ liệu.')
            imported = self.imported + added
            self.save_workspace(annotations, imported, self.suggestions)
        return dict(added=len(added), labels_updated=updated)

    def dataset_rows(self, reviewed_only=None):
        # The legacy argument is accepted for existing clients; both exports now include AI labels.
        rows = [r for r in self.rows() if usable_label(r)]
        if not rows:
            raise ValueError('Chưa có mẫu sạch có nhãn. Hãy gán nhãn tự động hoặc lưu nhãn thủ công.')
        return rows

    def save_cleaned(self):
        with self.lock:
            rows = self.rows()
            atomic_json(self.directory / 'processed.json', dict(rows=rows))
            temp = self.directory / 'processed.csv.tmp'
            temp.write_bytes(csv_bytes(rows))
            temp.replace(self.directory / 'processed.csv')
            return dict(saved=len(rows))

    def can_auto_label(self, row):
        # An explicit manual abstention is a decision too; never replace it with AI.
        return (row['quality'] == 'ready' and not row['label']
                and self.annotations.get(row['id'], {}).get('label_source') != 'manual')

    def start_suggestions(self, automatic=False):
        with self.lock:
            if self.annotation_job['running'] or self.job['running'] or self.feature_job['running']:
                raise ValueError('Chờ tác vụ gợi ý/huấn luyện hiện tại hoàn tất.')
            rows = [r for r in self.rows() if r['quality'] == 'ready' and not r['label'] and (automatic or not r['suggestion'])]
            if automatic:
                rows = [r for r in rows if self.can_auto_label(r)]
            if not rows:
                raise ValueError('Không có mẫu sạch chưa có nhãn phù hợp. Nhãn và quyết định đã lưu được giữ nguyên.')
            action = 'gán nhãn tự động' if automatic else 'tạo gợi ý'
            self.annotation_job = dict(running=True, automatic=automatic, message=f'Đang {action} cho {len(rows)} mẫu sạch chưa có nhãn…', error=False)
            try:
                threading.Thread(target=self.suggest, args=(rows, automatic), daemon=True).start()
            except Exception:
                self.annotation_job.update(running=False, error=True, message='Không khởi động được tác vụ. Hãy thử lại.')
                raise
        return dict(started=True, total=len(rows))

    def suggest(self, rows, automatic=False):
        if automatic:
            return self.annotate_contextually(rows)
        try:
            from labeling import automatic_annotation, generate_suggestions

            def notify(message):
                with self.lock:
                    self.annotation_job['message'] = message

            generated = [r['suggestion'] for r in rows if r.get('suggestion')]
            missing = [r for r in rows if not r.get('suggestion')]
            if missing:
                generated += generate_suggestions(missing, self.directory.parent / 'models' / 'vietnamese-toxicity', notify)
            with self.lock:
                current = {r['id']: r for r in self.rows()}
                suggestions = dict(self.suggestions)
                annotations = dict(self.annotations)
                saved = 0
                for item in generated:
                    row = current.get(item['id'])
                    if row and row['text_hash'] == item['text_hash'] and not row['label'] and row['quality'] == 'ready':
                        suggestions[item['id']] = item
                        if automatic:
                            annotations[item['id']] = dict(automatic_annotation(item, row['text_raw']), note=row['annotation_note'], excluded=False)
                        saved += 1
                self.save_workspace(annotations, self.imported, suggestions)
                self.annotation_job.update(message=f'Đã gán nhãn tự động {saved} mẫu. Có thể tải dataset hoặc huấn luyện.' if automatic else f'Đã xử lý {saved} mẫu. Gợi ý chờ người đọc duyệt.', error=False)
                if automatic:
                    try:
                        self.save_cleaned()
                        dataset = self.dataset_rows(reviewed_only=False)
                        atomic_json(self.directory / 'dataset_auto.json', dict(label_policy='includes_automatic', rows=dataset))
                        temp = self.directory / 'dataset_auto.csv.tmp'
                        temp.write_bytes(csv_bytes(dataset))
                        temp.replace(self.directory / 'dataset_auto.csv')
                    except Exception as error:
                        self.annotation_job.update(error=True, message=f'Nhãn đã lưu; xuất tệp thất bại: {error}. Có thể tải dataset bằng nút CSV/JSON.')
        except Exception as error:
            with self.lock:
                self.annotation_job.update(message=f'Xử lý nhãn thất bại: {error}', error=True)
        finally:
            with self.lock:
                self.annotation_job['running'] = False

    def annotate_contextually(self, rows):
        try:
            from contextual_annotation import generate_annotations
            def notify(message):
                with self.lock:
                    self.annotation_job['message'] = message
            saved = excluded = 0
            for original, annotation in generate_annotations(rows, self.rows(), self.directory, notify):
                with self.lock:
                    current = next((r for r in self.rows() if r['id'] == original['id']), None)
                    if not current or current['text_hash'] != original['text_hash'] or not self.can_auto_label(current):
                        continue
                    annotations = dict(self.annotations)
                    annotations[original['id']] = annotation
                    suggestions = dict(self.suggestions)
                    suggestions.pop(original['id'], None)
                    self.save_workspace(annotations, self.imported, suggestions)
                    saved += bool(annotation['label'])
                    excluded += annotation['excluded']
            with self.lock:
                self.save_cleaned()
                dataset = [r for r in self.rows() if r['quality'] == 'ready' and r['label'] in LABELS]
                atomic_json(self.directory / 'dataset_auto.json', dict(label_policy='includes_automatic', rows=dataset))
                temp = self.directory / 'dataset_auto.csv.tmp'
                temp.write_bytes(csv_bytes(dataset))
                temp.replace(self.directory / 'dataset_auto.csv')
                self.annotation_job.update(message=f'Qwen hoàn tất: {saved} nhãn mới; loại {excluded} câu chưa rõ khỏi dataset.', error=False)
        except Exception as error:
            with self.lock:
                self.annotation_job.update(message=f'Gán nhãn Qwen dừng: {error}. Kết quả từng câu đã xử lý được giữ lại.', error=True)
        finally:
            with self.lock:
                self.annotation_job['running'] = False

    def start_training(self, body=None):
        body = body or {}
        mode, include_visobert = body.get('mode', 'optimized'), body.get('include_visobert', False)
        if mode not in ('baseline', 'optimized') or type(include_visobert) is not bool or (include_visobert and mode != 'optimized'):
            raise ValueError('Chế độ huấn luyện không hợp lệ.')
        algorithms = validate_algorithms(body.get('algorithms'), include_visobert, mode == 'optimized')
        with self.lock:
            if self.job['running'] or self.annotation_job['running'] or self.feature_job['running']:
                raise ValueError('Chờ tác vụ huấn luyện/gợi ý hiện tại hoàn tất.')
            rows = self.experiment_rows()
            split_dataset(rows)
            if not self.features or self.features['key'] != feature_key(rows):
                raise ValueError('Hãy trích xuất đặc trưng cho dữ liệu sạch có nhãn trước khi huấn luyện.')
            self.job = dict(running=True, message='Đang chuẩn bị tối ưu trên validation…' if mode == 'optimized' else 'Đang chuẩn bị các baseline…', error=False)
            try:
                threading.Thread(target=self.train, args=(rows, self.features, mode, include_visobert, algorithms), daemon=True).start()
            except Exception:
                self.job.update(running=False, error=True, message='Không khởi động được huấn luyện.')
                raise
        return dict(started=True)

    def train(self, rows, prepared=None, mode='optimized', include_visobert=False, algorithms=None):
        run = 'run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        try:
            def notify(message):
                with self.lock:
                    self.job['message'] = message
            if mode == 'optimized':
                from improvements import train_improved
                result = train_improved(rows, self.directory / 'runs' / run, notify, prepared=prepared,
                                        include_visobert=include_visobert, algorithms=algorithms)
            else:
                result = train_experiment(rows, self.directory / 'runs' / run, notify, prepared=prepared, algorithms=algorithms)
            with self.lock:
                current = self.experiment_rows()
                if fingerprint(rows) != fingerprint(current) or input_fingerprint(rows) != input_fingerprint(current):
                    raise ValueError('Dữ liệu thay đổi trong lúc huấn luyện; không thay kết quả hiện hành.')
                result = publish_run(result, self.directory / 'runs' / run, self.directory, rows)
                self.run = run
                self.job.update(message=f'Đã chạy {len(result["trained_models"])} cấu hình, giữ {len(result["retained_models"])} kết quả cũ phù hợp. Chọn mô hình bằng validation.', error=False)
            # A report failure must never turn successful model training into a failure.
            try:
                from system_report_video import STORE
                if self.directory.resolve() == STORE.data.resolve():
                    STORE.enqueue(run)
            except Exception:
                pass
        except Exception as error:
            with self.lock:
                self.job.update(message=f'Huấn luyện thất bại: {error}', error=True)
        finally:
            with self.lock:
                self.job['running'] = False

    def predict(self, body):
        text = body.get('text')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 20000:
            raise ValueError('Nhập bình luận từ 1 đến 20.000 ký tự.')
        with self.lock:
            if self.job['running']:
                raise ValueError('Chờ lượt huấn luyện hoàn tất trước khi dự đoán.')
            result, run = self.result(), self.run
        if not result:
            raise ValueError('Chưa có mô hình; hãy gán nhãn và huấn luyện trước.')
        answer = predict(text, self.directory / 'runs' / run, body.get('model') or result['selected_model'])
        answer['stale'] = self.result_stale(result, self.experiment_rows())
        if body.get('explain'):
            from pipeline_trace import build_trace
            answer['trace'] = build_trace(text, self.directory / 'runs' / run, answer)
        return answer

    def report(self):
        experiment = self.experiment_rows()
        return build_report(self.rows(), self.result(), experiment_fingerprint=fingerprint(experiment),
                            experiment_input_fingerprint=input_fingerprint(experiment))
