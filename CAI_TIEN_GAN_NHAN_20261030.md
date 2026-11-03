## Hoàn tất nhãn máy 01/11/2026

Đã ghi thêm 4.165 nhãn máy vào workspace, giữ nguyên 946 nhãn người. 5.111 mẫu ready đều có nhãn: 220 toxic (4,30%), 4.891 non-toxic; toxic gồm 114 người + 106 máy chưa xác nhận. 736 bản trùng và 89 dòng lỗi/UI không ép gán. Không dùng nhãn máy làm gold. Đề không quy định tỷ lệ toxic tối thiểu; các kịch bản bổ sung và giới hạn tại [HOAN_TAT_NHAN_MAY_20261101.md](HOAN_TAT_NHAN_MAY_20261101.md). Hash workspace cũ đã thay đổi có chủ ý; cần snapshot mới trước thí nghiệm tiếp.

## Đối chiếu đề bài sau chia tập — 01/11/2026

Đã kiểm tra lại debai.jpg và artifact thực: đã chạy BoW/TF-IDF × NB/SVM, có đủ chỉ số đánh giá CV; chưa có lượt test cuối khóa trước/báo cáo hoàn chỉnh. Chưa chạy so sánh có/không ngữ cảnh. Kiểm tra hash/fold đạt, 79 test: 78 đạt, 1 bỏ qua. Bảo vệ chia tập UI hiện còn phụ thuộc artifact mặc định tồn tại; đường gọi experiments trực tiếp chưa tự nạp reservation. Chi tiết: [DOI_CHIEU_DE_BAI_20261101.md](DOI_CHIEU_DE_BAI_20261101.md).

## Chia tập và gợi ý dự phòng 01/11/2026

Đã thêm safe_labeling_split.py, tạo ranh giới canonical + trùng bắc cầu trước giữ riêng: 654 nhãn phát triển, 292 nhãn được cách ly khỏi lượt phát triển mới. Xuất 251 gợi ý cho mẫu thiếu ngữ cảnh, giữ 43 nhãn người. Đã nối bảo vệ chia tập vào nút huấn luyện; chưa nhập gợi ý vào workspace hoặc thay mô hình. TF-IDF/SVM mới recall toxic 2/82, chưa đạt để tự chốt. Chi tiết: [CHIA_TAP_VA_DU_PHONG_20261101.md](CHIA_TAP_VA_DU_PHONG_20261101.md).

## Rà soát toàn hệ thống 01/11/2026 — chưa chuyển sang huấn luyện mới

79 ca kiểm thử Python: 78 đạt, 1 smoke bỏ qua mặc định; smoke ONNX thật đã chạy riêng và đạt. Hash nguồn, 5.936 mẫu và 946 nhãn canonical còn nguyên. Phát hiện cần xử lý trước thí nghiệm: chính sách mã ngữ cảnh còn v2/v3.1, UI chưa nối pipeline ngữ cảnh, 1 nhãn phát triển trùng nhóm bài canonical với tập giữ riêng, đường huấn luyện UI cho phép nhãn máy và chưa bảo vệ reserved groups. Workspace hiện có 946 nhãn, 4.165 mẫu ready chưa có nhãn; không phải đã chốt toàn bộ corpus. Chi tiết và bằng chứng: [RA_SOAT_HE_THONG_20261101.md](RA_SOAT_HE_THONG_20261101.md).

## Cập nhật 01/11/2026 — tiền xử lý ngữ cảnh hoàn thành

Đã xuất 5.936 mẫu có cấu trúc bài viết → bình luận cha → câu cần xét, giữ phủ định/dấu câu/emoji, ghép 946 nhãn phát triển đã xác nhận. Có 294 mẫu được đánh dấu thiếu ngữ cảnh. Kiểm tra toàn bộ mẫu và 29 kiểm thử hồi quy đều qua; dữ liệu nguồn và nhãn không đổi. Chưa huấn luyện lại hoặc thay mô hình đang chạy. Chi tiết: [TIEN_XU_LY_NGU_CANH_20261101.md](TIEN_XU_LY_NGU_CANH_20261101.md).

## Cập nhật 01/11/2026 — thu thập ngữ cảnh

