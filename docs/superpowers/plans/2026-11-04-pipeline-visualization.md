# Pipeline visualization implementation plan
Goal: Minh họa và xuất video dự đoán thật.
Architecture: trace trả cùng API predict; trình duyệt điều khiển các bước và ghi canvas.
Tech Stack: Python, sklearn, JavaScript Canvas/MediaRecorder.
Spec: ../specs/2026-11-04-pipeline-visualization-design.md
Global Constraints: miễn phí, không sửa dataset/artifact; xóa test tạm.
Review Focus: nhánh chuẩn hóa, điểm/ngưỡng thật, dữ liệu cũ, XSS.
- [x] Test trace với mô hình nhỏ trước khi triển khai.
- [x] Tạo trace, nối API và giao diện.
- [x] Kiểm thử và xóa test tạm.

Validation: 21 tests.test_project passed; trace fixture passed; prediction + trace checked on saved BoW-NB, BoW-SVM, TF-IDF-NB, TF-IDF-SVM. JS syntax and mocked DOM navigation/reset/text safety passed. Browser MCP could not connect localhost; actual WebM playback/export and ViSoBERT trace remain unverified.
