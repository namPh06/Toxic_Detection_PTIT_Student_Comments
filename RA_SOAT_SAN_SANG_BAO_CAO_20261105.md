# Rà soát mức sẵn sàng làm báo cáo — 05/11/2026

## Kết luận
Đã đủ các thành phần chức năng và kết quả thực nghiệm theo debai.png để bắt đầu viết báo cáo. Không cần bổ sung TextCNN, ép tỷ lệ 50/50 hoặc huấn luyện lại chỉ để bắt đầu báo cáo. Đây không phải xác nhận mọi nhãn đều đúng hoặc hệ thống đã được kiểm định độc lập ngoài thực tế.

## Đối chiếu đề bài
| Yêu cầu | Hiện trạng | Kết luận |
|---|---|---|
| Thu thập dữ liệu | Selenium lấy bình luận Facebook, lưu bài viết/bình luận cha khi đọc được, JSON/CSV | Có |
| Tiền xử lý | NFC, xử lý URL/email/điện thoại, teencode theo ngữ cảnh, giữ phủ định; Underthesea cho NB/SVM | Có |
| Ít nhất hai biểu diễn đặc trưng | BoW và TF-IDF, mỗi loại ghép nhánh từ và char_wb; chỉ fit train | Đạt |
| Naive Bayes và SVM | BoW-NB, BoW-SVM, TF-IDF-NB, TF-IDF-SVM | Đạt |
| Chia train/test | Train 2.175, validation 699, test 646, nhóm bài độc lập | Đạt |
| Accuracy, Precision, Recall, F1, confusion matrix | Đủ cả năm mô hình; lớp dương toxic | Đạt |
| So sánh thuật toán/đặc trưng | Cùng tập chia, chọn tham số/ngưỡng theo validation | Có |
| Mô hình hiện đại bổ sung | ViSoBERT tinh chỉnh trên GPU, tokenizer riêng | Đạt |
| Báo cáo: giới thiệu, lý thuyết, thực nghiệm, tham khảo | Report.md được cập nhật từ kết quả hiện hành | Có bản nền; cần biên tập thành bài nộp |

## Dữ liệu và kết quả hiện hành
- Tổng 5.786 dòng / 622 bài; 587 bản trùng; 5.199 mẫu sạch có nhãn.
- Toxic 1.037 (19,95%); non-toxic 4.162 (80,05%).
- Nhóm phát triển 3.520 mẫu: 981 toxic, 2.539 non-toxic.
- 1.679 mẫu sạch thuộc các nhóm giữ riêng không tham gia lượt thực nghiệm; không tính 5.199 là cỡ mẫu train/test.
- Nguồn nhãn sạch: 5.198 automatic và 1 manual; toàn bộ 646 nhãn test là automatic.
- Run: run-20261104T182905355791Z; tiền xử lý: ptit-v4-contextual-dc-20261105.

| Mô hình | Accuracy test | Precision toxic | Recall toxic | F1 toxic | Macro-F1 test |
|---|---:|---:|---:|---:|---:|
| BoW-NB | 77.55% | 63.39% | 59.79% | 61.54% | 72.85% |
| BoW-SVM | 78.17% | 65.32% | 58.25% | 61.58% | 73.17% |
| TF-IDF-NB | 76.78% | 58.46% | 78.35% | 66.96% | 74.53% |
| TF-IDF-SVM | 80.50% | 68.68% | 64.43% | 66.49% | 76.37% |
| ViSoBERT | 84.37% | 75.41% | 71.13% | 73.21% | 81.09% |

## Bằng chứng kiểm tra
- Bộ unittest: 83 kiểm thử, 82 đạt, 1 bỏ qua (smoke mô hình cũ cần biến môi trường riêng); không phải phép đo độ chính xác Qwen.
- shared_dataset.py --check hợp lệ; pip check không có phụ thuộc lỗi.
- So sánh snapshot, phiên bản tiền xử lý và dấu vân tay đầu vào: khớp dữ liệu hiện tại.
- Các tập không giao nhau về ID, post_id, split_group hoặc text_clean.
- Nạp lại năm artifact, chạy dự đoán toàn bộ 646 mẫu test mỗi mô hình: 3.230 kết quả khớp nhãn đã lưu; điểm số khớp trong sai số 1e-5. Tính lại toàn bộ chỉ số và confusion matrix: khớp.
- ViSoBERT thực sự suy luận lại bằng CUDA trên NVIDIA GeForce RTX 3050 Laptop GPU.
- Kiểm tra mã lọc thu thập: đọc quy tắc hiện hành, chỉ lưu nhãn khớp chế độ; uncertain không vào kho bình luận chính. Tác vụ tự gán nhãn dùng cùng CollectionFilter và loại câu không quyết định được.
- Không thấy tham chiếu TextCNN trong mã Python/JS/HTML đang vận hành ngoài lịch sử và kiểm thử.
- Video tạo sẵn khớp run hiện hành; 28 phân đoạn, khoảng 9 phút 58 giây.
- Phiên máy chủ cũ đã được khởi động lại lúc không có tác vụ chạy để nạp mã hiện tại.
- Không tạo file test mới; kiểm tra bổ sung chạy trực tiếp từ stdin.

## Phạm vi chưa được xác nhận
- Chưa thực hiện một phiên crawl Facebook thật mới trong lượt rà soát này. Giao diện Facebook, quyền truy cập và độ đầy đủ bình luận vẫn phụ thuộc phiên đăng nhập; không khẳng định lấy đủ mọi bình luận.
- Chưa chạy phép đo độ chính xác Qwen độc lập trên bộ chuẩn do người gán nhãn. Bộ kiểm thử mô phỏng không thay thế việc này.
- Nhãn dùng ngữ cảnh khi có, nhưng năm bộ phân loại cuối chỉ nhận văn bản bình luận. Không mô tả ViSoBERT/NB/SVM hiện tại là mô hình hội thoại nhận cả bài viết và cha.
- Điểm test đo sự phù hợp với bộ nhãn tham chiếu hiện tại; không chứng minh nhãn đúng 100%. Bộ dữ liệu/test từng được xem trong quá trình phát triển, không gọi đây là kiểm định mù độc lập.
- Mất cân bằng lớp vẫn tồn tại: cần trình bày precision/recall/F1 toxic và macro-F1, không chỉ accuracy.

## Việc còn lại để nộp báo cáo
1. Biên tập Report.md thành định dạng bài nộp: thông tin nhóm, mục lục, hình/sơ đồ, bảng kết quả và tài liệu tham khảo theo mẫu giảng viên.
2. Trình bày đúng cấu hình chạy: BoW/TF-IDF ghép từ + ký tự; NB alpha và SVM C/ngưỡng lấy từ metrics.json/search.json; ViSoBERT tokenizer riêng, max_length 128, checkpoint epoch 4, GPU.
3. Thêm phân tích các lỗi FP/FN đại diện, giải thích giới hạn nhãn và ngữ cảnh; không thay nhãn dựa vào dự đoán để nâng điểm test.
4. Nếu muốn khẳng định độ chính xác thực, cần bộ đánh giá mới được người đọc gán độc lập; đây là bước tăng chất lượng bằng chứng, không phải yêu cầu định lượng ghi trong debai.png.
5. Chốt run trên để thống nhất bảng số liệu, ảnh giao diện và video; bổ sung dữ liệu/đổi tiền xử lý về sau thì chạy lại và cập nhật báo cáo.
