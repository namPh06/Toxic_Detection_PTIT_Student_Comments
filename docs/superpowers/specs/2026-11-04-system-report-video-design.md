# Video báo cáo toàn hệ thống

## Mục tiêu và phạm vi

Thay trải nghiệm phải tạo video cho từng dự đoán bằng một MP4 báo cáo dựng sẵn, phát trực tiếp trên giao diện. Giữ mức chi tiết và ngôn ngữ hình ảnh của `C:/Users/ADMIN/Downloads/test1.py`: biến đổi chữ, token di chuyển, vector, đồ thị, phép tính, camera pan/zoom. Không chỉ ghép chữ vào slide. Chạy cục bộ, không dịch vụ trả phí.

Người dùng đã chốt: khoảng 5–7 phút, hai ví dụ toxic/non-toxic dùng chung cho năm mô hình; lần lượt mô phỏng cả năm mô hình, kết luận từng mô hình, so sánh và kết luận chung. Đây là bản trình diễn cố định theo phiên bản huấn luyện, không phải video mới cho mọi bình luận nhập vào.

## Cách dựng

Chọn mở rộng bộ vẽ Python/Pillow và xuất MP4 bằng FFmpeg đã có. Video trình duyệt tạo khi bấm không đáp ứng yêu cầu phát ngay; hoạt hình trình duyệt trực tiếp cần bộ dựng khác và khó giữ một bản báo cáo cố định. MP4 dựng nền dùng lại nền tảng hiện tại và phát được qua endpoint hỗ trợ Range.

## Rà soát trước khi dựng

Đối chiếu đề bài, luồng thu thập/lọc/lưu, làm sạch/gán nhãn, chia tập, đặc trưng, huấn luyện, dự đoán và báo cáo. Không sửa nhãn hay xóa dữ liệu để phục vụ video. Kiểm tra lại các cảnh báo phiên bản chuẩn hóa, snapshot dữ liệu và tài liệu còn nhắc mô hình đã loại bỏ. Nếu cần huấn luyện lại để đồng bộ thì lưu run mới, giữ run cũ, dùng cấu hình đã có và GPU khi khả dụng. Không thay đổi định nghĩa toxic.

Bằng chứng ban đầu: 83 kiểm thử chạy, 82 đạt và 1 bỏ qua; năm bộ chỉ số test khớp dự đoán đã lưu; không giao ID hoặc nhóm giữa train/validation/test. Run hiện lưu preprocessing v2 trong khi mã hiện là v3. Đây chưa phải xác nhận toàn hệ thống đạt chất lượng thực tế hoặc nhãn hoàn toàn đúng.

## Kịch bản và chuyển cảnh

1. Mở đầu: bài toán, dữ liệu vào/ra, hai ví dụ cố định. Tóm lược nguồn dữ liệu và nhãn máy, không đánh đồng nhãn máy với chuẩn độc lập.
2. Raw text và làm sạch: tô đúng đoạn thay đổi, chuyển từ trước sang sau, giải thích giữ phủ định và nghĩa. Chỉ minh họa phép biến đổi thật sự có trong mã.
3. Tách từ của nhánh truyền thống: chip từ, từ ghép và các token bị loại theo cấu hình thật.
4. Đặc trưng BoW và TF-IDF: đếm từ, từ điển học trên train, giá trị IDF/chuẩn hóa từ artifact, vector thưa và giá trị khác 0; nêu rõ nếu có nhánh ký tự. Không giả định mọi mô hình dùng cùng từ điển/cấu hình.
5. **Đặc trưng riêng của ViSoBERT**: ngay sau phần BoW/TF-IDF, giữ tiêu đề chương Đặc trưng. Quay lại raw text, chuẩn hóa riêng, subword → token ID → mask → embedding. Hiển thị cắt ngắn/padding đúng thực tế. Không đưa đầu ra Underthesea hoặc vector BoW vào ViSoBERT.
6. Chương 7 — Mô hình: lần lượt BoW-NB, BoW-SVM, TF-IDF-NB, TF-IDF-SVM, ViSoBERT. Mỗi phần có hai ví dụ và kết luận riêng.
   - NB: prior, từng hạng x_i log P(từ_i|lớp), tổng log-score hai lớp, xác suất và ngưỡng lưu.
   - SVM: thành phần x_i*w_i có dấu, cộng intercept, điểm quyết định và ngưỡng validation. Không gọi điểm SVM là xác suất hoặc phần trăm tin cậy.
   - ViSoBERT: token/embedding → các tầng encoder theo config → đầu phân loại → logits → softmax → ngưỡng lưu. Giá trị trích từ lần suy luận thật; sơ đồ luồng attention chỉ minh họa cơ chế, không tuyên bố đó là lời giải thích nhân quả.
   - Chỉ hiển thị một số chiều/token cho dễ đọc, ghi rõ phần rút gọn; kết quả cuối dùng đầy đủ đầu vào hợp lệ.
