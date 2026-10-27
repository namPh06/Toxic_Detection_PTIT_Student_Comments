# PTIT Comment Lab

Ứng dụng chạy trên máy cá nhân cho bài tập lớn **phân loại toxic / non-toxic từ bình luận Facebook liên quan đến sinh viên PTIT**. Tận dụng crawler Selenium có sẵn, bổ sung giao diện, tiền xử lý, gán nhãn, thí nghiệm và báo cáo.

## Mở ứng dụng

**Bấm đúp `MO_CONG_CU.cmd`**, rồi mở http://127.0.0.1:8767/. Giữ cửa sổ chạy ứng dụng mở trong khi sử dụng. Cần Python 3.10+ (đã kiểm tra trên Python 3.13), Chrome để crawl và Internet khi cài thư viện/driver lần đầu. PyTorch cần tải khoảng hơn 100 MB và dung lượng giải nén lớn hơn.

Chạy thủ công bằng PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Không cần đăng nhập Facebook để làm sạch, gán nhãn, huấn luyện hoặc đọc báo cáo. Chrome chỉ mở khi bấm **Mở Chrome thu thập**. Nếu cổng 8767 đang được dùng, đóng phiên cũ bằng Ctrl+C trước khi mở lại; đóng tab web không tắt máy chủ.

Nếu Chrome báo `tab crashed` ngay khi mở: chạy `MO_CONG_CU.cmd` từ Explorer hoặc PowerShell thông thường. Trong lần kiểm tra này, máy chủ chạy trong môi trường hạn chế quyền làm Chrome crash ngay cả với trang HTML trống; cùng Chrome/driver chạy trong phiên Windows bình thường hoạt động được. Giữ nguyên thư mục `chrome-profile` để giữ phiên đăng nhập.

Khi đóng hết cửa sổ Chrome, ứng dụng kiểm tra phiên mỗi giây và cho mở lại bằng **Mở Chrome thu thập**. Lệnh crawl của phiên cũ bị bỏ trước khi mở phiên mới; dữ liệu đã lưu vẫn được giữ.

### CAPTCHA xong quay về đăng nhập

Nếu cùng tài khoản đăng nhập được trong Chrome thường nhưng cửa sổ thu thập bị lặp xác minh, có thể thử đăng nhập thủ công trong hồ sơ riêng của project:

1. Đóng cửa sổ **Chrome thu thập** đang mở. Có thể giữ máy chủ và giao diện tool chạy.
2. Bấm đúp **`DANG_NHAP_FACEBOOK.cmd`**. Chrome mở bằng hồ sơ `chrome-profile` của project; bạn tự đăng nhập và hoàn tất xác minh Facebook.
3. Khi đã vào được Facebook, đóng cửa sổ Chrome vừa mở để lưu và giải phóng hồ sơ.
4. Quay lại tool, bấm **Mở Chrome thu thập**, mở nhóm cần lấy dữ liệu rồi bắt đầu.

Lệnh từ chối mở nếu phiên Chrome điều khiển của tool còn hoạt động. Hồ sơ được giữ tại chỗ, không sao chép cookie từ Chrome cá nhân. Crawler vẫn dùng Selenium như trước; Facebook có thể yêu cầu xác minh lại. Cách này chưa bảo đảm khắc phục vòng lặp và không tự giải CAPTCHA.

## Quy trình sử dụng

1. **Tổng quan:** xem số bình luận/bài, mẫu sạch, tiến độ nhãn và phân bố chất lượng từ dữ liệu thật.
2. **Thu thập:** mở Chrome riêng, tự đăng nhập, nhập URL nhóm/fanpage hoặc để trống để dùng tab hiện tại, chọn 1–500 bài rồi bắt đầu. Có tiến độ, số bình luận, lý do kết thúc từng bài và nút dừng. Tải JSON gốc nếu cần.
3. **Làm sạch & gán nhãn:** bấm **Làm sạch & gán nhãn toàn bộ** một lần. Ứng dụng xử lý mọi mẫu sạch chưa có nhãn trong workspace, không phụ thuộc trang/bộ lọc; giữ nguyên nhãn đã lưu. Kết quả tự lưu vào `data/dataset_auto.csv/json`, bản làm sạch đầy đủ vào `data/processed.csv/json`. Dùng **Tải CSV / Tải JSON** trong mục **Tải dataset đã gán nhãn** để tải ngay; không cần lưu từng dòng. Có thể sửa từng nhãn khi cần. Phần **Gợi ý và duyệt thủ công (tùy chọn)** giữ chế độ gợi ý rồi xác nhận như trước.
4. **Huấn luyện & đánh giá:** khi đủ nhãn, chạy 5 cấu hình. Theo dõi tiến độ TextCNN, bảng Accuracy/Precision/Recall/F1/Macro-F1, confusion matrix, biểu đồ so sánh và thử dự đoán. Các nhãn dự đoán không tự trở thành nhãn chuẩn.
5. **Báo cáo:** xem/tải Markdown gồm giới thiệu, lý thuyết, thực nghiệm, kết luận và tài liệu tham khảo. Phần kết quả tự lấy từ lần huấn luyện hoàn tất gần nhất. Bổ sung tên thành viên/lớp/phân công trước khi nộp.

