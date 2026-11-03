# Gán lại toàn bộ theo v4

Phạm vi chụp lúc bắt đầu: 6.658 bình luận trong progress.json và workspace.json, bao gồm dữ liệu cào ngày 02/11/2026.

Chưa hoàn tất. Gemma3:4b không vượt qua kiểm tra phủ định và phàn nàn; kết quả thử của mô hình này đã bị loại, chưa áp dụng vào dữ liệu chính. Đang tải và kiểm thử Qwen3 4B Instruct 2507 miễn phí trên máy.

Quy trình: kiểm tra quy tắc → phân loại toàn bộ có ngữ cảnh → loại câu chưa rõ khỏi nguồn đang dùng → xuất dataset_v4.json/csv và data/dataset_auto.json/csv.

- status.json: số câu đã xử lý.
- job.log: tiến trình và lỗi.
- qualification.json: chỉ xuất khi vượt kiểm tra quy tắc cơ bản; không phải độ chính xác toàn bộ dữ liệu.
- applied.json và KET_QUA.md: chỉ xuất sau khi dữ liệu chính đã được đồng bộ. Không có hai tệp này nghĩa là chưa hoàn tất.
- before_*.json và snapshot.json: bản sao trước khi sửa.
- excluded_v4.json/csv: các mẫu bị loại khỏi tập dùng được, kèm lý do.
- audit.json: nhãn trước/sau và lý do cho từng câu.

Không biến nhãn máy thành nhãn đã được người duyệt. Không sử dụng kết quả đánh giá NB/SVM cũ làm đánh giá của dataset v4.

Lệnh tiếp tục khi bị gián đoạn (chỉ chạy một tiến trình): .venv\Scripts\python.exe -u run_relabel_v4.py
