# Kiểm tra luồng dữ liệu PTIT — cập nhật 27/10/2026

## Khôi phục crawl và kiểm tra Facebook thực tế — 27/10/2026

Sau khi người dùng đăng nhập thành công, đã xác nhận ba vấn đề: máy chủ không phản hồi nhưng giao diện còn nhãn “Sẵn sàng”; cửa sổ Chrome đăng nhập thủ công còn giữ hồ sơ của project; bộ lọc nguồn loại bài vì URL nhóm dùng ID `450310163844833` trong khi permalink Facebook dùng tên `2k5ptit`.

Đã khôi phục máy chủ và chuyển hồ sơ đã đăng nhập sang Chrome thu thập. Giao diện hiện báo “Mất kết nối”, khóa thao tác crawl và tự phục hồi khi máy chủ hoạt động lại. Bộ lọc nhận diện ID/tên nhóm qua đối tượng `Group` trong dữ liệu JSON của trang Facebook; vẫn loại liên kết nhóm khác và không chấp nhận tên nhóm chưa được đối chiếu.

**Lượt crawl thực tế đã xử lý 1 bài và lưu 5 bình luận mới**, nâng tổng từ **2.126 lên 2.131**. Cả 5 có mã bình luận Facebook và nội dung đã mở hết tại thời điểm đọc. Bản tải `/download` khớp chính xác `data/progress.json`; toàn bộ mã và nội dung của 2.126 bình luận trước đó được giữ nguyên. Số nhãn đã lưu vẫn là 2.087, nhãn người đọc duyệt vẫn là 0; lượt này không tự gán nhãn cho bình luận mới.

**25 kiểm thử Python liên quan, 20 kiểm tra DOM crawler và 63 kiểm tra giao diện đạt**, gồm trường hợp ID/tên nhóm, loại nguồn khác, mất kết nối và kết nối lại. Chi tiết lượt thực tế: `test-results/crawl-recovery.json`.

Lượt crawl dừng khi không còn tiến triển sau 5 vòng. **Chưa xác nhận đã lấy hết bình luận của bài hoặc toàn bộ nhóm.** Các mục bên dưới ghi lại trạng thái ở những lượt kiểm tra trước.

## Bổ sung đăng nhập thủ công — 27/10/2026

Người dùng báo CAPTCHA xong quay về đăng nhập trong Chrome thu thập, trong khi tài khoản vẫn truy cập được bằng trình duyệt/ứng dụng thường dùng. Đã kiểm tra tool đang chờ, không tự điều hướng hoặc xóa cookie. Cookie Facebook thông thường tồn tại nhưng chưa có phiên đăng nhập thành công; chưa đủ bằng chứng kết luận nguyên nhân vòng lặp.

Thêm `DANG_NHAP_FACEBOOK.cmd` và `dang_nhap.py` để người dùng tự đăng nhập, hoàn tất xác minh trong đúng hồ sơ `chrome-profile`, sau đó đóng Chrome và mở lại bằng nút **Mở Chrome thu thập**. Lệnh mở Chrome thông thường và từ chối chạy khi phiên điều khiển của tool còn hoạt động. Crawler, nhãn và logic xử lý dữ liệu giữ nguyên.

**20 kiểm thử liên quan đạt** (4 kiểm thử launcher mới và 16 kiểm thử vòng đời trình duyệt). Kiểm tra trực tiếp lệnh từ chối khi Chrome điều khiển còn mở; sau khi cửa sổ đó đóng, lệnh mở Chrome thủ công đã chạy thành công trong phiên Windows bình thường. **Chưa xác nhận người dùng đăng nhập thành công hoặc phiên được Facebook chấp nhận sau khi mở lại crawler.**

Trong thời gian thao tác, nguồn/nhật ký crawl đã được cập nhật sang nhóm khác. Đối chiếu lại vẫn đủ 2.126 mã bình luận và nội dung khớp với bản kiểm tra trước, không thêm/bớt; workspace nhãn và hai file dataset tự động giữ nguyên hash. Các số liệu/hash ở lượt kiểm tra bên dưới ghi nhận thời điểm chạy kiểm tra đó.

## Lượt kiểm tra cuối — 27/10/2026

**Làm sạch, gán nhãn toàn bộ và xuất dataset chạy ổn định trên corpus hiện có. Chưa thể xác nhận crawl Facebook thực tế hoặc độ chính xác ngữ nghĩa của nhãn.** Lần này không phát hiện thêm lỗi xử lý dữ liệu trong phạm vi kiểm tra; không sửa logic ứng dụng hay ghi đè dữ liệu thật.

