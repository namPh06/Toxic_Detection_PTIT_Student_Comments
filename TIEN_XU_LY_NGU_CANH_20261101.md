# Tiền xử lý ngữ cảnh — 01/11/2026

Đã tạo pipeline riêng context_preprocessing.py, chạy cục bộ bằng Pyvi 0.1.1, không dùng API trả phí. Đầu vào data/progress_with_context.json; đầu ra outputs/context_preprocessing_20261101/dataset.json. Chưa thay pipeline giao diện hoặc huấn luyện mô hình.

## Cách xử lý

Mỗi mẫu giữ riêng văn bản gốc, văn bản chuẩn hóa và văn bản tách từ của bài viết, chuỗi bình luận cha theo thứ tự nguồn, bình luận cần xét. model_text ghép các phần có tiêu đề; fields là dữ liệu có cấu trúc chính thức. Không chèn nhãn vào đầu vào mô hình.

Chuẩn hóa Unicode NFC, khoảng trắng, bỏ BOM và ký tự zero-width space. Giữ nguyên phủ định, stop words, tiếng tục, dấu câu, emoji và emoji nối bằng ZWJ; không tự mở rộng teencode mơ hồ. Không cắt ngắn, xóa trùng hay loại mẫu. Tách từ chỉ áp dụng trên các đoạn chữ để giữ nguyên dấu câu và emoticon. Chuẩn hóa không đồng nghĩa với hiểu ngữ nghĩa.

## Kết quả

- 5.936/5.936 mẫu được xuất; 369 nhóm bài chuẩn hóa danh tính.
- 5.649 mẫu có văn bản bài viết; 287 thiếu văn bản bài viết.
- 1.705 mẫu có phần bình luận cha, trong đó 3 mẫu chưa có văn bản cha; 7 mẫu chưa xác minh đầy đủ tổ tiên.
- Tổng cộng 294 mẫu có ít nhất một cờ thiếu ngữ cảnh (các loại có giao nhau).
- Cả 5.936 mẫu chưa có bằng chứng text_complete và bộ lọc bình luận; đây là hạn chế dữ liệu nguồn, không tự mặc định là đầy đủ.
- Ghép đúng 946 nhãn phát triển do người xác nhận: 114 toxic, 832 non-toxic. Những mẫu khác có supervision=null; nhãn AI chưa trở thành nhãn chuẩn huấn luyện.

context_gaps.json liệt kê các mẫu thiếu ngữ cảnh. manifest.json ghi cấu hình, hash nguồn và các giới hạn. target_usable chỉ có nghĩa văn bản đích không rỗng và không bị đánh dấu cắt, không xác nhận mẫu đã sẵn sàng làm nhãn chuẩn.

## Kiểm chứng

Đã kiểm tra toàn bộ 5.936 mẫu: văn bản gốc, thứ tự cha, hash đầu vào, dấu câu/emoji qua tách từ và toàn bộ 946 nhãn đều khớp. Hash các nguồn bảo vệ không đổi. Trường hợp phủ định, tiếng tục, emoticon và emoji gia đình ZWJ đều qua kiểm tra. Kết quả lưu verification.json. 29 kiểm thử hồi quy test_project và test_dataset_integrity đều qua. Kiểm thử mới thực hiện trực tiếp bằng Python -c, không tạo file test tạm.

## Tiếp theo

Tạo cách chia tập theo nhóm bài chuẩn hóa, nối nhóm văn bản trùng để tránh rò rỉ; giữ riêng các bài đã dành cho đánh giá. Sau đó so sánh mô hình chỉ đọc bình luận với mô hình đọc cả bài viết và bình luận cha trên cùng nhãn và cùng cách chia tập. Cần đánh giá precision, recall toxic và macro-F1; không thể suy ra độ chính xác nhãn từ việc tiền xử lý thành công.

Ảnh chưa được OCR, ngữ cảnh có thể thiếu hoặc thay đổi theo thời gian. Chưa thể cam kết nhận ra mọi câu đùa/mỉa mai hoặc gán nhãn đúng 100%.