Đã kiểm tra 392 link: 381 có văn bản, 8 không khả dụng, 3 chỉ có ảnh. Dữ liệu ghép: `data/progress_with_context.json` (5.936 bình luận, 5.649 có văn bản bài viết). Khôi phục thêm 2 bình luận cha. Nhãn và JSON gốc giữ nguyên; chưa huấn luyện lại mô hình. Chi tiết: [THU_THAP_NGU_CANH_20261101.md](THU_THAP_NGU_CANH_20261101.md).

# Thí nghiệm BoW/TF-IDF × NB/SVM — 31/10/2026

Đã cài Pyvi 0.1.1 và thêm word_preprocessing.py: tách từ trước lọc stop words, giữ phủ định/emoji; dataset.clean_text giữ hành vi mặc định cũ. Underthesea 6.8.4 cài thất bại do phụ thuộc build; Pyvi đã chạy thực tế. Tách từ mới dùng trong baseline_v32.py, chưa chuyển toàn bộ pipeline giao diện sang cách mới.

Đã chạy 4 cấu hình trên đúng 946 nhãn phát triển (114 toxic, 832 non-toxic), đánh giá chéo 5 fold theo 132 nhóm bài, nối bài trùng văn bản. Cả bốn dùng cùng fold, vectorizer chỉ fit train từng fold; 119 bài giữ riêng không dùng để fit/chọn mô hình. Nhãn người dùng, nguồn và canonical giữ nguyên hash.

Macro-F1 OOF: BoW-NB 0.4670; BoW-SVM 0.5167; TF-IDF-NB 0.4679; TF-IDF-SVM 0.5202. TF-IDF-SVM cao nhất theo macro-F1 trung bình fold 0.5174 nhưng chỉ phát hiện 7/114 toxic (6.14%), còn bỏ sót 107. NB không phát hiện toxic. Chưa đạt để thay chức năng tự động. Đây là đánh giá phát triển trên nhãn chọn lọc có hỗ trợ AI; không phải test độc lập và không suy rộng toàn corpus.

Kết quả: [báo cáo](outputs/baselines_v32_20261031/BAO_CAO.md), metrics.json, folds.json, dataset.json, bốn OOF predictions và bốn joblib ứng viên trong cùng thư mục. Mô hình joblib nhận text_word từ word_preprocessing.word_text, không đưa thẳng raw hay dùng experiments.predict kiểu cũ. Không cập nhật data/latest.json hoặc mô hình triển khai.

Theo đề: đã thực hiện bước 3 và lượt thí nghiệm bước 4; bước 5 mới có so sánh cross-validation phát triển, còn thiếu test độc lập và báo cáo cuối. Hướng tiếp theo: cải tiến bằng CV trên nhãn phát triển và bổ sung/khóa nhãn test độc lập trước đánh giá cuối. Không yêu cầu tự gán lại toàn bộ 5.111 câu.

---

# Kết quả đánh giá tự động theo nhãn người dùng — 31/10/2026

Mô hình chạy được nhưng chưa đủ tốt để tự chốt: trên 981 nhãn người dùng, đúng 734/981 (74,8%), phát hiện 63/115 toxic (54,8%), bỏ sót 52 toxic và bắt nhầm 195 non-toxic. Đây là chẩn đoán trên mẫu chọn lọc có hỗ trợ AI, không phải độ chính xác đại diện 5.111 câu. Nhóm bài giữ riêng 35 câu chỉ có 1 toxic, chưa đủ kiểm chứng. 189/200 mẫu kiểm chứng cố định chưa có nhãn người dùng.

Đã kiểm tra mô hình ONNX cục bộ thật: 16/16 điểm trùng cache. Nhãn người dùng, nguồn và mô hình giữ nguyên; chưa huấn luyện/thay mô hình. Cờ rà soát vẫn bỏ lọt 64 lỗi, nên không có cờ không đồng nghĩa đúng.

Chi tiết: outputs/label_evaluation_v32_20261031/BAO_CAO.md; đầy đủ 247 lỗi trong errors.json. Hướng tiếp: cải tiến ngoại tuyến bằng 946 nhãn phát triển, chia theo bài viết, giữ riêng bài kiểm chứng; chưa có bằng chứng gán nhãn đúng hết.

---

# Đã chốt 5 câu thành toxic — 31/10/2026