- **74/74 kiểm thử Python đạt, không bỏ qua**, gồm suy luận ONNX thực không dùng mạng, lưu lỗi, lọc trùng, nhãn gắn hash, xử lý đồng thời, vòng đời Chrome và các API.
- **119 kiểm tra trình duyệt đạt:** 18 DOM crawler, 14 cuộn/bố cục, 18 duyệt nhãn, 11 xử lý toàn bộ và 58 giao diện. Các thao tác ghi trong các ca giao diện được giả lập, chạy trên tab kiểm thử riêng.
- **Chạy lại từ đầu toàn bộ 2.126 bình luận trên workspace riêng**, bỏ nhãn/gợi ý đã lưu và dùng mô hình ONNX thật: hoàn tất trong **231,84 giây**, tạo đủ **2.087 nhãn**, không có nhãn khác lần trước, độ lệch điểm lớn nhất **0**. Lưu/nạp lại workspace cho kết quả giống hệt. Cả sáu tệp dữ liệu gốc/nhãn/kết quả vẫn giữ nguyên SHA-256.
- Đối chiếu mọi dòng với hash văn bản, kết quả làm sạch, phiên bản mô hình, điểm và ngưỡng nhãn; không có ID hay văn bản chuẩn hóa trùng trong dataset. `processed.csv/json` và `dataset_auto.csv/json` khớp chính xác workspace. API tải dữ liệu thật cũng khớp; ba lần đọc trạng thái liên tiếp nhất quán.
- Giao diện dùng API thật trả đúng 134 toxic, 1.953 non-toxic, 28 bản trùng, 11 mẫu rỗng/giao diện và 0 mẫu sạch chưa gán nhãn; không có lỗi JavaScript trong lượt này. Dataset đã duyệt vẫn từ chối xuất khi chưa có nhãn người đọc.
- **Chrome đã mở Facebook thành công**, `/status` báo `ready=true`. Trên trang đăng nhập thật, mã crawler trả `blocked=true`, không đọc/cuộn khi chưa đăng nhập. Người dùng xác nhận chưa thể đăng nhập lúc này, nên chưa chạy crawl một bài thực tế và chưa đối chiếu độ bao phủ với Facebook.

**Giới hạn chất lượng:** 2.087 nhãn đều là nhãn máy, 136 mẫu cần kiểm tra, 0 mẫu đã được người đọc xác nhận. Kết quả lặp lại giống nhau chỉ chứng minh tính ổn định, không phải accuracy. Cả 2.126 dòng legacy chưa có xác nhận đã lấy hết văn bản. Nhật ký có 7 bài đã ghi nhận trong phiên, còn corpus có 86 mã bài; hai con số không biểu thị cùng một phạm vi.

Bằng chứng cục bộ: `test-results/final-python-tests.log`, `final-browser-audit.json`, `final-data-audit.json`, `final-bulk-replay.json` và `final-crawler-live.json`. Hai script trong `test-results/final_data_audit.py` và `final_bulk_replay.py` chỉ phục vụ lượt đối chiếu này; bản chạy lại nằm riêng trong `test-results/final-replay/`.

## Kết quả hiện tại: làm sạch và gán nhãn toàn bộ

Đã chạy nút xử lý toàn bộ trên corpus thật, theo yêu cầu mới: không bắt buộc duyệt từng dòng. Đã kiểm tra cả API tải CSV/JSON, nội dung tệp trên đĩa và nhãn còn nguyên sau khi khởi động lại.

| Hạng mục | Số lượng |
|---|---:|
| Bình luận gốc / bài viết | 2.126 / 86 |
| Mẫu sạch đã gán nhãn tự động | 2.087 |
| Non-toxic / toxic | 1.953 / 134 |
| Mẫu sạch còn chưa có nhãn | 0 |
| Bản trùng / rỗng hoặc giao diện | 28 / 11 |
| Nhãn máy có cờ cần kiểm tra | 136 |
| Nhãn người đọc xác nhận | 0 |

Kết quả: `data/dataset_auto.csv` và `data/dataset_auto.json`. `data/processed.csv/json` giữ đủ 2.126 dòng với trạng thái chất lượng. Dataset có đủ điều kiện kỹ thuật để chia tập và huấn luyện; không cần lưu từng nhãn. Ngưỡng gán tự động là 0,5, nhãn máy ghi nguồn `automatic` cùng model/revision/điểm/hash. Nhãn người đọc được bảo vệ khi xử lý lại.

`data/progress.json` giữ nguyên SHA-256 `7b3ef8daf4391307282817e97be97d04f362852e5a9c2db5756b178b24f7feaa`. Chưa có phép đo độc lập về độ chính xác nhãn PTIT; 136 mẫu có điểm trong vùng chưa rõ vẫn có nhãn máy và được dùng trong dataset. Nhãn máy không được gọi là nhãn chuẩn người đọc.

