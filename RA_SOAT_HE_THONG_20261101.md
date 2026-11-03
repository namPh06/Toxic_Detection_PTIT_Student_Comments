# Rà soát hệ thống trước thí nghiệm ngữ cảnh — 01/11/2026

## Kết luận

Hệ thống có các thành phần thu thập, lưu trữ, duyệt nhãn, thí nghiệm và xuất báo cáo. Dữ liệu nguồn và nhãn người dùng còn nguyên. Tuy nhiên, chưa hoàn thiện một luồng ngữ cảnh thống nhất từ giao diện đến dự đoán, chưa có đánh giá độc lập đủ tin cậy, chưa thể xác nhận gán nhãn tự động đúng toàn bộ. Nên xử lý các điểm P1 bên dưới trước lượt huấn luyện mới.

Rà soát này đọc mã nguồn Python/JS, tài liệu, đề bài debai.jpg, kiểm tra dữ liệu và artifact, chạy kiểm thử Python và suy luận ONNX thật offline. Không chạy crawl Facebook mới, không kiểm thử giao diện bằng trình duyệt thật, không huấn luyện lại, không thay nhãn hay mô hình. Không phát sinh API trả phí. Không tìm thấy tool/skill supperpower trong phiên.

## Đối chiếu đề bài

| Bước | Bằng chứng hiện có | Trạng thái |
|---|---|---|
| 1. Thu thập | 5.936 bình luận, 392 link, 369 nhóm bài sau chuẩn hóa danh tính | Có dữ liệu; độ đầy đủ chưa xác minh |
| 2. Tiền xử lý | dataset.py phục vụ giao diện; word_preprocessing.py cho baseline; context_preprocessing.py giữ ngữ cảnh | Có ba đường chạy, chưa thống nhất |
| 3. Ít nhất hai cách trích đặc trưng | BoW, TF-IDF đã chạy; embedding/TextCNN có mã | BoW/TF-IDF có kết quả thực |
| 4. NB, SVM; chia train/test | Bốn baseline đã có đánh giá chéo phát triển; giao diện có mã train/validation/test | Chưa có lượt đánh giá cuối độc lập; chưa huấn luyện ngữ cảnh mới |
| 5. Accuracy, Precision, Recall, F1, confusion matrix và so sánh | Có metrics, dự đoán OOF, báo cáo baseline | Có số liệu phát triển; không phải kết quả test cuối |
| Báo cáo lý thuyết/thực nghiệm/tài liệu tham khảo | BAO_CAO.md, README, các báo cáo theo lượt | Có bản nháp/lịch sử; cần đồng bộ trước nộp |

Đề yêu cầu tách từ và kỹ thuật như lọc stop words. Luồng giữ ngữ cảnh cố ý không xóa stop words để tránh mất nghĩa; báo cáo cần mô tả khác biệt và so sánh lựa chọn lọc/không lọc. TextCNN và mô hình ngữ cảnh là phần mở rộng, không thay thế yêu cầu NB/SVM.

## Dữ liệu và nhãn thực tế

- Nguồn gốc, dữ liệu ghép và dữ liệu tiền xử lý đều đủ 5.936 mẫu; đối chiếu ID và nguyên văn từng bình luận khớp. Hash các đầu vào bảo vệ vẫn khớp manifest tiền xử lý.
- Giao diện hiện dùng 5.111 mẫu ready, 736 duplicate, 89 empty_or_ui theo bộ làm sạch cũ. Bộ ngữ cảnh giữ toàn bộ mẫu để truy vết; 5.936 target_usable không đồng nghĩa 5.936 mẫu sạch có nhãn chuẩn.
- Workspace có 946 nhãn: 114 toxic, 832 non-toxic; 862 nguồn imported và 84 manual. Nhãn chuẩn phát triển khớp chính xác artifact canonical có human_verified. Còn 4.165 mẫu ready chưa có nhãn trong workspace; suggestions hiện bằng 0. Các đề xuất AI lưu trong outputs không tự trở thành nhãn giao diện.
- 35 mẫu giữ riêng đã dùng chẩn đoán trước đây không được gọi là test mù mới. 946 nhãn phát triển cũng đã được duyệt có hỗ trợ AI.
- 5.649 mẫu có văn bản bài viết; 287 thiếu. Có 1.705 mẫu có phần cha, trong đó 3 chưa có văn bản cha; 7 chưa xác minh đầy đủ tổ tiên. Tổng cộng 294 mẫu có cờ thiếu ngữ cảnh.
- Tất cả mẫu thiếu bằng chứng text_complete và comment_filter. Không có cờ thiếu không chứng minh đã thu thập đầy đủ. Ảnh chưa OCR, quan hệ bạn bè không được suy ra từ emoji.