Theo xác nhận của người dùng, Can_bo_sung_435!B68, B81, B85, B113, B122 đều đổi từ n thành t. Đã đồng bộ workspace và nhãn người dùng, bỏ trạng thái chờ của cả 5 câu. Đợt 435 câu hiện có 30 toxic, 405 non-toxic. Bộ nhãn phát triển hợp nhất: 946 câu (114 toxic, 832 non-toxic); 24 câu thuộc bài kiểm chứng vẫn giữ riêng. Chưa huấn luyện hoặc đo độ chính xác mới.

File Excel gốc đang bị khóa ghi. Bản đã sửa: outputs/user_corrections_5_20261031/Ra_soat_4275_cau_da_sua.xlsx. Kiểm tra đủ toàn bộ ô: chỉ năm ô nhãn thay đổi; bảng, danh sách nhập t/n và vị trí cuộn giữ nguyên. Có bản sao trước sửa, corrections.json và verification.json cùng thư mục. Không tạo file test tạm.

---

# Đã rà file 435 nhãn người dùng — 31/10/2026

Đủ 435/435 nhãn: 25 toxic, 410 non-toxic, không lỗi ID/hash/nội dung hay nhãn sai định dạng. Đã đọc lại cả 435 câu. Ghi nhận đủ nhãn, giữ riêng 24 câu thuộc bài kiểm chứng. Bộ nhãn phát triển hiện 941 (109 toxic, 832 non-toxic); 5 nhãn n giữ nguyên nhưng tạm chờ làm rõ quy tắc, chưa đưa vào huấn luyện.

Năm ô cần xác nhận thêm ở Can_bo_sung_435: B68, B81, B85, B113, B122. Nội dung/lý do cụ thể: outputs/user_review_435_20261031/BAO_CAO.md. Excel giữ nguyên; dữ liệu nhập có sao lưu và import_verification.json. Chưa huấn luyện hay đo độ chính xác mới. Những đề xuất AI còn lại chưa được nâng thành nhãn chuẩn.

---

# Hoàn tất rà 4.275 câu còn lại — 31/10/2026

Đã đọc hết: AI đề xuất 104 toxic, 3.755 non-toxic, 416 cần ngữ cảnh. Tổng phạm vi đã đọc qua các lượt: 5.111/5.111 câu sạch. Các nhãn AI chưa được xác nhận, không phải bằng chứng đúng 100%.

Kết quả: outputs/remaining_semantic_review_20261031/Ra_soat_4275_cau.xlsx — AI_4275 xem toàn bộ, Can_bo_sung_435 gồm 416 câu mới + 19 câu chờ cũ. Cột B nhập t/n, D thêm ngữ cảnh. Không cần tự gán lại toàn bộ 4.275 câu. Chi tiết phương pháp và đối soát: outputs/remaining_semantic_review_20261031/BAO_CAO.md.

Giữ nguyên nhãn người dùng và dữ liệu gốc; chưa huấn luyện hoặc thay mô hình, không phát sinh phí dịch vụ.

---

# Rà tiếp ngữ nghĩa — 31/10/2026

Đã đọc thêm 100 bình luận chưa được rà trước đó, đối chiếu quy tắc v3.2 và ngữ cảnh cha có sẵn: AI đề xuất 2 toxic, 80 non-toxic, 18 chưa đủ ngữ cảnh. Chọn theo thứ tự manifest lịch sử sau khi loại các câu đã đọc và bài viết dành riêng kiểm chứng; đây không phải mẫu đánh giá ngẫu nhiên.

File outputs/assistant_review_batch2_20261031/Duyet_tiep_19_cau.xlsx gồm Can_duyet_19 (18 câu mới chưa rõ + 1 câu cũ còn trống), AI_100 và Huong_dan. Điền t/n ở cột B, giải thích/ngữ cảnh bạn biết ở cột D. Những nhãn AI đều lưu riêng, human_verified=false và training_eligible=false. Không suy quan hệ bạn bè từ emoji hoặc cách xưng hô.

Đã hợp nhất nhãn người dùng đủ điều kiện vào data/manual_review/canonical_development_v32_20261031.json: 535 câu (85 toxic, 450 non-toxic), loại câu chưa chốt và các bài kiểm chứng. Các tham chiếu cũ là lịch sử; dùng bản hợp nhất này khi chuẩn bị bước huấn luyện tiếp theo. Chưa huấn luyện hoặc thay mô hình trong lượt này.

