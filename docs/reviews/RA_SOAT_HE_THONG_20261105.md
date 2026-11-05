# Rà soát hệ thống ngày 05/11/2026

## Kết luận

Hệ thống có đủ các thành phần chức năng chính theo đề bài. Chưa nên chốt bản trình diễn/báo cáo: còn lỗi khởi tạo bộ tách từ khi chạy đồng thời, lỗi nhập lại JSON có nhãn phân vân và tài liệu/video dùng snapshot cũ. Đây là kết quả kiểm tra mã nguồn, dữ liệu và artifact; không phải xác nhận thủ công tính đúng của từng nhãn.

## Các vấn đề cần xử lý

### 1. Lỗi đồng thời khi khởi tạo Underthesea — ưu tiên cao

- Vị trí: `backend/dataset.py:28`, hàm `word_tokens` và `_word_tokens_cached`.
- Wrapper hiện không khóa khởi tạo. Underthesea công bố đối tượng toàn cục trước khi nạp xong bộ featurizer; luồng khác có thể gọi đối tượng chưa hoàn chỉnh. Cache không ngăn nhiều lượt gọi đầu tiên đồng thời.
- Thử thực tế bằng 12 luồng gọi bộ tách từ từ trạng thái mới: 10 lượt lỗi `AttributeError: 'NoneType' object has no attribute 'process'`.
- Tác vụ video trên máy chủ cũng báo đúng lỗi này. Chạy riêng phần dựng bằng chứng tính toán video thì đạt.
- Hướng sửa: bảo vệ khởi tạo bằng khóa tại wrapper dùng chung, rồi kiểm tra lại nhiều lượt gọi đồng thời từ tiến trình mới.

### 2. JSON nhãn máy phân vân không nhập lại được — ưu tiên cao

- Vị trí: `backend/contextual_annotation.py:33` và `backend/dataset.py:263`.
- Nhãn contextual phân vân có `review_reason=uncertain_v4_semantic`, `model_score=null`, `label_threshold=null`.
- Bộ nhập chưa nhận trường hợp này trong danh sách nhãn không có điểm nên từ chối chính JSON xuất ra, báo `model_score phải từ 0 đến 1`.
- Đã tái hiện bằng kiểm thử roundtrip hiện có. Cần giữ nguyên giá trị null và cờ phân vân khi nhập; không tự tạo điểm tin cậy.

### 3. Tài liệu và video chưa khớp mô hình hiện tại

- Run mới nhất: `run-20261105T063735842643Z`; chuẩn hóa `ptit-v4-contextual-dc-20261105`; đặc trưng ký tự đã tắt.
- `README.md` và `docs/Report.md` còn số liệu 5.786/5.199 và mô tả cấu hình ký tự cũ.
- Video đóng gói tại `assets/report_video/manifest.json` thuộc run `run-20261104T182905355791Z`. Video mới đang lỗi như mục 1. Không dùng video cũ để giải thích số liệu run mới.
- Cần cập nhật tài liệu và tạo lại video sau khi sửa lỗi đồng thời.

### 4. Trạng thái đặc trưng sau khi mở lại hệ thống gây nhầm lẫn

- `backend/lab.py:31` đặt `self.features=None` khi khởi động và không khôi phục cache đặc trưng đã lưu.
- Vì thế giao diện có thể báo chưa trích xuất sau khi mở lại, dù `data/features.joblib` còn tồn tại và mô hình đã huấn luyện vẫn dùng được.
- Đây là hạn chế khôi phục trạng thái, không phải bằng chứng mất dữ liệu hay dự đoán sai. Nếu khôi phục cache, cần kiểm tra hash dữ liệu và phiên bản trước khi dùng.

## Dữ liệu và kết quả đã đối chiếu

| Nội dung | Kết quả |
|---|---:|
| Dòng dữ liệu gốc | 5.841 |
| Mẫu sạch có nhãn dùng được | 5.254 |
| Non-toxic trong mẫu dùng được | 4.162 |
| Toxic trong mẫu dùng được | 1.092 |
| Dòng trùng bị loại | 587 |
| Nhãn tự động / thủ công | 5.252 / 2 |
| Mẫu phát triển trong run hiện tại | 3.575 |
| Train / validation / test | 2.060 / 721 / 794 |

5.254 mẫu dùng được không đồng nghĩa tất cả được đưa vào run phát triển: còn 1.679 mẫu thuộc phần giữ riêng/ngoài tập phát triển hiện tại.

