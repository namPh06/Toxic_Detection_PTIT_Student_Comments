# PTIT Comment Lab

Ứng dụng web chạy tại máy để thu thập bình luận Facebook, gán nhãn toxic/non-toxic,
trích xuất đặc trưng và so sánh mô hình cho bài tập lớn. Backend Python, giao diện
HTML/CSS/JavaScript; không cần Node.js hay bước build frontend.

## Chạy ứng dụng

Bấm đúp `Open_Tool.cmd`, hoặc chạy từ thư mục dự án:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Mở http://127.0.0.1:8767/. Cần Python 3.10+; đã chạy trên Python 3.13.
Giữ cửa sổ Python mở trong khi dùng. Đóng tab web không tắt máy chủ; nếu cổng đã
bị chiếm, dừng phiên cũ bằng Ctrl+C. Không cần đăng nhập Facebook để duyệt nhãn
hoặc huấn luyện. Chrome và Internet cần cho thu thập và tải phụ thuộc lần đầu.

Để thu thập, bấm **Mở Chrome thu thập**, đăng nhập bằng tài khoản của mình, vào
bài viết/nhóm có quyền truy cập rồi bắt đầu crawl. Có thể dùng `Login_Facebook.cmd`
để đăng nhập riêng. Giữ `chrome-profile/` để giữ phiên; không đưa thư mục này lên Git.
Nếu CAPTCHA quay về trang đăng nhập, hoàn tất đăng nhập trực tiếp trong Chrome,
không chạy nhiều phiên cùng dùng profile. Facebook có thể ẩn bình luận, câu trả lời
hoặc chỉ hiện nội dung thu gọn; số lượng thu được không chứng minh đã lấy đủ.

## Gán nhãn và chạy các bước tiếp theo

Hai thao tác trên giao diện được tách riêng:

- **Làm sạch dữ liệu** chỉ chuẩn hóa, kiểm tra chất lượng, lọc trùng và lưu bản
  `data/processed.json/csv`; không gọi mô hình hoặc thay đổi nhãn trong workspace.
- **Gán nhãn tự động** là tùy chọn, chỉ xử lý mẫu sạch chưa có nhãn. Không ghi đè
  nhãn đã lưu, kể cả quyết định của người đọc để nhãn trống chờ xem xét. Nút bị
  khóa khi không còn mẫu phù hợp. Mẫu sạch có nhãn máy dùng được ngay, không cần
  bước duyệt. Bản tải dataset ở phần chính gồm cả nhãn máy và nhãn sửa tay.
  Khi AI phân vân, nó vẫn chọn nhãn phù hợp nhất và đánh cờ **Cần kiểm tra**,
  kèm lý do. Chọn **Nhãn cần kiểm tra** trong ô lọc nhãn để xem riêng các câu này,
  giữ hoặc sửa nhãn rồi bấm **Xác nhận nhãn** để gỡ cờ. Cờ được lưu cùng nhãn
  và giữ khi mở lại project hoặc chia sẻ bằng JSON. Cờ này không phải xác suất
  đúng/sai; các nhãn cũ chưa có thông tin phân vân không tự được đánh cờ.

1. Thống nhất tiêu chí trong [QUY_TAC_GAN_NHAN.md](docs/QUY_TAC_GAN_NHAN.md).
2. Đọc bình luận gốc và ngữ cảnh bài viết/bình luận cha khi cần. Chọn nhãn rồi
   bấm **Lưu nhãn** hoặc **Lưu tất cả thay đổi** khi cần sửa. Câu không đủ ngữ
   cảnh hoặc không hợp lệ cần được loại/để chờ rà soát.
3. Tác vụ Qwen đọc tiêu chí và ngữ cảnh, cần Ollama cùng
   `qwen3:4b-instruct-2507-q4_K_M` tại máy. Không cần chạy lại tác vụ này khi nhận
   dữ liệu đã có nhãn. Việc sửa nhãn trên giao diện lưu vào `data/workspace.json`.
