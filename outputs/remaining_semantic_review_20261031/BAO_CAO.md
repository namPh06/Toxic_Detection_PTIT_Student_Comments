# Hoàn tất đọc 4.275 bình luận còn lại — 31/10/2026

Đã đọc từng bình luận theo thứ tự manifest, đối chiếu quy tắc v3.2 và bình luận cha nối bằng ID khi có. Kết quả đề xuất: **104 toxic, 3.755 non-toxic, 416 chưa đủ ngữ cảnh**. Cùng các lượt trước, 5.111/5.111 bình luận sạch đã được đọc; không còn câu chưa đọc trong phạm vi này. Đã đọc không đồng nghĩa mọi nhãn đã đúng hoặc được người dùng xác nhận.

## Tệp kết quả

- Ra_soat_4275_cau.xlsx: AI_4275 lưu đầy đủ kết quả; Can_bo_sung_435 gom 416 câu mới chưa rõ và 19 câu chờ cũ; Huong_dan giải thích cách sử dụng. Cột A bình luận, B nhập t/n, C ngữ cảnh, D giải thích của người dùng. Không cần tự gán lại 4.275 câu.
- assistant_labels.json giữ ID/hash, lý do, nguồn AI và cờ human_verified=false, training_eligible=false.
- review_queue.json giữ 435 trường hợp cần bổ sung, không phải lớp nhãn thứ ba.
- verification.json lưu các đối soát định danh và số lượng.

## Cách hiểu kết quả

Không suy quan hệ bạn bè chỉ từ emoji, mày–tao hoặc lời đùa thôi. Những lời có thể là trêu thân mật hoặc hạ nhục được để chờ khi thiếu căn cứ. Không lấy bình luận nằm cạnh nhau làm ngữ cảnh hội thoại. Nội dung bài gốc chưa có nên chưa thể chốt hết câu mỉa mai hay lời ám chỉ. Một số lý do non-toxic được mô tả chung theo nhóm nội dung sau khi đọc từng câu.

Sau khi đọc xong mới đối chiếu dự đoán máy đã lưu: 3.748 đồng ý, 111 bất đồng, 416 chưa chốt. Bất đồng không chứng minh máy sai; chưa có kiểm định độc lập để tính độ chính xác. Không dùng đề xuất AI làm nhãn chuẩn tự đánh giá.

## Kiểm tra

4.275 ID duy nhất, không trùng 836 câu đã rà trước; hợp nhất phạm vi đủ 5.111 ID. Tất cả hash nội dung khớp. progress.json và workspace.json giữ nguyên; workspace đối chiếu với snapshot đọc đầu lượt và hash trong canonical_development_v32_20261031.json. Bộ nhãn người dùng đủ điều kiện vẫn 535 câu. Các bài dành riêng kiểm chứng được đánh dấu reserved_for_validation trong JSON. Chưa huấn luyện, thay mô hình hay đưa nhãn AI vào workspace. Không sử dụng dịch vụ trả phí. Không tạo file test tạm.

## Bước tiếp theo

Nếu biết thêm bài gốc hoặc quan hệ người tham gia, bổ sung ở Can_bo_sung_435 rồi chốt t/n. Giữ trống khi chưa rõ. Các đề xuất còn lại có thể dùng để ưu tiên rà soát và đối chiếu, chưa thay thế bộ nhãn chuẩn. Chỉ đánh giá và nâng cấp mô hình bằng nhãn người dùng cùng tập kiểm chứng được giữ riêng.
