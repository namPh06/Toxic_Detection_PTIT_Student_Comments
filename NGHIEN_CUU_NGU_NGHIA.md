# Nghiên cứu gán nhãn theo ngữ nghĩa — 30/10/2026

## Kết luận

Có thể áp dụng LLM với hướng dẫn theo tiêu chí và ngữ cảnh, nhưng không có bằng chứng để gọi một mô hình là tốt nhất cho PTIT khi chưa so sánh trên tập chuẩn phù hợp. Đã tạo semantic_labeling.py như nhánh thực nghiệm riêng; chưa nối vào nút gán nhãn toàn bộ. Mô hình ONNX hiện tại vốn đã là mô hình Transformer, không phải bộ đếm từ tục; regex chỉ gắn cờ cần đọc.

## Định nghĩa và khác biệt giữa dữ liệu

Perspective định nghĩa toxicity theo tác động thô lỗ/thiếu tôn trọng khiến thảo luận khó tiếp tục, đồng thời có thuộc tính PROFANITY riêng. Không thể đồng nhất mọi cảm xúc tiêu cực hoặc sự xuất hiện từ tục với toxic trong mọi chính sách. Nguồn: https://developers.perspectiveapi.com/s/about-the-api-attributes-and-languages?language=en_US

ViCTSD dùng tiêu chí rộng hơn chính sách PTIT v2: cả một số lời phê bình/mỉa mai và thất vọng có thể nằm ở các mức toxic; sau đó gộp ba mức độc tính. Đây là lý do không thể chuyển nhãn/mô hình học từ ViCTSD sang chính sách PTIT mà coi các định nghĩa giống nhau. Đây là khả năng giải thích sai khác, chưa phải kết luận nguyên nhân của từng lỗi. Nguồn gốc: https://arxiv.org/html/2103.10069 (mục 3.1, 3.4).

Quy tắc dự án v2 là lựa chọn phạm vi của người phụ trách: xác định hành vi của người viết (xúc phạm/hạ nhục, đe dọa/gây hại, kỳ thị, quấy rối), phân biệt phát ngôn trực tiếp với phủ định/trích dẫn phản đối; từ tục đơn thuần và phàn nàn sự việc chưa đủ. Thiếu ngữ cảnh thì uncertain, không tự chuyển thành non-toxic. Xem QUY_TAC_GAN_NHAN.md.

## Các hướng mô hình đã tra cứu

| Hướng | Bằng chứng và khả năng áp dụng |
|---|---|
| ViHateT5 | Nghiên cứu ACL 2024 về mô hình text-to-text chuyên cho hate/toxic tiếng Việt. Tác giả báo kết quả mạnh trên benchmark của thời điểm công bố; không phải bằng chứng tốt nhất vào 2026 hay tốt nhất PTIT v2. Cần rà ánh xạ nhãn và kiểm thử riêng. |
| Qwen3-4B fine-tune ViHSD | Model card tác giả báo Macro-F1 ba lớp 0,637 trên ViHSD, so với nền 0,5085. Kết quả tự báo, chưa đo trên PTIT; phần giải thích được tạo heuristic, không phải nhãn người đọc xác nhận. Không thể suy thành chính xác 100%. |
| Qwen3.5-4B | Mô hình mở có thể đưa vào danh sách thử cục bộ dạng lượng tử hóa. Chưa tải/chưa benchmark trên máy này; không gọi là tốt nhất cho toxic tiếng Việt. |
| Qwen3.8-27B và các LLM lớn | Đã có phiên bản mới trong thông tin chính thức; không có kiểm chứng PTIT ở các nguồn đã xem. 27 tỷ tham số ở 4-bit riêng trọng số đã xấp xỉ 13,5GB (ước lượng thô, chưa gồm runtime/KV cache), khó phù hợp với máy đang gần hết RAM. API/máy mạnh là hướng thử tiếp; chưa gọi dịch vụ ngoài. |
| Gemma 3 4B đang có | Dùng kiểm tra tính khả thi ngay, không cần tải mô hình hoặc gửi bình luận ra ngoài. Kết quả dưới đây cho thấy chưa đạt. |