4. Sau khi gán nhãn, thực hiện **Trích xuất đặc trưng → Huấn luyện → Đánh giá/báo
   cáo**. Mẫu sạch có nhãn đã lưu trong nhóm phát triển được dùng trực tiếp,
   không phụ thuộc nguồn nhãn hoặc phê duyệt. Sửa nhãn làm đặc trưng cũ hết hiệu lực.
   Xuất bản dữ liệu như bên dưới khi chia sẻ cho nhóm.

Trước lần gán nhãn tự động đầu tiên, cài [Ollama cho Windows](https://ollama.com/download/windows),
mở Ollama và chạy lệnh sau trong terminal mới để tải mô hình (khoảng 2,5 GB):

```powershell
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

Giữ Ollama chạy khi gán nhãn. Mô hình chỉ cần tải một lần; các nhãn đã lưu vẫn
dùng được khi mở lại project. Nếu thay đổi code Python, khởi động lại máy chủ
bằng `Open_Tool.cmd` để nạp phiên bản mới.

Mốc kiểm tra 05/11/2026: **5.786 bình luận**, **622 bài**, **5.199 mẫu sạch có nhãn**,
587 bản trùng. Trong mẫu sạch có **4.162 non-toxic** và **1.037 toxic** (19,95%).
Nguồn nhãn: 5.198 tự động và 1 thủ công; nguồn nhãn và `human_verified` được giữ
để truy vết. Các con số này mô tả dữ liệu, không chứng minh độ chính xác nhãn.

Bản làm sạch hiện tại `ptit-v4-contextual-dc-20261105` chuẩn hóa `dc/đc` thành
`được` khi ngữ cảnh rõ, giữ dạng viết tắt mơ hồ; giữ phủ định, từ tục, emoji và
chuyển biểu cảm thành token. Chỉ bỏ hai stop words `các`, `những`. Bình luận gốc
và nguồn nhãn được bảo toàn.

`label_usable` cho biết mẫu sạch có nhãn dùng được. Không cần chạy lệnh phê duyệt.
`label_approved`, `label_approval_method` và `dataset_approval` cũ chỉ còn là lịch
sử, không chặn trích xuất/huấn luyện. Nhãn máy không bị đổi thành nhãn do người
gán; `human_verified` giữ đúng nguồn gốc. Nhãn không khớp nội dung hiện tại, mẫu
trùng/lỗi/đã loại hoặc chưa có nhãn vẫn không được dùng. Gợi ý chưa lưu nhãn cũng
không được coi là nhãn cuối.

### Sửa nhãn và kiểm tra chéo (tùy chọn)

- Đọc bản gốc trước, mở **Bản làm sạch & nguồn** và ngữ cảnh khi cần. Không lấy
  bình luận đứng gần làm bình luận cha nếu không có liên kết ID xác thực.
- **Dùng gợi ý** chỉ điền lựa chọn. Có thể sửa nhiều dòng, chuyển trang hoặc lọc
  rồi **Lưu tất cả thay đổi**; lưu trước khi tải lại hoặc đóng tab. Nếu nội dung
  đã đổi, cập nhật danh sách và đọc lại trước khi xác nhận. Lô lưu lỗi không được
  coi là đã lưu thành công; kiểm tra thông báo và các dòng còn chờ lưu.
- Kiểm tra riêng nhóm **Nhãn mâu thuẫn** và **Chưa mở hết nội dung**. Văn bản thiếu
  cần thu thập lại; sửa nhãn không bổ sung được phần văn bản bị thiếu. Câu chưa rõ
  để trống và ghi lý do, không mặc định thành non-toxic.
- Lấy mẫu kiểm tra chéo từ nhiều bài/chủ đề, gồm cả câu không bị máy gắn cờ. Không
  chỉ đọc các câu dễ hoặc gom toxic từ một bài và non-toxic từ bài khác.
- Khi kiểm định, người đọc không xem dự đoán/điểm máy. Hai người gán độc lập một
  phần dữ liệu, lưu nhãn riêng, thống nhất bất đồng rồi mới chốt nhãn cuối. Giao
  diện hiện lưu một nhãn cuối cùng, chưa quản lý hai lượt gán độc lập. Ghi số mẫu,
  người gán và cách giải quyết bất đồng; chỉ báo Cohen kappa sau khi thực sự đo.

## Kiểm tra dataset trước khi bàn giao hoặc huấn luyện

1. Đối chiếu số dòng nguồn, số bài, số mẫu sạch, trùng, bị loại, nhãn máy và nhãn
   đã được người xác nhận. Không lấy tổng dòng CSV làm số mẫu đủ điều kiện train.
2. Kiểm tra ID duy nhất và `text_hash` khớp nội dung gốc. Nội dung đổi phải được
   duyệt lại; không sửa ID/hash hoặc bỏ cột nguồn nhãn khi chỉnh CSV bằng Excel.
3. Rà các nhóm rỗng/giao diện, trùng, nhãn mâu thuẫn, chưa mở hết nội dung và đã
   loại. Giữ dữ liệu gốc để đối chiếu; nhãn trống không đồng nghĩa non-toxic.
4. Sau khi lưu, xuất rồi chạy `python -m backend.shared_dataset --check` như bên dưới. Lệnh kiểm
   tra checksum, nguồn dữ liệu/nhãn/ngữ cảnh, nhóm chia và bản xuất; không đánh giá
   tính đúng về ngữ nghĩa. Khi cần kiểm tra giao diện/API, đối chiếu ID, văn bản,
   nguồn nhãn và số dòng giữa bản tải xuống với workspace tương ứng.
5. Kiểm tra các bài nối bằng alias hoặc văn bản trùng không lọt sang các tập khác
   nhau. Không dùng nhóm đã dành riêng để chọn ví dụ, sửa prompt hoặc tối ưu ngưỡng.
6. Tách kiểm tra kỹ thuật khỏi chất lượng nhãn: chạy lại ra cùng kết quả chỉ chứng
   minh ổn định. Độ chính xác cần nhãn tham chiếu được người đọc kiểm tra độc lập;
   báo precision/recall/F1 toxic, macro-F1 và confusion matrix, không chỉ accuracy.
   Mẫu chẩn đoán chọn theo từ khóa không thay cho mẫu ngẫu nhiên của corpus.
7. Với dữ liệu crawl mới, đối chiếu một số bài trên Facebook đã đăng nhập để kiểm
   tra văn bản đầy đủ, bình luận cha và độ bao phủ. Kiểm thử DOM giả lập, số vòng
   cuộn hoặc việc crawler dừng không chứng minh đã thu thập hết bình luận.

## Chia sẻ dữ liệu đã gán nhãn qua Git

Dừng máy chủ trước khi xuất/commit hoặc pull để tránh ghi đè dữ liệu đang sửa.
Sau một đợt gán nhãn, chạy:

```powershell
.venv\Scripts\python.exe -m backend.shared_dataset --export
.venv\Scripts\python.exe -m backend.shared_dataset --check
git add data/progress.json data/workspace.json data/shared_dataset.json data/shared_dataset.csv data/shared_manifest.json data/post_context.json data/parent_context.json data/label_history
git commit -m "Cap nhat du lieu va nhan"
git push
```

Lần bàn giao code cần commit cả những file code đã sửa. Người nhận chỉ cần:

```powershell
git pull
.venv\Scripts\python.exe -m backend.shared_dataset --check
.venv\Scripts\python.exe app.py
```

Máy mới cần cài phụ thuộc trước. Nhãn đã xác nhận được giữ nguyên sau pull;
không phải crawl hay gán nhãn lại. Không dùng `--migrate-legacy` cho cập nhật thường
ngày. Nếu `--check` báo lệch, xử lý thay đổi rồi xuất và kiểm tra lại trước khi push.
Nếu nhiều người cùng sửa workspace, hợp nhất theo ID, `text_hash`, phiên bản tiêu
chí và lịch sử; không chọn toàn bộ một phía của xung đột rồi bỏ nhãn người khác.

## Cấu trúc và nguồn dữ liệu

| Vị trí | Vai trò |
| --- | --- |
| `app.py`, `backend/lab.py` | Máy chủ cục bộ, thu thập và điều phối tác vụ |
| `frontend/`, `assets/fonts/` | Giao diện HTML/CSS/JavaScript và font |
| `scripts/crawler/` | JavaScript do Selenium thực thi để đọc Facebook |
| `backend/` | Tiền xử lý, gán nhãn, đặc trưng, mô hình và tạo video |
| `data/progress.json` | Dữ liệu thu thập gốc |
| `data/workspace.json` | Nhãn, phê duyệt bộ nhãn, xác nhận riêng, ghi chú và dữ liệu nhập dùng chung |
| `data/post_context.json`, `data/parent_context.json` | Ngữ cảnh gán nhãn |
| `data/shared_dataset.json`, `.csv` | Bản xuất kèm nguồn nhãn, chất lượng, `human_verified` và trạng thái phê duyệt |
| `data/shared_manifest.json` | Checksum và ranh giới nhóm dữ liệu được giữ cố định |
| `data/label_history/` | Workspace trước khi chuyển sang tiêu chí hiện hành |
| `outputs/history.zip` | Lịch sử các đợt rà soát, quyết định của người gán và công cụ cũ |
| `tests/` | Bộ kiểm thử Python và các kịch bản kiểm tra trình duyệt |
| `docs/Report.md` | Phương pháp và trạng thái báo cáo bài làm |
| `docs/HUONG_DAN_MINH_HOA_PIPELINE.md` | Hướng dẫn video minh họa |
| `docs/QUY_TAC_GAN_NHAN.md` | Tiêu chí gán nhãn được dùng khi thu thập và kiểm tra dataset |
| `docs/reviews/`, `docs/superpowers/` | Các đợt rà soát, kế hoạch và thiết kế |
| `assets/images/debai.png` | Đề bài |

Giữ `app.py`, `Open_Tool.cmd` và `Login_Facebook.cmd` ở thư mục gốc để mở như trước.
Các lệnh tiện ích Python chạy từ gốc bằng `python -m backend.<tên_module>`, ví dụ
`python -m backend.post_context --help`. Tài liệu rà soát và kế hoạch cũ có thể ghi
đường dẫn trước khi gom thư mục; dùng cấu trúc và lệnh trong README này khi chạy.

Chỉ lấy dòng `quality=ready` khi cần dữ liệu sạch; CSV chia sẻ vẫn chứa cả trạng
thái loại/trùng để đối chiếu. Nhãn máy chưa xác nhận không phải đáp án chuẩn cho
train/validation/test. Các nhóm từng dành riêng để chẩn đoán tiếp tục được giữ
riêng, kể cả sau khi nối alias/trùng văn bản; chúng chưa phải bộ test mù độc lập.

Dữ liệu hiện hành và nhãn được Git theo dõi. `.venv/`, `models/`, profile Chrome,
cache, dữ liệu xử lý và các lần huấn luyện trong `data/runs/` được tạo tại từng máy
và bỏ qua trong Git. `outputs/history.zip` chỉ để tra cứu, không phải nơi gán nhãn
hằng ngày; bên trong có checksum từng file và giữ đường dẫn gốc để khôi phục khi cần.
Các ảnh xem trước, mô hình thử cũ, bản xuất CSV trùng JSON và `node_modules` cũ đã bỏ.

Các tài liệu rời trước đây như `Label_Guide.md`, `Check_Dataset.md`,
`KIEM_DINH_NHAN.md` và hướng dẫn từng đợt được giữ nguyên bản trong file nén này,
kèm checksum. Phần thao tác còn áp dụng đã gộp ở trên; các số liệu, đường dẫn và
quy trình ONNX/Gemma cũ chỉ là lịch sử, không thay thế README và quy tắc v4 hiện hành.

## Kiểm thử

Chạy từ thư mục dự án; dùng `-B` để không sinh cache bytecode:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s tests
.venv\Scripts\python.exe -B -m backend.shared_dataset --check
```

Kiểm tra ngày 05/11/2026 sau khi thêm cờ kiểm tra nhãn AI và xử lý lỗi Ollama: 94 kiểm thử Python, 93 đạt và 1 bỏ qua. Các kiểm thử
Qwen dùng mô phỏng phản hồi; kết quả này không đo độ chính xác nhãn trên corpus thật.
Kiểm thử dữ liệu/HTTP dùng dữ liệu tạm, không sửa bộ dữ liệu thật. Các file JavaScript
trong `tests/` là kịch bản nhận đối tượng `page` từ công cụ kiểm tra trình duyệt.

## Huấn luyện và tối ưu mô hình

Phạm vi đã chốt: tối ưu NB/SVM, chọn ngưỡng bằng validation, bổ sung ViSoBERT. Giữ nguyên nhãn, đầu vào bình luận và các nhóm chia; không thực hiện rà/gán lại nhãn hoặc bổ sung ngữ cảnh.

Trong trang **Huấn luyện**, đánh dấu các mô hình cần chạy lại: Naive Bayes, SVM hoặc ViSoBERT. ViSoBERT mặc định không được chọn để tránh chạy lại ngoài ý muốn. Khi dùng cả BoW và TF-IDF, danh sách gồm đúng 5 mô hình: **BoW-NB, BoW-SVM, TF-IDF-NB, TF-IDF-SVM, ViSoBERT**. Nếu chỉ chọn một phương pháp đặc trưng thì NB/SVM chỉ chạy cho phương pháp đó. Không sinh thêm mô hình theo unigram/bigram hoặc hậu tố tuned. Lần đầu cần mạng để tải trọng số ViSoBERT; CPU chạy lâu hơn GPU.

Chỉ các mô hình được chọn mới huấn luyện. Mô hình khác được giữ từ lượt hoàn tất gần nhất khi nhãn, đầu vào, bộ chia và cấu hình đặc trưng liên quan còn phù hợp; bảng kết quả ghi rõ **Giữ kết quả cũ**. Nếu đổi unigram/bigram hoặc giới hạn đặc trưng thì không ghép lại NB/SVM dùng cấu hình cũ. Không giữ mô hình của phương pháp BoW/TF-IDF đã bỏ chọn. Checkpoint được liên kết cứng trong thư mục run mới khi hệ thống hỗ trợ, tránh nhân đôi trọng số; nếu không thì sao chép.

Có thể chạy cùng quy trình từ dòng lệnh sau khi trích xuất đặc trưng trên web. Lệnh dùng lại bộ đặc trưng trong `data/features.joblib`; nếu dữ liệu đã đổi thì yêu cầu trích xuất lại:

```powershell
.venv\Scripts\python.exe -B -m backend.improvements --include-visobert
.venv\Scripts\python.exe -B -m backend.improvements --algorithms NB SVM
.venv\Scripts\python.exe -B -m backend.improvements --algorithms ViSoBERT
```

Bỏ `--include-visobert` nếu chỉ cần NB/SVM. Tham số `--visobert-epochs` đặt số epoch tối đa của ViSoBERT (mặc định 4). Dừng sớm và khôi phục checkpoint theo validation.

ViSoBERT tự dùng GPU khi `torch.cuda.is_available()` trả về true; nếu không thì dùng CPU. Giao diện hiển thị thiết bị khả dụng, kết quả lưu thiết bị đã huấn luyện. NB/SVM của scikit-learn vẫn chạy CPU. Máy có GPU NVIDIA cần driver và bản PyTorch hỗ trợ CUDA phù hợp, theo [hướng dẫn chính thức của PyTorch](https://pytorch.org/get-started/locally/); chỉ có card đồ họa nhưng cài bản PyTorch CPU thì vẫn chạy CPU. ViSoBERT trên GPU tinh chỉnh toàn bộ encoder, trên CPU tinh chỉnh hai tầng cuối nên hai chiến lược không bảo đảm cho kết quả giống nhau.

ViSoBERT dùng GPU cả khi huấn luyện và dự đoán. Với GPU tối đa 6 GB, hệ thống giới hạn batch thực tế ở 2, tăng tích lũy gradient tương ứng và bật gradient checkpointing để giảm bộ nhớ. Cấu hình thực tế được lưu trong `training.json`; nhật ký hiển thị tên thiết bị. Bộ nhớ còn phụ thuộc ứng dụng khác và độ dài câu, nên cơ chế này không bảo đảm mọi cấu hình đều vừa GPU.

Ví dụ cài PyTorch CUDA 12.8 trên Windows có driver NVIDIA tương thích (cần tải khoảng 2,9 GB):

```powershell
.venv\Scripts\python.exe -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Sau khi đổi PyTorch, dừng và mở lại hệ thống để tiến trình nạp thư viện mới.

- Unigram/bigram, phương pháp BoW/TF-IDF và giới hạn từ vựng chỉ chọn ở bước **Trích xuất đặc trưng**. NB/SVM dùng lại đúng ma trận và vectorizer đã lưu, không tự trích xuất hay đổi n-gram trong lúc huấn luyện.
- Huấn luyện tự chọn tham số bằng validation: thử alpha NB, C và trọng số lớp SVM trên cùng bộ đặc trưng, chỉ lưu một mô hình cuối cùng cho mỗi cặp đặc trưng/thuật toán.
- Chọn tham số bằng macro-F1 validation, rồi chọn ngưỡng trên validation; lưu chỉ số trước/sau ngưỡng và áp dụng lại ngưỡng khi dự đoán. Không chọn cấu hình/ngưỡng theo test.
- ViSoBERT lưu revision nguồn, tokenizer, cấu hình và checkpoint. CPU tinh chỉnh hai tầng encoder cuối cùng với bộ phân loại; GPU tinh chỉnh toàn bộ encoder với bộ phân loại. Đầu vào giữ dấu câu/emoji và dùng tokenizer riêng của ViSoBERT.

Mỗi lượt chạy dùng chung một thư mục `data/runs/<run>/`: `metrics.json`, dự đoán từng mô hình, `search.json` và checkpoint. `data/latest.json` trỏ đến lượt hoàn tất; giao diện tự nhận kết quả mới, kể cả khi chạy từ dòng lệnh. `docs/Report.md` được cập nhật từ số đo thực tế. Thời gian trong chế độ chọn tham số bao gồm tìm kiếm trong nhóm, nên không dùng để so trực tiếp tốc độ dự đoán hoặc tốc độ huấn luyện một cấu hình.

Nhãn/dữ liệu dùng chung vẫn được Git theo dõi như phần bàn giao ở trên. Trọng số, cache và kết quả chạy được bỏ qua trong Git; người nhận có sẵn nhãn để chạy bước đặc trưng/huấn luyện, không phải gán lại. Ngưỡng đã tối ưu chỉ dùng được kèm đúng checkpoint của lượt chạy tương ứng.

## Video báo cáo dùng chung

Video tạo sẵn nằm trong `assets/report_video/report.mp4`, kèm mục lục chương
trong `assets/report_video/manifest.json`. Hai file này cần được commit và push
cùng mã nguồn. Người pull về mở công cụ rồi vào **Báo cáo** là xem được,
không cần tải mô hình hoặc huấn luyện lại chỉ để xem video.

Khi dựng video mới thành công, hệ thống tự cập nhật hai file trên. Hãy commit
và push cả hai để chia sẻ phiên bản mới. Video có sẵn thể hiện lần huấn luyện
ghi trong thông tin video; không phải kết quả huấn luyện mới trên máy người xem.
