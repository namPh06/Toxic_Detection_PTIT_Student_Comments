# Thu thập ngữ cảnh bài viết — 01/11/2026

Đã truy cập đủ 392 link trong data/progress.json bằng Playwright MCP, không dùng API trả phí.

## Kết quả

- 381 link lấy được văn bản bài viết gốc.
- 8 link Facebook báo nội dung hiện không khả dụng; không kết luận bài đã bị xóa.
- 3 link là bài chỉ có ảnh, không có phần văn bản; đã xác minh bằng ID bình luận trùng với dữ liệu gốc.
- 5.649/5.936 bình luận có văn bản bài viết đi kèm; 287 câu chưa có văn bản bài viết.
- Khôi phục 2 bình luận cha: “1 ngày” và “😭”, bổ sung ngữ cảnh cho 4 câu trả lời. Hai bình luận cha khác xác minh được permalink nhưng không có văn bản; ảnh hưởng 3 câu trả lời.
- 1.702 câu có bình luận cha đọc được; 4.231 câu không có parent_comment_id trong nguồn. Không suy luận quan hệ cha–con từ vị trí dòng.
- 392 mã/link quy về 369 nhóm bài khi giải mã ID bình luận Facebook. Khi chia train/test cần nhóm theo canonical_post_id, tránh cùng một bài qua hai link pfbid rơi vào hai tập.

## File và cách dùng

- data/post_context.json: nội dung bài, URL, thời điểm đọc và cách xác minh.
- data/parent_context.json: 4 bình luận cha được kiểm tra, chỉ làm ngữ cảnh, không thêm vào bộ nhãn.
- data/progress_with_context.json: đủ 5.936 dòng gốc, thêm context.post_text và context.parents; mọi trường gốc và nhãn giữ nguyên.
- Chạy lại xuất dữ liệu: .venv/Scripts/python.exe post_context.py
- app.py tự đọc kho ngữ cảnh khi khởi động, ghép vào posts khi xuất/lưu và thu thập văn bản bài viết ở các lượt cào sau. Cần khởi động lại tool để nạp mã mới.
- post_message.js là bộ đọc DOM dùng chung; không lấy tiêu đề trang thay cho nguyên văn bài viết.

## Sửa lỗi thu thập

- Loại phần văn bản bị lặp trong các bài nền màu do bản DOM aria-hidden. Các trường hợp phát hiện đã được đọc lại.
- Giữ emoji từ thuộc tính alt trong cả bài và bình luận.
- Không loại “1 ngày” như nội dung giao diện khi nó nằm trong thân bình luận đã xác minh.
- Không ghi đè một bản đầy đủ bằng bản rút gọn và không lưu nội dung chưa xác minh đúng bài.

## Giới hạn còn lại

Chưa trích xuất chữ trong ảnh/video (kể cả ảnh đính kèm bài đã có caption); has_media hiện có thể bao gồm media trong bình luận. text_complete=true chỉ có nghĩa không thấy nút See more trong khối văn bản lúc đọc, không bảo đảm mọi dữ liệu nguồn đầy đủ. Bộ bình luận gốc thiếu cờ text_complete và comment_filter=unknown; chưa chứng minh đã cào hết bình luận. Bài được đọc sau ngày thu thập bình luận nên có thể đã chỉnh sửa. Các parent bổ sung chưa xác minh được tổ tiên xa hơn (parent_chain_verified=false). Đây là bổ sung dữ liệu, chưa huấn luyện lại mô hình hoặc chứng minh nhãn chính xác hơn.

## Kiểm chứng

38 kiểm thử test_project, test_dataset_integrity, test_crawler_integrity đạt. Kiểm tra thêm việc ghép đúng post_id, giữ nguyên 5.936 dòng và nhãn, không ghép cha khác bài, phát hiện chu trình, lưu ngữ cảnh và chống ghi đè bản đầy đủ. Bộ trích xuất mới đã đọc được bài thật trên Facebook. Không tạo file test tạm; thư mục dữ liệu kiểm thử tạm được dọn tự động.

SHA256 progress.json không đổi: e478f195be50d8fd842f22e49c2b4d19f54563d3c00d4b30a6b180f1f006df00.

## Link không khả dụng

- https://www.facebook.com/groups/2k5ptit/posts/1308995287976312/
- https://www.facebook.com/groups/2k5ptit/posts/1309419584600549/
- https://www.facebook.com/groups/2k5ptit/posts/1307920308083810/
- https://www.facebook.com/groups/2k5ptit/posts/1312408804301627/
- https://www.facebook.com/groups/2k5ptit/posts/1311259454416562/
- https://www.facebook.com/groups/408571091380061/posts/1468516765385483/
- https://www.facebook.com/groups/408571091380061/posts/1480584067512086/
- https://www.facebook.com/groups/408571091380061/posts/1480631207507372/

## Link chỉ có ảnh

- https://www.facebook.com/antiptit/posts/pfbid0gqY1E98DvaS4C1GdB4VGRB3xDgX24ieByvNJSoFx9U3C8AzUAJmzVyEcg9vcJEScl
- https://www.facebook.com/antiptit/posts/pfbid02ZicPNdaCL5VhhZxeN55EjpbuHphoRHFZD9aZW74FbajPoD7ZKiHvAFQ3KvqXLBfRl
- https://www.facebook.com/antiptit/posts/pfbid0gkX2aaeCeyJ18pHhkYQTCzyx44oCMehH22qhKzLhg5tAY1Dc6kjxzGL87TveXhg4l
