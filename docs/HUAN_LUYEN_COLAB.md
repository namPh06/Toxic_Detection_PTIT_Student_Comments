# Huấn luyện ViSoBERT trên Google Colab

Luồng sử dụng: **web xuất gói ZIP → notebook Colab huấn luyện → web nhập ZIP kết quả**.

## Thao tác

1. Mở trang **Trích xuất đặc trưng**, chọn cấu hình và thực hiện trích xuất trên dữ liệu hiện tại.
2. Sang **Huấn luyện & đánh giá → Chạy ViSoBERT trên Google Colab**. Bấm **Xuất gói Colab**, lưu `ptit-colab-input.zip`.
3. Bấm **Tải notebook**, lưu `PTIT_Colab.ipynb`. Mở [Google Colab](https://colab.research.google.com/), chọn **Upload notebook** để mở tệp này. Notebook cũng có sẵn bên trong ZIP đầu vào.
4. Chọn **Runtime → Change runtime type → GPU**. Chọn A100 nếu tài khoản được cấp; các GPU CUDA khác cũng dùng được.
5. Chạy lần lượt các ô. Ô tải tệp sẽ yêu cầu chọn `ptit-colab-input.zip`. Lần đầu notebook tải mô hình nền ViSoBERT từ Hugging Face.
6. Ô huấn luyện in tiến độ từng epoch. Mặc định chạy 4 epoch, batch 16 và tích lũy 1; nếu GPU nhỏ, chương trình tự giảm batch để tiết kiệm bộ nhớ. Có thể điều chỉnh cấu hình trong ô này.
7. Chạy ô cuối để tải `ptit-colab-result-<mã gói>.zip`. Tải về trước khi kết thúc phiên Colab. Nếu chỉ tải xuống bị lỗi, chạy lại riêng ô cuối.
8. Trên web bấm **Nhập kết quả Colab**, chọn ZIP kết quả. Đợi thông báo hoàn tất. Mô hình vừa nhập sẽ có trong bảng so sánh, báo cáo và mục **Thử phân loại bình luận**.

NB/SVM vẫn huấn luyện tại máy. Các kết quả NB/SVM cũ được giữ khi cùng dữ liệu, cách chia tập và cấu hình đặc trưng. Mô hình được chọn chung bằng Macro-F1 validation; không mặc định chọn ViSoBERT nếu mô hình khác có validation tốt hơn.

## Khi gặp lỗi

- **Chưa trích xuất đặc trưng:** thực hiện lại bước trích xuất rồi xuất gói.
- **Web đã khởi động lại:** trích xuất lại cùng cấu hình trước khi nhập ZIP. Không cần huấn luyện lại Colab nếu dữ liệu, nhãn, cấu hình và cách chia vẫn khớp.
- **Dữ liệu hoặc cấu hình đã đổi:** web từ chối kết quả cũ; xuất gói mới và chạy lại Colab.
- **Không có GPU:** đổi runtime sang GPU rồi kết nối lại. A100 phụ thuộc quyền truy cập và tài nguyên Colab, ứng dụng không tự cấp GPU.
- **ZIP không thuộc máy này:** dùng web đã xuất gói ban đầu; thông tin đối chiếu nằm trong `data/colab_jobs/`. Không xóa thư mục đó trong lúc chờ Colab.

## Dữ liệu và kiểm tra kết quả

Gói đầu vào chứa các mẫu thuộc lượt thực nghiệm hiện tại, nhãn, cách chia tập, cấu hình đặc trưng và mã huấn luyện. Không chứa cookie, hồ sơ Chrome hoặc thông tin đăng nhập. Bình luận được tải lên phiên Colab do bạn chọn.

Notebook dựng lại đặc trưng và đối chiếu chính xác cách chia trước khi huấn luyện. Chọn checkpoint và ngưỡng bằng validation. Khi nhập, web kiểm tra mã gói, dấu vân tay dữ liệu, mẫu/nhãn trong từng tập và ngưỡng validation; tính lại chỉ số từ dự đoán; kiểm tra mô hình/tokenizer có nạp và chạy được trước khi thay kết quả hiện hành. Web chỉ nhận trọng số safetensors và các JSON hỗ trợ, không nạp pickle/joblib từ ZIP Colab.

Hướng dẫn về runtime và quyền truy cập GPU: [Colab FAQ](https://research.google.com/colaboratory/faq.html).