7. So sánh: biểu đồ và confusion matrix trên cùng split, Accuracy, precision/recall/F1 toxic, macro-F1; phân biệt validation chọn mô hình/ngưỡng với test báo cáo. Không so trực tiếp điểm thô SVM với xác suất NB/ViSoBERT.
8. Kết luận chung: mô hình được chọn theo validation, ưu/nhược điểm từ số liệu thật, giới hạn nhãn tự động và mất cân bằng. Không bỏ phiếu năm mô hình hoặc tự công bố đúng tuyệt đối.

Chuyển bước lớn giữ camera pan/zoom của bản gốc. Chuyển trong chương dùng hiệu ứng riêng, tiết chế: BoW ↔ TF-IDF morph cột; sang ViSoBERT mở hai nhánh rồi trượt/lật thẻ để thể hiện thay cách biểu diễn. Chuyển giữa năm mô hình dùng hiệu ứng relay theo đường vector. Giữ nhãn chương trên màn hình và màu sắc nhất quán, tránh nhấp nháy.

## Nội dung và dữ liệu thực

Builder chọn hai ví dụ ngắn, có nhãn toxic/non-toxic trong dữ liệu hợp lệ; cố định ID và text hash trong manifest. Không chọn chỉ để cả năm đều đúng; nếu sai phải hiển thị sai so với nhãn dataset. Không dùng hai ví dụ này để chỉnh siêu tham số/ngưỡng. Che thông tin cá nhân khi hiển thị, không thay đầu vào tính toán một cách âm thầm.

Trích bằng chứng từ artifact đã fit: bộ vector hóa, NB log probabilities/priors, SVM coefficients/intercept, tokenizer/config/weights của ViSoBERT, ngưỡng và metrics. Lưu manifest có run ID, fingerprint dữ liệu, phiên bản preprocessing/tokenizer, renderer version, ví dụ và thời điểm dựng. Kiểm tra phép cộng/trả nhãn khớp API dự đoán trong sai số số thực.

## Vòng đời và giao diện

Thêm khu vực Video báo cáo toàn hệ thống với player và mục lục theo timestamp. Có thể tải tùy chọn nhưng không bắt buộc tải để xem. Tự dựng bản đầu tiên cho run hợp lệ hiện tại; sau huấn luyện thành công, đưa snapshot bất biến vào hàng đợi một worker. Không làm chậm phản hồi hoàn tất huấn luyện vì encode video.

Cache theo nội dung manifest, không chỉ trạng thái trong bộ nhớ. Ghi file tạm rồi kiểm tra và đổi tên nguyên tử; cập nhật con trỏ latest-ready chỉ khi thành công. Khởi động lại vẫn nhận bản có sẵn. Chạy mới liên tiếp: không cho job cũ ghi đè latest của run mới; ưu tiên run mới nhất đang chờ. Dựng lỗi vẫn phát được bản cũ và hiện lỗi/thử lại. Giao diện ghi rõ run/ngày, đang cập nhật hoặc bản cũ; không tuyên bố bản cũ là hiện tại. Nếu chưa có bản nào, hiển thị tiến độ trung thực.

## Kiểm chứng và tiêu chí nghiệm thu

- Các phép tính minh họa khớp dự đoán của đủ năm artifact; không có điểm tự đặt.
- Chạy lại kiểm thử phù hợp, kiểm tra metadata/split và cập nhật tài liệu theo run thực tế.
- MP4 có thời lượng mục tiêu, đọc được, không tràn/chồng chữ, xem mẫu mỗi chương và các điểm chuyển cảnh; player tua và phát trực tiếp được.
- Cả hai ví dụ có kết luận ở cả năm mô hình; có bảng so sánh và kết luận cuối.
- Kiểm tra cache sau restart, phiên bản cũ, job lỗi và cập nhật sau huấn luyện.
- Không tạo file test tồn dư; giữ bộ test có sẵn. Không sửa file gốc test1.py.

## Các lựa chọn do builder đề xuất

1280×720, 24 fps, không thêm giọng đọc hoặc nhạc khi chưa được yêu cầu; nhịp cảnh chừa đủ thời gian đọc. Khung ảnh tối và màu xanh/cam/đỏ kế thừa bản gốc, thêm mục lục chương. Thời lượng được điều chỉnh trong 5–7 phút khi kiểm tra độ đọc. Không hứa bản mới xuất hiện tức thì sau huấn luyện; phát ngay bản gần nhất đã dựng là yêu cầu vận hành.