Tổng cộng 836 bình luận duy nhất đã được đọc qua các lượt, còn 4.275/5.111 câu chưa rà ngữ nghĩa. Con số đã đọc không đồng nghĩa đã có nhãn chuẩn. Chưa có bằng chứng mọi nhãn đúng.

Kiểm tra đạt: nguồn và workspace giữ nguyên byte/hash; 100 ID không trùng nhóm đã rà hoặc bài kiểm chứng; hash nội dung đúng; Excel có đúng ba sheet và ô B nhập nhãn để trống. Đã kiểm tra hình ảnh xem trước. Không phát sinh chi phí dịch vụ; không tạo file test tạm. Hồ sơ: assistant_labels.json, review_queue.json, verification.json trong cùng thư mục đầu ra.

Tiếp theo: nhập quyết định người dùng cho 19 câu khi có, tiếp tục đọc phần còn lại theo cùng quy tắc; chỉ đánh giá mô hình bằng nhóm kiểm chứng tách biệt và nêu rõ các nhãn đã được người dùng xem đề xuất AI.

---

# Cập nhật sau người dùng chốt Excel — 31/10/2026

Đã thêm giải thích v3.2 về đùa thân mật vào QUY_TAC_GAN_NHAN.md. Không suy nhãn từ emoji hay mặc định mọi non-toxic là đùa.

Excel có 93/94 câu đã điền: 82 xác nhận lại nhãn trong workspace (15 đổi n thành t), 11 nhãn người dùng cho nhóm kiểm chứng được giữ riêng. Workspace có 536 nhãn lịch sử: 85 toxic, 451 non-toxic. Một câu chưa chốt ở Can_xem_lai!B56: “thể loại này mà cũng làm bạn đợc à”; giữ nhãn cũ trong lịch sử nhưng excluded=true để chưa dùng huấn luyện.

Đã kiểm tra ID/hash/nội dung, không sửa nguồn crawl và workbook; các nhãn ngoài phạm vi giữ nguyên. Sao lưu và hồ sơ từng quyết định: outputs/assistant_review_20261031/user_resolutions_20261031.json. 11 câu được duyệt sau khi thấy đề xuất AI, không coi là test mù độc lập. 189 đề xuất AI còn lại chưa thành nhãn người dùng. Các JSON tham chiếu/ảnh/báo cáo trước đó là lịch sử; lần huấn luyện sau phải hợp nhất quyết định mới theo ID/hash, không dùng lại nguyên bộ nhãn cũ.

Việc tiếp: chốt câu B56 hoặc tiếp tục để chờ nếu thiếu ngữ cảnh; sau đó rà tiếp phần dữ liệu chưa đọc, ưu tiên hội thoại có cha và các trường hợp mỉa mai/đùa thân mật, giữ nhóm kiểm chứng tách biệt. Chưa thể kết luận mọi nhãn đúng hoặc triển khai mô hình mới.

---

# Rà soát ngữ nghĩa ngày 31/10/2026

Đã kiểm tra và nhập 60 nhãn người dùng mới (6 toxic, 54 non-toxic). Workspace hiện có 536 nhãn người dùng: 70 toxic, 466 non-toxic. Giữ nguyên 476 quyết định trước; sao lưu workspace trước nhập ở outputs/assistant_review_20261031/workspace_before_import.json.

Đã tự đọc 200 câu còn trống của Kiem_chung_200 theo tiêu chí v3.1 và bình luận cha có sẵn: đề xuất 2 toxic, 187 non-toxic, để 11 câu chưa rõ. Mỗi câu có lý do riêng trong assistant_labels.json. Nguồn là assistant_semantic_review, human_verified=false; không nhập các nhãn này vào tập nhãn người dùng hoặc dùng để đo độ chính xác. Đây là kết quả đọc của trợ lý trong phiên này, chưa phải thuật toán tự động có thể tái chạy trong ứng dụng.

Đã rà lại toàn bộ 536 nhãn người dùng: 83 trường hợp cần đối chiếu (29 đề xuất toxic, 54 cần làm rõ). Giữ nguyên nhãn gốc, đề xuất nằm riêng. 36 quyết định đã được người dùng xử lý riêng theo v3.1 được giữ nguyên, không đưa lại vào hàng chờ chỉ vì khác cách hiểu phổ thông. Không phát hiện vấn đề mới ở 453 câu còn lại không đồng nghĩa bảo đảm chúng đúng tuyệt đối.