Nguồn sơ cấp:
- https://aclanthology.org/2024.findings-acl.355/
- https://huggingface.co/vominhmanh/qwen3-4b-vihsd
- https://huggingface.co/Qwen/Qwen3.5-4B
- https://github.com/QwenLM/Qwen3.8
- https://ai.google.dev/gemma/docs/core/model_card_3
- https://docs.ollama.com/capabilities/structured-outputs

## Kiểm tra máy và chạy thật

Máy có khoảng 15,63GiB RAM, lúc kiểm tra còn 1,68GiB trống; đĩa dự án còn 22,9GiB. PyTorch hiện tại không thấy CUDA, nhưng ollama ps cho thấy Gemma đang chia CPU/GPU (56%/44%); không kết luận máy không có GPU. Ollama có gemma3:4b 3,4GB. Không sửa cài đặt service hay tải thêm mô hình lớn.

Đã chạy 3 biến thể hướng dẫn trên 8 câu phát triển (ví dụ tự soạn và câu người dùng đã chọn); không phải test độc lập hay phép đo độ chính xác toàn bộ.

| Lần | Đúng nhãn và đầu ra hợp lệ | Bị từ chối vì đầu ra không hợp lệ |
|---|---:|---:|
| Hướng dẫn tiếng Việt ban đầu | 6/8 | 1 |
| Bổ sung ví dụ/phủ định, siết bằng chứng | 4/8 | 3 |
| Hướng dẫn tiếng Anh nhấn mạnh hành vi | 4/8 | 1 |

Câu phản đối “Đừng gọi bạn ấy là đồ ngu.” vẫn bị gán toxic ở cả ba lần. Ở lần cuối, câu cảnh báo đường đi có từ tục bị giải thích sai thành miệt thị ngoại hình. Đây là bằng chứng không được mặc định LLM nhỏ hiểu đúng ngữ nghĩa dù có lời giải thích. Không thêm quy tắc ép đúng riêng các câu này để tạo kết quả đẹp.

Kết quả: data/label_audit/semantic_feasibility.json, semantic_feasibility_v2.json, semantic_feasibility_v3.json. Mỗi dự đoán hợp lệ lưu digest mô hình, hash prompt/văn bản/ngữ cảnh, policy v2, thời gian; human_verified=false và needs_review=true. Đầu ra sai schema/nhãn/category, bằng chứng không nguyên văn hoặc sinh chưa xong bị từ chối. Lý do sinh ra vẫn có thể sai dù vượt kiểm tra định dạng.

## Cách dùng thử

~~~powershell
.venv\Scripts\python.exe -X utf8 -B semantic_labeling.py --text 'Mày ngu thế.' --model gemma3:4b
~~~

Thêm --context khi có bài viết/bình luận cha; tool không tự có ngữ cảnh còn thiếu. Chỉ hỗ trợ Ollama cục bộ đã có model, không tự tải hay gửi ra API ngoài. Chưa tự nhập vào workspace hoặc tạo nhãn chuẩn.

## Kiểm thử và bước tiếp

Bộ xác thực: một trường hợp hợp lệ và 6 tình huống lỗi đều xử lý đúng. Unittest hiện có: 79 ca, 78 đạt, 1 smoke bị bỏ qua vì chưa bật LABELING_SMOKE trong lượt này. Không tạo file test mới; dữ liệu thử chạy trong bộ nhớ, các JSON kết quả giữ làm báo cáo kiểm định.

Bước tiếp để nâng cấp có căn cứ: lập tập đối chứng đủ toxic/non-toxic và trường hợp phủ định/trích dẫn/mỉa mai/teencode theo v2; giữ riêng phần test; so sánh ONNX hiện tại với mô hình chuyên tiếng Việt và LLM mạnh hơn. Đo Macro-F1/Precision/Recall, tỷ lệ uncertain/lỗi đầu ra, thời gian và chi phí. Chỉ tích hợp backend thắng trên phần giữ riêng; không dùng nhãn máy làm đáp án cho chính nó.
