# Phân loại bình luận toxic và non-toxic trong các nhóm Facebook liên quan đến sinh viên PTIT


## 1. Giới thiệu bài toán

Mục tiêu: hỗ trợ nhận diện bình luận độc hại trong ngữ cảnh cộng đồng sinh viên. Đầu vào là văn bản bình luận; đầu ra là toxic hoặc non-toxic. Đây là công cụ hỗ trợ nghiên cứu, không tự động kết luận tư cách sinh viên hay áp dụng chế tài với người viết.

Nguồn dữ liệu: bình luận văn bản do Selenium thu thập từ các nhóm/trang người dùng có quyền truy cập. Không suy ra mọi người bình luận đều là sinh viên PTIT. Không khẳng định đã thu thập đầy đủ; bộ lọc Facebook, bình luận ẩn, ảnh/sticker và thay đổi giao diện có thể tạo thiên lệch mẫu.


## 2. Cơ sở lý thuyết

Toxic: công kích cá nhân/nhóm, lăng mạ, đe dọa, quấy rối hoặc miệt thị. Non-toxic: hỏi đáp, trao đổi thông tin, phản biện lịch sự và ý kiến tiêu cực không công kích. Từ tục trong trích dẫn hoặc đùa thân mật cần xét ngữ cảnh, không dùng từ khóa đơn lẻ làm nhãn chuẩn.

BoW biểu diễn số lần xuất hiện token/ngram. TF-IDF giảm trọng số token phổ biến và tăng trọng số token đặc trưng. Với cấu hình mặc định: idf(t)=log((1+n)/(1+df(t)))+1, sau đó chuẩn hóa L2. Mặc định dùng unigram/bigram từ, tối đa 20.000 đặc trưng cho nhánh từ. Khi bật char_features, ghép thêm nhánh char_wb 3–5 ký tự, tối đa 20.000 đặc trưng riêng; tổng hai nhánh có thể tới 40.000. Có thể chọn lại cấu hình trên trang Trích xuất đặc trưng. Từ vựng và IDF chỉ học trên train; NB/SVM dùng lại ma trận đã trích xuất.

Multinomial Naive Bayes dùng xác suất có điều kiện với giả định độc lập đặc trưng và làm trơn alpha=1. LinearSVC là SVM tuyến tính, cấu hình ban đầu C=1, class_weight=balanced. Khi tối ưu, alpha/C/trọng số lớp được chọn bằng validation; bảng cấu hình thực tế bên dưới ghi giá trị cuối cùng.

Mô hình học sâu bổ sung: ViSoBERT, encoder Transformer tiền huấn luyện cho văn bản mạng xã hội tiếng Việt. Dùng tokenizer riêng và tinh chỉnh bộ phân loại trên nhãn train; chọn checkpoint và ngưỡng bằng validation.


## 3. Thực nghiệm và kết quả


### 3.1. Thu thập và tiền xử lý

Dữ liệu hiện tại: **5786 bình luận**, **622 bài**; **5199 mẫu sạch duy nhất**, **5199 mẫu sạch đã gán nhãn**. Phân bố nhãn trong mẫu sạch: {"non-toxic": 4162, "toxic": 1037}. Kiểm tra chất lượng: {"ready": 5199, "duplicate": 587}.

Nguồn nhãn: {"automatic": 5198, "manual": 1}. Số mẫu sạch có nhãn dùng được: 5199. Nhãn máy đã lưu được dùng trực tiếp, không yêu cầu duyệt. Nguồn automatic và xác nhận riêng được giữ để truy vết.