Excel kết quả: [Kết quả gán nhãn và rà soát](outputs/assistant_review_20261031/Ket_qua_gan_nhan_va_ra_soat.xlsx). Sheet Can_xem_lai có 94 dòng = 83 nhãn người dùng cần đối chiếu + 11 câu AI chưa rõ. Cột B cho người dùng chốt t/n, cột C nhãn gốc, D đề xuất, E lý do, F ngữ cảnh. AI_200 lưu toàn bộ đề xuất; Ra_soat_536 lưu toàn bộ lượt rà; JSON đi kèm lưu ID/hash/nguồn.

Phạm vi đọc ngữ nghĩa lần này là 736 câu, gồm 536 nhãn người dùng và 200 câu AI. Chưa đọc ngữ nghĩa hết 5.111 câu sạch. Dự đoán toàn bộ corpus của ONNX là bộ nhớ đệm mô hình, không phải nhãn chuẩn. Không có bằng chứng đúng hết; chưa nâng cấp/triển khai mô hình mới. Không phát sinh phí API.

Không chỉnh file Excel gốc và dữ liệu crawl. Giữ riêng 119 bài của nhóm 200 khỏi huấn luyện/truy hồi. Không chạy evaluate-frozen với nhãn AI. Muốn kiểm chứng độc lập vẫn cần người đọc xác nhận nhóm này mà không dựa vào đề xuất AI, hoặc tạo tập mới trước một lần thử mô hình sau.

---

# Đợt duyệt tiếp theo đã chuẩn bị — 31/10/2026

Đã tạo [Excel đợt 2](outputs/label_review_20261031/Gan_nhan_bo_sung_va_kiem_chung.xlsx): 60 câu bổ sung dữ liệu phát triển và 200 câu kiểm chứng để riêng. Việc người dùng làm trước: điền cột B của **Bo_sung_60** bằng t/n, câu chưa rõ để trống và ghi lý do ở D, lưu file rồi báo đã xong. [Hướng dẫn chi tiết](HUONG_DAN_DOT_GAN_NHAN_20261031.md).

200 câu chọn ngẫu nhiên bằng thứ tự hash cố định từ 1.026 câu/217 bài chưa có nhãn người dùng. Giữ riêng 119 bài chứa các câu được chọn khỏi huấn luyện và truy hồi ví dụ. Không suy rộng kết quả cho toàn bộ 5.111 câu. Dự đoán hai mô hình đối chiếu đã đóng băng trước nhãn mới; chưa mở nhãn kiểm chứng và chưa đo chất lượng trên 200 câu.

Đã thêm review_round.py để kiểm tra file, xuất riêng nhãn phát triển và bảo vệ tập kiểm chứng. review_excel.py hỗ trợ cấu hình hai sheet mới và giữ ghi chú; vẫn đọc đúng workbook cũ. 79 kiểm tra hồi quy và kiểm tra nhập nhãn/rò rỉ tập kiểm chứng đạt. Nguồn crawl và workspace giữ nguyên. Các file kiểm thử tạm đã xóa.

Chưa thể huấn luyện theo 60 câu hoặc kiểm chứng 200 câu khi người dùng chưa điền nhãn. Không tự điền AI vào vị trí nhãn chuẩn.

---

# Kết quả mới nhất — 31/10/2026

Đã thử cải tiến theo tiêu chí ptit-v3.1-school-feedback-20261030 sau khi người phụ trách chốt đủ 36/36 câu. Chưa có bản mới đủ chất lượng để đưa vào chức năng tự động. Không phát sinh phí API; chỉ dùng thư viện và Gemma đã cài trên máy.

Bộ nhãn hiện tại: 476 nhãn người dùng (64 toxic, 412 non-toxic), gồm 450 câu Excel (60 toxic, 390 non-toxic) và 26 câu duyệt trước. Không sửa nhãn người dùng hay dữ liệu crawl trong lần thử này.

## Thử mô hình kết hợp

hybrid_labeling.py kết hợp TF-IDF ký tự/từ, bình luận cha khi có và điểm ONNX. Giữ nguyên danh sách 340 câu phát triển và 110 câu đối chiếu từ lần trước; chia theo bài viết. Tham số chọn bằng cross-validation theo bài viết chỉ trên tập phát triển, vectorizer học riêng từng fold.

