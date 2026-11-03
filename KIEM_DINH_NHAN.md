# Kiểm định nhãn tự động — 27/10/2026

## Kết luận

Chức năng chạy được, nhưng nhãn máy chưa đủ tin cậy để coi là nhãn chuẩn. Chưa có nhãn độc lập do người đọc xác nhận nên chưa đo được độ chính xác thật của corpus PTIT. Các số dưới đây chỉ là độ khớp với đánh giá sơ bộ của Codex AI, không phải số liệu dùng để tuyên bố chất lượng mô hình trong BTL.

## Phương pháp và kết quả

Nguồn: data/progress.json, 5.936 bình luận, 5.111 mẫu ready sau làm sạch. Chọn 100 mẫu ngẫu nhiên seed 20261027, đọc và lưu nhãn AI trước khi chạy dự đoán. Không nhìn điểm mô hình khi gán nhãn. Có 11 mẫu thiếu ngữ cảnh/khó quyết định, loại khỏi phép tính chứ không coi là non-toxic. Trong 89 mẫu còn lại có 86 non-toxic và chỉ 3 toxic theo AI.

| Chỉ số trên 89 mẫu rõ | Giá trị |
|---|---:|
| Accuracy | 93,26% |
| Precision toxic | 20,00% |
| Recall toxic | 33,33% |
| F1 toxic | 25,00% |
| Macro-F1 | 60,74% |

Confusion matrix [non-toxic, toxic], hàng tham chiếu/cột dự đoán: [[82,4],[2,1]]. Baseline đoán tất cả non-toxic đạt 86/89 = 96,63% Accuracy; vì vậy Accuracy cao không chứng minh mô hình tốt. Chỉ có 3 mẫu toxic nên các chỉ số lớp toxic rất bất ổn. Không dùng tập này để chọn ngưỡng rồi báo lại điểm như test độc lập.

Thêm 50 mẫu chẩn đoán có từ khóa, seed 20261028, không trùng mẫu ngẫu nhiên: 10 chưa rõ, 40 mẫu tính điểm, chỉ 2 toxic; Accuracy 90%, Precision 25%, Recall 50%, F1 33,33%. Đây là mẫu chọn có chủ đích, không gộp với mẫu ngẫu nhiên để ước lượng độ chính xác corpus. Regex chọn mẫu còn khớp tên riêng như Nguyễn, nên đây cũng không phải tập bao phủ đầy đủ toxic.

Lỗi quan sát: nhầm lời phàn nàn có từ tục thành công kích; viết tắt như cc có nhiều nghĩa; bỏ sót cách viết né từ và quấy rối tình dục. Mẫu có tên/định danh được giữ cục bộ trong artifact kiểm định, không đưa nguyên văn vào báo cáo công bố.

## Nghiên cứu và thay đổi

Model card chính thức mô tả mô hình nền ViSoBERT, huấn luyện bằng ViHSD/ViCTSD. Tác giả công bố tại ngưỡng 0,5 Recall 0,81 và Precision 0,62 trên tập nguồn; các số này không phải kết quả trên PTIT và trang hiện tại có thể khác revision đang chốt. Nguồn: https://huggingface.co/dangvansam/vietnamese-toxicity

Không thể sửa đồng thời false positive và false negative chỉ bằng nâng/hạ ngưỡng. Scikit-learn yêu cầu tách dữ liệu tối ưu ngưỡng khỏi dữ liệu đánh giá để tránh overfit: https://scikit-learn.org/stable/modules/classification_threshold.html

Giữ nguyên revision và ngưỡng 0,5. Bổ sung định tuyến rà soát ngữ cảnh trong labeling.py: từ tục, viết tắt đa nghĩa, một số cách viết né từ, quấy rối và đe dọa được đánh dấu needs_review kể cả điểm rất cao/thấp. Quy tắc chỉ ưu tiên người đọc, không đổi nhãn thành toxic/non-toxic và không tự nhận biết đúng toàn bộ ngữ cảnh. UI nêu lý do context riêng.

Trên chính mẫu phát triển này, cờ mới đánh dấu 6/6 lỗi ở tập ngẫu nhiên và 4/4 ở tập chẩn đoán, lần lượt cần rà 11/89 và 5/40 mẫu rõ. Đây là kiểm tra trên dữ liệu đã dùng để xây quy tắc, chưa phải hiệu quả trên tập giữ lại độc lập. Điểm phân loại không thay đổi. Mẫu không có cờ vẫn có thể sai; needs_review không chặn huấn luyện hiện tại.

## Quy trình nâng cấp tiếp

1. Dùng data/label_audit/human_review_template.json: một người đọc không xem predictions.json hoặc reference_ai.json, điền reference_label toxic/non-toxic/uncertain. Chỉ đặt human_verified=true sau khi thực sự được người đọc xác nhận; nên có người thứ hai xử lý bất đồng. Không dùng nhãn AI làm nhãn người.
2. Thu thập thêm mẫu toxic đã kiểm tra chéo từ nhiều bài, giữ riêng một tập ngẫu nhiên phản ánh phân bố thật. Chốt phạm vi từ tục không công kích, đùa và trích dẫn trước khi gán.
3. Chia theo bài: tập phát triển để hiệu chỉnh ngưỡng hoặc fine-tune ViSoBERT với nhãn PTIT; tập test giữ lại để so sánh Precision/Recall/Macro-F1 và tỷ lệ cần duyệt. Không huấn luyện/fine-tune bằng chính nhãn máy rồi dùng nhãn máy làm bằng chứng nâng cấp.
4. Chỉ thay mô hình khi đánh giá trên test độc lập cải thiện đủ rõ. Hiện chưa có cơ sở tuyên bố cải thiện độ chính xác hoặc tự động thay checkpoint.

