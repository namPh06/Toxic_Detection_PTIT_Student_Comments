# Chia tập an toàn và nhãn dự phòng — 01/11/2026

Đã thêm safe_labeling_split.py. Chạy cục bộ, không dùng API trả phí. Không tìm thấy tool/skill supperpower trong phiên.

## Ranh giới mới

Chuẩn hóa canonical_post_id, gộp bắc cầu các bài có bình luận trùng theo bản chuẩn hóa giữ nghĩa và các biểu diễn tiền xử lý cũ, rồi mới áp dụng danh sách 119 bài giữ riêng. So khớp trùng không dùng nhãn hay học vocabulary trên tập giữ riêng. Câu trùng ngắn phổ biến vẫn nối nhóm; lựa chọn bảo thủ này làm giảm số mẫu phát triển, không âm thầm tách nhóm để tăng điểm.

Có 2.396 mẫu thuộc 102 nhóm giữ riêng sau khi mở rộng nhóm trùng. Trong 946 nhãn phát triển cũ, 292 thuộc nhóm cần cách ly; giữ nguyên nhãn nhưng loại khỏi lượt phát triển mới. Còn 654 nhãn (82 toxic, 572 non-toxic), 111 nhóm. Toàn bộ 5.936 mẫu đều có phân vùng trong partitions.json. 292 mẫu không trở thành test mù mới vì đã được dùng trước đây.

Đã xuất cùng 5 fold cho bốn cấu hình BoW/TF-IDF × NB/SVM. Mỗi mẫu phát triển có đúng một dự đoán OOF. Không chồng nhóm canonical, nhóm trùng, ID hoặc đầu vào văn bản giữa train và validation; không có nhóm giữ riêng trong CV. Vectorizer chỉ fit train. Đây là CV phát triển, không phải test độc lập.

lab.py áp dụng manifest mới khi bắt đầu huấn luyện cho workspace dự án: kiểm tra hash dữ liệu nguồn và partitions, chặn mẫu mới/nội dung đổi, loại nhãn automatic và nhóm giữ riêng. experiments.py dùng split_group để chia. Kiểm tra đường giao diện bằng gọi hàm và mock luồng huấn luyện cho 654 mẫu có nhãn: train 362, validation 75, test 217, không chồng nhóm. Đây vẫn là cách chia phát triển trên nhãn từng dùng, không phải đánh giá mù cuối. Chưa chạy huấn luyện giao diện hoặc E2E trình duyệt.

## Gợi ý nhãn dự phòng

294 mẫu có cờ thiếu ngữ cảnh được dự đoán chỉ từ bình luận, gồm:

- 251 gợi ý nhãn máy mới: 250 non-toxic, 1 toxic.
- 43 mẫu đã có nhãn người: giữ nguyên, không tạo nhãn thay thế; dự đoán ứng viên để đối chiếu.

Lưu fallback_review.json. Mỗi mẫu có văn bản, hash, nhóm, cờ thiếu ngữ cảnh, dự đoán cả bốn mô hình và nguồn dự đoán. Mẫu phát triển dùng dự đoán OOF; mẫu ngoài phát triển dùng mô hình chỉ fit 654 nhãn phát triển. Tất cả gợi ý cần duyệt, human_verified=false, không nhập workspace và không làm đáp án đánh giá. Nhãn người vẫn tách riêng. Không xuất xác suất đúng giả: score=null vì điểm NB/SVM chưa hiệu chỉnh. Cờ thiếu ngữ cảnh chỉ là cách chọn mẫu cần xem, không chứng minh từng câu đều khó hiểu.

TF-IDF/SVM được chọn theo macro-F1 trung bình fold; macro-F1 OOF 0,4876, recall toxic 2/82 (2,44%). NB phát hiện 0/82; BoW/SVM 1/82. Chưa đủ để tự chốt nhãn hoặc thay mô hình sản xuất. So sánh trực tiếp điểm này với lượt 946 mẫu cũ không công bằng vì tập phát triển đã thay đổi. Luồng này học theo nhãn canonical v3.2, không gọi các prompt ngữ nghĩa cũ; việc đồng bộ toàn bộ prompt cũ vẫn còn trong danh sách rà soát.

## Kiểm chứng và tệp

Kiểm chứng toàn corpus, hash nguồn/nhãn không đổi, các fold không chồng, nguồn OOF cho mẫu phát triển, 43 nhãn người được bảo vệ, nạp lại bốn joblib; tình huống tổng hợp alias và chuỗi trùng bắc cầu đều đạt. verification.json lưu kiểm chứng offline. Kiểm tra đường huấn luyện UI và chặn văn bản đổi đạt. Không tạo file test tạm.

Tất cả artifact nằm tại outputs/safe_fallback_20261101: partitions.json, folds.json, metrics.json, fallback_review.json, bốn OOF và bốn mô hình ứng viên. Mô hình triển khai chưa thay; JSON nguồn và workspace chưa sửa.

Tiếp theo: dùng ranh giới/fold này để so sánh đầu vào có ngữ cảnh với chỉ bình luận; xử lý mất cân bằng và xem FP/FN. Hoàn thiện chính sách prompt trước khi dùng lại mô-đun LLM ngữ cảnh cũ. Chưa yêu cầu người dùng gán lại toàn bộ dữ liệu.
