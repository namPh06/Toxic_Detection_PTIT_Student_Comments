# Phân loại bình luận toxic và non-toxic trong các nhóm Facebook liên quan đến sinh viên PTIT


## 1. Giới thiệu bài toán

Mục tiêu: hỗ trợ nhận diện bình luận độc hại trong ngữ cảnh cộng đồng sinh viên. Đầu vào là văn bản bình luận; đầu ra là toxic hoặc non-toxic. Đây là công cụ hỗ trợ nghiên cứu, không tự động kết luận tư cách sinh viên hay áp dụng chế tài với người viết.

Nguồn dữ liệu: bình luận văn bản do Selenium thu thập từ các nhóm/trang người dùng có quyền truy cập. Không suy ra mọi người bình luận đều là sinh viên PTIT. Không khẳng định đã thu thập đầy đủ; bộ lọc Facebook, bình luận ẩn, ảnh/sticker và thay đổi giao diện có thể tạo thiên lệch mẫu.


## 2. Cơ sở lý thuyết

Toxic: công kích cá nhân/nhóm, lăng mạ, đe dọa, quấy rối hoặc miệt thị. Non-toxic: hỏi đáp, trao đổi thông tin, phản biện lịch sự và ý kiến tiêu cực không công kích. Từ tục trong trích dẫn hoặc đùa thân mật cần xét ngữ cảnh, không dùng từ khóa đơn lẻ làm nhãn chuẩn.

BoW biểu diễn số lần xuất hiện token/ngram. TF-IDF giảm trọng số token phổ biến và tăng trọng số token đặc trưng. Với cấu hình mặc định: idf(t)=log((1+n)/(1+df(t)))+1, sau đó chuẩn hóa L2. Mặc định dùng unigram/bigram, tối đa 20.000 đặc trưng; có thể chọn lại trên trang Trích xuất đặc trưng. Từ vựng và IDF chỉ học trên train; NB/SVM dùng lại ma trận đã trích xuất.

Multinomial Naive Bayes dùng xác suất có điều kiện với giả định độc lập đặc trưng và làm trơn alpha=1. LinearSVC là SVM tuyến tính với C=1, class_weight=balanced để giảm tác động mất cân bằng lớp.

Mô hình học sâu bổ sung: TextCNN theo hướng Kim (2014), có thể khởi tạo embedding bằng Word2Vec tiền huấn luyện hoặc embedding ngẫu nhiên 64 chiều để so sánh. Với Word2Vec: ghép vector với từ vựng chỉ tạo từ train, từ không có vector được khởi tạo ngẫu nhiên; validation/test dùng token UNK cho từ ngoài từ vựng train. Có thể giữ cố định embedding hoặc cho học tiếp khi huấn luyện TextCNN. 3 cửa sổ convolution 2/3/4 token, mỗi cửa sổ 48 bộ lọc, ReLU, global max pooling, dropout 0,3 và lớp tuyến tính 2 nhãn. Adam, learning rate 0,001; batch 32; tối đa 12 epoch; chọn epoch bằng macro-F1 validation. TextCNN vẫn phải học phân loại trên dữ liệu đã gán nhãn, kể cả khi embedding đã tiền huấn luyện.


## 3. Thực nghiệm và kết quả


### 3.1. Thu thập và tiền xử lý

Dữ liệu hiện tại: **2131 bình luận**, **87 bài**; **2089 mẫu sạch duy nhất**, **2089 mẫu sạch đã gán nhãn**. Phân bố nhãn trong mẫu sạch: {"non-toxic": 1951, "toxic": 138}. Kiểm tra chất lượng: {"ready": 2089, "empty_or_ui": 6, "duplicate": 36}.

Nguồn nhãn: {"automatic": 2085, "manual": 4}. Nhãn automatic được mô hình gán, chưa phải nhãn người đọc xác nhận.