| Trên 110 câu đối chiếu | ONNX hiện tại | Mô hình kết hợp |
|---|---:|---:|
| Đúng tổng | 61/110 | 70/110 |
| Toxic phát hiện | 7/15 | 6/15 |
| Toxic bỏ sót | 8/15 | 9/15 |
| Non-toxic bị gán toxic | 41/95 | 31/95 |
| Macro F1 | 0.4551 | 0.4963 |

Không đưa vào ứng dụng vì giảm khả năng phát hiện toxic. Kết quả chi tiết: data/label_audit/hybrid_v31/evaluation.json. Đây là tập khó đã xem từ trước, không phải kiểm chứng độc lập hay đại diện cho toàn bộ 5.111 câu.

## Thử Gemma hiểu ngữ cảnh

semantic_v31.py chạy gemma3:4b cục bộ, kèm tiêu chí mới và 6 ví dụ truy hồi từ tập phát triển; loại ví dụ cùng bài viết với câu cần xét. Chọn 20 câu chẩn đoán trong tập đối chiếu bằng hash ID cố định, không chọn theo nhãn. Có 2 toxic và 18 non-toxic. Không dùng nhãn đối chiếu làm ví dụ.

Lượt đầu có nhiều lỗi bằng chứng; đã sửa chỉ dẫn định dạng, giữ lại kết quả đầu và chạy lại cùng 20 câu để chẩn đoán kỹ thuật. Lượt sau: 14 câu cho nhãn hợp lệ, trong đó 6 đúng và 8 sai (7 gán toxic nhầm, 1 bỏ sót toxic); 5 câu lỗi định dạng/bằng chứng và 1 câu mô hình chủ động trả chưa rõ. Lỗi kỹ thuật được ghi riêng, không tính thành non-toxic hoặc thiếu ngữ cảnh. Kết quả này không đạt, không triển khai. Mô hình vẫn hiểu nhầm cải thiện điểm môn học thành chê chất lượng giảng dạy.

Chi tiết có đầu ra thô: data/label_audit/semantic_v31/diagnostic_20_schema2.json; thống kê: data/label_audit/semantic_v31/summary.json. Đây chỉ là chẩn đoán nhỏ, đã thử lại trên cùng câu; không suy rộng thành độ chính xác toàn bộ dữ liệu.

## Kiểm tra và việc tiếp theo

79 kiểm tra hồi quy chạy đạt trong lần này. Không tạo file test tạm. Hash nguồn và bộ 450 nhãn khớp trước thử nghiệm. Không tích hợp hai thử nghiệm vào chức năng tự động, không ghi đè workspace bằng dự đoán.

Hướng tiếp theo là bổ sung dữ liệu đã duyệt đại diện theo bài viết và các ví dụ sát ranh giới góp ý/chê bai, mỉa mai/yêu cầu dừng; dành riêng một tập kiểm chứng mới, không dùng để chọn mô hình hay sửa prompt. Chưa có bằng chứng gán đúng toàn bộ 5.111 câu và không thể dùng các thử nghiệm thất bại này làm nhãn chuẩn.

---

# Lịch sử ngày 30/10/2026

Các số liệu bên dưới thuộc những thời điểm trước đó; dùng phần kết quả mới nhất ở trên để biết trạng thái hiện tại.

> Đã chốt đủ 36/36 câu rà theo tiêu chí v3.1; B306, B359, B445 giữ non-toxic theo trả lời 19–21. Đã đối chiếu nhãn trong hồ sơ với workspace. Bộ Excel 450 câu: 60 toxic, 390 non-toxic. Chưa có kết quả kiểm thử mô hình mới theo bộ nhãn sau rà soát.

> Đã xác nhận non-toxic cho 18 câu số 1–18 trong danh sách 21 câu còn lại; giữ nguyên n. Ba câu B306, B359, B445 còn chờ trả lời.

> B223 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B59 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B141 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B112 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B106 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B201 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B209 đã được người phụ trách xác nhận lại non-toxic theo tiêu chí mới; giữ nguyên n.

> B208 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B383 đã được người phụ trách xác nhận toxic, đổi thành t trong Excel và workspace. Bộ 450 câu hiện có 60 toxic, 390 non-toxic.

> B388 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B336 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B119 đã được người phụ trách xác nhận non-toxic; giữ nguyên n.