**Tại thời điểm kiểm tra, corpus có 0 nhãn chuẩn đã xác nhận.** Chưa có Accuracy/Precision/Recall/F1 trên dữ liệu PTIT; chạy được mô hình gợi ý không chứng minh độ chính xác trên corpus này. Báo cáo nêu rõ trạng thái dữ liệu; các fixture kiểm thử phần mềm không phải số liệu BTL. Xem [hướng dẫn gán nhãn](HUONG_DAN_GAN_NHAN.md).

## Gán nhãn tự động toàn bộ

Nút chính dùng ngưỡng **điểm toxic ≥ 0,5 → toxic**, thấp hơn → non-toxic. Mọi mẫu hợp lệ chưa có nhãn đều được xử lý, kể cả mẫu có điểm chưa rõ. Điểm nằm giữa 0,2–0,8 hoặc văn bản phải cắt vì quá dài được đánh dấu `needs_review`; cờ này không chặn tải dataset hay huấn luyện. Kết quả ghi `label_source=automatic`, điểm, ngưỡng, model/revision và hash văn bản để phân biệt với nhãn do người đọc xác nhận. Kết quả mô hình đã lưu còn khớp nội dung được dùng lại, chỉ chạy suy luận cho mẫu còn thiếu.

**Có thể huấn luyện trực tiếp trên nhãn máy**, nhưng chỉ số trên validation/test có nhãn máy đo mức khớp với bộ nhãn đó, chưa phải độ chính xác độc lập trên PTIT. Giao diện và báo cáo ghi rõ giới hạn này.

### Chế độ chỉ tạo gợi ý (tùy chọn)

