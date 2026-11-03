# Hoàn tất nhãn máy và thống kê — 01/11/2026

Đã chạy complete_machine_labels.py, bổ sung 4.165 nhãn automatic vào data/workspace.json: đối chiếu và dùng lại 3.941 đề xuất semantic v3.2 khớp ID/hash nội dung; 224 mẫu còn thiếu dùng TF-IDF/SVM dự phòng fit trên 654 nhãn phát triển đã cách ly. Không gọi API trả phí hoặc tải mô hình mới. Không tìm thấy supperpower trong công cụ phiên này.

## Kết quả trên mẫu sạch duy nhất

| Nguồn | Toxic | Non-toxic | Tổng |
|---|---:|---:|---:|
| Người duyệt | 114 | 832 | 946 |
| Máy, chưa xác nhận | 106 | 4.059 | 4.165 |
| Toàn bộ | 220 | 4.891 | 5.111 |

Toxic toàn bộ nhãn hiện là 4,3044%; riêng nhãn người duyệt 12,0507%. Đây là phân bố nhãn đang lưu, không phải ước lượng tỷ lệ toxic thật trong quần thể hay chứng nhận nhãn đúng. Đề xuất semantic cũ có trước lúc bổ sung bài viết; lần này đối chiếu nguyên văn và metadata, không phải đọc lại bằng mô hình ngữ cảnh mới. Mô hình dự phòng có recall toxic thấp. Tất cả 4.165 nhãn máy needs_review=true và human_verified=false, score/threshold=null vì không có xác suất đã hiệu chỉnh.

5.936 mẫu nguồn vẫn nguyên vẹn. 736 bản trùng và 89 dòng empty_or_ui không ép gán nhãn thành mẫu độc lập. Không còn mẫu ready chưa có nhãn. 946 annotation cũ được giữ nguyên toàn bộ object; snapshot trước khi ghi lưu ở outputs/completed_labels_20261101/workspace_before.json. Các nhãn chẩn đoán riêng ngoài workspace giữ lịch sử riêng, không được dùng để nâng nhãn máy thành nhãn chuẩn tại bước này.

## Cần thêm bao nhiêu toxic?

Ảnh đề không quy định tối thiểu mẫu toxic, tổng mẫu hay tỷ lệ cân bằng. Vì vậy không có con số bắt buộc phải kiếm thêm để đạt điều kiện số lượng trong ảnh. Không cần ép tỷ lệ 50–50. Chất lượng nhãn và đánh giá vẫn phải hoàn thiện.

Các kịch bản dưới đây chỉ là phép tính khi GIỮ toàn bộ mẫu đang có và CHỈ thêm toxic mới, hợp lệ, không trùng, được người đọc xác nhận:

| Mục tiêu toxic | Trên 5.111 nhãn gồm máy (220 toxic tạm) | Trên 946 nhãn người (114 toxic) |
|---|---:|---:|
| 20% | thêm 1.003 | thêm 95 |
| 25% | thêm 1.411 | thêm 164 |
| 30% | thêm 1.877 | thêm 243 |
| 50% | thêm 4.671 | thêm 718 |

Công thức x = max(0, ceil((q*N - T)/(1-q))). Những số này không bảo đảm chất lượng mô hình, không có nghĩa phải thu thập bấy nhiêu; đổi một nhãn sai đang có thì tính lại. Nếu thu thêm cả non-toxic, số toxic cần thêm cũng đổi.

Tập phát triển dùng thực nghiệm sau reservation hiện chỉ 654 nhãn (82 toxic). Nếu chỉ thêm toxic vào đúng tập này, tỷ lệ 20% cần thêm 61; 25% thêm 109; 30% thêm 164. Mẫu bổ sung phải qua kiểm tra nhóm bài/trùng và tạo lại manifest, không được lấy từ nhóm giữ riêng để tùy tiện cải thiện train. Nên đo lại recall/precision toxic thay vì chọn số mẫu theo tỷ lệ một cách máy móc.

## Tích hợp và kiểm chứng

Nhãn máy mới được lưu đúng label_source=automatic, không trở thành nhãn người. dataset.py hỗ trợ xuất/nhập nhãn chưa có score với reason riêng và bắt buộc needs_review=true; UI mô tả đúng trạng thái này. CSV/JSON mẫu thử nhập lại vẫn giữ nguồn automatic và score=null. Toàn bộ nguồn và 946 annotation người khớp backup, phân bố quality không đổi. Đường huấn luyện tiếp tục loại nhãn máy và nhóm reserved; kiểm tra trực tiếp còn 654 nhãn dùng được, không bắt đầu huấn luyện.

unittest discover: 79 ca, 78 đạt, 1 smoke mô hình thật bỏ qua mặc định. Kiểm tra bổ sung chạy Python -c, không tạo file test tạm. Không chạy E2E trình duyệt. Nếu ứng dụng đang mở từ trước khi ghi workspace, cần khởi động lại ứng dụng để nạp nhãn mới; chưa thao tác với phiên máy chủ đang chạy trong bước này.

Artifact outputs/completed_labels_20261101: dataset_auto.csv/json, summary.json, new_annotations_audit.json, rejected_proposals.json, workspace_before.json. Không thay mô hình triển khai. Workspace đổi làm hash workspace trong artifact tiền xử lý/baseline cũ không còn khớp; đây là thay đổi chủ ý, cần tạo snapshot/manifest mới khi chạy thí nghiệm tiếp theo, không ghi đè lịch sử.
