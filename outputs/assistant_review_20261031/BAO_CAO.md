# Rà soát ngữ nghĩa ngày 31/10/2026

Đã kiểm tra và nhập 60 nhãn người dùng mới (6 toxic, 54 non-toxic). Workspace hiện có 536 nhãn người dùng: 70 toxic, 466 non-toxic. Giữ nguyên 476 quyết định trước; sao lưu workspace trước nhập ở outputs/assistant_review_20261031/workspace_before_import.json.

Đã tự đọc 200 câu còn trống của Kiem_chung_200 theo tiêu chí v3.1 và bình luận cha có sẵn: đề xuất 2 toxic, 187 non-toxic, để 11 câu chưa rõ. Mỗi câu có lý do riêng trong assistant_labels.json. Nguồn là assistant_semantic_review, human_verified=false; không nhập các nhãn này vào tập nhãn người dùng hoặc dùng để đo độ chính xác. Đây là kết quả đọc của trợ lý trong phiên này, chưa phải thuật toán tự động có thể tái chạy trong ứng dụng.

Đã rà lại toàn bộ 536 nhãn người dùng: 83 trường hợp cần đối chiếu (29 đề xuất toxic, 54 cần làm rõ). Giữ nguyên nhãn gốc, đề xuất nằm riêng. 36 quyết định đã được người dùng xử lý riêng theo v3.1 được giữ nguyên, không đưa lại vào hàng chờ chỉ vì khác cách hiểu phổ thông. Không phát hiện vấn đề mới ở 453 câu còn lại không đồng nghĩa bảo đảm chúng đúng tuyệt đối.

Excel kết quả: [Kết quả gán nhãn và rà soát](outputs/assistant_review_20261031/Ket_qua_gan_nhan_va_ra_soat.xlsx). Sheet Can_xem_lai có 94 dòng = 83 nhãn người dùng cần đối chiếu + 11 câu AI chưa rõ. Cột B cho người dùng chốt t/n, cột C nhãn gốc, D đề xuất, E lý do, F ngữ cảnh. AI_200 lưu toàn bộ đề xuất; Ra_soat_536 lưu toàn bộ lượt rà; JSON đi kèm lưu ID/hash/nguồn.

Phạm vi đọc ngữ nghĩa lần này là 736 câu, gồm 536 nhãn người dùng và 200 câu AI. Chưa đọc ngữ nghĩa hết 5.111 câu sạch. Dự đoán toàn bộ corpus của ONNX là bộ nhớ đệm mô hình, không phải nhãn chuẩn. Không có bằng chứng đúng hết; chưa nâng cấp/triển khai mô hình mới. Không phát sinh phí API.

Không chỉnh file Excel gốc và dữ liệu crawl. Giữ riêng 119 bài của nhóm 200 khỏi huấn luyện/truy hồi. Không chạy evaluate-frozen với nhãn AI. Muốn kiểm chứng độc lập vẫn cần người đọc xác nhận nhóm này mà không dựa vào đề xuất AI, hoặc tạo tập mới trước một lần thử mô hình sau.

---

