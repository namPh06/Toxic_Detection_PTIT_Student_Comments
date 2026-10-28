# Hướng dẫn gán nhãn bình luận PTIT

Có thể làm sạch và gán nhãn **toàn bộ tập dữ liệu trong một lần**, không cần duyệt từng bình luận. Chỉ có hai nhãn: `toxic` và `non-toxic`.

## Xử lý toàn bộ (cách dùng chính)

1. Mở `http://127.0.0.1:8767/#data`, tải lại trang bằng Ctrl+F5 nếu đang dùng giao diện cũ.
2. Bấm **Làm sạch & gán nhãn toàn bộ**. Tác vụ lấy toàn bộ mẫu hợp lệ chưa có nhãn, dù đang ở trang nào hoặc đang lọc gì. Giữ cửa sổ chạy ứng dụng mở.
3. Đợi thông báo hoàn tất rồi tải **Tải CSV / Tải JSON** trong mục **Tải dataset đã gán nhãn**. Kết quả cũng tự lưu trong `data/dataset_auto.csv` và `data/dataset_auto.json`; bản làm sạch gồm mọi trạng thái ở `data/processed.csv/json`.
4. Có thể chuyển sang **Huấn luyện & đánh giá** khi đủ mẫu và nhóm bài; không cần bấm Lưu đánh giá từng dòng. Chỉnh từng nhãn là tùy chọn, nhãn thủ công được giữ nguyên khi chạy lại.

Mô hình chạy cục bộ, dùng điểm toxic ≥ 0,5 để gán `toxic`, thấp hơn gán `non-toxic`. Mẫu có điểm giữa 0,2–0,8 hoặc đầu vào dài hơn 512 token vẫn được gán nhãn nhưng có `needs_review=true`. Mẫu rỗng, chữ giao diện, trùng, nhãn mâu thuẫn, đã loại hoặc biết là chưa mở hết văn bản không vào dataset sạch. Không xóa dữ liệu gốc.

Nhãn tự động có `label_source=automatic`, model/revision, điểm và ngưỡng trong tệp xuất. Khi nhập lại, giữ các cột này để không biến nhãn máy thành nhãn người đọc. Điểm mô hình không phải độ chính xác; validation/test dùng nhãn máy chỉ đo mức khớp với nhãn máy. Muốn đo chất lượng thực trên PTIT cần bộ đánh giá độc lập do người đọc gán.

## Duyệt thủ công (tùy chọn)

Đơn vị duyệt là một bình luận: đọc nguyên văn trước khi xem bản đã làm sạch. Trường hợp chưa rõ có thể bỏ nhãn và ghi chú để rà soát. Quy tắc và các bước dưới đây dành cho lúc bạn muốn kiểm tra hoặc sửa kết quả tự động.

## Quy tắc

| Nhãn | Tiêu chí | Ví dụ minh họa tự soạn |
|---|---|---|
| non-toxic | Hỏi đáp, thông tin, lời cảm ơn, trao đổi thông thường | “Cho mình hỏi hạn đăng ký học phần là ngày nào?” |
| non-toxic | Phê bình vấn đề/sản phẩm/cách tổ chức mà không xúc phạm người khác | “Lịch học này bất tiện, mình mong trường điều chỉnh.” |
| toxic | Lăng mạ, hạ nhục cá nhân hoặc nhóm người | “Mày ngu quá, câm mồm đi.” |
| toxic | Đe dọa, kích động hành vi gây hại | “Tao sẽ tìm mày để đánh.” |
| Chưa gán | Thiếu ngữ cảnh; có thể là trích dẫn, đùa thân mật hoặc mỉa mai | Ghi rõ lý do trong ô ghi chú, trao đổi để thống nhất |
| Loại mẫu | Văn bản lỗi, chỉ là giao diện, ngoài phạm vi nghiên cứu | Chọn “Loại mẫu khỏi huấn luyện”; không xóa bản gốc |

Từ tục không tự quyết định nhãn. Nội dung phản đối hành vi toxic có thể chứa trích dẫn từ tục nhưng không có ý công kích. Việc không chứa từ tục cũng không đảm bảo non-toxic: đe dọa hoặc miệt thị vẫn có thể được diễn đạt lịch sự. Không đồng nhất phân loại cảm xúc với phân loại toxic.

## Cách thực hiện trên giao diện

