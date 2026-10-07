# Báo Cáo Lab Day 21 - CI/CD cho AI Systems

<!--
HƯỚNG DẪN - đọc rồi XÓA TOÀN BỘ các khối chú thích này sau khi điền xong:

  - Giới hạn: KHÔNG QUÁ 1 TRANG A4, tương đương khoảng 450 - 550 từ nội dung.
  - Chỉ điền vào các chỗ ___ và các ô trong bảng. Không thêm mục mới.
  - Viết bằng câu hoàn chỉnh, không gạch đầu dòng cụt lủn.
  - Kiểm tra độ dài sau khi đã xóa hết chú thích:
        wc -w nop-bai/bao-cao.md
    và xem trước bản in bằng cách mở file trên GitHub rồi Ctrl+P / Cmd+P.
-->

| | |
|---|---|
| Họ và tên | ___ |
| MSSV | ___ |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/___/___ |
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

<!-- Nêu 2 - 3 khó khăn thật, mỗi ô một câu ngắn. -->

| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| ___ | ___ | ___ |
| ___ | ___ | ___ |
| ___ | ___ | ___ |

---

## 4. So Sánh Bước 2 và Bước 3 (bắt buộc, 2 - 3 câu)

<!-- Lấy số liệu từ bảng ở mục 3.6 của tasks/buoc-3.md. -->

| | f1_score | accuracy |
|---|---|---|
| Bước 2 (chỉ `train_batch1`) | Chưa chạy trên cloud | Chưa chạy trên cloud |
| Bước 3 (thêm `train_batch2`) | Chưa chạy trên cloud | Chưa chạy trên cloud |

**Nhận xét:** Chưa có kết quả GitHub Actions để so sánh. Cần cấu hình GCS remote, secrets và VM, sau đó lấy số liệu từ artifact của hai lần chạy; không suy diễn rằng thêm dữ liệu chắc chắn làm F1 tăng.

<!--
Một câu trả lời trung thực kiểu "f1 giảm 0,01 vì dữ liệu mới cùng phân phối, không mang
thêm thông tin mới" được đánh giá cao hơn kết luận sai rằng thêm dữ liệu luôn tốt hơn.
-->

---

## 5. Phần Bonus Đã Thực Hiện (nếu có)

<!-- Xóa cả mục 5 nếu không làm bonus. Mỗi bonus tối đa 1 dòng. -->

- [ ] Bonus 1 - Tracking MLflow từ xa với DagsHub: ___
- [ ] Bonus 2 - Điều chỉnh ngưỡng quyết định: ___
- [ ] Bonus 3 - Báo cáo precision / recall tự động: ___
- [ ] Bonus 4 - Hoàn trả về phiên bản trước: ___
- [ ] Bonus 5 - Cảnh báo lệch lạc dữ liệu: ___