> B334 đã sửa thành toxic theo xác nhận người phụ trách, đồng bộ Excel và workspace. Bộ 450 câu hiện có 59 toxic, 391 non-toxic. Kết quả mô hình cũ là lịch sử trước lần sửa nhãn này.

> B256 đã được người phụ trách xác nhận non-toxic: chưa có ý chê trường; giữ nguyên nhãn n.

> Làm rõ v3.1: B102 là góp ý có lý do cụ thể (dốc, khó đi), người phụ trách xác nhận non-toxic. Không áp dụng máy móc quy tắc mọi lời chê trường đều toxic; cần phân biệt góp ý với chê bai/công kích.

> Cập nhật tiêu chí v3: người phụ trách quy định bình luận chê trường là toxic, gồm “Học phí đắt vcl”. Các kết quả dưới đây dùng nhãn v2, chưa đánh giá theo v3. Cần rà lại nhãn trước khi huấn luyện tiếp. Danh sách ứng viên: data/manual_review/policy_v3_review_queue.json; từ khóa chỉ dùng tìm câu cần đọc, không phải quy tắc tự gán toxic.

# Cải tiến gán nhãn — 30/10/2026

Đã nạp 476 nhãn người dùng xác nhận vào data/workspace.json (62 toxic, 414 non-toxic), đối chiếu mã và hash văn bản; không sửa data/progress.json. 450 nhãn Excel và 26 nhãn duyệt trước đó. Chức năng tự động hiện tại chỉ xử lý câu chưa có nhãn nên giữ nguyên các nhãn này. Đây là xác nhận người dùng, không bảo đảm đúng tuyệt đối.

## Thử nghiệm miễn phí

learned_labeling.py dùng TF-IDF ký tự/từ và Logistic Regression, thử có/không bình luận cha. Không gọi API trả phí. 340 câu phát triển, 110 câu kiểm thử; chia theo post_id, không để cùng bài viết ở hai tập. Các ngưỡng/tham số được chọn bằng cross-validation theo bài viết chỉ trên tập phát triển. Vectorizer cũng chỉ học trong từng fold. Đã lưu danh sách ID và kết quả trong data/label_audit/learned_review/evaluation.json.

| Trên 110 câu kiểm thử | Mô hình cũ | Mô hình thử |
|---|---:|---:|
| Đúng tổng | 61 | 77 |
| Toxic phát hiện / 15 | 7 | 3 |
| Toxic bỏ sót | 8 | 12 |
| Non-toxic bị gán toxic / 95 | 41 | 21 |
| Macro F1 | 0.4551 | 0.4858 |

Không đưa mô hình thử vào chức năng chính vì giảm recall toxic. Tăng ngưỡng mô hình cũ lên 0.975 (chọn trên tập phát triển) cho 89/110 đúng nhưng chỉ phát hiện 2/15 toxic: cũng không đạt. Không dùng accuracy tổng làm tiêu chí duy nhất.

Đây là 450 câu được chọn vì khó, không phải mẫu đại diện 5.111 câu. Tập kiểm thử đã được xem kết quả; phải giữ nguyên và không dùng nó để chọn các lần cải tiến sau. Cần một tập kiểm chứng mới trước khi tuyên bố chất lượng bản triển khai.

## Các điểm về tiêu chí

Giữ nguyên tất cả lựa chọn người dùng. B305, B307, B148 được xác nhận toxic dù có thể đọc là phàn nàn/khuyến nghị về trường; B178 non-toxic dù có thể đọc là chế giễu cơ thể. B218 toxic và B219 non-toxic với cùng bình luận cha. Người phụ trách đã giải thích: B218 là mỉa mai người đối thoại; B219 là nhắc người đối thoại dừng cách nói chuyện với mình. Cặp này đã được làm rõ, giữ nguyên hai nhãn. Các ví dụ này được lưu trong confirmation_history; không tự mở rộng thành quy tắc mọi lời chê trường đều toxic hoặc mọi lời chế giễu đều non-toxic. Cặp B218/B219 đã có giải thích; các trường hợp còn lại cần làm rõ tiêu chí trước khi huấn luyện mô hình ngữ nghĩa theo bộ nhãn này.

## Kiểm tra

79 kiểm tra hồi quy chạy thành công, 1 bỏ qua; kiểm tra nhập nhãn xác nhận 476 nhãn khớp nội dung, không thêm bình luận, nguồn crawl không đổi. Không tạo file test tạm.

