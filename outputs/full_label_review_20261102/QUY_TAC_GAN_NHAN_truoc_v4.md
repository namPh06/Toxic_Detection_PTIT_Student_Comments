# Quy tắc gán nhãn PTIT — v3 (bao gồm chê trường)

Ngày chốt: 30/10/2026. Phiên bản: ptit-v3.1-school-feedback-20261030. Trạng thái: đã được người phụ trách chốt các tiêu chí dưới đây trong cuộc trao đổi.
Phạm vi: bộ dữ liệu của đề tài này; không tự nhận là định nghĩa toxic phổ quát.

## Đơn vị gán

Đọc nguyên văn một bình luận. Đọc bài viết/bình luận cha khi cần; nếu thiếu ngữ cảnh thì để Chưa rõ. Không suy luận nhãn từ danh tính người viết.

## Quy tắc

- toxic: xét hành vi công kích, hạ nhục, quấy rối, kỳ thị, đe dọa/cổ vũ gây hại trong nghĩa và ngữ cảnh câu. Có từ tục không đủ để kết luận; không có từ tục vẫn có thể toxic.
- Quy tắc riêng của đề tài, được người phụ trách cập nhật: bình luận do chính người viết chê trường được gán toxic, với ngoại lệ góp ý có lý do cụ thể được người phụ trách làm rõ dưới đây; bao gồm chê học phí, cơ sở vật chất, giảng dạy và dịch vụ của trường; không yêu cầu có lời tục hay công kích cá nhân.
- non-toxic: hỏi đáp, thông tin, cảm ơn hoặc trao đổi không thuộc các điều kiện toxic, bao gồm quy tắc chê trường ở trên. Chỉ nhắc tới trường hoặc thuật lại/phản đối lời chê của người khác không đủ để kết luận chính người viết đang chê trường.
- Ngoại lệ đã chốt: trích lời xúc phạm để phản đối hành vi xúc phạm là non-toxic khi bản thân bình luận không có nội dung toxic khác. Phân biệt trích để phản đối và dùng trích dẫn để tiếp tục công kích.
- Chưa rõ: trạng thái chờ xử lý; để trống nhãn, ghi lý do. Không phải lớp thứ ba khi huấn luyện, không tự chuyển thành non-toxic. Trích dẫn không rõ mục đích, mỉa mai hoặc đùa thiếu ngữ cảnh được đưa vào trạng thái này.

## Ví dụ minh họa tự soạn

| Bình luận | Nhãn | Lý do |
|---|---|---|
| Cho mình hỏi hạn đăng ký học phần? | non-toxic | Hỏi thông tin |
| Lịch học này bất tiện quá. | non-toxic | Phàn nàn không có lời tục/xúc phạm |
| Học phí đắt quá, mình không đủ tiền đóng. | toxic khi chê học phí của trường | Cập nhật theo quy tắc chê trường của v3; thay ví dụ v2 |
| Học phí đắt vcl. | toxic | Người phụ trách xác nhận nhãn non-toxic trước đây là nhầm |
| Mày ngu thế. | toxic | Hạ nhục trực tiếp |
| Tao sẽ tìm mày để đánh. | toxic | Đe dọa gây hại |
| Đừng gọi bạn ấy là “đồ ngu”. | non-toxic | Người phụ trách chọn 1: phản đối lời xúc phạm |
| Đồ ngốc :)) | Chưa rõ nếu thiếu ngữ cảnh | Emoji không tự chứng minh là đùa thân mật |

## Lưu và kiểm tra nhãn

1. Ẩn dự đoán/điểm mô hình khi người đọc chọn nhãn.
2. Chỉ đặt human_verified=true sau khi người thực sự đọc và xác nhận; nhãn AI lưu riêng.
3. Ghi chú câu khó; kiểm tra chéo bất đồng khi có thể.
4. Đổi quy tắc phải ghi phiên bản và rà lại mẫu liên quan.
5. Ví dụ minh họa và 20 mẫu thực hành không phải tập test độc lập. Chưa dùng chúng để tuyên bố độ chính xác.

Quy tắc này thay thế phần định nghĩa cũ về từ tục trong HUONG_DAN_GAN_NHAN.md. Các kết quả đối chiếu AI trước ngày chốt dùng tiêu chí trước đó, cần rà lại theo v1; không coi là nhãn chuẩn theo v1.

## Thay đổi từ v1

Người phụ trách chọn 2: đánh giá nghĩa/ngữ cảnh, không dùng sự xuất hiện từ tục làm điều kiện đủ. Thay thế lựa chọn B trước đó. Câu bổ sung 1 có vcl được xác nhận non-toxic. Các nhãn thực hành v1 giữ lịch sử phiên bản; cần rà lại nếu bị ảnh hưởng, không tự gán lại toàn bộ. Các phần hướng dẫn cũ trái với v2 được thay thế bởi v2.

## Làm rõ B218 và B219 theo giải thích của người phụ trách

