# Phân loại bình luận toxic và non-toxic trong các nhóm Facebook liên quan đến sinh viên PTIT


## 1. Giới thiệu bài toán

Mục tiêu: hỗ trợ nhận diện bình luận độc hại trong ngữ cảnh cộng đồng sinh viên. Đầu vào là văn bản bình luận; đầu ra là toxic hoặc non-toxic. Đây là công cụ hỗ trợ nghiên cứu, không tự động kết luận tư cách sinh viên hay áp dụng chế tài với người viết.

Nguồn dữ liệu: bình luận văn bản do Selenium thu thập từ các nhóm/trang người dùng có quyền truy cập. Không suy ra mọi người bình luận đều là sinh viên PTIT. Không khẳng định đã thu thập đầy đủ; bộ lọc Facebook, bình luận ẩn, ảnh/sticker và thay đổi giao diện có thể tạo thiên lệch mẫu.


## 2. Cơ sở lý thuyết

Toxic: công kích cá nhân/nhóm, lăng mạ, đe dọa, quấy rối hoặc miệt thị. Non-toxic: hỏi đáp, trao đổi thông tin, phản biện lịch sự và ý kiến tiêu cực không công kích. Từ tục trong trích dẫn hoặc đùa thân mật cần xét ngữ cảnh, không dùng từ khóa đơn lẻ làm nhãn chuẩn.

BoW biểu diễn số lần xuất hiện token/ngram. TF-IDF giảm trọng số token phổ biến và tăng trọng số token đặc trưng. Với cấu hình mặc định: idf(t)=log((1+n)/(1+df(t)))+1, sau đó chuẩn hóa L2. Cả hai dùng unigram/bigram, tối đa 20.000 đặc trưng; từ vựng và IDF chỉ học trên train.

Multinomial Naive Bayes dùng xác suất có điều kiện với giả định độc lập đặc trưng và làm trơn alpha=1. LinearSVC là SVM tuyến tính với C=1, class_weight=balanced để giảm tác động mất cân bằng lớp.

Mô hình học sâu bổ sung: TextCNN theo hướng Kim (2014), embedding 64 chiều học từ đầu, 3 cửa sổ convolution 2/3/4 token, mỗi cửa sổ 48 bộ lọc, ReLU, global max pooling, dropout 0,3 và lớp tuyến tính 2 nhãn. Adam, learning rate 0,001; batch 32; tối đa 12 epoch; chọn epoch bằng macro-F1 validation. Đây là baseline học sâu, không phải Transformer hay mô hình đã tiền huấn luyện.


## 3. Thực nghiệm và kết quả


### 3.1. Thu thập và tiền xử lý

Dữ liệu hiện tại: **2126 bình luận**, **86 bài**; **2087 mẫu sạch duy nhất**, **2087 mẫu sạch đã gán nhãn**. Phân bố nhãn trong mẫu sạch: {"non-toxic": 1953, "toxic": 134}. Kiểm tra chất lượng: {"ready": 2087, "empty_or_ui": 11, "duplicate": 28}.

Nguồn nhãn: {"automatic": 2087}. Nhãn automatic được mô hình gán, chưa phải nhãn người đọc xác nhận.

Quy trình: chuẩn hóa Unicode NFC, chữ thường, giải mã HTML; ẩn URL/email/số điện thoại bằng token; bỏ ký tự vô hình và dấu câu; chuẩn hóa một số teencode; tách token theo âm tiết/khoảng trắng và emoji; loại danh sách stop words ngắn. Giữ dấu tiếng Việt, từ phủ định, từ tục và emoji. Chưa ghép từ đa âm tiết bằng bộ phân đoạn tiếng Việt; bigram giúp biểu diễn các cụm gần nhau. Không xóa bản gốc. Văn bản trùng sau chuẩn hóa chỉ giữ một mẫu; nhãn mâu thuẫn bị loại khỏi train cho tới khi rà soát. Mẫu còn nội dung thu gọn được đánh dấu incomplete và không dùng huấn luyện; độ đầy đủ của bản crawl cũ thiếu thông tin này chưa được xác minh.


### 3.2. Quy trình gán nhãn

Người gán nhãn đọc văn bản gốc, chọn nhãn, ghi chú trường hợp khó hoặc loại dữ liệu không hợp lệ. Các trường hợp thiếu ngữ cảnh nên để trống để thảo luận. Nên có hai người gán độc lập một phần dữ liệu, thống nhất bất đồng và báo cáo Cohen kappa trước khi chốt bộ chuẩn. Hiện công cụ lưu một nhãn cuối cùng/mẫu; chưa có số liệu đồng thuận giữa người gán nhãn.

Công cụ hỗ trợ gợi ý bằng dangvansam/vietnamese-toxicity, revision bac60f3e162d3a06003bf561a9f8365982ccc67a, chạy ONNX trên CPU tại máy người dùng, không gửi bình luận tới dịch vụ ngoài. Đầu vào giữ văn bản gốc, chỉ chuẩn hóa NFC/khoảng trắng. Điểm toxic là sigmoid chưa hiệu chỉnh trên PTIT, không phải độ chính xác. Điểm ≤ 0,2 gợi ý non-toxic; ≥ 0,8 gợi ý toxic; ở giữa hoặc văn bản vượt 512 token kể cả token đặc biệt thì không đề xuất nhãn. “Dùng gợi ý” chỉ điền lựa chọn; “Lưu đánh giá” mới xác nhận sau khi đọc. Mô hình nền ViSoBERT được công bố cho mục đích nghiên cứu.

