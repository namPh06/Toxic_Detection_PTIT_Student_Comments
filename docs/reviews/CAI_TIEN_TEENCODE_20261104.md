# Cải thiện teencode — 04/11/2026

Giữ nguyên text_raw và nhãn. Thêm text_normalized riêng trong dữ liệu chuẩn bị và CSV; text_clean dùng chuẩn hóa thận trọng. Không thay cố định mk, bn, dc; chỉ mở rộng một số mẫu có dấu hiệu cục bộ rõ. Giữ nguyên m và từ chưa rõ nghĩa. Giữ C++/C# trong văn bản sạch.

Trang trích xuất có tùy chọn bổ sung cụm ký tự 3–5 cho BoW/TF-IDF của NB/SVM. Từ vựng và IDF chỉ học trên train. Giới hạn số đặc trưng áp dụng từng nhánh; tổng tối đa gấp đôi. Cấu hình cũ vẫn đọc được.

Kiểm chứng: 86 kiểm thử, 85 qua và 1 bỏ qua (kiểm thử mô hình cục bộ tùy chọn). Đã huấn luyện và nạp lại 4 cấu hình BoW/TF-IDF × NB/SVM với nhánh ký tự trên bộ dữ liệu giả lập. Kiểm tra cú pháp JavaScript và so sánh cấu hình giao diện đều qua. Chưa đánh giá mức tăng F1 trên dữ liệu thực.

Hai tệp data/processed.json và data/workspace.json giữ nguyên mã SHA256. Không tự chạy gán nhãn hoặc huấn luyện lại dữ liệu thật.

Cách dùng: khởi động lại hệ thống, làm sạch dữ liệu, sang Trích xuất đặc trưng, bật Bổ sung đặc trưng ký tự rồi trích xuất lại và huấn luyện NB/SVM. ViSoBERT/Ollama tiếp tục nhận câu gốc theo luồng hiện có; không tích hợp bộ viết lại tự do.