## Các phát hiện cần xử lý

### P1 — Quy tắc gán nhãn chưa thống nhất trong mã

QUY_TAC_GAN_NHAN.md đã có bổ sung v3.2 về đùa thân mật nhưng tiêu đề/metadata đầu tài liệu vẫn v3.1. semantic_labeling.py còn POLICY_VERSION v2; context_labeling.py nhập lại phiên bản này và dòng 11/22 nói phàn nàn học phí không toxic nếu không công kích cá nhân. Điều đó trái quy tắc chê trường và ví dụ học phí đắt vcl đã chốt. semantic_v31.py và hybrid_labeling.py cũng mang v3.1.

Cần tạo chính sách hiện hành thống nhất, cập nhật prompt/checklist/logic quyết định cùng phiên bản; không chỉ đổi chuỗi phiên bản. context_labeling.decide còn yêu cầu mục tiêu công kích xuất hiện trực tiếp trong câu đích, nên trường hợp tham chiếu tới mục tiêu chỉ nằm trong cha có thể bị trả uncertain. Đây là hạn chế thiết kế cần kiểm thử, không tự coi là lỗi gán nhãn hiện hành vì mô-đun này đang thử nghiệm.

### P1 — Giao diện chưa dùng pipeline ngữ cảnh

app.py đã bổ sung lưu văn bản bài viết, nhưng Lab.rows gọi dataset.prepare; start_suggestions gọi labeling.py, mô hình ONNX chỉ đọc câu đích. train/predict vẫn đi experiments.py. Không có liên kết sang context_preprocessing.py/dataset.json mới. Nút huấn luyện hiện không tạo mô hình đọc bài viết và chuỗi cha. predict chỉ nhận text.

Cần nối riêng đường chạy ngữ cảnh, ghi rõ phiên bản tiền xử lý và yêu cầu đầu vào của từng mô hình; tránh đưa text mới vào model cũ sai định dạng. post_context và parent_context có thể thay đổi sau khi tiền xử lý; phải kiểm tra hash/ngày tạo để tái tạo snapshot trước huấn luyện.

### P1 — Cách ly tập giữ riêng theo ID chuẩn hóa

Baseline cũ đã nối bài có câu trùng và không thấy chồng nhóm canonical giữa train/validation trong cả 5 fold đã lưu. Tuy nhiên, đối chiếu danh sách giữ riêng bằng canonical_post_id mới cho thấy 1 mẫu phát triển thuộc cùng nhóm bài giữ riêng:

- id: 87d11c2124be2b29d839bb28
- post_id: pfbid02bKSSku6dSeCGTxyDzHXTS6Ur4eekA2qKifRdyAbLNAXoZfXJXZAsNVcayiuhyfdwl
- canonical_post_id: 1659860986153487

Baseline kiểm tra reserved bằng post_id gốc, nên không bắt alias này. Không làm mất hiệu lực kết quả CV phát triển đã đo; nhưng tập giữ riêng hiện không cách ly hoàn toàn theo bài. Phải gộp canonical ID và nhóm trùng trước, rồi áp dụng ranh giới giữ riêng trên cả nhóm. Không tự chuyển nhãn hoặc xóa mẫu; quyết định loại khỏi phát triển/đánh giá cần ghi manifest. Khi nối nhóm trùng, cần kiểm tra cả quan hệ bắc cầu và tránh dùng bình luận phổ biến để nối mọi bài ngoài ý muốn.

