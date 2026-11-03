# Bốn cấu hình theo đề bài — 31/10/2026

946 nhãn phát triển do người dùng xác nhận (114 toxic, 832 non-toxic). Tách từ Pyvi 0.1.1 trước lọc stop words; giữ phủ định, emoji và văn bản gốc. Không dùng nhãn AI chưa xác nhận.

Đánh giá chéo 5 fold theo nhóm bài; nối các bài trùng văn bản. Cùng fold cho cả bốn cấu hình. Vectorizer chỉ fit trên phần train mỗi fold. Không dùng 119 bài giữ riêng để học hoặc chọn mô hình. Đây là kết quả phát triển trên nhãn có hỗ trợ AI, không phải test độc lập hay độ chính xác toàn corpus.

| Cấu hình | Accuracy OOF | Precision toxic | Recall toxic | F1 toxic | Macro-F1 OOF | Macro-F1 trung bình fold |
|---|---:|---:|---:|---:|---:|---:|
| BoW-NB | 0.8763 | 0.0000 | 0.0000 | 0.0000 | 0.4670 | 0.4670 |
| BoW-SVM | 0.8710 | 0.3182 | 0.0614 | 0.1029 | 0.5167 | 0.5163 |
| TF-IDF-NB | 0.8795 | 0.0000 | 0.0000 | 0.0000 | 0.4679 | 0.4679 |
| TF-IDF-SVM | 0.8763 | 0.4118 | 0.0614 | 0.1069 | 0.5202 | 0.5174 |

Ứng viên theo macro-F1 trung bình fold: TF-IDF-SVM. Chưa thay mô hình tự động trong ứng dụng. Chỉ số đã dùng chọn ứng viên nên cần tập test độc lập mới trước kết luận chất lượng.

Confusion matrix: hàng thật, cột dự đoán; thứ tự non-toxic, toxic.
BoW-NB: [[829, 3], [114, 0]]
BoW-SVM: [[817, 15], [107, 7]]
TF-IDF-NB: [[832, 0], [114, 0]]
TF-IDF-SVM: [[822, 10], [107, 7]]

Giới hạn: nhãn phát triển chọn lọc, mất cân bằng và đã được AI hỗ trợ; chưa kiểm chứng mù. Quy tắc chê trường là toxic là tiêu chí riêng của dự án, có ngoại lệ góp ý đã chốt. Pyvi tách từ, không tự giải quyết ngữ cảnh hay xác định toxic.

Tiếp theo: tạo/chốt nhãn test độc lập, kiểm tra chéo, khóa trước dự đoán; đánh giá ứng viên rồi hoàn thiện báo cáo. Các file joblib là ứng viên nghiên cứu fit toàn bộ 946 nhãn, không dùng chúng để tự đánh giá lại trên 946 câu.

Tài liệu tách từ: https://github.com/trungtv/pyvi

Kiểm tra: 29 kiểm tra hồi quy đạt; tính lại đủ bốn confusion matrix/chỉ số từ 946 dự đoán OOF, xác nhận mỗi câu chỉ xuất hiện ở validation một lần, không trùng bài/văn bản giữa train và validation, hash dữ liệu gốc và nhãn không đổi. Không tạo file test tạm.