Đã tính lại chỉ số từ dự đoán lưu của cả năm mô hình, đối chiếu accuracy, precision, recall, F1 và confusion matrix với artifact: khớp. Nhãn dự đoán cũng khớp phép so sánh điểm với ngưỡng. Không có ID, bài viết hoặc nhóm chia giao nhau giữa train/validation/test.

| Mô hình | Macro-F1 test |
|---|---:|
| BoW–NB | 0,7302 |
| BoW–SVM | 0,7036 |
| TF-IDF–NB | 0,7076 |
| TF-IDF–SVM | 0,7364 |
| ViSoBERT | 0,8093 |

Tập test có 792/794 nhãn tự động. Các chỉ số trên phản ánh đối chiếu với nhãn dataset, chưa thay thế đánh giá độc lập trên tập được kiểm chứng thủ công.

## Luồng và thuật toán

- Lọc thu thập: bình luận mới phải qua bộ lọc nhãn trước khi được lưu ở chế độ chỉ toxic/non-toxic; mẫu phân vân không qua bộ lọc nghiêm ngặt này. Dữ liệu cũ không bị xóa bởi bộ lọc thu thập.
- Chính sách lọc đọc phiên bản quy tắc hiện hành và dùng chữ ký để làm mới cache.
- BoW/TF-IDF chỉ học từ vựng và IDF trên train; validation/test chỉ được biến đổi.
- Chia nhóm kết hợp bài viết và văn bản sạch trùng để tránh giao nhóm giữa các tập.
- Chọn ngưỡng và mô hình bằng validation, không dùng test để chọn.
- SVM sử dụng điểm quyết định, không coi đó là xác suất; NB dùng xác suất lớp toxic.
- ViSoBERT dùng văn bản Unicode cùng tokenizer riêng, có chọn CUDA khi khả dụng. Metadata run hiện tại ghi nhận NVIDIA RTX 3050 Laptop GPU.
- Phần dựng bằng chứng video đã chạy đạt với hai ví dụ; chưa có nghĩa MP4 mới đã tạo thành công.
- Không tìm thấy TextCNN trong các phần mã nguồn/tài liệu hoạt động đã tìm kiếm.

## Đối chiếu đề bài

Đã xem `assets/images/debai.png`. Các yêu cầu chính có triển khai: dữ liệu bình luận PTIT, chuẩn hóa/tách từ, BoW và TF-IDF, Naive Bayes và SVM, chia tập, accuracy/precision/recall/F1/confusion matrix, so sánh mô hình và mô hình hiện đại ViSoBERT. TextCNN không phải điều kiện bắt buộc khi đã chọn ViSoBERT. Có chức năng không tự động bảo đảm chất lượng nhãn hoặc mọi tình huống vận hành đều đạt.

## Kiểm thử và phạm vi

- Bộ unittest: 95 ca trong 51,681 giây; kết quả 4 failure, 2 error, 1 skipped. Log: `outputs/system_audit_verified_tests.log`.
- Một error là lỗi JSON thực tế ở mục 2. Error pickle còn lại xảy ra khi tạo fixture alias module cũ; không chứng minh artifact mô hình hiện tại bị hỏng.
- Bốn failure còn lại liên quan kỳ vọng CSV cũ về nguồn nhãn/metadata; cần đối chiếu lại hợp đồng xuất nhập, không xóa thông tin nguồn nhãn chỉ để làm xanh test.
- Kiểm tra dataset chia sẻ: hợp lệ. Kiểm tra phụ thuộc: không có xung đột. Kiểm tra cú pháp ba tệp JavaScript giao diện và `git diff --check`: đạt.
- Không chạy lại toàn bộ huấn luyện, không cào Facebook mới, không duyệt thủ công từng bình luận và không render lại toàn bộ MP4 trong lần rà soát này.
- Không tạo file test mới; các kiểm tra bổ sung chạy trực tiếp trong tiến trình. Không sửa mã nguồn trong lần rà soát này. Thay đổi có sẵn ở `backend/pipeline_trace.py` được giữ nguyên.

## Thứ tự hoàn thiện

1. Sửa khởi tạo bộ tách từ và kiểm tra cold-start đồng thời.
2. Sửa JSON roundtrip nhãn phân vân, đồng bộ kỳ vọng kiểm thử CSV.
3. Chạy lại các kiểm thử bị ảnh hưởng.
4. Tạo lại video từ run hiện tại, cập nhật số liệu và cấu hình trong tài liệu.
5. Kiểm tra trình diễn từ lúc mở hệ thống đến dự đoán và xem video trước khi chốt báo cáo.