Quy trình: chuẩn hóa Unicode NFC, chữ thường, giải mã HTML; ẩn URL/email/số điện thoại bằng token; bỏ ký tự vô hình trong chữ và dấu câu; chuẩn hóa một số teencode; chỉ loại stop words các/những. Giữ dấu tiếng Việt, từ phủ định, được/thì/mà, từ tục và emoji. Giữ k/cc khi mơ hồ; dạng tiền 10-50 k thành 10-50k; ko đc thành không được. Biểu cảm :))/=))) thành emoticon_smile, :(( thành emoticon_sad; không dùng biểu cảm làm nhãn. Chuẩn hóa j/hc trong các cụm đã xác định ngữ cảnh (làm j → làm gì, đi hc → đi học); gom c.u/c_u/c*u về cu. Chỉ rút gọn chữ kéo dài khi khớp danh sách từ đã rà soát về từ gốc; giữ tên/từ chưa nhận diện. Phiên bản tiền xử lý hiện tại: ptit-v4-canonical-normalization. Tách từ bằng Underthesea trước trích xuất đặc trưng, phiên bản underthesea-9.5.0-word-v1. Từ đa âm tiết được nối bằng dấu gạch dưới (sinh viên → sinh_viên); unigram là một từ, bigram là hai từ liền nhau. Giữ nguyên token ẩn thông tin, biểu cảm, emoji ghép và dạng tiền. NB/SVM, TextCNN và dự đoán dùng cùng bộ tách từ. Không xóa bản gốc. Văn bản trùng sau chuẩn hóa chỉ giữ một mẫu; nhãn mâu thuẫn bị loại khỏi train cho tới khi rà soát. Mẫu còn nội dung thu gọn được đánh dấu incomplete và không dùng huấn luyện; độ đầy đủ của bản crawl cũ thiếu thông tin này chưa được xác minh.


### 3.2. Quy trình gán nhãn

Người gán nhãn đọc văn bản gốc, chọn nhãn, ghi chú trường hợp khó hoặc loại dữ liệu không hợp lệ. Các trường hợp thiếu ngữ cảnh nên để trống để thảo luận. Nên có hai người gán độc lập một phần dữ liệu, thống nhất bất đồng và báo cáo Cohen kappa trước khi chốt bộ chuẩn. Hiện công cụ lưu một nhãn cuối cùng/mẫu; chưa có số liệu đồng thuận giữa người gán nhãn.

Công cụ hỗ trợ gợi ý bằng dangvansam/vietnamese-toxicity, revision bac60f3e162d3a06003bf561a9f8365982ccc67a, chạy ONNX trên CPU tại máy người dùng, không gửi bình luận tới dịch vụ ngoài. Đầu vào giữ văn bản gốc, chỉ chuẩn hóa NFC/khoảng trắng. Điểm toxic là sigmoid chưa hiệu chỉnh trên PTIT, không phải độ chính xác. Điểm ≤ 0,2 gợi ý non-toxic; ≥ 0,8 gợi ý toxic; ở giữa hoặc văn bản vượt 512 token kể cả token đặc biệt thì không đề xuất nhãn. “Dùng gợi ý” chỉ điền lựa chọn; “Lưu đánh giá” mới xác nhận sau khi đọc. Mô hình nền ViSoBERT được công bố cho mục đích nghiên cứu.

Chế độ “Làm sạch & gán nhãn toàn bộ” gán nhãn máy trực tiếp cho mọi mẫu sạch chưa có nhãn: điểm toxic ≥ 0,5 là toxic, còn lại là non-toxic. Giữ nhãn người đọc đã lưu. Mẫu có điểm giữa 0,2–0,8 hoặc bị cắt do quá dài vẫn có nhãn máy và cờ needs_review; mẫu trùng/rỗng/bị loại/chưa mở hết nội dung không vào dataset. Lưu nguồn automatic, mô hình, revision, điểm và ngưỡng; dataset_auto.csv/json và /api/dataset-auto.csv/json chứa các mẫu sạch đã có nhãn, gồm cả nhãn máy.

Gợi ý, điểm, model/revision và dấu vân tay văn bản được lưu tách khỏi nhãn xác nhận. data/workspace.json là kho chính, ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử; annotations.json/imported.json cũ chỉ dùng làm nguồn chuyển đổi khi chưa có workspace. Nhãn có dấu vân tay không còn khớp nội dung phải được duyệt lại. Bản xuất /api/dataset.csv và /api/dataset.json chỉ chứa mẫu ready có nhãn xác nhận/nhập từ người gán, không chứa gợi ý chưa duyệt.


### 3.3. Thiết kế đánh giá

Chia theo nhóm bài viết độc lập, mục tiêu khoảng 60% train / 20% validation / 20% test theo số nhóm (tỷ lệ bình luận thực tế có thể khác). Các bài chứa bình luận trùng được nối cùng nhóm. Không có bài hoặc văn bản chuẩn hóa trùng giữa các tập. Seed 42; seed 43 cho validation. Chọn lần chia đầu tiên mà cả hai lớp xuất hiện trong mỗi tập; không chọn theo điểm mô hình. Tối thiểu 10 mẫu mỗi lớp và 5 nhóm độc lập chỉ là điều kiện chạy kỹ thuật; cần nhiều dữ liệu hơn cho kết luận đáng tin cậy.

Mỗi phương pháp đặc trưng được chọn được dùng cho hai baseline NB và SVM; TextCNN dùng cùng các tập chia. Chọn mô hình theo macro-F1 validation, không chọn theo test. Test được dùng để so sánh cuối cùng. Không cân bằng mẫu hoặc học từ vựng trên toàn bộ dữ liệu trước khi chia.

Nhãn validation/test cần được người đọc gán độc lập, không xem gợi ý tự động, rồi kiểm tra chéo và khóa trước đánh giá. Việc này phải thực hiện bằng quy trình nhóm/bản xuất riêng; giao diện chưa tự che gợi ý hay khóa bộ test. Cần công bố phần dữ liệu có hỗ trợ tự động và quy trình duyệt; chưa có bằng chứng về độ chính xác của mô hình gợi ý trên corpus PTIT.

Accuracy=(TP+TN)/N; Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2PR/(P+R). Lớp dương là toxic. Macro-F1 là trung bình F1 hai lớp. Confusion matrix: hàng là nhãn tham chiếu trong dataset, cột là dự đoán, thứ tự [non-toxic, toxic], tức [[TN, FP], [FN, TP]]. Mẫu số bằng 0 được ghi 0.


### 3.4. Kết quả

Kết quả dưới đây thuộc snapshot huấn luyện 03/11/2026 05:07 (UTC+7). Snapshot trùng với dữ liệu và cách tách từ hiện tại.

**Lần huấn luyện này dùng nhãn tự động.** Nếu validation/test có nhãn máy, các chỉ số đo mức khớp với nhãn máy, chưa đo độ chính xác thực trên PTIT. Xem automatic_labels trong thống kê từng tập.

Snapshot: b8123b22a75e7a9de083627e18a4f7361fcbab69e846a31e6d83fbed7eb15129. Phiên bản thư viện: {"python": "3.10.11", "sklearn": "1.7.0", "torch": "2.9.1+cpu"}.

Bộ tách từ của lần chạy: Underthesea; phiên bản: underthesea-9.5.0-word-v1.

Cấu hình thực tế: {"ngram_range": [1, 2], "max_features": 20000, "feature_methods": ["BoW", "TF-IDF"], "nb_alpha": 1, "svm_C": 1, "cnn_embedding": 64, "cnn_embedding_source": "random", "cnn_embedding_trainable": true, "cnn_filters": 48, "cnn_kernels": [2, 3, 4], "cnn_max_length": 128, "cnn_dropout": 0.3, "cnn_epochs": 6, "cnn_learning_rate": 0.001, "cnn_batch_size": 32}.

Embedding TextCNN: {"source": "random", "dimensions": 64, "trainable": true}. Các vector xem ở trang đặc trưng là giá trị khởi tạo; nếu học tiếp, vector trong mô hình sau huấn luyện sẽ thay đổi.

Phân chia thực tế: {"train": {"count": 1131, "groups": 45, "labels": {"non-toxic": 1068, "toxic": 63}, "automatic_labels": 1131}, "validation": {"count": 678, "groups": 15, "labels": {"non-toxic": 616, "toxic": 62}, "automatic_labels": 674}, "test": {"count": 280, "groups": 15, "labels": {"non-toxic": 267, "toxic": 13}, "automatic_labels": 280}}.

| Cấu hình | Val macro-F1 | Accuracy | Precision toxic | Recall toxic | F1 toxic | Macro-F1 | Giây |
|---|---:|---:|---:|---:|---:|---:|---:|
| BoW-NB | 0.5228 | 0.9536 | 0.5000 | 0.1538 | 0.2353 | 0.6057 | 0.000 |
| BoW-SVM | 0.6652 | 0.9571 | 1.0000 | 0.0769 | 0.1429 | 0.5604 | 0.047 |
| TF-IDF-NB | 0.5103 | 0.9536 | 0.5000 | 0.1538 | 0.2353 | 0.6057 | 0.000 |
| TF-IDF-SVM | 0.6725 | 0.9536 | 0.5000 | 0.2308 | 0.3158 | 0.6459 | 0.062 |
| TextCNN | 0.5971 | 0.8750 | 0.1071 | 0.2308 | 0.1463 | 0.5395 | 4.719 |

Mô hình được chọn theo validation: **TF-IDF-SVM**. TextCNN lấy epoch 4.

Với BoW, chênh lệch test macro-F1 của SVM so với NB là -0.0452.

Với TF-IDF, chênh lệch test macro-F1 của SVM so với NB là +0.0402.

Với NB, chênh lệch test macro-F1 của TF-IDF so với BoW là +0.0000.

Với SVM, chênh lệch test macro-F1 của TF-IDF so với BoW là +0.0854.

- BoW-NB: confusion matrix `[[265, 2], [11, 2]]`.

- BoW-SVM: confusion matrix `[[267, 0], [12, 1]]`.

- TF-IDF-NB: confusion matrix `[[265, 2], [11, 2]]`.

- TF-IDF-SVM: confusion matrix `[[264, 3], [10, 3]]`.

- TextCNN: confusion matrix `[[242, 25], [10, 3]]`.

Các chênh lệch trên chỉ mô tả một lần chia; chưa chứng minh ý nghĩa thống kê. Xem *-predictions.json cùng dataset.json trong thư mục run để phân tích các lỗi FP/FN.


## 4. Kết luận và hạn chế

Hệ thống cung cấp luồng thu thập → làm sạch → gán nhãn → trích chọn đặc trưng → huấn luyện → đánh giá → dự đoán. Hạn chế: số bài ít, thiên lệch chọn nhóm, chưa xác minh danh tính sinh viên, mỉa mai và hội thoại cần ngữ cảnh, ảnh/sticker bị bỏ qua, tách từ có thể sai với tiếng lóng, TextCNN cắt ở 128 token. Cần tăng số nhóm/bài và nhãn được kiểm tra chéo; mở rộng đánh giá sang dữ liệu ở thời điểm khác. Tránh điều chỉnh lặp lại dựa trên test. Bản gốc vẫn có thể chứa thông tin cá nhân; ẩn tên và định danh trước khi chia sẻ corpus, không chia sẻ chrome-profile.


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

10. Underthesea: https://github.com/undertheseanlp/underthesea

11. PhoW2V (Nguyen et al., 2020): https://github.com/datquocnguyen/PhoW2V. Vector theo từ 100 chiều; dùng cho nghiên cứu/giáo dục, không phân phối lại vector.
