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

Dữ liệu hiện tại: **5453 bình luận**, **541 bài**; **4868 mẫu sạch duy nhất**, **4868 mẫu sạch đã gán nhãn**. Phân bố nhãn trong mẫu sạch: {"non-toxic": 4162, "toxic": 706}. Kiểm tra chất lượng: {"ready": 4868, "duplicate": 585}.

Nguồn nhãn: {"automatic": 4867, "manual": 1}. Số mẫu sạch có nhãn dùng được: 4868. Nhãn máy đã lưu được dùng trực tiếp, không yêu cầu duyệt. Nguồn automatic và xác nhận riêng được giữ để truy vết.

Quy trình: chuẩn hóa Unicode NFC, chữ thường, giải mã HTML; ẩn URL/email/số điện thoại bằng token; bỏ ký tự vô hình trong chữ và dấu câu; chuẩn hóa một số teencode; chỉ loại stop words các/những. Giữ dấu tiếng Việt, từ phủ định, được/thì/mà, từ tục và emoji. Giữ k/cc khi mơ hồ; dạng tiền 10-50 k thành 10-50k; ko đc thành không được. Biểu cảm :))/=))) thành emoticon_smile, :(( thành emoticon_sad; không dùng biểu cảm làm nhãn. Phiên bản tiền xử lý hiện tại: ptit-v2-preserve-meaning-20261103. Tách từ bằng Underthesea trước trích xuất đặc trưng, phiên bản underthesea-9.5.0-v1. Từ đa âm tiết được nối bằng dấu gạch dưới (sinh viên → sinh_viên); unigram là một từ, bigram là hai từ liền nhau. Giữ nguyên token ẩn thông tin, biểu cảm, emoji ghép và dạng tiền. NB/SVM, TextCNN và dự đoán dùng cùng bộ tách từ. Không xóa bản gốc. Văn bản trùng sau chuẩn hóa chỉ giữ một mẫu; nhãn mâu thuẫn bị loại khỏi train cho tới khi rà soát. Mẫu còn nội dung thu gọn được đánh dấu incomplete và không dùng huấn luyện; độ đầy đủ của bản crawl cũ thiếu thông tin này chưa được xác minh.


### 3.2. Quy trình gán nhãn

Người gán nhãn đọc văn bản gốc, chọn nhãn, ghi chú trường hợp khó hoặc loại dữ liệu không hợp lệ. Các trường hợp thiếu ngữ cảnh nên để trống để thảo luận. Nên có hai người gán độc lập một phần dữ liệu, thống nhất bất đồng và báo cáo Cohen kappa trước khi chốt bộ chuẩn. Hiện công cụ lưu một nhãn cuối cùng/mẫu; chưa có số liệu đồng thuận giữa người gán nhãn.

Bộ nhãn hiện hành có hỗ trợ Qwen3 4B Instruct qua Ollama tại máy. Tác vụ đọc quy tắc v4, bình luận gốc, ngữ cảnh bài viết và chuỗi bình luận cha có sẵn. “Làm sạch dữ liệu” và “Gán nhãn tự động” là hai thao tác riêng; tác vụ tự động chỉ xử lý mẫu sạch chưa có nhãn, giữ nguyên nhãn, ghi chú và quyết định để trống do người đọc đã lưu.

Mẫu sạch có nhãn toxic/non-toxic đã lưu được đưa vào trích xuất đặc trưng và huấn luyện, kể cả nhãn máy chưa có xác nhận riêng. Không có bước duyệt bắt buộc. Người dùng có thể sửa nhãn hoặc loại mẫu tại bảng dữ liệu; sửa nhãn làm đặc trưng/kết quả cũ hết hiệu lực. human_verified chỉ thể hiện xác nhận riêng đã được lưu; thông tin phê duyệt cũ được giữ như lịch sử, không quyết định quyền sử dụng nhãn. Nhãn không khớp nội dung gốc hiện tại vẫn bị loại.

Gợi ý, điểm, model/revision và dấu vân tay văn bản được lưu tách khỏi nhãn xác nhận. data/workspace.json là kho chính, ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử; annotations.json/imported.json cũ chỉ dùng làm nguồn chuyển đổi khi chưa có workspace. Nhãn có dấu vân tay không còn khớp nội dung phải được duyệt lại. Bản xuất /api/dataset.csv và /api/dataset.json chứa mẫu ready có nhãn đã lưu, bao gồm nhãn máy, kèm nguồn nhãn và label_usable; gợi ý chưa lưu nhãn không được đưa vào dataset.


### 3.3. Thiết kế đánh giá

Chia theo nhóm bài viết độc lập, mục tiêu khoảng 60% train / 20% validation / 20% test theo số nhóm (tỷ lệ bình luận thực tế có thể khác). Các bài chứa bình luận trùng được nối cùng nhóm. Không có bài hoặc văn bản chuẩn hóa trùng giữa các tập. Seed 42; seed 43 cho validation. Chọn lần chia đầu tiên mà cả hai lớp xuất hiện trong mỗi tập; không chọn theo điểm mô hình. Tối thiểu 10 mẫu mỗi lớp và 5 nhóm độc lập chỉ là điều kiện chạy kỹ thuật; cần nhiều dữ liệu hơn cho kết luận đáng tin cậy.

Mỗi phương pháp đặc trưng được chọn được dùng cho hai baseline NB và SVM; TextCNN dùng cùng các tập chia. Chọn mô hình theo macro-F1 validation, không chọn theo test. Test được dùng để so sánh cuối cùng. Không cân bằng mẫu hoặc học từ vựng trên toàn bộ dữ liệu trước khi chia.

Nhãn validation/test cần được người đọc gán độc lập, không xem gợi ý tự động, rồi kiểm tra chéo và khóa trước đánh giá. Việc này phải thực hiện bằng quy trình nhóm/bản xuất riêng; giao diện chưa tự che gợi ý hay khóa bộ test. Cần công bố phần dữ liệu có hỗ trợ tự động và quy trình duyệt; chưa có bằng chứng về độ chính xác của mô hình gợi ý trên corpus PTIT.

Accuracy=(TP+TN)/N; Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2PR/(P+R). Lớp dương là toxic. Macro-F1 là trung bình F1 hai lớp. Confusion matrix: hàng là nhãn tham chiếu trong dataset, cột là dự đoán, thứ tự [non-toxic, toxic], tức [[TN, FP], [FN, TP]]. Mẫu số bằng 0 được ghi 0.


### 3.4. Kết quả

Kết quả dưới đây thuộc snapshot huấn luyện 03/11/2026 22:46 (UTC+7). Dữ liệu hoặc cách tách từ hiện tại đã thay đổi; cần chạy lại để cập nhật.

**Lần huấn luyện này dùng nhãn tự động.** Nếu validation/test có nhãn máy, các chỉ số đo mức khớp với nhãn máy, chưa đo độ chính xác thực trên PTIT. Xem automatic_labels trong thống kê từng tập.

Snapshot: b437f70a6891cd6c527e9c036989747f3f371b0076775e30ac918529b4fe5716. Phiên bản thư viện: {"python": "3.12.6", "sklearn": "1.9.1", "torch": "2.14.1+cpu", "transformers": "4.57.6"}.

Bộ tách từ của lần chạy: Underthesea; phiên bản: underthesea-9.5.0-v1.

Cấu hình thực tế: {"ngram_range": [1, 2], "max_features": 20000, "feature_methods": ["BoW", "TF-IDF"], "nb_alpha": 1, "svm_C": 1, "cnn_embedding": 100, "cnn_embedding_source": "PhoW2V_words_100dims", "cnn_embedding_trainable": true, "cnn_filters": 48, "cnn_kernels": [2, 3, 4], "cnn_max_length": 128, "cnn_dropout": 0.3, "cnn_epochs": 12, "cnn_learning_rate": 0.001, "cnn_batch_size": 32}.

Embedding TextCNN: {"source": "PhoW2V_words_100dims", "source_url": "https://github.com/datquocnguyen/PhoW2V", "sha256": "41b1a7fe6d3c7f0146df2efdcf5f256d822ec7212eb790abea4e22c319623454", "dimensions": 100, "trainable": true, "vocabulary_size": 4996, "matched_words": 3754, "oov_words": 1242, "word_coverage": 0.7514011208967174, "token_coverage": 0.934478888501877, "vocabulary_limit": 20000, "max_length": 128}. Các vector xem ở trang đặc trưng là giá trị khởi tạo; nếu học tiếp, vector trong mô hình sau huấn luyện sẽ thay đổi.

Phân chia thực tế: {"train": {"count": 1743, "groups": 199, "labels": {"non-toxic": 1282, "toxic": 461}, "automatic_labels": 1743}, "validation": {"count": 636, "groups": 67, "labels": {"non-toxic": 559, "toxic": 77}, "automatic_labels": 635}, "test": {"count": 810, "groups": 67, "labels": {"non-toxic": 698, "toxic": 112}, "automatic_labels": 810}}.

| Cấu hình | Val macro-F1 | Accuracy | Precision toxic | Recall toxic | F1 toxic | Macro-F1 | Giây |
|---|---:|---:|---:|---:|---:|---:|---:|
| BoW-NB | 0.6283 | 0.8802 | 0.6087 | 0.3750 | 0.4641 | 0.6983 | 0.016 |
| BoW-SVM | 0.6206 | 0.8901 | 0.6322 | 0.4911 | 0.5528 | 0.7451 | 0.015 |
| TF-IDF-NB | 0.4673 | 0.8630 | 1.0000 | 0.0089 | 0.0177 | 0.4720 | 0.016 |
| TF-IDF-SVM | 0.6554 | 0.8667 | 0.5139 | 0.6607 | 0.5781 | 0.7495 | 0.016 |
| TextCNN | 0.6901 | 0.8765 | 0.5395 | 0.7321 | 0.6212 | 0.7737 | 36.875 |
| ViSoBERT | 0.7491 | 0.8963 | 0.6045 | 0.7232 | 0.6585 | 0.7987 | 3164.172 |

Mô hình được chọn theo validation: **ViSoBERT**. TextCNN lấy epoch 3.

Thiết bị huấn luyện: BoW-NB: cpu, BoW-SVM: cpu, TF-IDF-NB: cpu, TF-IDF-SVM: cpu, TextCNN: cpu, ViSoBERT: cpu.

ViSoBERT dùng uitnlp/visobert, revision 196a62afad9cbe4f52a54aabad828b13f0eec59a; chiến lược last_two_encoder_layers_and_head, thiết bị cpu, checkpoint epoch 3. Chuẩn hóa Unicode/URL/email, giữ dấu câu và emoji; dùng tokenizer tiền huấn luyện, không tách từ Underthesea. Bộ phân loại được học trên nhãn train, chọn checkpoint và ngưỡng bằng validation.

Với BoW, chênh lệch test macro-F1 của SVM so với NB là +0.0467.

Với TF-IDF, chênh lệch test macro-F1 của SVM so với NB là +0.2775.

Với NB, chênh lệch test macro-F1 của TF-IDF so với BoW là -0.2263.

Với SVM, chênh lệch test macro-F1 của TF-IDF so với BoW là +0.0044.

- BoW-NB: confusion matrix `[[671, 27], [70, 42]]`.

- BoW-SVM: confusion matrix `[[666, 32], [57, 55]]`.

- TF-IDF-NB: confusion matrix `[[698, 0], [111, 1]]`.

- TF-IDF-SVM: confusion matrix `[[628, 70], [38, 74]]`.

- TextCNN: confusion matrix `[[628, 70], [30, 82]]`.

- ViSoBERT: confusion matrix `[[645, 53], [31, 81]]`.

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
