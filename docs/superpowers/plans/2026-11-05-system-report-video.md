# Video báo cáo hệ thống — kế hoạch thực thi

Goal: MP4 dựng sẵn 5–7 phút, năm artifact thật và hai ví dụ cố định, phát trực tiếp.
Architecture: evidence bất biến → renderer Pillow/FFmpeg → cache nguyên tử → HTTP Range/player.
Tech stack: Python, sklearn, torch/transformers, Pillow, imageio/FFmpeg, JavaScript thuần.
Spec: ../specs/2026-11-04-system-report-video-design.md

Constraints: không sửa dữ liệu/nhãn, không sửa test1.py, không dịch vụ phí, không lưu test tạm.
Review focus: phép tính thật; nhánh ký tự; tokenizer riêng; cache restart/lỗi/run mới; đọc được.

- [x] system_report_video.py: evidence NB/SVM/ViSoBERT, snapshot và cache một worker.
- [x] report_animation.py: storyboard 5–7 phút, hoạt hình token/vector/tầng mạng/so sánh.
- [x] app.py, lab.py, index.html, report-video.js: enqueue sau train/khởi động, player/mục lục.
- [x] Kiểm tra toán với artifact, vòng đời cache, toàn bộ suite; dựng MP4, xem frame/preview.

Ledger: thực thi tại workspace đang có thay đổi của người dùng; không commit hoặc tạo checkout khác.
RED: import module mới phải thất bại trước triển khai. Kiểm thử bổ sung dùng stdin, không file test tồn dư.

Verification 2026-11-05: 83 unittest, 82 pass / 1 skip (37.496 s); JS syntax and py_compile pass. Real artifact arithmetic and cache restart/failure/retry/latest-worker tests pass. Temporary fixtures removed. MP4: 354.125 s, 1280x720, 24 fps, 12,721,759 bytes, 23 chapters; decoded start/middle/end frames reviewed. Browser: metadata loaded, Range 206 / 1024 bytes, chapter seek and playback verified. Ready cache ID e2d7131fd4b87a7e64fc34bde6d0bd16f305b1075e8fad341ebda59950350deb.
