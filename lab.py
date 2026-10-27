"""Local dataset workspace; annotations never overwrite crawl output."""
import json
import re
import threading
from datetime import datetime, timezone

from dataset import LABELS, LABEL_METADATA, TOKENIZER_VERSION, atomic_json, csv_bytes, fingerprint, parse_import, prepare, row_id, summary, text_hash
from experiments import build_report, predict, split_dataset, train_experiment
from features import build_features, feature_key, feature_summary, preview_features, validate_settings


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
        if not isinstance(self.annotations, dict) or not isinstance(self.imported, list) or not isinstance(self.suggestions, dict):
            raise ValueError('Kho nhãn/dữ liệu nhập không hợp lệ; không ghi đè dữ liệu.')
        self.job = dict(running=False, message='Chưa chạy huấn luyện.', error=False)
        self.feature_job = dict(running=False, message='Chưa trích xuất đặc trưng.', error=False)
        self.features = None
        feature_path = self.directory / 'features.joblib'
        if feature_path.exists():
            try:
                import joblib
                self.features = joblib.load(feature_path)
                if self.features.get('schema_version') != 1:
                    raise ValueError('Phiên bản đặc trưng không còn phù hợp.')
                feature_summary(self.features)
                self.feature_job['message'] = 'Đã khôi phục bộ đặc trưng đã lưu.'
            except Exception:
                self.features = None
                self.feature_job.update(error=True, message='Không đọc được bộ đặc trưng đã lưu. Hãy trích xuất lại.')
        self.annotation_job = dict(running=False, message='Bấm “Làm sạch & gán nhãn toàn bộ” để tạo dataset trong một lần.', error=False)
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
            rows = prepare(self.source() + list(self.imported), self.annotations)
            for row in rows:
                suggestion = self.suggestions.get(row['id'])
                row['suggestion'] = (dict(suggestion) if suggestion and suggestion['text_hash'] == row['text_hash']
                                     and row['quality'] == 'ready' and not row['label'] else None)
            return rows

    def save_workspace(self, annotations, imported, suggestions):
        # One atomic file prevents half-imported rows/labels after a write failure.
        atomic_json(self.directory / 'workspace.json', dict(schema_version=1, annotations=annotations,
                                                            imported=imported, suggestions=suggestions))
        self.annotations, self.imported, self.suggestions = annotations, imported, suggestions

    def result(self):
        with self.lock:
            return self.read(f'runs/{self.run}/metrics.json', None) if self.run else None

    def status(self):
        with self.lock:
            rows = self.rows()
            result = self.result()
            job = dict(self.job)
            annotation_job = dict(self.annotation_job)
        stats = summary(rows)
        key = feature_key(rows)
        with self.lock:
            if self.split_check is None or self.split_check[0] != key:
                try:
                    split_dataset(rows)
                    self.split_check = (key, True, 'Đủ điều kiện kỹ thuật để chia tập; chưa phải chứng nhận chất lượng nhãn.')
                except ValueError as error:
                    self.split_check = (key, False, str(error))
            _, training_ready, training_message = self.split_check
        automatic = stats['label_sources'].get('automatic', 0)
        health = dict(reviewed=stats['labeled'] - automatic, automatic=automatic,
                      needs_review=sum(bool(r.get('needs_review')) for r in rows if r['quality'] == 'ready'),
                      suggested=sum(bool(r['suggestion'] and r['suggestion']['suggested_label']) for r in rows),
                      abstained=sum(bool(r['suggestion'] and not r['suggestion']['suggested_label']) for r in rows),
                      stale_annotations=sum(r['annotation_stale'] for r in rows), incomplete=stats['quality'].get('incomplete', 0),
                      unknown_completeness=sum(r.get('text_complete') is None for r in rows),
                      training_ready=training_ready, training_message=training_message)
        return dict(summary=stats, job=job, annotation_job=annotation_job, dataset_health=health, result=result,
                    features=self.feature_status(rows),
                    stale=bool(result and (result['fingerprint'] != fingerprint(rows) or
                                           (self.features and result.get('feature_created_at') != self.features['created_at']) or
                                           result.get('tokenizer_version') != TOKENIZER_VERSION)))

    def feature_status(self, rows=None):
        with self.lock:
            bundle = self.features
            stale = bool(bundle and bundle['key'] != feature_key(self.rows() if rows is None else rows))
            return dict(job=dict(self.feature_job), ready=bool(bundle and not stale), stale=stale,
                        result=feature_summary(bundle) if bundle else None)

    def feature_preview(self, index=0, split='all'):
        with self.lock:
            if not self.features or self.features['key'] != feature_key(self.rows()):
                raise ValueError('Chưa có đặc trưng phù hợp với dữ liệu hiện tại. Hãy trích xuất lại.')
            return preview_features(self.features, index, split)

    def start_features(self, body):
        settings = validate_settings(dict(body, embedding='word2vec', word2vec_path='', embedding_trainable=True))
        with self.lock:
            if self.feature_job['running'] or self.job['running'] or self.annotation_job['running']:
                raise ValueError('Chờ tác vụ trích xuất, huấn luyện hoặc gán nhãn hiện tại hoàn tất.')
            rows = self.rows()
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
                if bundle['key'] != feature_key(self.rows()):
                    raise ValueError('Dữ liệu đã thay đổi trong lúc trích xuất. Hãy chạy lại.')
                self.directory.mkdir(parents=True, exist_ok=True)
                joblib.dump(bundle, temp)
                temp.replace(self.directory / 'features.joblib')
                self.features = bundle
                self.feature_job.update(message='Đã lưu đặc trưng và embedding Word2Vec. TextCNN sẽ cho embedding học tiếp khi huấn luyện.', error=False)
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

    def dataset_rows(self, reviewed_only=True):
        rows = [r for r in self.rows() if r['quality'] == 'ready' and r['label'] in LABELS
                and (not reviewed_only or r['label_source'] != 'automatic')]
        if not rows:
            raise ValueError('Chưa có mẫu sạch phù hợp. Hãy gán nhãn toàn bộ, hoặc duyệt nhãn nếu cần bản dataset chỉ có người xác nhận.')
        return rows

    def save_cleaned(self):
        with self.lock:
            rows = self.rows()
            atomic_json(self.directory / 'processed.json', dict(rows=rows))
            temp = self.directory / 'processed.csv.tmp'
            temp.write_bytes(csv_bytes(rows))
            temp.replace(self.directory / 'processed.csv')
            return dict(saved=len(rows))

    def start_suggestions(self, automatic=False):
        with self.lock:
            if self.annotation_job['running'] or self.job['running'] or self.feature_job['running']:
                raise ValueError('Chờ tác vụ gợi ý/huấn luyện hiện tại hoàn tất.')
            rows = [r for r in self.rows() if r['quality'] == 'ready' and not r['label'] and (automatic or not r['suggestion'])]
            if not rows:
                raise ValueError('Không còn mẫu sạch cần xử lý. Có thể tải dataset đã gán nhãn.')
            self.annotation_job = dict(running=True, automatic=automatic, message=f'Đang xử lý toàn bộ {len(rows)} mẫu sạch chưa gán nhãn…', error=False)
            try:
                threading.Thread(target=self.suggest, args=(rows, automatic), daemon=True).start()
            except Exception:
                self.annotation_job.update(running=False, error=True, message='Không khởi động được tác vụ. Hãy thử lại.')
                raise
        return dict(started=True, total=len(rows))

    def suggest(self, rows, automatic=False):
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
                            annotations[item['id']] = dict(automatic_annotation(item), note=row['annotation_note'], excluded=False)
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

    def start_training(self):
        with self.lock:
            if self.job['running'] or self.annotation_job['running'] or self.feature_job['running']:
                raise ValueError('Chờ tác vụ huấn luyện/gợi ý hiện tại hoàn tất.')
            rows = self.rows()
            if not self.features or self.features['key'] != feature_key(rows):
                raise ValueError('Hãy trích xuất đặc trưng cho dữ liệu hiện tại trước khi huấn luyện.')
            self.job = dict(running=True, message='Đang chuẩn bị huấn luyện từ bộ đặc trưng đã lưu…', error=False)
            try:
                threading.Thread(target=self.train, args=(rows, self.features), daemon=True).start()
            except Exception:
                self.job.update(running=False, error=True, message='Không khởi động được huấn luyện. Hãy thử lại.')
                raise
        return dict(started=True)

    def train(self, rows, prepared=None):
        run = 'run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        try:
            def notify(message):
                with self.lock:
                    self.job['message'] = message
            result = train_experiment(rows, self.directory / 'runs' / run, notify, prepared=prepared)
            with self.lock:
                atomic_json(self.directory / 'latest.json', dict(run=run))
                self.run = run
                self.job.update(message=f'Đã hoàn tất {len(result["models"])} cấu hình. Kết quả chọn mô hình dựa trên validation.', error=False)
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
        answer['stale'] = result['fingerprint'] != fingerprint(self.rows())
        return answer

    def report(self):
        return build_report(self.rows(), self.result())
