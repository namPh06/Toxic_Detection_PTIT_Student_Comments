# Rà soát trước triển khai video — 04/11/2026

## Kết luận

Các luồng phần mềm được kiểm thử hoạt động; chưa nên chốt video báo cáo như bản hiện hành trước khi huấn luyện lại bằng chuẩn hóa v3. Lượt rà soát này không huấn luyện lại toàn bộ, không sửa nhãn hay ghi đè mô hình.

## Đối chiếu debai.png

Có nguồn bình luận PTIT, tiền xử lý/tách từ/stopwords, hai biểu diễn BoW và TF-IDF, Naive Bayes và SVM, chia tập, Accuracy/Precision/Recall/F1/Confusion Matrix và mô hình hiện đại ViSoBERT. Năm mô hình: BoW-NB, BoW-SVM, TF-IDF-NB, TF-IDF-SVM, ViSoBERT. Đây là đối chiếu chức năng; không chứng nhận toàn bộ nhãn đúng.

## Bằng chứng kiểm tra mới

- Dữ liệu chia sẻ: kiểm tra toàn vẹn valid=true. Tổng 5.786 dòng; 5.199 sạch có nhãn (1.037 toxic, 4.162 non-toxic); 587 trùng. 5.198 nhãn máy, 1 nhãn thủ công.
- Tập phát triển: 3.520 mẫu (981 toxic, 2.539 non-toxic). Phần còn lại thuộc ranh giới dữ liệu lịch sử giữ riêng.
- Run hiện tại: run-20261104T151325636854Z. Train 2.175, validation 699, test 646; không giao ID hoặc nhóm bài viết.
- Tính lại Accuracy, macro-F1 và confusion matrix từ dự đoán đã lưu: khớp cả năm mô hình.
- Macro-F1 test: BoW-NB 0,753767; BoW-SVM 0,741983; TF-IDF-NB 0,737100; TF-IDF-SVM 0,771003; ViSoBERT 0,810856. Không dùng điểm ViSoBERT 0,815279 của run trước cho video mới.
- Nạp artifact, dự đoán một bình luận và tạo trace: đạt cả năm mô hình, gồm ViSoBERT thực tế.
- CUDA nhận NVIDIA GeForce RTX 3050 Laptop GPU.
- Ollama hoạt động, có qwen3:4b-instruct-2507-q4_K_M. Kiểm tra endpoint ứng dụng tại 8767 thành công. Không gọi gán nhãn lại dữ liệu trong lượt rà soát.
- Bộ kiểm thử: 83 chạy, 82 đạt, 1 bỏ qua do ONNX tùy chọn; lần cuối 27,585 giây.
- pip check, cú pháp ui.js/pipeline.js và git diff --check đạt.

## Sửa trong lượt rà soát

- Trạng thái mô hình và báo cáo kiểm tra cả phiên bản chuẩn hóa/tokenizer, ngoài fingerprint. Tái hiện lỗi bằng trường hợp fingerprint không đổi nhưng phiên bản cũ; sửa và kiểm chứng lại các trường hợp cũ/mới.
- Chuẩn hóa xuống dòng/khoảng trắng ở index.html, requirements.txt, README.md; không thay chức năng.
- Cập nhật Report.md theo run thực tế và cảnh báo snapshot cũ.

## Việc cần làm trước khi chốt video

1. Trích xuất lại và huấn luyện đủ năm mô hình với ptit-v3-conservative-teencode-20261104; lưu run mới, giữ run cũ. Hiện run dùng ptit-v2-preserve-meaning-20261103.
2. Kiểm chứng lại chỉ số và phép tính minh họa theo artifact của run mới, rồi cố định ví dụ/manifest video.
3. Video phải tách nhánh ViSoBERT (raw text → chuẩn hóa riêng → tokenizer/embedding) khỏi BoW/TF-IDF. Gán nhãn có ngữ cảnh bài viết/cha không đồng nghĩa năm bộ phân loại hiện tại cùng nhận những ngữ cảnh đó; chúng phân loại văn bản bình luận.
4. Video hiện tại vẫn là bản tạo theo từng dự đoán, chưa có cache bền qua khởi động lại và video báo cáo toàn hệ thống; đây là phần sẽ triển khai theo thiết kế đã lưu.

## Giới hạn kiểm chứng

Chưa chạy phiên Facebook thật, kiểm thử trực quan toàn bộ giao diện hoặc huấn luyện lại toàn dataset trong lượt này. Phần lớn nhãn và nhãn test là tự động; chỉ số trên dataset không thay thế đánh giá độc lập của con người. Không tạo file test tạm.
