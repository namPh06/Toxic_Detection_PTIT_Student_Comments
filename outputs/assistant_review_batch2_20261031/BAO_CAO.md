# Rà tiếp ngữ nghĩa — 31/10/2026

Đã đọc thêm 100 bình luận chưa được rà trước đó, đối chiếu quy tắc v3.2 và ngữ cảnh cha có sẵn: AI đề xuất 2 toxic, 80 non-toxic, 18 chưa đủ ngữ cảnh. Chọn theo thứ tự manifest lịch sử sau khi loại các câu đã đọc và bài viết dành riêng kiểm chứng; đây không phải mẫu đánh giá ngẫu nhiên.

File outputs/assistant_review_batch2_20261031/Duyet_tiep_19_cau.xlsx gồm Can_duyet_19 (18 câu mới chưa rõ + 1 câu cũ còn trống), AI_100 và Huong_dan. Điền t/n ở cột B, giải thích/ngữ cảnh bạn biết ở cột D. Những nhãn AI đều lưu riêng, human_verified=false và training_eligible=false. Không suy quan hệ bạn bè từ emoji hoặc cách xưng hô.

Đã hợp nhất nhãn người dùng đủ điều kiện vào data/manual_review/canonical_development_v32_20261031.json: 535 câu (85 toxic, 450 non-toxic), loại câu chưa chốt và các bài kiểm chứng. Các tham chiếu cũ là lịch sử; dùng bản hợp nhất này khi chuẩn bị bước huấn luyện tiếp theo. Chưa huấn luyện hoặc thay mô hình trong lượt này.

Tổng cộng 836 bình luận duy nhất đã được đọc qua các lượt, còn 4.275/5.111 câu chưa rà ngữ nghĩa. Con số đã đọc không đồng nghĩa đã có nhãn chuẩn. Chưa có bằng chứng mọi nhãn đúng.

Kiểm tra đạt: nguồn và workspace giữ nguyên byte/hash; 100 ID không trùng nhóm đã rà hoặc bài kiểm chứng; hash nội dung đúng; Excel có đúng ba sheet và ô B nhập nhãn để trống. Đã kiểm tra hình ảnh xem trước. Không phát sinh chi phí dịch vụ; không tạo file test tạm. Hồ sơ: assistant_labels.json, review_queue.json, verification.json trong cùng thư mục đầu ra.

Tiếp theo: nhập quyết định người dùng cho 19 câu khi có, tiếp tục đọc phần còn lại theo cùng quy tắc; chỉ đánh giá mô hình bằng nhóm kiểm chứng tách biệt và nêu rõ các nhãn đã được người dùng xem đề xuất AI.
