# Kết quả gán lại v4

{
  "completed_at": "2026-11-03T01:11:24.044659+00:00",
  "policy_version": "ptit-v4-abuse-context-20261102",
  "total": 6658,
  "active": 5147,
  "removed_from_active": 1511,
  "usable": 4559,
  "labels": {
    "non-toxic": 4159,
    "toxic": 400
  },
  "quality": {
    "ready": 4559,
    "excluded": 1499,
    "duplicate": 588,
    "conflict": 12
  },
  "changed": 1118,
  "human_verified": false
}

Nhãn được mô hình cục bộ gán tự động, chưa phải bộ nhãn chuẩn do người duyệt. Tệp dataset_v4 chỉ chứa mẫu dùng được; excluded_v4 lưu các mẫu bị loại và lý do. Mô hình NB/SVM và đánh giá cũ cần chạy lại với ranh giới chia tập mới.
