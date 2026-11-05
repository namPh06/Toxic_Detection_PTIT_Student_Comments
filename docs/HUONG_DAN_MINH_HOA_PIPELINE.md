# Minh họa pipeline bằng hoạt hình MP4

1. Khởi động lại hệ thống và tải lại trang bằng Ctrl+F5.
2. Vào Huấn luyện và đánh giá → Thử phân loại bình luận.
3. Nhập bình luận, chọn mô hình và bấm Phân loại.
4. Bấm **Tạo video hoạt hình MP4**, chờ hoàn tất rồi nhấn phát bên dưới. Bấm **Tải video MP4** để dùng khi báo cáo.

Video dùng bộ vẽ, chuyển camera và hiệu ứng biến đổi chữ từ test1.py gốc. Nội dung lấy từ artifact thực tế. Đổi mô hình/bình luận sẽ bỏ video đang hiển thị; cần phân loại và tạo video mới. Sau huấn luyện lại, video mới dùng run mới. Không tự dựng video khi huấn luyện vì còn cần bình luận minh họa.

NB/SVM: chuẩn hóa → Underthesea → BoW/TF-IDF thực tế → quyết định và ngưỡng. ViSoBERT: Unicode → tokenizer riêng → encoder và đầu phân loại → quyết định. Không thêm điểm emoji hoặc độ tự tin giả. Trọng số đặc trưng không phải mức đóng góp vào toxic.

Dựng cục bộ, một video mỗi lần; không cần dịch vụ trả phí. Lỗi dựng có thể thử lại. Văn bản dài chỉ rút gọn phần hiển thị; dự đoán dùng nguyên đầu vào. Kết quả máy có thể sai. Cài thư viện theo requirements.txt khi chuyển máy.


## Video báo cáo toàn hệ thống (05/11/2026)

Mở mục **Báo cáo** → **Video báo cáo toàn hệ thống**. Video dựng sẵn phát ngay trong giao diện; nút mục lục chuyển tới từng cảnh. Không cần nhập lại bình luận hoặc tải MP4 để xem.

Video dùng hai ví dụ cố định và cùng snapshot gồm BoW-NB, BoW-SVM, TF-IDF-NB, TF-IDF-SVM, ViSoBERT. Các điểm số, trọng số, logits và chỉ số đánh giá đọc từ artifact đã lưu. Sơ đồ luồng encoder chỉ minh họa cơ chế, không phải bằng chứng giải thích nhân quả.

Sau huấn luyện thành công, hệ thống tự xếp lượt dựng video cho run mới. Mở lại công cụ sẽ dùng bản đã lưu, hoặc dựng nếu thiếu. Trong khi cập nhật hoặc khi dựng lỗi, bản hoàn chỉnh trước vẫn xem được. Nút **Cập nhật video** thử lại khi cần; không chạy nhiều lượt dựng song song.

Video và manifest bằng chứng nằm tại `outputs/system_report_videos/`; `latest-ready.json` chỉ tới bản hoàn chỉnh. Thư mục outputs được gitignore nên người pull mã cần có các artifact mô hình và dựng video trên máy mình, hoặc được cung cấp riêng video đã xuất.