Đo lại sau khi hoàn tất bản tham chiếu:

~~~powershell
.venv\Scripts\python.exe -X utf8 -B audit_labels.py --reference data/label_audit/human_review_template.json --predictions data/label_audit/predictions.json --output data/label_audit/human_results.json
~~~

Script không thay đổi nhãn huấn luyện; từ chối nhãn trống, ID trùng, hash hoặc văn bản không khớp, điểm không hợp lệ. Nhãn uncertain bị loại có đếm rõ; kết quả không được người đọc xác nhận được ghi provisional AI agreement.

## Kiểm thử

79/79 kiểm thử hiện có đạt, gồm suy luận ONNX thật offline. Kiểm tra thêm luồng context -> lưu/đọc lại -> CSV giữ nguyên nguồn nhãn máy, và từ chối reference/prediction lỗi hash, ID trùng, văn bản đổi, NaN. Dữ liệu kiểm thử tạm tự dọn; không tạo tệp test mới. Corpus gốc không đổi; chưa gán nhãn toàn bộ workspace thật.

## Chạy toàn bộ 5.111 mẫu (27/10/2026)

Đã suy luận thật bằng ONNX offline trên 5.111/5.111 mẫu ready trong 68,19 giây (lần chạy cuối, suy luận từng mẫu). Kiểm tra đủ ID duy nhất và khớp hash văn bản; checksum mô hình hợp lệ; hash progress.json trước/sau không đổi. Tổng nguồn 5.936 dòng: 736 trùng, 89 rỗng/UI được ghi riêng ở excluded.json.

Máy dự đoán 349 toxic và 4.762 non-toxic. Có 449 mẫu cần duyệt: 335 do điểm không chắc và 114 do ngữ cảnh. Đây là phân bố dự đoán, không phải số nhãn đúng. 4.662 mẫu không có cờ vẫn có thể sai. Cả 5.111 mẫu thiếu thuộc tính xác nhận đã thu thập hết văn bản; không suy diễn rằng chúng đều bị cắt.

Kết quả tại data/label_audit/full_corpus/: predictions.json, machine_labels.json, review_queue.json, human_review_blind.json, excluded.json, summary.json và acceptance.json. Các nhãn máy chưa được nhập vào workspace hoặc coi là nhãn huấn luyện đã xác nhận.

Chế độ --require-perfect từ chối đạt: 0 nhãn tham chiếu đã đánh giá, 5.111 nhãn tham chiếu chưa điền/chưa xác nhận; errors=null và accuracy=null. Không có bằng chứng đúng 100%. Bộ kiểm tra điều kiện đạt đã thử trường hợp hợp lệ và từ chối thiếu mẫu, chưa xác nhận, chưa quyết định, dự đoán sai, lệch hash, NaN, ID trùng, ID thừa và corpus rỗng, không tạo file test. 79/79 kiểm thử hiện có tiếp tục đạt, gồm ONNX thật.

Chạy lại toàn bộ:

~~~powershell
.venv\Scripts\python.exe -X utf8 -B audit_corpus.py
~~~

Sau khi có người đọc độc lập hoàn thành human_review_blind.json (không chép nhãn dự đoán vào đó):

~~~powershell
.venv\Scripts\python.exe -X utf8 -B audit_labels.py --reference data/label_audit/full_corpus/human_review_blind.json --predictions data/label_audit/full_corpus/predictions.json --corpus data/progress.json --require-perfect --output data/label_audit/full_corpus/acceptance.json
~~~

Lệnh trả mã 2 khi chưa đạt. Sau khi sửa mô hình phải tạo lại predictions; chỉ được thông báo khớp 100% trên bộ tham chiếu cố định nếu đủ nhãn xác nhận và không có lỗi. Tối ưu lặp trên cùng bộ kiểm tra có thể ghi nhớ bộ đó; vẫn cần tập độc lập để kết luận khả năng tổng quát.

### Sửa điểm phụ thuộc thành phần lô

Khi đối chiếu 150 mẫu chạy riêng với lần chạy toàn bộ ban đầu, điểm cùng văn bản lệch tối đa 0,0864. Đổi labeling.BATCH_SIZE từ 16 thành 1 để mỗi bình luận được suy luận độc lập; chạy lại toàn bộ. So hai lần chạy 5.111 mẫu, chênh điểm lớn nhất 0,1961 và 15 nhãn qua ngưỡng 0,5 thay đổi. Chi tiết ở batch_stability_change.json. Đây là sửa tính ổn định, chưa chứng minh nhãn mới đúng hơn.

Kiểm tra thật ba mẫu từng lệch điểm khi chạy trong tập con đảo thứ tự, thêm mẫu khác và một mẫu chạy đơn: điểm khớp lần chạy toàn bộ trong sai số 1e-12. Cả 79 kiểm thử tiếp tục đạt sau sửa. Kiểm tra đủ 5.111 ID/hash/điểm hữu hạn và hash dữ liệu nguồn đều đạt. Không tạo file test.

Đo lại với cùng tham chiếu AI đã lưu: random_ai_agreement.json và challenge_ai_agreement.json; chỉ số phân loại không đổi (F1 toxic 25% và 33,33%). Vì thế chưa khắc phục hết sai ngữ nghĩa; không coi đây là bản đạt 100% hoặc đã cải thiện độ chính xác. Cần nhãn độc lập để tiếp tục tối ưu mô hình và kiểm chứng.