Ở lượt kiểm tra trước khi cải thiện giao diện: 73 kiểm thử Python riêng biệt và 61 kiểm tra trình duyệt đã đạt. Kết quả kiểm tra cuối hiện tại là **74/74 Python và 119 kiểm tra trình duyệt**, được ghi ở đầu tài liệu.

Đã phát hiện và dừng phiên ứng dụng cũ chạy trùng cổng 8767; thêm chặn khởi động trùng để bảo vệ workspace. Khởi động bản thứ hai hiện báo cổng đang dùng và thoát.

Cách dùng: mở `http://127.0.0.1:8767/#data`, Ctrl+F5, bấm **Tải CSV / Tải JSON** trong mục **Tải dataset đã gán nhãn** để tải kết quả đã có. Khi thu thập thêm, bấm **Làm sạch & gán nhãn toàn bộ**; tác vụ không bị giới hạn bởi trang hay bộ lọc.

Các mục phía dưới ghi lại lần kiểm tra trước, khi ứng dụng chỉ hỗ trợ gợi ý và duyệt thủ công. Quy trình hiện tại được mô tả ở trên và trong `HUONG_DAN_GAN_NHAN.md`.

## Bổ sung sửa lỗi mở Chrome — 27/10/2026

Đã tái hiện Chrome 155.0.8059.85 bị crash với trang HTML trống khi máy chủ chạy trong môi trường hạn chế quyền. Cùng Chrome/ChromeDriver chạy trong phiên Windows bình thường mở trang, tạo tab mới và quay lại tab cũ thành công. Đã khởi động lại ứng dụng trong phiên phù hợp: `/api/browser` trả 200, sau đó `/status` báo `phase=ready`, `ready=true` khi mở Facebook.

Sửa kiểm tra phiên khi Chrome đang chờ; chuyển sang tab còn lại nếu tab hiện tại đóng; mở lại được sau khi toàn bộ phiên chết. Thêm bảo vệ hai phiên khởi động đồng thời, bỏ lệnh cũ trước khi mở lại và khôi phục trạng thái kể cả khi khởi động luồng, ghi nhật ký hoặc đóng driver gặp lỗi. **30 kiểm thử liên quan đạt**, trong đó 16 kiểm thử điều hướng/vòng đời trình duyệt. Dữ liệu crawl gốc không thay đổi. Chưa thực hiện thêm một lượt crawl Facebook đã đăng nhập trong lần sửa lỗi này.

## Kết quả kiểm tra dataset trước đó

Luồng làm sạch → gợi ý cục bộ → người duyệt → xuất dataset đã chạy qua kiểm tra chức năng. **Chưa thể kết luận chất lượng nhãn hoặc độ đầy đủ của crawler là hoàn hảo.** Chưa có nhãn chuẩn PTIT và chưa kiểm chứng lại việc thu thập trên Facebook đang đăng nhập.

## Kết quả trên dữ liệu hiện có

| Hạng mục | Số lượng |
|---|---:|
| Bình luận gốc | 2.126 |
| Bài viết trong dữ liệu | 86 |
| Mẫu qua bộ lọc làm sạch | 2.087 |
| Bản trùng | 28 |
| Rỗng / chữ giao diện | 11 |
| Gợi ý non-toxic | 1.870 |
| Gợi ý toxic | 81 |
| Không đề xuất nhãn vì điểm nằm giữa hai ngưỡng | 136 |
| Nhãn đã được người đọc xác nhận | 0 |

Mô hình đã xử lý đủ 2.087 mẫu trên CPU của máy này. Các con số gợi ý không phải phân bố nhãn chuẩn, precision, recall hay accuracy. Gợi ý được lưu riêng vào `data/workspace.json` và đã kiểm tra còn nguyên sau khi khởi động lại máy chủ. Đã xuất `data/processed.json` và `data/processed.csv`; đây là bản làm sạch gồm mọi trạng thái chất lượng, chưa phải tập huấn luyện có nhãn.

`data/progress.json` không thay đổi so với bản gốc trong Git. Dữ liệu cũ thiếu thông tin đã mở hết văn bản: cả 2.126 dòng mang trạng thái **chưa xác nhận độ đầy đủ**, không được diễn giải thành đã thu thập đầy đủ.

## Những lỗi đã sửa