1. Mở **Làm sạch & gán nhãn**, bộ lọc mặc định là “Tất cả nhãn” và “Mẫu sạch duy nhất”.
2. Đọc văn bản gốc. Mở **Bản làm sạch & nguồn** để đối chiếu bản chuẩn hóa và mã bài; mở **Thông tin nhãn** để xem điểm và mô hình.
3. Nếu chỉ muốn tạo gợi ý, mở **Gợi ý và duyệt thủ công (tùy chọn)**, bấm **Tạo gợi ý tự động**, chờ hoàn tất rồi bấm **Cập nhật danh sách**. Mô hình chạy trên máy; lần đầu tải khoảng 100 MB, không gửi bình luận lên mạng. Trong chế độ này, **Dùng gợi ý** chỉ điền ô chọn nhãn, chưa lưu và chưa đưa mẫu vào dataset huấn luyện.
4. Đọc và quyết định nhãn, sửa gợi ý sai, ghi chú các trường hợp khó. Có thể chỉnh nhiều dòng, chuyển trang hoặc lọc rồi bấm **Lưu tất cả thay đổi** ở cuối danh sách; số bên cạnh nút là tổng dòng đang chờ lưu, kể cả ngoài trang hiện tại. **Lưu đánh giá** vẫn dùng được nếu chỉ muốn lưu riêng một dòng. Nhãn tự động đã được lưu sẵn, chỉ cần lưu lại phần bạn chỉnh sửa. Nhãn xác nhận và dấu vân tay văn bản được ghi vào `data/workspace.json`; gợi ý được lưu riêng. Nếu văn bản đã đổi từ lúc mở dòng, cập nhật danh sách, đọc lại và chỉnh dòng đó trước khi lưu. Lưu trước khi tải lại hoặc đóng tab; các chỉnh sửa chưa lưu chỉ được giữ trong phiên giao diện. Nếu lô lưu có lỗi, toàn bộ lô chưa được ghi và bản chỉnh sửa vẫn được giữ để thử lại.
5. Chuyển bộ lọc sang “Tất cả nhãn” để sửa nhãn đã lưu; chọn “Chưa gán nhãn” và lưu để bỏ nhãn. Khi có cảnh báo nội dung thay đổi, nhãn cũ chỉ để đối chiếu và không được dùng huấn luyện đến khi bạn đọc lại, xác nhận lại.
6. Kiểm tra nhóm chất lượng “Nhãn mâu thuẫn” và “Chưa mở hết nội dung”. Các văn bản giống nhau sau chuẩn hóa nhưng mang hai nhãn khác nhau đều bị loại khỏi tập huấn luyện đến khi được sửa. Mẫu biết là bị thu gọn cần crawl lại để lấy đủ nội dung; nhãn không khắc phục được thiếu văn bản. Mẫu cũ chưa có thông tin đầy đủ cũng cần kiểm tra nguồn khi có nghi ngờ.
7. Gán nhãn ở nhiều bài khác nhau. Không gán toàn bộ toxic từ một bài và non-toxic từ một bài khác: mô hình có thể học chủ đề hoặc ngôn ngữ của bài thay vì độc tính.
8. Dùng **Tải CSV đã duyệt / Tải JSON đã duyệt** để xuất mẫu sạch có nhãn xác nhận (`/api/dataset.csv`, `/api/dataset.json`). **Xuất bản làm sạch → Tải CSV/JSON toàn bộ** dành cho kiểm tra chất lượng và lưu bản đối chiếu, có cả dòng chưa có nhãn hoặc không đủ điều kiện huấn luyện.

Gợi ý dùng `dangvansam/vietnamese-toxicity`, revision `bac60f3e162d3a06003bf561a9f8365982ccc67a`. Điểm toxic ≤ 0,2 gợi ý `non-toxic`, ≥ 0,8 gợi ý `toxic`; ở giữa không đề xuất nhãn. Điểm này chưa được hiệu chỉnh trên PTIT, **không phải độ chính xác hay độ chắc chắn rằng bình luận được gán đúng**. Đầu vào dài hơn 512 token (kể cả token đặc biệt) phải bị cắt nên hệ thống không đề xuất nhãn; đọc toàn bộ để quyết định. Không coi nhãn trống là non-toxic.

Tại thời điểm kiểm tra, corpus chưa có nhãn chuẩn xác nhận và chưa có độ chính xác PTIT được đo. Mô hình hỗ trợ có thể sai với ngữ cảnh sinh viên; việc chạy thành công không thay cho kiểm định nhãn. Mô hình nền [ViSoBERT](https://huggingface.co/uitnlp/visobert) được công bố cho nghiên cứu; sử dụng trong phạm vi nghiên cứu BTL.

Tối thiểu kỹ thuật là 10 mẫu mỗi lớp và 5 nhóm bài độc lập, với hai lớp hiện diện ở cả train/validation/test. Nên gán nhiều hơn đáng kể và phủ đa dạng chủ đề, thời điểm, độ dài. Giữ phân bố tự nhiên khi báo cáo; không chọn riêng bình luận “dễ” để tạo điểm cao.

## Kiểm soát chất lượng nhãn cho báo cáo

- Chốt định nghĩa nhãn trước khi gán toàn bộ.
- Chọn các bài dành cho đánh giá độc lập trước khi dùng gợi ý; người gán validation/test không xem dự đoán mô hình. Có thể làm trên bản xuất riêng chỉ giữ mã và văn bản, bỏ cột gợi ý/điểm. Giao diện hiện không tự che gợi ý hay khóa một tập test riêng. Không dùng chính nhãn mô hình đề xuất làm nhãn chuẩn để đánh giá mô hình đó.
- Hai thành viên có thể gán độc lập trên bản xuất riêng một phần dữ liệu, đối chiếu bất đồng và tính Cohen kappa bằng công cụ thống kê. Giao diện hiện lưu **một nhãn cuối cùng**, chưa phải hệ thống nhiều người gán đồng thời.
- Ghi lại số người gán, số mẫu kiểm tra chéo, tiêu chí xử lý bất đồng và các trường hợp khó. Không tự điền chỉ số đồng thuận khi chưa đo.
- Khóa bộ test sau khi thống nhất nhãn; tránh xem kết quả test rồi liên tục sửa mô hình để tăng điểm.
- Ghi rõ trong báo cáo phần dữ liệu có nhãn tự động, model/revision, ngưỡng 0,5 của chế độ toàn bộ hoặc 0,2/0,8 của chế độ gợi ý; ghi quy trình người đọc duyệt nếu có. Không gọi nhãn máy là nhãn người đọc xác nhận.
- Không suy ra mọi tài khoản trong nhóm đều là sinh viên PTIT. Không đưa tên/định danh cá nhân vào báo cáo minh họa nếu chưa ẩn danh.