## Việc tiếp theo

Làm rõ các ranh giới nhãn nêu trên và xây dựng tập kiểm chứng đại diện được lấy ngẫu nhiên theo bài viết. Mô hình thử hiện chỉ là nghiên cứu, chưa tích hợp và không có bằng chứng gán đúng toàn bộ 5.111 câu.


## Rà soát nhãn ngày 01/11/2026 — danh sách cần quyết định

Đã xuất 18 câu cần quyết định kèm ngữ cảnh tại `outputs/label_review_selection_20261101/can_quyet_dinh.md`. Chuẩn bị mẫu cố định 300 câu từ nhóm máy gán non-toxic và toàn bộ 106 câu máy gán toxic để kiểm tra chất lượng nhãn. Chưa thay đổi nhãn. Xem `outputs/label_review_selection_20261101/HUONG_DAN.md` để biết phạm vi, cách kiểm tra và giới hạn.


### Đã nhận 18 quyết định từ người phụ trách

Đã lưu 4 toxic / 14 non-toxic, chuyển cả 18 từ nhãn máy sang nhãn người xác nhận; sửa 6 nhãn toxic thành non-toxic. Tổng hiện tại: 5111 câu, 214 toxic (4,19%) và 4897 non-toxic. Người xác nhận: 964 câu; nhãn máy còn lại: 4147 câu. Đã kiểm tra dữ liệu gốc, nhãn ngoài phạm vi và số lượng chất lượng không đổi. Có bản sao workspace trước thay đổi và nhật ký tại `outputs/label_review_selection_20261101/user_decisions.json`. Các bộ kiểm tra ngẫu nhiên đã chốt trước đó giữ nguyên; câu trùng với 18 quyết định không còn được coi là kiểm tra mù độc lập. Chưa huấn luyện lại mô hình; các bản xuất và manifest cũ là ảnh chụp lịch sử.


### Xác nhận mẫu ngẫu nhiên 300 câu — 01/11/2026

Đã nhận xác nhận 300/300 câu non-toxic. Phát hiện 0 toxic trong mẫu; sửa 0 nhãn; thêm 300 nhãn người xác nhận. Tổng nhãn: {'non-toxic': 4897, 'toxic': 214}; người xác nhận: {'non-toxic': 1146, 'toxic': 118}; nhãn máy: {'non-toxic': 3751, 'toxic': 96}. Không suy ra độ chính xác 100% toàn bộ dữ liệu; chưa huấn luyện lại.


### Cập nhật hai câu trong danh sách 96

Đã chuyển câu 4 và 22 thành non-toxic theo xác nhận trực tiếp; chưa coi 94 câu còn lại là đã được xác nhận. Tổng 212 toxic / 4899 non-toxic; nhãn người xác nhận 1266, nhãn máy 3845. Đã kiểm tra nhãn ngoài phạm vi và dữ liệu gốc không đổi.


### Hoàn tất duyệt 96 câu máy gán toxic

Đã xác nhận 94 câu còn lại là toxic; hoàn tất duyệt danh sách 96 câu (94 t, 2 n). Tổng 5111 câu: 212 toxic (4,15%), 4899 non-toxic. Người xác nhận: 1360 câu (212 t, 1148 n). Máy chưa được người xác nhận: 3751 câu, đều đang mang nhãn non-toxic. Mẫu ngẫu nhiên 300 câu có 0 toxic được người duyệt phát hiện; kết quả không chứng minh 3751 nhãn máy còn lại đều đúng. Chưa huấn luyện lại mô hình.


## Chính sách hiện hành 02/11/2026 — v4

Người phụ trách đã bỏ quy tắc chê trường là toxic. Áp dụng QUY_TAC_GAN_NHAN.md v4; các nội dung v3 trong báo cáo này là lịch sử. Đã cập nhật prompt bộ lọc thu thập và phiên bản bộ phân loại ngữ nghĩa. Nhãn cũ, mô hình NB/SVM và các thử nghiệm v3 chưa tự trở thành tương thích v4; cần rà lại dữ liệu trước khi huấn luyện/đánh giá. Không đổi nhãn hàng loạt trong bước cập nhật chính sách. Phiên thu thập đang chạy cần khởi động lại để nạp chính sách mới.
