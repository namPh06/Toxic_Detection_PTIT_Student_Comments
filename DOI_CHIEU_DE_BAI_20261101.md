# Đối chiếu đề bài sau sửa chia tập — 01/11/2026

Đã đọc lại debai.jpg, safe_labeling_split.py, lab.py, experiments.py, word_preprocessing.py, artifact safe_fallback và cấu trúc BAO_CAO.md. Đây là rà soát, không huấn luyện thêm hoặc sửa nhãn.

## Mức đáp ứng

| Yêu cầu đề bài | Bằng chứng | Đánh giá |
|---|---|---|
| Bình luận sinh viên PTIT trên Facebook; phân loại toxic/non-toxic | progress.json: 5.936 mẫu từ 392 link | Đúng lựa chọn nguồn/bài toán; không xác minh được mọi tác giả đều là SV PTIT chỉ từ văn bản |
| Thu thập dataset | Có crawler, lưu JSON, văn bản bài/chuỗi cha | Có dữ liệu thực; 294 mẫu thiếu ngữ cảnh, độ đầy đủ nguồn chưa xác minh |
| Tiền xử lý, tách từ, stop words | word_preprocessing.py dùng Pyvi trước lọc stop words; dataset.py xử lý cũ; context_preprocessing.py giữ dấu câu/emoji/stop words | Đã có và đã chạy; ba đường xử lý cần mô tả chính xác, UI chưa dùng tách từ mới |
| Ít nhất hai phương pháp trích đặc trưng | CountVectorizer và TfidfVectorizer thực sự fit từng fold | Đạt phạm vi BoW và TF-IDF |
| Naive Bayes và SVM | Bốn cấu hình BoW/TF-IDF × MultinomialNB/LinearSVC, có joblib và OOF | Đã thực nghiệm cả hai, không bị thay bởi mô hình khác |
| Chia train/test | Có 5 fold nhóm; giao diện có mã chia train/validation/test theo split_group | Có kiểm chứng chia nhóm; kết quả mới là CV phát triển, chưa có lượt chạy đánh giá cuối trên test khóa trước |
| Accuracy, Precision, Recall, F1, Confusion Matrix | metrics.json có đủ cho cả bốn cấu hình, kèm macro-F1 | Đạt về cách tính/chỉ số; chất lượng dự đoán còn thấp |
| So sánh đặc trưng/thuật toán | Cùng 654 mẫu, cùng fold cho bốn cấu hình | Có thể so sánh trên cùng điều kiện; không so trực tiếp điểm với lượt 946 mẫu cũ |
| Báo cáo gồm tiêu đề, giới thiệu, cơ sở lý thuyết, thực nghiệm/kết quả, tài liệu tham khảo | BAO_CAO.md có các đề mục | Có cấu trúc; nội dung/kết quả lịch sử cần cập nhật để nộp |

Ảnh đề không quy định phải gán nhãn đúng 100%, mức accuracy tối thiểu, bắt buộc LLM/TextCNN, OCR hay thêm ngữ cảnh. Các mục này là mục tiêu cải tiến bổ sung. Kết quả yếu vẫn phải báo cáo trung thực, không đồng nghĩa đã thiếu thuật toán mà đề yêu cầu. Tuy nhiên cần lượt đánh giá cuối và báo cáo thống nhất để hoàn thiện bài.

## Kết quả hiện hành

654 nhãn phát triển: 572 non-toxic, 82 toxic. 292 nhãn canonical cũ được cách ly khỏi lượt phát triển mới do alias/trùng bắc cầu liên quan nhóm giữ riêng; không xóa nhãn. Tập giữ riêng đã từng được dùng chẩn đoán không được gọi là test mù mới.

| Cấu hình | Accuracy OOF | Precision toxic | Recall toxic | F1 toxic | Macro-F1 OOF |
|---|---:|---:|---:|---:|---:|
| BoW-NB | 0.8731 | 0.0000 | 0.0000 | 0.0000 | 0.4661 |
| BoW-SVM | 0.8563 | 0.0714 | 0.0122 | 0.0208 | 0.4716 |
| TF-IDF-NB | 0.8746 | 0.0000 | 0.0000 | 0.0000 | 0.4666 |
| TF-IDF-SVM | 0.8700 | 0.2857 | 0.0244 | 0.0449 | 0.4876 |

Chọn TF-IDF/SVM theo macro-F1 trung bình fold, không theo test độc lập. Mô hình này bỏ sót 80/82 toxic. Dự đoán toàn non-toxic trên 654 mẫu cũng có accuracy 572/654 = 87,46%; vì vậy accuracy khoảng 87% không chứng minh mô hình nhận diện toxic tốt.

251 gợi ý thiếu ngữ cảnh vẫn là nhãn máy cần duyệt, không trở thành nhãn chuẩn. 43 mẫu đã có nhãn người giữ nguyên. Chưa có mô hình huấn luyện được giao diện chọn qua data/latest.json; các joblib ứng viên lưu ở outputs không phải mô hình đã triển khai.

## Những việc chưa hoàn thành

1. Chưa so sánh NB/SVM đọc riêng bình luận với NB/SVM thêm bài viết/cha. Các mô hình safe_fallback hiện đọc word_text của câu đích, chưa đọc fields ngữ cảnh.
2. Chưa đồng bộ prompt ngữ nghĩa v2/v3.1 với chính sách v3.2. Không dùng các prompt cũ để tự chốt nhãn theo quy tắc hiện hành.
3. UI vẫn dùng text_clean cũ khi train/predict; chỉ phần bảo vệ ranh giới đã được nối. Cần ghi phiên bản đầu vào chính xác và kiểm thử tương thích khi nối pipeline mới.
4. Bảo vệ chia tập trong Lab.start_training hiện có điều kiện partitions.json tồn tại ở thư mục mặc định. Nếu artifact bị di chuyển/xóa, code quay về chia tập cũ; chạy trực tiếp experiments.py cũng không tự nạp reservation. Đây là giới hạn cần sửa trước bàn giao, không tuyên bố mọi đường chạy đều được bảo vệ. Giao diện còn có thể nhận nhãn imported mới không thuộc canonical; cần khóa snapshot nhãn/phiên bản khi đánh giá cuối.
5. Cách gộp cả câu trùng ngắn là bảo thủ, khiến nhiều bài nối bắc cầu. Cần mô tả quy tắc và số mẫu bị ảnh hưởng; không tự phá nhóm để tăng chất lượng đo.
6. Chưa có test cuối độc lập khóa trước và chưa đồng bộ BAO_CAO/README với kết quả mới. Không cần nhãn đủ cả 5.936 mẫu để bắt đầu thí nghiệm trên tập người duyệt.

## Kiểm tra lượt này

Hash toàn bộ đầu vào safe_fallback và hash partitions còn khớp. Kiểm tra cả 5 fold không chồng nhóm và không chứa nhóm giữ riêng: đạt. unittest discover: 79 ca, 78 đạt, 1 smoke mô hình thật bỏ qua mặc định; không chạy lại smoke thật trong lượt này. Không tạo file test tạm, không mở Facebook hoặc chạy E2E trình duyệt. Không tìm thấy tool/skill supperpower trong phiên.

## Thứ tự tiếp theo

Ưu tiên hoàn thiện bảo vệ chia tập trên mọi đường chạy và snapshot nhãn; đồng bộ chính sách/pipeline. Sau đó thử NB/SVM có và không có ngữ cảnh trên cùng fold, phân tích lỗi lớp toxic; khóa tập đánh giá cuối và cập nhật báo cáo. Chưa có cơ sở để tuyên bố gán nhãn đúng toàn bộ.
