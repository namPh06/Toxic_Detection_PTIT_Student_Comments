# Đánh giá gán nhãn tự động theo v3.2 — 31/10/2026

**Kết luận: mô hình hiện tại chưa đủ tốt để tự chốt toàn bộ nhãn.** Chức năng chạy được, nhưng còn bỏ sót toxic và gán nhầm nhiều câu người dùng chọn non-toxic.

## Dữ liệu và kết quả

Chỉ dùng 981 nhãn do người dùng xác nhận: 946 câu phát triển (114 toxic, 832 non-toxic) và 35 câu thuộc bài giữ riêng (1 toxic, 34 non-toxic). Không dùng 3.859 đề xuất AI còn lại làm nhãn chuẩn. Nguồn và workspace không thay đổi.

| Phạm vi | Đúng/tổng | Độ đúng | Precision toxic | Recall toxic | Macro F1 |
|---|---:|---:|---:|---:|---:|
| Phát triển, chẩn đoán |700/946|74,0%|24,2%|54,4%|58,7%|
| Bài giữ riêng, chẩn đoán nhỏ |34/35|97,1%|50,0%|100,0%|82,6%|
| Toàn bộ nhãn người dùng, chẩn đoán |734/981|74,8%|24,4%|54,8%|59,1%|

Độ đúng chung không phải độ chính xác đại diện của 5.111 câu. Tập người dùng tập trung nhiều câu khó, đã xem đề xuất/sàng lọc AI; không phải kiểm chứng mù. Nhóm 35 chỉ có một câu toxic nên recall 100% không chứng minh phát hiện toxic tốt. Tập kiểm chứng cố định 200 câu mới có 11 nhãn người dùng; 189 câu còn lại không được lấy nhãn AI thay thế. 24 nhãn còn lại của nhóm bài giữ riêng nằm ngoài mẫu 200 nhưng trong các bài được dành riêng. Không tính kết quả 35 câu như đã hoàn thành kiểm chứng 200.

Ma trận toàn bộ 981 câu (hàng=nhãn người dùng, cột=nhãn máy; thứ tự non-toxic, toxic): [[671,195],[52,63]]. Mô hình tìm được 63/115 toxic và bỏ sót 52. Trong 258 câu máy gọi toxic, chỉ 63 câu trùng nhãn người dùng. Vì 866/981 câu là non-toxic, đoán toàn non-toxic đạt 88,3% accuracy nhưng recall toxic bằng 0; vì vậy không lựa chọn mô hình chỉ theo accuracy.

## Kiểm tra chức năng và cờ rà soát

- Model/tokenizer cục bộ đúng kích thước và SHA-256 của phiên bản đã chốt.
- Chạy ONNX thật trên 16 câu chọn bằng hash cố định không dùng nhãn: cả 16 điểm khớp cache, sai lệch tối đa 0. Không tải mô hình hoặc gọi API trả phí. Đây là kiểm tra nhất quán runtime, không thêm 16 mẫu vào đánh giá.
- Đối chiếu đủ 981 ID, nội dung, hash và nguồn nhãn. Nhãn máy dùng đúng hàm automatic_annotation/ngưỡng 0,5 đang có; không đổi ngưỡng sau khi xem kết quả.
- Cờ rà soát đánh dấu 449 câu và bắt được 183/247 lỗi. Vẫn có **64 lỗi không bị đánh dấu** trong 532 câu không có cờ (đúng 88,0%). Không có cờ không có nghĩa nhãn chắc chắn đúng.
- Mô hình hybrid v3.1 cũ cũng đúng 34/35 ở nhóm bài giữ riêng, chưa thể chứng minh tốt hơn baseline. Hash candidate giữ nguyên; những dự đoán thuộc mẫu đóng băng trùng điểm đã lưu. Không fit/tìm ngưỡng trên nhóm giữ riêng.

## Các lỗi bỏ sót

- Chê trường/dịch vụ/cơ sở vật chất: 16 câu.
- Công kích, coi thường, thách thức hoặc đe dọa: 14 câu.
- Mỉa mai/công kích nhóm người hâm mộ: 9 câu.
- Hạ thấp theo danh tính, giới, khuyết tật hoặc nhóm sinh viên: 12 câu.
- Quấy rối tình dục: 1 câu.

Ví dụ bỏ sót theo nhãn người dùng: “Học phí quốc tế cơ sở nhà vườn”, “thương trường nghề Nguyễn Trãi”, “Babybuu241 bại não”, “Gg ko tính phí bớt hỏi ngoo”. Một số câu chỉ vài từ hoặc tên gọi trong nhóm cần ngữ cảnh; đây là phân nhóm chẩn đoán theo nhãn đã chốt, không mở rộng quy tắc bằng từ khóa.

Ví dụ non-toxic bị máy gán toxic: “Ko thi cử j buổi đó thì ko s đâu, điểm danh thì trừ 1 điểm cc thôi”, “Ngân Chii mạnh vl mà b”, “=)))) đã dốc rồi cái đoạn lên t3 còn toàn cát, trơn vl trơn luôn”. Mô hình không được huấn luyện cho đúng ranh giới riêng chê trường/góp ý/đùa thân mật của đề tài; từ viết tắt và lời tục dễ gây nhầm. Các ví dụ là minh họa, không phải kết luận đã phân nhóm thủ công toàn bộ 195 false positive.

## Quyết định bước tiếp theo

Cần cải tiến ứng viên ngoại tuyến dựa trên 946 nhãn phát triển: chia chéo theo bài viết, so sánh với baseline, chọn tham số chỉ bên phát triển; giữ 119 bài kiểm chứng khỏi huấn luyện/truy hồi. Ưu tiên giảm bỏ sót toxic mà không làm tăng bắt nhầm quá nhiều. Với câu thiếu bài gốc, cần cơ chế từ chối chốt và xin ngữ cảnh; không thể giải quyết bằng thêm từ khóa hoặc đổi ngưỡng đơn thuần.

Chưa huấn luyện hoặc thay mô hình đang chạy trong lượt đánh giá này. Cần nhãn người dùng độc lập đủ đại diện, đặc biệt thêm toxic, trước khi kết luận ứng viên tốt hơn. Những bộ đã mở nhãn là chẩn đoán lịch sử, không trở lại thành kiểm chứng mù cho lần nâng cấp tiếp theo. Không bảo đảm đúng 100%.

## Tệp kiểm tra

- evaluation.json: chỉ số, phạm vi, hash và giới hạn.
- predictions_vs_human.json: đủ 981 đối chiếu.
- errors.json: toàn bộ 247 bất đồng với nhãn người dùng.
- missed_toxic_analysis.json: phân nhóm 52 toxic bị bỏ sót.
- runtime_verification.json: kiểm tra ONNX thật 16 câu.

Không tạo file test tạm. Các script trong thư mục này là công cụ đánh giá tái lập, không sửa dữ liệu hoặc triển khai mô hình.
