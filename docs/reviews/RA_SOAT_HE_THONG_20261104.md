# Rà soát hệ thống — 04/11/2026

Đối chiếu trực tiếp debai.png, mã nguồn, dữ liệu chia sẻ và run `run-20261103T183548227832Z`.

## Đối chiếu đề bài

| Yêu cầu | Bằng chứng hiện tại |
|---|---|
| Thu thập bình luận Facebook liên quan PTIT | Selenium; lưu bài viết, bình luận, liên kết cha và trạng thái đầy đủ. Chưa chạy lại một phiên Facebook thật trong lần rà soát này. |
| Tiền xử lý, tách từ, stopwords | Có chuẩn hóa, tách từ, lọc trùng/chất lượng; nhánh Transformer giữ Unicode, dấu câu và tiếng lóng phù hợp tokenizer riêng. |
| Ít nhất hai cách biểu diễn | BoW, TF-IDF; thêm embedding cho ViSoBERT. |
| Naive Bayes, SVM | Có đủ bốn tổ hợp BoW/TF-IDF × NB/SVM, đã lưu mô hình. |
| Chia tập huấn luyện và kiểm tra | Có train/validation/test; kiểm tra trực tiếp split đã lưu: không giao nhóm bài giữa ba tập. |
| Accuracy, Precision, Recall, F1, Confusion Matrix và so sánh | Có trong metrics.json, dự đoán từng mẫu và Report.md; đã tính lại macro-F1/confusion matrix từ dự đoán test của các mô hình được giữ lại. |
| Bổ sung mô hình hiện đại | Có ViSoBERT. |
| Báo cáo | Report.md đã cập nhật đúng run mới nhất và fingerprint dữ liệu hiện tại. |

## Dữ liệu và kết quả đã lưu

- Tổng 5.786 dòng: 5.199 mẫu sạch duy nhất và 587 dòng trùng.
- 5.199 nhãn dùng được: 1.037 toxic (19,95%), 4.162 non-toxic (80,05%).
- Nguồn nhãn: 5.198 automatic, 1 manual. Đây không phải 5.199 nhãn đã được người kiểm tra độc lập.
- Tập phát triển: 3.520 mẫu (981 toxic, 2.539 non-toxic).
- 1.679 mẫu có nhãn thuộc nhóm lịch sử được giữ riêng. Nhóm này không phải tập kiểm tra mù độc lập.
- Con số 2.266 chưa sử dụng trên giao diện = 587 trùng + 1.679 giữ riêng; phần mô tả ngắn của giao diện chưa giải thích rõ trường hợp giữ riêng.
- Train 2.175 mẫu, validation 699, test 646. Toàn bộ 646 nhãn test là automatic.

| Mô hình | Macro-F1 test tính lại |
|---|---:|
| BoW-NB | 0,753767 |
| BoW-SVM | 0,741983 |
| TF-IDF-NB | 0,737100 |
| TF-IDF-SVM | 0,771003 |
| ViSoBERT | 0,815279 |

ViSoBERT: confusion matrix [[403,49],[51,143]], hàng là nhãn dataset, cột là dự đoán; thứ tự non-toxic, toxic. Các kết quả mô tả khả năng khớp nhãn dataset hiện tại, chưa đủ để khẳng định độ chính xác theo đánh giá con người.

## Kiểm thử và sửa đổi

- Toàn bộ unittest Python: 83 kiểm thử, 82 đạt, 1 bỏ qua do thiếu mô hình ONNX cục bộ tùy chọn. Chạy lại sau khi cài CUDA: vẫn đạt, thời gian 37,349 giây. Ba kiểm thử cấu hình GPU/CPU riêng cũng đạt trước đó.
- Huấn luyện dữ liệu giả: NB/SVM, lưu/nạp, dự đoán và báo cáo đã được kiểm thử.
- Đồng bộ kiểm thử API/gán nhãn với luồng contextual_annotation hiện tại; bỏ kỳ vọng cũ rằng nhãn máy phải được duyệt mới xuất được. Mô hình nhãn thật không bị gọi trong các kiểm thử này.
- shared_dataset.py --check: valid=true; dấu kiểm toàn vẹn và nhãn khớp dữ liệu.
- git diff --check: đạt.
- Không ghi đè mô hình thực nghiệm hiện tại, không sửa nhãn dữ liệu. File kiểm thử tạm được xóa; kiểm thử có sẵn của dự án được giữ lại.

## GPU

Trước sửa: máy có RTX 3050 Laptop 4 GB nhưng PyTorch là bản CPU, nên CUDA không được nhận. Mã huấn luyện vốn đã tự chọn CUDA nếu khả dụng.

Đã bổ sung: dự đoán ViSoBERT cũng tự chọn GPU; GPU tối đa 6 GB dùng batch thực tế tối đa 2, tăng tích lũy gradient và bật gradient checkpointing. Với cấu hình mặc định: batch 2, tích lũy 8. Thông số thực tế lưu trong training.json và tên thiết bị hiện trong nhật ký. Không bảo đảm mọi độ dài/cấu hình đều vừa VRAM.

Kết quả kiểm chứng GPU thực tế: đã cài torch 2.10.0+cu128; CUDA 12.8 khả dụng, nhận NVIDIA GeForce RTX 3050 Laptop GPU. Phép nhân ma trận CUDA đạt. ViSoBERT huấn luyện một epoch trên bốn mẫu giả, lưu/nạp và dự đoán đều đạt. Lặp lại với câu dài tới giới hạn 128 token cũng đạt, bộ nhớ tensor đỉnh khoảng 1.880 MiB (không bao gồm toàn bộ bộ nhớ driver/ứng dụng khác). Đây là kiểm thử chức năng, không phải phép đo chất lượng hay benchmark tốc độ toàn dataset. pip check không phát hiện phụ thuộc hỏng.

CPU mặc định chỉ tinh chỉnh hai tầng encoder cuối; GPU tinh chỉnh toàn bộ encoder. Vì khác chiến lược nên không dùng thời gian và điểm hai lần chạy này làm so sánh tốc độ/chất lượng có kiểm soát.

## Phần còn hạn chế

Chưa chạy kiểm thử giao diện trình duyệt, một lượt thu thập Facebook thật hoặc huấn luyện lại đầy đủ toàn bộ dataset trong lần rà soát này. Kiểm thử phần mềm đạt không có nghĩa tất cả nhãn đúng. Ưu tiên chất lượng đánh giá tiếp theo là tập kiểm tra độc lập có nhãn con người và đủ mẫu toxic, đồng thời giữ nguyên ranh giới nhóm để tránh rò rỉ dữ liệu.
