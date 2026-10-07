# Báo Cáo Lab Day 21 - CI/CD cho AI Systems


| | |
|---|---|
| Họ và tên | Trần Hoàng Duy Anh |
| MSSV | 2A202602558 |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/Josee0801/K4-L3L4-Track2-Day21-TranHoangDuyAnh-2A202602558-CI-CD-for-AI-Systems |
| Ngày nộp | 2026-10-07 |

---

## 1. Bộ Siêu Tham Số Đã Chọn và Lý Do

| Lần chạy | n_estimators | learning_rate | max_depth | f1_score | accuracy |
|---|---|---|---|---|---|
| 1 | 100 | 0.1 | 3 | 0.7109 | 0.8780 |
| 2 | 50 | 0.05 | 2 | 0.6051 | 0.8460 |
| 3 | 200 | 0.1 | 5 | 0.7149 | 0.8740 |

**Bộ siêu tham số đã chọn:** `n_estimators=200`, `learning_rate=0.1`, `max_depth=5`.

**Lý do:** Cấu hình lần 3 đạt F1 cao nhất (0.7149), vượt ngưỡng 0.65; cấu hình lần 2 không đạt ngưỡng. Accuracy cao nhất thuộc lần 1 (0.8780), không trùng lần có F1 cao nhất. Điều này cho thấy accuracy không phản ánh đầy đủ khả năng nhận diện lớp thu nhập cao; cấu hình cần được chọn theo F1 của lớp dương.

---

## 2. Vì Sao Ngưỡng Chất Lượng Đặt Trên F1 Chứ Không Phải Accuracy

Trong dữ liệu, khoảng 24,8% mẫu thuộc lớp thu nhập trên 50.000 USD. Mô hình luôn dự đoán “thu nhập thấp” vẫn đạt accuracy khoảng 0,752 nhưng bỏ sót toàn bộ lớp thu nhập cao, nên F1 của lớp dương bằng 0. F1 cân bằng precision và recall cho chính lớp cần phát hiện; vì vậy lab dùng `f1_score(y_true, y_pred)` mặc định cho lớp 1, không dùng weighted hoặc macro average vốn có thể bị lớp đa số chi phối và làm quality gate kém ý nghĩa.

---

## 3. Khó Khăn Gặp Phải và Cách Giải Quyết


| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| Không tạo được bucket S3 | User IAM thiếu quyền `s3:CreateBucket` | Được cấp thêm quyền, rồi tạo bucket và bật Block Public Access |
| GitHub Actions không assume được role AWS | Secret `AWS_ROLE_ARN` sai định dạng, sau đó trust policy chưa khớp `sub` của repo | Dán đúng ARN đầy đủ và thêm `sub` dạng immutable vào trust policy |
| SSM không thấy EC2 để deploy | Role EC2 thiếu `AmazonSSMManagedInstanceCore` | Gắn policy rồi khởi động lại SSM Agent |

---

## 4. So Sánh Bước 2 và Bước 3 (bắt buộc, 2 - 3 câu)


| | f1_score | accuracy |
|---|---|---|
| Bước 2 (chỉ `train_batch1`) | 0.7149 | 0.8740 |
| Bước 3 (thêm `train_batch2`) | 0.7354 | 0.8820 |

**Nhận xét:** Sau khi thêm `train_batch2`, số mẫu huấn luyện tăng gấp đôi (22.361 lên 44.722) và F1 tăng từ 0.7149 lên 0.7354 (accuracy từ 0.874 lên 0.882), cùng chạy trên GitHub Actions và đều vượt ngưỡng 0.65. Mức tăng khoảng 0.02 cho thấy dữ liệu mới có ích, nhưng chỉ là một lần chạy trên một tập holdout nên chưa đủ để kết luận thêm dữ liệu luôn cải thiện mô hình.
