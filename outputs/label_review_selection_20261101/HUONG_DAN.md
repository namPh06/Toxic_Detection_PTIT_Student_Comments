# Rà soát nhãn và kế hoạch kiểm tra — 01/11/2026

Đã quét 4165 nhãn máy theo dấu hiệu từ ngữ dễ nhầm; đọc lại 76 câu được lọc và đọc ngữ cảnh liên quan để chọn 18 câu cần người phụ trách quyết định. Đây là rà soát có mục tiêu, không phải xác nhận thủ công toàn bộ dữ liệu. Không thay đổi nhãn trong workspace.

- can_quyet_dinh.md/json: 18 câu, kèm bài viết, bình luận cha và lý do cần quyết định.
- kiem_tra_ngau_nhien.md/json: 300 câu lấy bằng thứ tự băm cố định từ 4059 câu máy gán non-toxic; dùng tìm toxic bị bỏ sót.
- kiem_tra_nhom_con_lai.md/json: toàn bộ 106 câu máy gán toxic; dùng tìm trường hợp bị gán toxic nhầm.
- doi_chieu_noi_bo.json: nhãn máy và thông tin chọn mẫu, tách khỏi biểu mẫu người duyệt.

Cách làm: trước tiên trả lời 18 câu theo số thứ tự với t/n/?. Sau đó duyệt hai bộ kiểm tra mà không xem file đối chiếu hoặc dự đoán cũ. Ghi ? nếu thiếu thông tin; không ép thành n. Các mẫu kiểm tra có thể trùng danh sách 18 câu, giữ nguyên và dùng cùng một quyết định, không đếm hai lần.

Đánh giá: báo riêng số câu sai, số câu chưa rõ và số câu đã duyệt; với mẫu 300 câu, tỷ lệ toxic phát hiện là ước lượng tỷ lệ bỏ sót trong nhóm máy gán non-toxic, không phải recall của mô hình. Nhóm 106 câu cho biết mức gán toxic nhầm trong nhóm dự đoán dương. Danh sách 18 câu được chọn có chủ đích không dùng để ước tính tỷ lệ lỗi toàn tập. Bình luận cùng bài có thể tương quan.

Nếu người duyệt sửa nhãn và dùng các câu này cải tiến hệ thống thì đây là dữ liệu phát triển/kiểm tra chất lượng nhãn, không còn là tập kiểm thử độc lập cuối cùng. Đánh giá NB/SVM cuối cùng cần tập người gán nhãn độc lập, giữ ranh giới nhóm bài viết và loại nhãn máy khỏi chuẩn đánh giá. Báo Precision/Recall/F1 của toxic, macro-F1, confusion matrix, kèm Accuracy; không kết luận từ Accuracy khi lớp lệch. Không bảo đảm 100% chính xác từ việc kiểm tra mẫu.

Nguồn ngữ cảnh có thể thiếu ảnh, phần văn bản bị thu gọn hoặc lịch sử hội thoại; biểu mẫu giữ cảnh báo trong JSON. Không suy ra quan hệ bạn bè hoặc đồng thuận chỉ từ emoji.

Đã kiểm tra: 18 ID hợp lệ, 300 mẫu không trùng nhau, 106 mẫu đúng nhóm nguồn; SHA256 workspace không đổi: 54330037502ba61a964c5c268ec633df98b7af5407afe5220a8d65cf59d2c521. Không tạo file test tạm.