### P1 — Huấn luyện giao diện chấp nhận nhãn máy

experiments.split_dataset lấy mọi mẫu ready có label; Lab.start_training không giới hạn nhãn người duyệt hoặc loại các bài dành riêng. Cơ chế này có cảnh báo trong README/báo cáo, nhưng không phải đường đánh giá chuẩn v3.2. Nếu dùng nút gán toàn bộ trước huấn luyện, nhãn máy có thể lọt cả train và test. Cần tách rõ chế độ thí nghiệm nhãn máy với đánh giá trên nhãn người; ghi nguồn nhãn và reserved groups vào manifest.

### P1 — Chất lượng mô hình chưa đạt

TF-IDF/SVM cũ có macro-F1 OOF khoảng 0,5202, recall toxic chỉ 7/114 (6,14%); NB không phát hiện được mẫu toxic. Accuracy cao do lớp non-toxic chiếm đa số không chứng minh hệ thống tốt. Chưa có bằng chứng mô hình mới hiểu đùa/mỉa mai tốt hơn. Không lấy nhãn AI làm đáp án rồi công bố mô hình đúng trên chính chúng.

### P2 — Tài liệu lịch sử dễ gây hiểu nhầm

README có đoạn 0 nhãn chuẩn ở phần thân dù đầu file nói 981; mô tả token hóa và trạng thái pipeline thuộc thời điểm cũ. BAO_CAO và các báo cáo từng lượt cần giữ lịch sử nhưng thêm dẫn chiếu trạng thái mới. data/latest.json không tồn tại: chưa có mô hình huấn luyện được giao diện chọn; các joblib baseline trong outputs không tự được triển khai. data/startup-error.txt chứa lỗi Chrome mất kết nối cũ, không chứng minh phiên hiện tại đang lỗi.

## Kiểm chứng đã thực hiện

- unittest discover: 79 ca, 78 đạt, 1 bỏ qua mặc định là smoke mô hình thật.
- Chạy riêng smoke ONNX thật với LABELING_SMOKE=1, chặn mạng theo test: đạt. Hai asset model.onnx/tokenizer.json đúng kích thước và SHA-256.
- pip check: No broken requirements found.
- AST parse: toàn bộ 28 file Python hợp lệ cú pháp.
- Kiểm tra 5.936 ID/nguyên văn, 946 nhãn canonical, hash nguồn và ranh giới canonical của 5 fold baseline: đạt các đối chiếu mô tả trên; phát hiện 1 mẫu chồng nhóm giữ riêng như đã ghi.
- Không tạo file test tạm mới; kiểm thử dùng thư mục tạm và tự dọn. Giữ các test hồi quy có sẵn của dự án.

Kiểm thử phần mềm đạt không đồng nghĩa nhãn đúng hoặc Facebook thật hoạt động mọi trường hợp. Phiên này chưa chạy E2E trình duyệt thật, chưa cào lại nguồn và chưa đo lại chất lượng dự đoán trên toàn bộ corpus.

## Thứ tự làm tiếp

1. Đồng bộ chính sách v3.2 và cơ chế tách nhãn người/AI; bổ sung trường hợp hồi quy về góp ý, chê trường, phủ định, trích dẫn và đùa có/thiếu ngữ cảnh.
2. Chuẩn hóa nhóm bài, nhóm trùng và ranh giới giữ riêng; xuất manifest mới, xử lý mẫu alias bị chồng mà không sửa nguyên văn/nhãn.
3. Dùng cùng tập phát triển và cùng fold hợp lệ để so sánh chỉ câu đích với có ngữ cảnh; vectorizer chỉ fit train. Xem riêng recall toxic, precision, macro-F1 và lỗi FP/FN.
4. Chỉ nối mô hình vào giao diện sau khi kết quả và định dạng đầu vào đã được kiểm chứng; đồng bộ README/báo cáo. Khóa test độc lập trước đánh giá cuối.
