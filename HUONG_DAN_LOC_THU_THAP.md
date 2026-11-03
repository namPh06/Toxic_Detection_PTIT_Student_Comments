# Lọc bình luận khi thu thập

Trong màn hình **Thu thập dữ liệu**, chọn **Bình luận mới được giữ lại**: Tất cả, Chỉ toxic hoặc Chỉ non-toxic, rồi bắt đầu như trước. Khởi động lại máy chủ để nạp phiên bản mới.

Hai chế độ lọc dùng Ollama cục bộ với gemma3:4b đã cài trên máy và nội dung QUY_TAC_GAN_NHAN.md tại thời điểm bắt đầu. Không gọi API trả phí, không tải mô hình tự động. Cần mở Ollama khi lọc; chế độ Tất cả không cần Ollama.

Mô hình đọc câu cần xét cùng bài viết và chuỗi bình luận cha thu được. Các câu cha không đạt bộ lọc được giữ trong bộ nhớ để hỗ trợ xét câu con; bản chụp ngữ cảnh có thể đi cùng câu con được giữ. Chúng không trở thành mẫu bình luận riêng trong dataset. Ngữ cảnh/ảnh không có trong nguồn không được tự suy đoán.

Chỉ câu có nhãn trùng chế độ mới được đưa vào kho ROWS và progress.json, từ đó vào các bản xuất JSON/CSV. Câu chưa đầy đủ, quá dài, uncertain hoặc phản hồi không hợp lệ bị bỏ qua; lỗi dịch vụ dừng phiên và báo lỗi. Bộ đếm hiển thị các bình luận mới đã xét, giữ, loại và chưa rõ. Không tạo file chứa các câu bị loại.

Dữ liệu và nhãn có trước phiên được giữ nguyên, không bị xóa hoặc sửa bởi chế độ lọc. Vì vậy file tổng có thể vẫn chứa cả hai lớp từ các phiên trước. Muốn thu một tập chỉ toxic riêng cần dùng kho dữ liệu riêng, không xóa kho hiện tại.

Nhãn dùng để lọc là **nhãn máy chưa duyệt**, lưu nguồn automatic, needs_review và lý do/dẫn chứng, mã mô hình, băm quy tắc. Không tự trở thành nhãn chuẩn hoặc xuất vào dataset chỉ gồm nhãn đã duyệt. Không có bảo đảm đúng 100%; cần duyệt lại mẫu đã giữ và kiểm tra khả năng bỏ sót. Lọc từng câu trên CPU chậm hơn thu thập thông thường, giới hạn thời gian mỗi bài vẫn áp dụng. Các file dữ liệu đã xuất trước phiên không tự được viết lại.

Cập nhật 02/11/2026: giảm cửa sổ ngữ cảnh từ 16.384 xuống 8.192 token, batch 64 và dùng tối đa 32 lớp GPU cho mô hình hiện tại; nạp thử trước khi tìm bài. Ngữ cảnh đầu vào trên 6.000 ký tự chưa được xét, để tránh cắt mất quy tắc hoặc nội dung. Mô hình giữ trong bộ nhớ 2 phút sau yêu cầu cuối. Thiếu RAM/VRAM hoặc mất kết nối được báo trực tiếp trên tiến độ, không lưu câu chưa phân loại.