Chế độ “Làm sạch & gán nhãn toàn bộ” gán nhãn máy trực tiếp cho mọi mẫu sạch chưa có nhãn: điểm toxic ≥ 0,5 là toxic, còn lại là non-toxic. Giữ nhãn người đọc đã lưu. Mẫu có điểm giữa 0,2–0,8 hoặc bị cắt do quá dài vẫn có nhãn máy và cờ needs_review; mẫu trùng/rỗng/bị loại/chưa mở hết nội dung không vào dataset. Lưu nguồn automatic, mô hình, revision, điểm và ngưỡng; dataset_auto.csv/json và /api/dataset-auto.csv/json chứa các mẫu sạch đã có nhãn, gồm cả nhãn máy.

Gợi ý, điểm, model/revision và dấu vân tay văn bản được lưu tách khỏi nhãn xác nhận. data/workspace.json là kho chính, ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử; annotations.json/imported.json cũ chỉ dùng làm nguồn chuyển đổi khi chưa có workspace. Nhãn có dấu vân tay không còn khớp nội dung phải được duyệt lại. Bản xuất /api/dataset.csv và /api/dataset.json chỉ chứa mẫu ready có nhãn xác nhận/nhập từ người gán, không chứa gợi ý chưa duyệt.


### 3.3. Thiết kế đánh giá

Chia theo nhóm bài viết độc lập, mục tiêu khoảng 60% train / 20% validation / 20% test theo số nhóm (tỷ lệ bình luận thực tế có thể khác). Các bài chứa bình luận trùng được nối cùng nhóm. Không có bài hoặc văn bản chuẩn hóa trùng giữa các tập. Seed 42; seed 43 cho validation. Chọn lần chia đầu tiên mà cả hai lớp xuất hiện trong mỗi tập; không chọn theo điểm mô hình. Tối thiểu 10 mẫu mỗi lớp và 5 nhóm độc lập chỉ là điều kiện chạy kỹ thuật; cần nhiều dữ liệu hơn cho kết luận đáng tin cậy.

Bốn baseline dùng cùng các tập chia: BoW+NB, BoW+SVM, TF-IDF+NB, TF-IDF+SVM; TextCNN dùng cùng tập. Chọn mô hình theo macro-F1 validation, không chọn theo test. Test được dùng để so sánh cuối cùng. Không cân bằng mẫu hoặc học từ vựng trên toàn bộ dữ liệu trước khi chia.

Nhãn validation/test cần được người đọc gán độc lập, không xem gợi ý tự động, rồi kiểm tra chéo và khóa trước đánh giá. Việc này phải thực hiện bằng quy trình nhóm/bản xuất riêng; giao diện chưa tự che gợi ý hay khóa bộ test. Cần công bố phần dữ liệu có hỗ trợ tự động và quy trình duyệt; chưa có bằng chứng về độ chính xác của mô hình gợi ý trên corpus PTIT.

Accuracy=(TP+TN)/N; Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2PR/(P+R). Lớp dương là toxic. Macro-F1 là trung bình F1 hai lớp. Confusion matrix: hàng là nhãn tham chiếu trong dataset, cột là dự đoán, thứ tự [non-toxic, toxic], tức [[TN, FP], [FN, TP]]. Mẫu số bằng 0 được ghi 0.


### 3.4. Kết quả

Chưa có thực nghiệm: gán nhãn tự động toàn bộ hoặc gán nhãn thủ công rồi chạy huấn luyện. Nhãn máy không phải nhãn chuẩn do người đọc xác nhận.

Chưa có Accuracy/Precision/Recall/F1/confusion matrix để báo cáo. Không dùng nhãn tự suy đoán hoặc dữ liệu kiểm thử phần mềm làm kết quả trên sinh viên PTIT. Hoàn thành gán nhãn, chạy huấn luyện rồi xuất lại báo cáo.


## 4. Kết luận và hạn chế

Hệ thống cung cấp luồng thu thập → làm sạch → gán nhãn → trích chọn đặc trưng → huấn luyện → đánh giá → dự đoán. Hạn chế: số bài ít, thiên lệch chọn nhóm, chưa xác minh danh tính sinh viên, mỉa mai và hội thoại cần ngữ cảnh, ảnh/sticker bị bỏ qua, token hóa âm tiết, TextCNN cắt ở 128 token. Cần tăng số nhóm/bài và nhãn được kiểm tra chéo; mở rộng đánh giá sang dữ liệu ở thời điểm khác. Tránh điều chỉnh lặp lại dựa trên test. Bản gốc vẫn có thể chứa thông tin cá nhân; ẩn tên và định danh trước khi chia sẻ corpus, không chia sẻ chrome-profile.


## Tài liệu tham khảo

1. Scikit-learn: https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction

2. Naive Bayes: https://scikit-learn.org/stable/modules/naive_bayes.html

3. LinearSVC: https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html

4. GroupShuffleSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html

5. Kim, Y. (2014). Convolutional Neural Networks for Sentence Classification. EMNLP. https://aclanthology.org/D14-1181/

6. PyTorch: https://docs.pytorch.org/docs/stable/nn.html

7. Selenium: https://www.selenium.dev/documentation/webdriver/

8. Model gợi ý: [dangvansam/vietnamese-toxicity](https://huggingface.co/dangvansam/vietnamese-toxicity), revision bac60f3e162d3a06003bf561a9f8365982ccc67a.

9. Nguyen et al. (2023), [ViSoBERT](https://aclanthology.org/2023.emnlp-main.315/); [model card và phạm vi nghiên cứu](https://huggingface.co/uitnlp/visobert).
