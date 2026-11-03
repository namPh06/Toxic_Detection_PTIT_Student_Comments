# Rà lại 435 nhãn người dùng — 31/10/2026

Đã đọc lại 435 câu và nhãn người dùng trong Can_bo_sung_435. Đủ 435/435: 25 toxic, 410 non-toxic, không còn ô nhãn trống; AI_4275 không có chỉnh sửa nhãn ở cột B. Kiểm tra toàn bộ ID, hash, nội dung và công thức: không phát hiện lỗi định dạng/định danh hay nhãn mâu thuẫn giữa sheet. Không sửa file Excel.

Đã ghi nhận đủ 435 nhãn vào user_labels.json. 411 câu thuộc phạm vi phát triển được nhập workspace, trong đó 5 câu giữ nguyên lựa chọn non-toxic nhưng tạm loại khỏi huấn luyện để làm rõ quy tắc. 24 câu thuộc bài đã dành riêng kiểm chứng lưu tại reserved_post_user_labels.json, không đưa vào workspace/phát triển. Bộ nhãn phát triển hợp nhất hiện 941 câu: 109 toxic, 832 non-toxic. Các nhãn người dùng khác giữ nguyên; có workspace_before.json và canonical_before.json để khôi phục.

## Năm câu cần xác nhận nghĩa/ngữ cảnh

1. **Can_bo_sung_435!B68** — éo mẹ quả xếp chỗ xem khắm vili
   Nhãn bạn chọn: n. Câu chê cách xếp chỗ xem là khắm. Cần xác nhận đây có phải dịch vụ/sự kiện do trường tổ chức hay chỉ nhận xét sự kiện ngoài trường.

2. **Can_bo_sung_435!B81** — Nguyễn Anh Minh Được cấp phép nhma xây như này thì tiền đi đâu :((((
   Nhãn bạn chọn: n. Nêu xây như này thì tiền đi đâu có thể là chê công trình và ám chỉ chi tiêu của trường; chưa có giải thích để áp dụng ngoại lệ góp ý.

3. **Can_bo_sung_435!B85** — Trọng Khánh tăng nữa tăng mãi bạn ạ. Cứ tưởng có nhà xe ngon ai ngờ vớ ngày đc thiết kế đi vào lòng đất
   Nhãn bạn chọn: n. Nói tăng học phí và nhà xe được thiết kế đi vào lòng đất có vẻ trực tiếp chê trường; cần đối chiếu lại nhãn n với quy tắc riêng.

4. **Can_bo_sung_435!B113** — thương trường nghề Nguyễn Trãi
   Nhãn bạn chọn: n. Thương trường nghề Nguyễn Trãi có thể là tự trào hoặc gọi trường bằng tên hạ thấp; cần xác nhận nghĩa trong bài gốc.

5. **Can_bo_sung_435!B122** — Tiến Long Trần Mihn cao đẳng ptit vẫn là căng đảo bitis
   Nhãn bạn chọn: n. Cao đẳng PTIT có thể là hạ thấp trường hoặc trích/đùa để bảo vệ trường. Cần xác nhận vì những câu trường nghề/cao đẳng khác trong file được chọn toxic.

Không tự sửa nhãn người dùng. Những cờ này là yêu cầu làm rõ phạm vi quy tắc, không phải kết luận người dùng gán sai. Các nhãn n còn lại không mặc nhiên được giải thích là đùa thân mật nếu không có ghi chú cụ thể. Các câu xúc phạm bạn bè vẫn cần tuân thủ ngoại lệ v3.2; lượt này ghi nhận quyết định của người dùng, không tạo thêm bằng chứng quan hệ.

## Giới hạn

Đây là nhãn do người dùng duyệt sau sàng lọc/đề xuất AI, không phải kiểm chứng mù. Việc rà lại chưa chứng minh toàn bộ 5.111 nhãn đúng; 3.859 đề xuất có nhãn của lượt AI trước vẫn chưa được người dùng xác nhận. Không dùng các đề xuất đó làm nhãn chuẩn hoặc tự tính độ chính xác. Chưa huấn luyện/thay mô hình; chưa đo độ chính xác mới. Nguồn và Excel giữ nguyên hash. Không phát sinh phí dịch vụ, không tạo file test tạm.