- Khi mở rộng bình luận, giữ định danh dự phòng trong cùng DOM; văn bản đầy đủ có thể thay bản cắt ngắn, kể cả khi ngắn hơn. Bản bị thu gọn không ghi đè nội dung đầy đủ đã lưu.
- Ghi lỗi riêng cho bài crawl thất bại. Lỗi mở tab không đóng nhầm tab nguồn; lỗi ghi tệp vẫn giữ các bình luận đã đọc trong bộ nhớ để tải xuống.
- Loại mẫu biết là chưa mở hết nội dung khỏi tập dùng cho mô hình. Giữ trạng thái loại mẫu và ghi chú khi nhập lại dữ liệu.
- Nhãn gắn với SHA-256 của nội dung gốc. Nội dung đổi thì nhãn cần duyệt lại; API từ chối lưu đánh giá thiếu hash hoặc dùng hash cũ. Nhãn legacy trong dữ liệu crawl cũng bị vô hiệu khi nội dung thay đổi.
- Ghi nhãn, dữ liệu nhập và gợi ý trong một lần thay tệp nguyên tử, tránh cập nhật nửa chừng khi ghi thất bại.
- Gợi ý hoàn tất sau khi người đọc đã sửa nhãn, loại mẫu hoặc nội dung đổi sẽ không ghi đè trạng thái mới.
- Nhập lại CSV có ký tự đầu dòng dễ bị Excel coi là công thức vẫn giữ nguyên văn bản nhờ đối chiếu hash.
- Cuộn nhật ký có giới hạn chiều cao, tiêu đề cố định; polling giữ vị trí cuộn. Các trang và bảng được kiểm tra ở chiều rộng 1.440 và 390 px.

## Kiểm tra đã chạy

- **49 kiểm thử Python đạt, không bỏ qua**, gồm mô hình ONNX thực chạy khi mạng bị chặn trong kiểm thử; lỗi ghi tệp; nhập/xuất; đồng thời sửa nhãn và suy luận; hash nội dung; chia tập theo bài; lưu/nạp và dự đoán của 5 cấu hình huấn luyện trên dữ liệu giả lập.
- **50 kiểm tra trình duyệt đạt**: 18 kiểm tra DOM crawler, 14 kiểm tra cuộn/bố cục, 18 kiểm tra giao diện gợi ý và xác nhận. Các thao tác ghi trong kiểm tra giao diện đều được giả lập, không gán nhãn dữ liệu thật. Không có lỗi JavaScript trong lượt kiểm tra này.
- Kiểm tra API thật sau khi khởi động lại: đủ 2.087 kết quả gợi ý, 0 nhãn xác nhận; `/api/dataset.csv` và `/api/dataset.json` trả lỗi 400 đúng dự kiến khi chưa có nhãn xác nhận. Không xuất nhầm gợi ý thành nhãn chuẩn.
- Kiểm tra giao diện với dữ liệu thật: hiển thị gợi ý, số liệu đúng; nút huấn luyện và xuất dataset đã duyệt bị khóa khi chưa đủ điều kiện.

Chạy lại kiểm thử Python trong PowerShell:

```powershell
$env:LABELING_SMOKE='1'
.venv\Scripts\python.exe -m unittest discover -v
```

Kiểm tra trình duyệt nằm trong `test_crawler_browser.js` và `test_labeling_browser.js`, chạy bằng các hàm `checkCrawlerBrowser`, `checkDashboardScroll`, `checkLabelingBrowser` trên trang Playwright riêng. Chỉ thay đổi viewport của trang kiểm thử.

## Quy trình duyệt thủ công trước đây và giới hạn

Mở `http://127.0.0.1:8767/#data`, tải lại trang nếu đang dùng phiên giao diện cũ. Đọc bình luận, bấm **Dùng gợi ý** nếu đồng ý, sửa nhãn/ghi chú khi cần rồi bấm **Lưu đánh giá**. Gợi ý chỉ điền lựa chọn; thao tác lưu mới xác nhận. Nút **Dataset đã duyệt** xuất các mẫu sạch có nhãn. Có thể gán nhãn thủ công cho 136 mẫu không có đề xuất.

Mô hình `dangvansam/vietnamese-toxicity` chốt revision `bac60f3e162d3a06003bf561a9f8365982ccc67a`; ngưỡng 0,2/0,8 chưa được hiệu chỉnh trên PTIT. Văn bản vượt 512 token không được đề xuất nhãn. Mô hình chạy cục bộ, không gửi bình luận lên mạng. Xem [hướng dẫn gán nhãn](HUONG_DAN_GAN_NHAN.md) về đánh giá độc lập và tránh thiên lệch do nhìn gợi ý trước.

Chưa đo độ chính xác nhãn, độ đồng thuận giữa người gán hoặc độ bao phủ bình luận trên Facebook. Nhật ký trình duyệt trước đó có lỗi mất phiên Chrome/DevTools; cần xác minh một phiên crawl thực sau khi đăng nhập, đối chiếu một số bài với Facebook. Các kiểm tra DOM giả lập không thay thế bước này. Chế độ toàn bộ hiện cho phép huấn luyện trên nhãn máy; chỉ số đó phải được mô tả là mức khớp với nhãn máy, không phải độ chính xác trên nhãn chuẩn PTIT.