`labeling.py` chạy mô hình [dangvansam/vietnamese-toxicity](https://huggingface.co/dangvansam/vietnamese-toxicity), chốt revision `bac60f3e162d3a06003bf561a9f8365982ccc67a`, bằng ONNX Runtime trên CPU. Lần đầu tải khoảng 100 MB vào `models/vietnamese-toxicity`; ứng dụng kiểm tra kích thước và SHA-256 trước khi dùng. Cache mô hình đã được tải và kiểm tra trong lần bàn giao này. Khi cache còn hợp lệ, có thể tạo gợi ý không cần Internet; nội dung bình luận không được gửi lên dịch vụ bên ngoài.

Mô hình đọc bản gốc đã chuẩn hóa NFC/khoảng trắng, không đọc bản đã bỏ stop words. Điểm toxic là sigmoid của đầu ra mô hình, **chưa hiệu chỉnh trên PTIT, không phải độ chính xác hay xác suất đúng của nhãn**. Điểm ≤ 0,2 gợi ý `non-toxic`; điểm ≥ 0,8 gợi ý `toxic`; khoảng giữa để trống. Văn bản vượt 512 token của tokenizer, tính cả token đặc biệt, cũng không nhận nhãn gợi ý vì đầu vào phải bị cắt. Người đọc cần xem toàn bộ bình luận và ngữ cảnh.

Gợi ý được lưu riêng với model/revision, điểm, thời gian và dấu vân tay văn bản; không tự trở thành nhãn huấn luyện. Mẫu lỗi, trùng, đã có nhãn hoặc biết là chưa mở hết nội dung không được tạo gợi ý. Mô hình có thể sai với tiếng lóng, phủ định, trích dẫn và mỉa mai. Theo [model card ViSoBERT nguồn](https://huggingface.co/uitnlp/visobert), mô hình nền dành cho mục đích nghiên cứu; tính năng này được dùng trong phạm vi BTL nghiên cứu.

## Đối chiếu yêu cầu đề bài

| Yêu cầu | Chức năng / tệp |
|---|---|
| Thu thập bình luận Facebook | Crawler Selenium, `app.py`, `dom.js`, `helpers.js`; màn hình Thu thập |
| Tiền xử lý, tách token, stop words | `dataset.py`; chuẩn hóa NFC/chữ thường/teencode, token hóa âm tiết + emoji, lọc stop words, URL/email/điện thoại, bản trùng và dòng lỗi |
| Ít nhất 2 cách trích đặc trưng | BoW, TF-IDF (unigram + bigram); embeddings học từ đầu cho TextCNN |
| Naive Bayes và SVM, chia train/test | Bốn cấu hình BoW/TF-IDF × MultinomialNB/LinearSVC; chia thêm validation để chọn mô hình |
| Mô hình hiện đại bổ sung | TextCNN (mô hình học sâu CNN cho văn bản, theo Kim 2014); chạy CPU, không cần tải pretrained weights |
| Accuracy, Precision, Recall, F1, confusion matrix | `experiments.py`; bảng/biểu đồ giao diện; tệp metrics và báo cáo |
| So sánh đặc trưng và thuật toán | Cùng phép chia cho mọi cấu hình; báo cáo chênh lệch macro-F1 giữa NB/SVM và BoW/TF-IDF |
| Báo cáo có lý thuyết, thực nghiệm và tài liệu tham khảo | Xuất Markdown từ giao diện; `BAO_CAO.md` là bản tại thời điểm bàn giao |

## Tiền xử lý và ý nghĩa mẫu sạch

`text_raw` luôn giữ nguyên. `text_clean` chuẩn hóa Unicode, loại ký tự vô hình/dấu câu, giải mã HTML, thay URL/email/điện thoại bằng token, đổi một số teencode và bỏ danh sách stop words ngắn. Giữ phủ định, dấu tiếng Việt, từ tục và emoji. Token hóa hiện theo âm tiết/khoảng trắng, **chưa ghép từ đa âm tiết bằng VnCoreNLP/underthesea**; bigram được dùng cho hai baseline.

`quality=ready` là mẫu văn bản duy nhất qua kiểm tra tự động, không đảm bảo đúng phạm vi/ngữ cảnh; người gán cần rà soát. Các trạng thái khác: `duplicate`, `conflict` (bản trùng có nhãn khác nhau), `empty_or_ui`, `excluded`, `incomplete` (crawler còn thấy nội dung chưa mở hết). Dữ liệu cũ thiếu `text_complete` có độ đầy đủ chưa xác minh, cần kiểm tra lại nguồn khi cần; không được coi là đã xác nhận đầy đủ.

**Xuất bản làm sạch → Tải CSV/JSON toàn bộ** giữ tất cả trạng thái để kiểm tra. **Dataset đã gán nhãn** (`GET /api/dataset-auto.csv` hoặc `/api/dataset-auto.json`) và tập huấn luyện dùng mẫu `ready` có nhãn, gồm cả nhãn máy. **Dataset đã duyệt** (`/api/dataset.csv`, `/api/dataset.json`) chỉ chứa nhãn người dùng xác nhận/nhập; không chứa nhãn máy hay gợi ý. Nếu chưa có mẫu phù hợp, ứng dụng trả thông báo thay vì tạo dataset rỗng. CSV bảo vệ ô bắt đầu bằng ký tự công thức bằng dấu nháy đơn; nhập lại bằng ứng dụng sẽ đối chiếu hash để khôi phục nguyên văn.

Nhãn mới gắn với SHA-256 của `text_raw`. Nếu crawler cập nhật nội dung, nhãn cũ được giữ để đối chiếu nhưng mất hiệu lực huấn luyện/xuất dataset; cần chạy lại gán nhãn toàn bộ hoặc đọc và lưu lại thủ công. Nhãn cũ từ phiên bản chưa có dấu vân tay cần được rà soát khi chuyển sang quy trình này.

Nhập JSON dạng `{"rows":[...]}` hoặc mảng dòng; CSV dùng UTF-8, các cột bắt buộc `post_id,comment_id,text_raw`. `label` chỉ được trống, `toxic`, `non-toxic`; `annotation_note` tùy chọn. Khi nhập dataset tự động đã xuất, giữ `label_source=automatic` cùng hash, điểm, ngưỡng, model/revision, `needs_review` và `review_reason`; ứng dụng kiểm tra và giữ nguồn nhãn máy. Nhãn không ghi nguồn được coi là người dùng nhập, vì vậy không bỏ metadata của nhãn tự động. Tệp tối đa 10 MB, 10.000 dòng/lượt, tổng workspace tối đa 20.000 dòng. Trùng ID chỉ cập nhật nhãn khi văn bản giống hệt; nhãn người đọc có thể thay nhãn máy, nhãn máy không ghi đè nhãn người đọc. Dữ liệu mới và nhãn được ghi cùng nhau vào `data/workspace.json`.

## Thiết kế thí nghiệm

- Học từ mẫu sạch có nhãn, gồm nhãn tự động nếu có. Tối thiểu 10 mẫu mỗi lớp và 5 nhóm bài độc lập để chạy; cần nhiều hơn để có kết quả đáng tin cậy. Thống kê từng tập ghi số `automatic_labels`.
- Chuẩn bị nhãn validation/test do người đọc gán độc lập, không nhìn gợi ý mô hình; kiểm tra chéo và khóa nhãn trước đánh giá. Giao diện chưa tự che gợi ý hoặc quản lý bộ test khóa riêng: dùng bản xuất và quy trình nhóm để thực hiện. Nhãn test chỉ sao chép từ gợi ý sẽ làm phép đánh giá thiên lệch.
- Chia theo **bài viết**, nối các bài có bình luận trùng vào cùng nhóm. Mục tiêu 60/20/20 theo số nhóm; tỷ lệ mẫu thực tế hiển thị sau khi chạy. Không âm thầm chuyển sang random split theo dòng nếu thiếu nhóm.
- Các tập đều cần có hai lớp. Chọn lần chia hợp lệ đầu tiên với seed 42/43; không tối ưu phép chia theo điểm mô hình.
- BoW/TF-IDF chỉ fit trên train: 20.000 đặc trưng tối đa, ngram 1–2. NB alpha=1. SVM tuyến tính C=1, balanced class weights.
- TextCNN: embedding 64, kernels 2/3/4 × 48 filters, ReLU + max pooling, dropout 0,3, Adam lr=0,001, batch 32, 12 epoch. Từ vựng train tối đa 20.000 token, OOV token riêng, cắt 128 token. Epoch chọn theo macro-F1 validation; class weights lấy từ train.
- Chọn mô hình cuối cùng theo **validation macro-F1**, sau đó trình bày kết quả test của cả năm. Không có xác suất “độ tin cậy” giả cho SVM. Lớp dương = toxic; confusion matrix hàng thật/cột dự đoán, thứ tự `[non-toxic, toxic]`.
- Mỗi lượt có snapshot, seed, phiên bản thư viện, tham số và phép chia để truy vết. Khi nhãn/dữ liệu thay đổi, giao diện báo kết quả cũ. Không coi một lần chia là bằng chứng vượt trội có ý nghĩa thống kê.

## Dữ liệu và tệp

```text
app.py                  Máy chủ localhost + điều khiển crawler sẵn có
index.html/style.css/ui.js  Giao diện tiếng Việt, không dùng CDN
dataset.py              Làm sạch, lọc trùng, nhập/xuất
lab.py                  Lưu workspace, quản lý gợi ý và huấn luyện
labeling.py             Gợi ý nhãn bằng mô hình ONNX đã chốt phiên bản
experiments.py          Chia tập, 4 baseline, đánh giá, báo cáo
neural.py               TextCNN PyTorch
test_project.py         Kiểm thử trên fixture riêng
data/progress.json      Kho crawl gốc (không sửa khi gán nhãn)
data/workspace.json     Kho chính: nhãn, dữ liệu nhập và gợi ý; ghi nguyên tử
data/annotations.json   Nhãn phiên bản cũ, chỉ đọc khi chưa có workspace.json
data/imported.json      Dữ liệu nhập phiên bản cũ, chỉ đọc khi chưa có workspace.json
models/vietnamese-toxicity/  model.onnx và tokenizer.json được kiểm tra SHA-256
data/processed.*        Bản làm sạch xuất tại lần bấm lưu
data/dataset_auto.*     Mẫu sạch đã gán nhãn, gồm nhãn máy; xuất khi xử lý toàn bộ
data/latest.json        Tham chiếu lần huấn luyện hoàn tất gần nhất
data/runs/run-.../      dataset.json, split.json, metrics.json, report.md,
                        *-predictions.json, *.joblib, TextCNN.pt, vocabulary.json
```

`workspace.json` là nguồn chính khi đã tồn tại. Nếu chưa có, ứng dụng đọc `annotations.json`/`imported.json` cũ; lần lưu nhãn, nhập dữ liệu hoặc lưu gợi ý tiếp theo ghi trạng thái vào workspace trong một lần thay tệp nguyên tử. Các tệp cũ không bị xóa nhưng không tiếp tục nhận cập nhật; không sửa chúng để thay nhãn khi workspace đã có.

Không mở hai app dùng cùng workspace. Sao lưu toàn bộ `data` khi máy chủ đã tắt. Không tải artifact `.joblib` từ nguồn không tin cậy để thay vào thư mục mô hình; đây là định dạng pickle chỉ dành cho artifact do chính app tạo. Không chia sẻ `chrome-profile` (chứa phiên đăng nhập). Dữ liệu raw/ID vẫn có thể mang thông tin cá nhân; che tên, định danh và nội dung nhạy cảm trước khi công bố.

## Giới hạn crawler được giữ lại

Selenium dùng Chrome profile riêng, không lấy mật khẩu, không vượt CAPTCHA/hạn chế. Mỗi bài tối đa 3 phút; kho crawl tối đa 10.000 mẫu. Facebook có thể chỉ hiện một phần bình luận và thay DOM. `no_progress` chỉ nghĩa là không thấy tiến triển, không phải đã lấy hết. Bấm Bắt đầu lần nữa để quét lại các bài tìm được, kể cả bài đã có trong nhật ký; bình luận đã có cùng ID được giữ và cập nhật nội dung dài hơn, không cần đổi tên hay xóa `progress.json`. Crawler cuộn cả vùng lồng nhau, thử vùng chứa khi vùng con đã tới cuối và giữ thao tác bình luận trong hộp thoại bài viết. Nút tải thêm được thử tiếp khi nội dung bình luận thay đổi; nút không tạo tiến triển bị giới hạn hai lần thử. Dừng có thể phải chờ thao tác điều hướng tối đa 35 giây. Công cụ chưa xác minh tài khoản bình luận là sinh viên PTIT.

## Kiểm thử

```powershell
.venv\Scripts\python.exe -m unittest discover -v
node --check ui.js
```

Kiểm tra làm sạch/Unicode/phủ định/ẩn thông tin, lọc trùng/xung đột, lưu nhãn không sửa raw, lỗi ghi đĩa, dữ liệu nhập, chống rò rỉ nhóm bài/văn bản, chiều confusion matrix, chạy-lưu-tải-dự đoán cả 5 mô hình, báo cáo, validation API và origin/host. Kiểm thử crawler xác nhận quét lại bài chưa hoàn tất không làm mất dữ liệu/nhãn, và rê chuột tìm link mới khi link cũ còn trên feed. Toàn bộ fixture và artifact thí nghiệm thử đặt trong thư mục tạm.

`test_crawler_browser.js` cung cấp hai hàm cho Playwright: `checkCrawlerBrowser(page, helpersSource, domSource)` chạy DOM mô phỏng độc lập; `checkDashboardScroll(page, 'http://127.0.0.1:8767')` kiểm tra giao diện khi app đang mở. Dùng tab kiểm thử riêng và đóng tab sau khi chạy; các hàm không gửi bình luận, không chạy crawl thật, không ghi nhãn. Bao phủ vùng cuộn lồng nhau, hộp thoại, nút tải thêm dùng lại, giới hạn nút không phản hồi, vị trí nhật ký khi cập nhật, bàn phím và giao diện rộng/hẹp.

`test_interface_browser.js` cung cấp `checkInterfaceBrowser(page, baseURL)` để kiểm tra giao diện ở 375, 768, 1024 và 1440 px: điều hướng, thông tin kỹ thuật thu gọn, thông báo lỗi và nội dung lỗi được escape. `test_labeling_browser.js` kiểm tra gợi ý, duyệt nhãn và xử lý toàn bộ dataset. Các tác vụ ghi dữ liệu trong kiểm thử đều được mô phỏng; chạy trên tab riêng khi app đang mở.

Tài liệu: [scikit-learn](https://scikit-learn.org/stable/), [TextCNN — Kim 2014](https://aclanthology.org/D14-1181/), [PyTorch](https://docs.pytorch.org/docs/stable/), [Selenium](https://www.selenium.dev/documentation/webdriver/).
