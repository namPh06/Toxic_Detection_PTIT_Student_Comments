# Xét nhãn theo ngữ cảnh — bản thử cục bộ

Dùng tiêu chí trong QUY_TAC_GAN_NHAN.md (v2). Không gọi API trả phí, không tải mô hình mới. Sử dụng Gemma3:4b đã có trong Ollama trên máy.

context_labeling.py nối bình luận cha theo cặp post_id/comment_id, tối đa 8 cấp. Không lấy bình luận liền kề làm ngữ cảnh. Ghi rõ thiếu cha, vòng lặp hoặc thiếu nội dung bài viết. Dữ liệu hiện có chỉ có thông tin thu thập bài viết, chưa có nội dung bài viết để đọc.

Bộ xét yêu cầu mô hình xác định hành vi xúc phạm/đe dọa/kỳ thị/quấy rối, người viết có thực hiện hoặc tán thành hành vi đó không, đối tượng, bằng chứng nguyên văn và phần ngữ cảnh còn thiếu. Phàn nàn hoặc từ tục đơn lẻ không đủ kết luận toxic. Kết quả mâu thuẫn, bằng chứng sai hoặc đối tượng bị suy diễn được để Chưa rõ. Điều kiện đối tượng xuất hiện nguyên văn là kiểm tra bảo thủ, có thể bỏ sót công kích gián tiếp; không phải thuật toán chứng minh ngữ nghĩa.

Mọi kết quả vẫn cần duyệt (human_verified=false). CLI này chưa thay thế nút gán nhãn tự động của ứng dụng, không ghi nhãn vào workspace hay dùng làm nhãn chuẩn huấn luyện.

Chạy nhóm được chọn:

    .venv/Scripts/python.exe context_labeling.py --ids data/manual_review/priority_context5.json --output data/label_audit/context_priority5.json --limit 5

Kết quả phát triển trên 8 ví dụ: 5 khớp kỳ vọng, 3 chờ duyệt sau kiểm tra đối tượng; không có nhãn nhị phân sai trong nhóm nhỏ này. Đây là ví dụ phát triển, không phải độ chính xác kiểm định độc lập. Kết quả tại data/label_audit/context_feasibility.json; gồm cả checklist thô để kiểm tra lỗi suy diễn.

Đã chạy 10 bình luận thật: 7 đề xuất non-toxic, 3 chờ duyệt. Chín bình luận chưa được người xác nhận nên không thể tính độ chính xác. Mô hình còn hiểu sai cảnh báo nguy hiểm thành đe dọa; lớp kiểm tra đã chặn quyết định toxic ở câu này nhưng chưa sửa được khả năng hiểu nghĩa của mô hình.

Bước tiếp: người phụ trách xác nhận từng mẫu trong priority_context5.json, đặc biệt câu có khả năng toxic. Không hiển thị dự đoán khi xác nhận. Chỉ sau xác nhận mới lưu nhãn người đọc và dùng đối chiếu. Giữ riêng nhóm phát triển và nhóm đánh giá độc lập trong tương lai.