- B218 — toxic: “mày thích giở giọng ông cụ à” được người phụ trách hiểu là mỉa mai, chế giễu người đối thoại.
- B219 — non-toxic: “m đừng có dở giọng ông cụ với t” được người phụ trách hiểu là yêu cầu người đối thoại dừng cách nói chuyện với mình, không phải chủ động chế giễu họ.
- Khi xét câu tương tự, phân biệt hành vi mỉa mai/hạ nhục người khác với việc phản đối cách họ đối xử hoặc nói chuyện. Xét toàn câu và ngữ cảnh; không dùng từ “đừng” làm điều kiện tự động cho non-toxic. Một câu yêu cầu dừng vẫn có thể toxic nếu kèm công kích, đe dọa hoặc nội dung toxic khác.
- Đây là giải thích cho hai nhãn đã chốt, không phải thay nhãn hay khẳng định có thể suy ra ý định mọi câu chỉ từ cấu trúc câu.

## Thay đổi v3

Người phụ trách xác nhận: “cứ chê trường thì cho là toxic”, và sửa ví dụ “học phí đắt vcl” thành toxic. Đây là phạm vi nhãn riêng của đề tài, rộng hơn tiêu chí công kích người ở v2. Các nhãn đã duyệt và báo cáo mô hình theo v2 phải rà lại trước khi dùng để đánh giá theo v3; không diễn giải các kết quả cũ là kết quả v3. Các ví dụ trong phần lịch sử trái v3 đã bị thay thế.

## Làm rõ v3.1 — góp ý có lý do cụ thể

Người phụ trách xác nhận B102 là non-toxic: “Quả gửi xe 3 tầng này dốc vl, lại còn khó đi nữa. Trường xây tiết kiệm diện tích hay sao ý. May quá ra trường rồi =))”. Lý do: đây là góp ý, nêu cụ thể dốc và khó đi, từ đó nhận xét trường tiết kiệm diện tích. Trường hợp này là ngoại lệ của phát biểu rộng “cứ chê trường thì toxic”.

Khi rà các câu khác, phân biệt góp ý nêu vấn đề/lý do cụ thể với chê bai hoặc công kích. Có lý do không tự động vô hiệu hóa lời hạ nhục, kỳ thị hay đe dọa đi kèm. Từ tục đứng riêng cũng không quyết định nhãn. Chưa tự mở rộng nhãn B102 cho các câu khác chưa được đối chiếu.

B256: “Trường phải đập đi mà xây lại, chứ làm như này lên còn khó hơn” — người phụ trách xác nhận non-toxic vì chưa có ý chê trường. Giữ giải thích ở phạm vi câu đã duyệt; không dùng từ “đập” hay “xây lại” làm dấu hiệu tự động quyết định nhãn.

B334 được người phụ trách sửa từ non-toxic sang toxic vì là chê trường; nhãn trước do chưa đọc kỹ. Việc nêu lý do trong câu không tự động khiến mọi lời chê trường thành góp ý non-toxic; cần xét cách diễn đạt và ngữ cảnh.


## Làm rõ v3.2 — đùa thân mật (31/10/2026)

Phiên bản bổ sung: ptit-v3.2-friendly-banter-20261031. Kế thừa v3.1 và các ngoại lệ đã chốt.

- Người phụ trách xác nhận rằng một số câu trông như chê/mỉa mai thực tế là đùa giữa bạn bè. Đùa thân mật được gán non-toxic khi có xác nhận cụ thể của người phụ trách hoặc ngữ cảnh cho thấy hai bên trêu qua lại, cùng hưởng ứng và không kèm hành vi toxic khác.
- Xem phản ứng người nhận, yêu cầu dừng, dấu hiệu khó chịu, mục đích hạ nhục/đe dọa/quấy rối. Quan hệ bạn bè không tự loại trừ toxic.
- Emoji, haha, mày–tao hoặc tự nói đùa thôi không đủ chứng minh đồng thuận. Thiếu bằng chứng thì để Chưa rõ, không đoán quan hệ.
- Không suy ra mọi nhãn non-toxic mới đều là đùa giữa bạn bè. Lời giải thích chung của người dùng không xác định câu cụ thể; chỉ ghi lý do đùa thân mật cho từng mẫu khi có căn cứ riêng.
- Nhãn người dùng chốt sau khi xem đề xuất AI là nhãn duyệt có hỗ trợ AI, không phải kiểm chứng mù độc lập. Nhãn AI chưa chốt giữ riêng, không tính độ chính xác theo chính chúng.


## Các trường hợp người phụ trách xác nhận ngày 01/11/2026

Tham chiếu `outputs/label_review_selection_20261101/user_decisions.json` (18 câu). Đây là quyết định cho câu cụ thể trong ngữ cảnh đã cung cấp, không mở rộng thành quy tắc rằng mọi câu đùa hoặc phàn nàn đều non-toxic.

- Câu 3 và 13 là đùa, non-toxic theo xác nhận của người phụ trách.
- Câu 5 là toxic: mỉa mai gọi trường là cao đẳng. Câu 4 là toxic dù có nhắc lịch thực hành bị trùng.
- Câu 6 chưa có dấu hiệu chê; câu 7 chưa đủ điều kiện toxic; câu 8 chỉ phàn nàn: đều non-toxic.
- Câu 1, 4, 5, 14 toxic; các câu còn lại non-toxic.