Quy trình: chuẩn hóa Unicode NFC, chữ thường, giải mã HTML; ẩn URL/email/số điện thoại bằng token; bỏ ký tự vô hình trong chữ và dấu câu; chuẩn hóa một số teencode; chỉ loại stop words các/những. Giữ dấu tiếng Việt, từ phủ định, được/thì/mà, từ tục và emoji. Giữ k/cc khi mơ hồ; dạng tiền 10-50 k thành 10-50k; ko đc thành không được. Biểu cảm :))/=))) thành emoticon_smile, :(( thành emoticon_sad; không dùng biểu cảm làm nhãn. Phiên bản tiền xử lý hiện tại: ptit-v4-contextual-dc-20261105. Tách từ bằng Underthesea trước trích xuất đặc trưng, phiên bản underthesea-9.5.0-v1. Từ đa âm tiết được nối bằng dấu gạch dưới (sinh viên → sinh_viên); unigram là một từ, bigram là hai từ liền nhau. Giữ nguyên token ẩn thông tin, biểu cảm, emoji ghép và dạng tiền. NB/SVM và dự đoán baseline dùng cùng bộ tách từ; ViSoBERT dùng tokenizer riêng. Không xóa bản gốc. Văn bản trùng sau chuẩn hóa chỉ giữ một mẫu; nhãn mâu thuẫn bị loại khỏi train cho tới khi rà soát. Mẫu còn nội dung thu gọn được đánh dấu incomplete và không dùng huấn luyện; độ đầy đủ của bản crawl cũ thiếu thông tin này chưa được xác minh.


### 3.2. Quy trình gán nhãn

Người gán nhãn đọc văn bản gốc, chọn nhãn, ghi chú trường hợp khó hoặc loại dữ liệu không hợp lệ. Các trường hợp thiếu ngữ cảnh nên để trống để thảo luận. Nên có hai người gán độc lập một phần dữ liệu, thống nhất bất đồng và báo cáo Cohen kappa trước khi chốt bộ chuẩn. Hiện công cụ lưu một nhãn cuối cùng/mẫu; chưa có số liệu đồng thuận giữa người gán nhãn.

Bộ nhãn hiện hành có hỗ trợ Qwen3 4B Instruct qua Ollama tại máy. Tác vụ đọc quy tắc v4, bình luận gốc, ngữ cảnh bài viết và chuỗi bình luận cha có sẵn. “Làm sạch dữ liệu” và “Gán nhãn tự động” là hai thao tác riêng; tác vụ tự động chỉ xử lý mẫu sạch chưa có nhãn, giữ nguyên nhãn, ghi chú và quyết định để trống do người đọc đã lưu.

Mẫu sạch có nhãn toxic/non-toxic đã lưu được đưa vào trích xuất đặc trưng và huấn luyện, kể cả nhãn máy chưa có xác nhận riêng. Không có bước duyệt bắt buộc. Người dùng có thể sửa nhãn hoặc loại mẫu tại bảng dữ liệu; sửa nhãn làm đặc trưng/kết quả cũ hết hiệu lực. human_verified chỉ thể hiện xác nhận riêng đã được lưu; thông tin phê duyệt cũ được giữ như lịch sử, không quyết định quyền sử dụng nhãn. Nhãn không khớp nội dung gốc hiện tại vẫn bị loại.

Gợi ý, điểm, model/revision và dấu vân tay văn bản được lưu tách khỏi nhãn xác nhận. data/workspace.json là kho chính, ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử; annotations.json/imported.json cũ chỉ dùng làm nguồn chuyển đổi khi chưa có workspace. Nhãn có dấu vân tay không còn khớp nội dung phải được duyệt lại. Bản xuất /api/dataset.csv và /api/dataset.json chứa mẫu ready có nhãn đã lưu, bao gồm nhãn máy, kèm nguồn nhãn và label_usable; gợi ý chưa lưu nhãn không được đưa vào dataset.


### 3.3. Thiết kế đánh giá

Chia theo nhóm bài viết độc lập, mục tiêu khoảng 60% train / 20% validation / 20% test theo số nhóm (tỷ lệ bình luận thực tế có thể khác). Các bài chứa bình luận trùng được nối cùng nhóm. Không có bài hoặc văn bản chuẩn hóa trùng giữa các tập. Seed 42; seed 43 cho validation. Chọn lần chia đầu tiên mà cả hai lớp xuất hiện trong mỗi tập; không chọn theo điểm mô hình. Tối thiểu 10 mẫu mỗi lớp và 5 nhóm độc lập chỉ là điều kiện chạy kỹ thuật; cần nhiều dữ liệu hơn cho kết luận đáng tin cậy.

Mỗi phương pháp đặc trưng được chọn được dùng cho hai baseline NB và SVM; ViSoBERT dùng cùng các tập chia. Chọn mô hình theo macro-F1 validation, không chọn theo test. Test được dùng để so sánh cuối cùng. Không cân bằng mẫu hoặc học từ vựng trên toàn bộ dữ liệu trước khi chia.

Nhãn validation/test cần được người đọc gán độc lập, không xem gợi ý tự động, rồi kiểm tra chéo và khóa trước đánh giá. Việc này phải thực hiện bằng quy trình nhóm/bản xuất riêng; giao diện chưa tự che gợi ý hay khóa bộ test. Cần công bố phần dữ liệu có hỗ trợ tự động và quy trình duyệt; chưa có bằng chứng về độ chính xác của mô hình gợi ý trên corpus PTIT.

Accuracy=(TP+TN)/N; Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2PR/(P+R). Lớp dương là toxic. Macro-F1 là trung bình F1 hai lớp. Confusion matrix: hàng là nhãn tham chiếu trong dataset, cột là dự đoán, thứ tự [non-toxic, toxic], tức [[TN, FP], [FN, TP]]. Mẫu số bằng 0 được ghi 0.


### 3.4. Kết quả

Kết quả dưới đây thuộc snapshot huấn luyện 05/11/2026 01:29 (UTC+7). Snapshot trùng với dữ liệu và cách tách từ hiện tại.

**Lần huấn luyện này dùng nhãn tự động.** Nếu validation/test có nhãn máy, các chỉ số đo mức khớp với nhãn máy, chưa đo độ chính xác thực trên PTIT. Xem automatic_labels trong thống kê từng tập.

Snapshot: 198fa5414698434128a9595c0a6b4f871f695ada0743eb93053844ccbd967492. Phiên bản thư viện: {"python": "3.13.2", "sklearn": "1.9.1", "torch": "2.10.0+cu128", "transformers": "4.57.6"}.

Bộ tách từ của lần chạy: Underthesea; phiên bản: underthesea-9.5.0-v1.

Cấu hình thực tế: {"ngram_range": [1, 2], "max_features": 20000, "char_features": true, "feature_methods": ["BoW", "TF-IDF"], "nb_alpha": 1, "svm_C": 1}.

Phân chia thực tế: {"train": {"count": 2175, "groups": 248, "labels": {"non-toxic": 1570, "toxic": 605}, "automatic_labels": 2174}, "validation": {"count": 699, "groups": 83, "labels": {"non-toxic": 517, "toxic": 182}, "automatic_labels": 699}, "test": {"count": 646, "groups": 83, "labels": {"non-toxic": 452, "toxic": 194}, "automatic_labels": 646}}.

| Cấu hình | Val macro-F1 | Accuracy | Precision toxic | Recall toxic | F1 toxic | Macro-F1 | Giây |
|---|---:|---:|---:|---:|---:|---:|---:|
| BoW-NB | 0.7220 | 0.7755 | 0.6339 | 0.5979 | 0.6154 | 0.7285 | 0.047 |
| BoW-SVM | 0.7518 | 0.7817 | 0.6532 | 0.5825 | 0.6158 | 0.7317 | 1.954 |
| TF-IDF-NB | 0.7208 | 0.7678 | 0.5846 | 0.7835 | 0.6696 | 0.7453 | 0.059 |
| TF-IDF-SVM | 0.7266 | 0.8050 | 0.6868 | 0.6443 | 0.6649 | 0.7637 | 0.565 |
| ViSoBERT | 0.7994 | 0.8437 | 0.7541 | 0.7113 | 0.7321 | 0.8109 | 781.296 |

Mô hình được chọn theo validation: **ViSoBERT**.

Thiết bị huấn luyện: BoW-NB: cpu, BoW-SVM: cpu, TF-IDF-NB: cpu, TF-IDF-SVM: cpu, ViSoBERT: cuda.

### Tối ưu tham số và ngưỡng

Cột Giây của mô hình tối ưu gồm thời gian tìm kiếm tham số trong nhóm; không dùng để so trực tiếp tốc độ huấn luyện một cấu hình hay tốc độ dự đoán.

Giữ nguyên nhãn, không bổ sung ngữ cảnh. Mỗi mô hình chỉ giữ một kết quả cuối cùng. NB/SVM dùng đúng ma trận và từ vựng đã tạo ở bước trích xuất, không fit lại vectorizer. NB thử alpha 0,1/0,3/1/3; SVM thử C 0,03/0,1/0,3/1/3, có/không class_weight balanced. Unigram/bigram, phương pháp và số đặc trưng tối đa do bước trích xuất quyết định. Từ vựng và IDF chỉ fit train. search.json lưu các lượt chọn tham số phân loại.

Sau khi chốt tham số bằng ngưỡng mặc định, chọn ngưỡng macro-F1 trên validation, không dùng test. Điểm SVM là decision score, không phải xác suất/độ tin cậy đã hiệu chỉnh. Các xác suất NB/ViSoBERT cũng chưa được kiểm định hiệu chỉnh. Ngưỡng chỉ thay đổi quyết định, không tự cải thiện khả năng xếp hạng của mô hình.

| Cấu hình | Ngưỡng | Val macro-F1 mặc định → tối ưu | Test precision mặc định → tối ưu | Test recall mặc định → tối ưu |
|---|---:|---:|---:|---:|
| BoW-NB | 0.20137 | 0.7163 → 0.7220 | 0.6667 → 0.6339 | 0.5773 → 0.5979 |
| BoW-SVM | -0.06920 | 0.7460 → 0.7518 | 0.6687 → 0.6532 | 0.5722 → 0.5825 |
| TF-IDF-NB | 0.17393 | 0.7047 → 0.7208 | 0.6508 → 0.5846 | 0.6340 → 0.7835 |
| TF-IDF-SVM | 0.09515 | 0.7204 → 0.7266 | 0.6385 → 0.6868 | 0.7010 → 0.6443 |
| ViSoBERT | 0.99836 | 0.7846 → 0.7994 | 0.6831 → 0.7541 | 0.8557 → 0.7113 |

Test đã được xem ở các thực nghiệm trước; cần dữ liệu độc lập cho kết luận tổng quát hóa cuối cùng. Điểm validation sau tìm kiếm có thể lạc quan; các kết quả test ở đây mang tính so sánh trên bộ tham chiếu hiện tại.

ViSoBERT dùng uitnlp/visobert, revision 196a62afad9cbe4f52a54aabad828b13f0eec59a; chiến lược full_encoder_and_head, thiết bị cuda, checkpoint epoch 4. Chuẩn hóa Unicode/URL/email, giữ dấu câu và emoji; dùng tokenizer tiền huấn luyện, không tách từ Underthesea. Bộ phân loại được học trên nhãn train, chọn checkpoint và ngưỡng bằng validation.

Với BoW, chênh lệch test macro-F1 của SVM so với NB là +0.0032.

Với TF-IDF, chênh lệch test macro-F1 của SVM so với NB là +0.0184.

Với NB, chênh lệch test macro-F1 của TF-IDF so với BoW là +0.0168.

Với SVM, chênh lệch test macro-F1 của TF-IDF so với BoW là +0.0320.

- BoW-NB: confusion matrix `[[385, 67], [78, 116]]`.

- BoW-SVM: confusion matrix `[[392, 60], [81, 113]]`.

- TF-IDF-NB: confusion matrix `[[344, 108], [42, 152]]`.

- TF-IDF-SVM: confusion matrix `[[395, 57], [69, 125]]`.

- ViSoBERT: confusion matrix `[[407, 45], [56, 138]]`.

Các chênh lệch trên chỉ mô tả một lần chia; chưa chứng minh ý nghĩa thống kê. Xem *-predictions.json cùng dataset.json trong thư mục run để phân tích các lỗi FP/FN.


## 4. Kết luận và hạn chế

Hệ thống cung cấp luồng thu thập → làm sạch → gán nhãn → trích chọn đặc trưng → huấn luyện → đánh giá → dự đoán. Hạn chế: số bài ít, thiên lệch chọn nhóm, chưa xác minh danh tính sinh viên, mỉa mai và hội thoại cần ngữ cảnh, ảnh/sticker bị bỏ qua, tách từ có thể sai với tiếng lóng, ViSoBERT giới hạn độ dài đầu vào theo cấu hình đã lưu. Cần tăng số nhóm/bài và nhãn được kiểm tra chéo; mở rộng đánh giá sang dữ liệu ở thời điểm khác. Tránh điều chỉnh lặp lại dựa trên test. Bản gốc vẫn có thể chứa thông tin cá nhân; ẩn tên và định danh trước khi chia sẻ corpus, không chia sẻ chrome-profile.


## Tài liệu tham khảo

1. Scikit-learn: https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction

2. Naive Bayes: https://scikit-learn.org/stable/modules/naive_bayes.html

3. LinearSVC: https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html

4. GroupShuffleSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html

5. PyTorch: https://docs.pytorch.org/docs/stable/nn.html

6. Selenium: https://www.selenium.dev/documentation/webdriver/

7. Model gợi ý: [dangvansam/vietnamese-toxicity](https://huggingface.co/dangvansam/vietnamese-toxicity), revision bac60f3e162d3a06003bf561a9f8365982ccc67a.

8. Nguyen et al. (2023), [ViSoBERT](https://aclanthology.org/2023.emnlp-main.315/); [model card và phạm vi nghiên cứu](https://huggingface.co/uitnlp/visobert).

9. Underthesea: https://github.com/undertheseanlp/underthesea
