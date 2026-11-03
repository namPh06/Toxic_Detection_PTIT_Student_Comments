# Gán lại toàn bộ nhãn theo v4

Phạm vi: 6.658 bình luận trong ảnh chụp dữ liệu ngày 02/11/2026, bao gồm dữ liệu mới cào có trong data/progress.json tại thời điểm bắt đầu.

Đang chạy mô hình cục bộ Qwen. Xem status.json để biết số lượng đã xử lý; classification_complete chỉ xác nhận phân loại xong. Chỉ khi applied.json xuất hiện mới xác nhận dữ liệu đang dùng đã được cập nhật.

Mỗi câu được xét lại với bài viết và chuỗi cha có định danh. Mẫu thiếu ngữ cảnh cần thiết, nội dung không đầy đủ hoặc không thể phân loại sẽ bị loại khỏi dữ liệu đang dùng. Bản gốc được lưu trong before_*.json và snapshot.json.

Khi hoàn tất, dataset_v4.json/csv chứa dữ liệu dùng được; excluded_v4.json/csv chứa mẫu loại; audit.json lưu nhãn cũ, nhãn mới và lý do. Nhãn do máy gán, không bảo đảm đúng tuyệt đối và không coi là người đã duyệt.

Tiến trình sẽ dừng nếu nguồn dữ liệu thay đổi trong lúc chạy, tránh ghi đè dữ liệu vừa cào thêm. Không chạy thêm phiên gán nhãn hoặc thu thập vào cùng nguồn khi tiến trình còn chạy.
