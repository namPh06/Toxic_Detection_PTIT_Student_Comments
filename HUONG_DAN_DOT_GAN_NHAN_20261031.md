# Gán nhãn đợt 2 — 31/10/2026

File: [Mở Excel](outputs/label_review_20261031/Gan_nhan_bo_sung_va_kiem_chung.xlsx).

## Việc bạn làm ngay

1. Mở sheet **Bo_sung_60**.
2. Đọc bình luận ở A và ngữ cảnh ở C. Nhập **t** (toxic) hoặc **n** (non-toxic) vào B.
3. Nếu chưa đủ căn cứ, để B trống và ghi lý do ở D. Không cần đoán cho đủ.
4. Lưu, đóng file và báo đã điền xong 60 câu để tiếp tục cải tiến.

Không sửa A, C, E, F, G hoặc chuyển dòng giữa hai nhóm. Có thể lọc hoặc sắp xếp cả bảng. Cột G chứa địa chỉ bài viết gốc nếu truy cập được. Ngữ cảnh C chỉ có bình luận cha nối bằng ID thực tế; dữ liệu chưa có nội dung bài viết. Với ô dài, đọc thanh công thức hoặc mở rộng hàng để xem đủ.

Sheet **Kiem_chung_200** dành cho bước kiểm chứng về sau. Điền cùng cách khi làm đến bước này. Nhãn nhóm này không được nhập chung vào tập huấn luyện hay dùng sửa prompt/ngưỡng. Excel không hiển thị dự đoán mô hình.

## Tiêu chí

Áp dụng [quy tắc v4](QUY_TAC_GAN_NHAN.md): xét hành vi xúc phạm, hạ nhục, quấy rối, kỳ thị, đe dọa hoặc cổ vũ gây hại. Chê trường, phàn nàn, phản biện và từ tục không tự động toxic. Thiếu ngữ cảnh thì để trống và ghi chú.

## Đã chuẩn bị

- 60 câu chưa được người dùng duyệt từ các bài đã có nhãn: 20 câu nhắc vấn đề trường học, 20 câu mô hình bất đồng, 20 câu gần ngưỡng mô hình thử. Đây là cách tìm câu cần đọc, không phải quy tắc gán nhãn.
- 200 câu chọn bằng thứ tự SHA256 với seed cố định, không dùng nhãn hay điểm dự đoán để chọn, từ 1.026 câu/217 bài chưa có nhãn người dùng. Mẫu trải trên 119 bài. Giữ riêng toàn bộ 119 bài, kể cả câu không được chọn, khỏi huấn luyện và truy hồi ví dụ.
- Hai nhóm không trùng bài. 476 nhãn hiện có và dữ liệu crawl không thay đổi.
- Dự đoán ONNX và mô hình kết hợp đã đóng băng trước nhãn mới để có mốc so sánh. Chưa đo chất lượng trên 200 câu vì chưa có nhãn. Mẫu này chỉ phản ánh nhóm bài chưa được duyệt, không đại diện toàn bộ 5.111 câu; số toxic thực tế còn chưa biết.

## Vận hành cho lần tiếp theo

Chạy trong thư mục dự án với Python của .venv:

- Kiểm tra số lượng và lỗi: python review_round.py check.
- Sau khi người dùng điền, xuất riêng nhãn phát triển: python review_round.py export-development. Lệnh không xuất nhãn kiểm chứng, không sửa workspace. Chỉ ô t/n đã được điền mới có nhãn; ghi chú câu chưa rõ được giữ trong kết quả kiểm tra.
- Bộ đọc review_excel.read_review vẫn đọc workbook 30/10 theo cấu hình cũ.

Hàm assert_training_posts_allowed đã được gọi trong learned_labeling, hybrid_labeling và truy hồi ví dụ semantic_v31. Hàm chặn bài thuộc danh sách kiểm chứng. Luồng mới cũng cần gọi rào chắn này trước khi học hoặc chọn ví dụ.

Không dùng nhãn kiểm chứng để chọn tham số. Lệnh evaluate-frozen chỉ đối chiếu hai mốc đã đóng băng, yêu cầu đủ 200 nhãn và chặn đánh giá lặp. Với ứng viên cải tiến tiếp theo, phải lưu thêm dự đoán/phiên bản mô hình trước khi mở nhãn kiểm chứng; chưa có ứng viên đó trong lần chuẩn bị này. Sau khi xem kết quả, lần chỉnh tiếp cần tập kiểm chứng mới.

## Kiểm tra lần tạo file

Đối chiếu đủ 260 mã/hash và ngữ cảnh: nhãn trống, không lỗi. 79 kiểm tra hồi quy đạt. Kiểm tra riêng từ chối nhãn lạ, công thức, sửa nội dung/ngữ cảnh, trùng mã, chuyển nhóm; giữ ô trống và ghi chú; đọc đúng 450 nhãn cũ; chặn bài kiểm chứng khỏi huấn luyện. File thử tạm được xóa tự động. Đã xem ảnh dựng cả ba sheet.
