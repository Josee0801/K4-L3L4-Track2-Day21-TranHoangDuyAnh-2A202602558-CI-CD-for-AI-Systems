# Lab MLOps Thực Hành: Từ Thực Nghiệm Cục Bộ Đến Triển Khai Liên Tục

Course: AIInAction - VinUni
Buổi: Day 21 - CI/CD cho AI Systems
Khoá: K4

---

## Mục Tiêu Học Tập

Sau khi hoàn thành lab này, bạn có khả năng:

1. Thiết lập quá trình theo dõi thí nghiệm máy học bằng MLflow trên máy tính cá nhân.
2. Quản lý và phiên bản hóa dữ liệu bằng DVC với Amazon S3 làm remote.
3. Xây dựng pipeline CI/CD hoàn chỉnh trên GitHub Actions với bốn giai đoạn: kiểm thử, huấn luyện, kiểm tra chất lượng, triển khai.
4. Triển khai mô hình lên máy chủ ảo trên cloud (GCE / EC2 / Azure VM) dưới dạng REST API bằng FastAPI.
5. Chọn đúng chỉ số đánh giá cho bài toán có phân bố lớp mất cân bằng.
6. Mô phỏng quy trình huấn luyện liên tục: bổ sung dữ liệu mới và kích hoạt pipeline hoàn toàn tự động.

---

## Tổng Quan Kiến Trúc

Toàn bộ lab được triển khai theo ba bước liên tiếp, mỗi bước xây dựng trên kết quả của bước trước:

```
[Máy tính cá nhân]
      |
      |  git push
      v
[GitHub repository]
      |
      |  GitHub Actions kích hoạt tự động
      v
[Runner: Unit Test -> Train -> Quality Gate (f1 >= 0.65) -> Release]
      |                                          |
      |  dvc pull                                |  upload model
      v                                          v
[Cloud Object Storage]                      [Cloud VM]
  data/                                       income-api (FastAPI)
  artifacts/current/                            POST /score
```

Bước 1 chỉ chạy trên máy tính cá nhân. Bước 2 và Bước 3 sử dụng toàn bộ kiến trúc trên.

---

## Yêu Cầu Trước Khi Bắt Đầu

Phần mềm cần cài đặt trên máy tính cá nhân:

- Python 3.10 trở lên
- Git và tài khoản GitHub
- Tài khoản AWS và AWS CLI v2 đã cấu hình quyền truy cập (xem hướng dẫn tại
  [tasks/buoc-2-aws.md](tasks/buoc-2-aws.md)).
- Repo này được cấu hình cho AWS: Amazon S3/DVC, GitHub Actions OIDC, EC2 và
  Systems Manager Run Command.

Kiểm tra cài đặt:

```bash
python --version     # Python 3.10.x trở lên
git --version
aws --version
```

---

## Tập Dữ Liệu

Tập dữ liệu **Adult / Census Income** (UCI Machine Learning Repository) chứa thông tin nhân khẩu học và nghề nghiệp trích từ điều tra dân số Hoa Kỳ năm 1994. Nhiệm vụ là dự đoán một người có thu nhập trên 50.000 USD mỗi năm hay không.

Nguồn: https://archive.ics.uci.edu/dataset/2/adult

Bộ dữ liệu gốc gồm 48.842 mẫu. Sau khi loại bỏ các dòng thiếu giá trị (đánh dấu bằng `?` trong file gốc), còn lại **45.222 mẫu**.

Đặc trưng đầu vào (10 cột, đều là số sau khi `prepare_data.py` mã hóa sẵn):

| Tên cột | Mô tả | Miền giá trị |
|---|---|---|
| age | Tuổi | 17 - 90 |
| workclass | Nhóm nghề nghiệp (đã mã hóa) | 0 - 6 |
| education_num | Số năm học quy đổi | 1 - 16 |
| marital_status | Tình trạng hôn nhân (đã mã hóa) | 0 - 6 |
| occupation | Ngành nghề (đã mã hóa) | 0 - 13 |
| relationship | Vai trò trong hộ gia đình (đã mã hóa) | 0 - 5 |
| sex | Giới tính | 0 = Nữ, 1 = Nam |
| capital_gain | Thu nhập từ vốn | 0 - 99999 |
| capital_loss | Lỗ từ vốn | 0 - 4356 |
| hours_per_week | Số giờ làm việc mỗi tuần | 1 - 99 |

Nhãn dự đoán (cột `target`):

| Giá trị | Ý nghĩa | Nhãn trả về bởi API |
|---|---|---|
| 0 | Thu nhập <= 50K USD/năm | `thu_nhap_thap` |
| 1 | Thu nhập > 50K USD/năm | `thu_nhap_cao` |

### Bảng giải mã các cột phân loại

`prepare_data.py` mã hóa các cột dạng chuỗi thành số nguyên **theo thứ tự bảng chữ cái**. Bạn không cần tự mã hóa, nhưng cần bảng này để đọc hiểu dữ liệu và tự tạo payload thử nghiệm:

| Cột | Mã |
|---|---|
| workclass | 0=Federal-gov, 1=Local-gov, 2=Private, 3=Self-emp-inc, 4=Self-emp-not-inc, 5=State-gov, 6=Without-pay |
| marital_status | 0=Divorced, 1=Married-AF-spouse, 2=Married-civ-spouse, 3=Married-spouse-absent, 4=Never-married, 5=Separated, 6=Widowed |
| occupation | 0=Adm-clerical, 1=Armed-Forces, 2=Craft-repair, 3=Exec-managerial, 4=Farming-fishing, 5=Handlers-cleaners, 6=Machine-op-inspct, 7=Other-service, 8=Priv-house-serv, 9=Prof-specialty, 10=Protective-serv, 11=Sales, 12=Tech-support, 13=Transport-moving |
| relationship | 0=Husband, 1=Not-in-family, 2=Other-relative, 3=Own-child, 4=Unmarried, 5=Wife |
| sex | 0=Female, 1=Male |

### Vì sao lab này dùng F1 thay vì Accuracy

Chỉ **24,8%** số mẫu thuộc lớp thu nhập cao. Một mô hình vô dụng, luôn trả lời "thu nhập thấp" cho mọi đầu vào, vẫn đạt accuracy **0,752**.

Vì vậy ngưỡng chất lượng của lab này đặt trên `f1_score` của lớp dương (thu nhập > 50K), không phải accuracy. Đây là quyết định thiết kế quan trọng nhất của bài, và bạn sẽ gặp lại nó trong mọi bài toán phân loại mất cân bằng ngoài thực tế.

### Phân chia dữ liệu

| File | Số mẫu | Mục đích |
|---|---|---|
| data/train_batch1.csv | 22.361 | Huấn luyện ở Bước 1 và 2 |
| data/holdout.csv | 500 | Đánh giá mô hình (không bao giờ dùng để huấn luyện) |
| data/train_batch2.csv | 22.361 | Dữ liệu mới bổ sung ở Bước 3 |

Chạy script sau một lần duy nhất để tải và chia dữ liệu:

```bash
python prepare_data.py
```

Kết quả mong đợi:

```
train_batch1.csv : 22361 mau
holdout.csv      : 500 mau
train_batch2.csv : 22361 mau
Ty le lop >50K   : 24.8%
```

---

## Cấu Trúc Thư Mục

Cấu trúc này là kết quả cuối cùng sau khi hoàn thành cả ba bước:

```
<thu-muc-goc-cua-repo>/
├── .github/
│   └── workflows/
│       └── cicd.yml           <- Pipeline CI/CD (Bước 2)
├── .dvc/
│   └── config                 <- Cấu hình DVC remote (Bước 2)
├── data/
│   ├── train_batch1.csv.dvc   <- Con trỏ DVC (Bước 2)
│   ├── holdout.csv.dvc
│   └── train_batch2.csv.dvc
├── src/
│   ├── __init__.py
│   ├── train.py               <- Script huấn luyện (Bước 1)
│   └── serve.py               <- API suy luận (Bước 2)
├── tests/
│   ├── __init__.py
│   └── test_train.py          <- Unit test (Bước 2)
├── nop-bai/                   <- Bằng chứng nộp bài (đã cung cấp sẵn khung)
│   ├── bao-cao.md             <- Template báo cáo, không quá 1 trang A4
│   └── anh-chup-man-hinh/     <- Chuỗi ảnh 01 -> 05 theo thứ tự
├── prepare_data.py            <- Script tạo dữ liệu (đã cung cấp)
├── append_batch.py            <- Script thêm dữ liệu mới (đã cung cấp)
├── params.yaml                <- Siêu tham số mô hình
├── requirements.txt           <- Thư viện Python
└── .gitignore
```

---

## Cài Đặt Môi Trường

### Bước chuẩn bị (thực hiện một lần)

```bash
# 1. Clone hoặc khởi tạo repo của bạn
git clone <URL_REPO_CUA_BAN>
cd <TEN_THU_MUC_REPO>          # thư mục vừa được clone ra

# 2. Tạo và kích hoạt môi trường ảo
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows

# 3. Cài đặt thư viện
pip install -r requirements.txt

# 4. Tải dữ liệu
python prepare_data.py
```

### `.gitignore`

```
mlflow.db
mlartifacts/
models/
outputs/
data/train_batch1.csv
data/holdout.csv
data/train_batch2.csv
sa-key.json
.env
.venv/
__pycache__/
```

### `requirements.txt`

```
mlflow==2.13.0
scikit-learn==1.4.2
pandas==2.2.2
# DVC S3 remote
dvc[s3]==3.50.1
pathspec==0.11.2
pytest==8.2.0
fastapi==0.111.0
uvicorn==0.29.0
joblib==1.4.2
boto3==1.34.131
pyyaml==6.0.1
```

---

## Hướng Dẫn Lab

| Bước | Nội dung | File hướng dẫn |
|---|---|---|
| 1 | Thực nghiệm cục bộ và theo dõi bằng MLflow | tasks/buoc-1.md |
| 2 | Pipeline CI/CD tự động với GitHub Actions, DVC, AWS S3 và EC2 | [tasks/buoc-2-aws.md](tasks/buoc-2-aws.md) |
| 3 | Huấn luyện liên tục khi có dữ liệu mới | tasks/buoc-3.md |

Bắt đầu từ [Bước 1](tasks/buoc-1.md).

---

## Rubric Chấm Điểm

### Tiêu chí chính (80 điểm)

| Hạng mục | Tiêu chí đánh giá | Điểm tối đa |
|---|---|---|
| Bước 1 - MLflow tracking | MLflow UI hiển thị ít nhất 3 lần chạy với các siêu tham số khác nhau | 12 |
| Bước 1 - Độ đo | Mỗi lần chạy ghi nhận đủ cả `f1_score` và `accuracy` | 8 |
| Bước 1 - Phân tích | Xác định bộ siêu tham số tốt nhất và giải thích vì sao dùng F1 thay vì accuracy | 4 |
| Bước 2 - DVC | Remote đã cấu hình, `dvc push` thành công, dữ liệu hiển thị trên cloud storage | 12 |
| Bước 2 - CI/CD | Cả bốn GitHub Actions jobs (Unit Test, Train, Quality Gate, Release) đều qua (màu xanh) | 16 |
| Bước 2 - Quality gate | Release job tự động bị chặn khi f1_score dưới ngưỡng 0.65 | 4 |
| Bước 2 - Serving | VM trả về kết quả đúng tại endpoint POST /score | 12 |
| Bước 3 - Tự động hóa | Một commit dữ liệu mới kích hoạt toàn bộ pipeline không cần tác động thủ công | 12 |
| Tổng | | 80 |

### Thang điểm chi tiết

| Khoảng điểm | Nhận xét |
|---|---|
| 90 - 100 | Xuất sắc. Toàn bộ pipeline hoạt động chính xác, đầy đủ bằng chứng và có điểm bonus. |
| 72 - 89 | Tốt. Hoàn thành toàn bộ tiêu chí chính, có thể còn thiếu một phần bằng chứng. |
| 56 - 71 | Đạt yêu cầu tối thiểu. Hoàn thành được các bước chính nhưng còn lỗi hoặc thiếu bước. |
| Dưới 56 | Chưa đạt. Nhiều phần chưa được thực hiện hoặc không hoạt động. |

### Hướng dẫn nộp bài

Toàn bộ bằng chứng nộp bài nằm trong thư mục [nop-bai/](nop-bai/) — khung thư mục và
template đã có sẵn trong repo, bạn chỉ cần điền vào và commit.

**1. URL repo GitHub công khai** chứa toàn bộ code, cấu hình và thư mục `nop-bai/` đã điền.
Đây là thứ duy nhất bạn nộp: dán link repo vào bài nộp tương ứng trên
**https://vlearn.dev**. Ảnh chụp màn hình và báo cáo được chấm trực tiếp trong repo,
không nộp rời.

**2. Chuỗi chụp màn hình theo thứ tự** — đặt trong [nop-bai/anh-chup-man-hinh/](nop-bai/anh-chup-man-hinh/),
đúng tên file dưới đây (yêu cầu chi tiết của từng ảnh xem tại
[nop-bai/anh-chup-man-hinh/README.md](nop-bai/anh-chup-man-hinh/README.md)):

| Thứ tự | Tên file | Nội dung |
|---|---|---|
| 1 | `01-mlflow-ui.png` | MLflow UI hiển thị ít nhất 3 thí nghiệm, thấy rõ cả `f1_score` và `accuracy` |
| 2 | `02-actions-buoc-2.png` | GitHub Actions tab hiển thị cả bốn jobs màu xanh (Bước 2) |
| 3 | `03-actions-buoc-3.png` | GitHub Actions của lần chạy do commit dữ liệu kích hoạt (Bước 3) |
| 4 | `04-curl-api.png` | Kết quả `curl http://VM_IP:8080/healthz` và `curl http://VM_IP:8080/score` |
| 5 | `05-cloud-storage.png` | Cloud Storage Console hiển thị dữ liệu `dvc/` và model đã upload |

**3. File báo cáo ngắn** (không quá 1 trang A4) — điền vào template
[nop-bai/bao-cao.md](nop-bai/bao-cao.md), gồm:

- Bộ siêu tham số đã chọn và lý do (kết quả Bước 1).
- Giải thích vì sao ngưỡng chất lượng của lab đặt trên F1 chứ không phải accuracy.
- Bất kỳ khó khăn nào gặp phải và cách giải quyết.
- So sánh `f1_score` giữa Bước 2 và Bước 3 kèm nhận xét.

Checklist đầy đủ trước khi nộp: [nop-bai/README.md](nop-bai/README.md).

---

## Thách Thức Nâng Cao (Bonus)

Các thách thức dưới đây không bắt buộc. Hoàn thành đủ cả 5 thách thức sẽ được cộng tối đa 20 điểm, nâng tổng điểm lên 100.

### Bonus 1: Tracking MLflow Từ Xa Với DagsHub (4 điểm)

Thay vì lưu MLflow vào file cục bộ (`sqlite:///mlflow.db`), kết nối đến server MLflow miễn phí trên DagsHub:

- Tạo tài khoản tại https://dagshub.com và kết nối repo GitHub của bạn.
- Thêm các biến môi trường MLflow vào GitHub Secrets.
- Cập nhật `cicd.yml` để sử dụng tracking server của DagsHub thay vì file cục bộ.

Kết quả: Mỗi lần chạy trong GitHub Actions sẽ được ghi lên DagsHub, có thể xem từ bất cứ đâu.

### Bonus 2: Điều Chỉnh Ngưỡng Quyết Định (4 điểm)

`model.predict()` mặc định gán nhãn 1 khi xác suất vượt 0.5. Với dữ liệu mất cân bằng, đây hiếm khi là ngưỡng tối ưu:

- Dùng `model.predict_proba(X_eval)[:, 1]` để lấy xác suất thay vì nhãn.
- Quét ngưỡng từ 0.1 đến 0.9 (bước 0.05), tính `f1_score` tại mỗi ngưỡng.
- Ghi ngưỡng tốt nhất và F1 tương ứng vào `outputs/report.json`, đồng thời log lên MLflow.
- So sánh với F1 tại ngưỡng mặc định 0.5 và nhận xét.

### Bonus 3: Báo Cáo Precision / Recall Tự Động (4 điểm)

Thêm một bước trong `cicd.yml` để tự động tạo báo cáo chi tiết sau mỗi lần huấn luyện:

- Tính confusion matrix và in ra ở dạng văn bản (không cần ảnh).
- Tính `precision` và `recall` riêng cho từng lớp, ghi vào `outputs/detail.txt`.
- Giải thích trong báo cáo: với bài toán này, sai lầm nào tốn kém hơn — bỏ sót người thu nhập cao (recall thấp) hay gán nhầm người thu nhập thấp (precision thấp)?
- Dùng `actions/upload-artifact` để lưu file này cùng với `report.json`.

### Bonus 4: Hoàn Trả Về Phiên Bản Trước (4 điểm)

Xây dựng cơ chế an toàn: nếu model mới có F1 thấp hơn model hiện tại đang chạy, pipeline tự động hủy triển khai:

- Trước khi release, tải `outputs/report.json` của lần chạy trước từ cloud storage (nếu có).
- So sánh F1 mới với F1 cũ.
- Chỉ triển khai khi F1 mới cao hơn hoặc bằng F1 cũ.
- Ghi lại kết quả so sánh vào log của pipeline.

### Bonus 5: Cảnh Báo Lệch Lạc Dữ Liệu (4 điểm)

Thêm bước kiểm tra phân phối dữ liệu trước khi huấn luyện:

- Tính tỷ lệ lớp dương (target = 1) trong tập huấn luyện.
- Nếu tỷ lệ này lệch quá 5 điểm phần trăm so với tỷ lệ tham chiếu 24.8%, in cảnh báo rõ ràng vào log.
- Ghi tỷ lệ lớp dương vào `outputs/report.json` bên cạnh `f1_score` và `accuracy`.

---

## Xử Lý Sự Cố Thường Gặp

Xem phần xử lý sự cố chi tiết trong từng file hướng dẫn:

- Lỗi DVC authentication: tasks/buoc-2.md
- Lỗi GitHub Actions dvc pull: tasks/buoc-2.md
- Pipeline Bước 3 không được kích hoạt: tasks/buoc-3.md
- Service trên VM không khởi động: tasks/buoc-2.md

---

Bắt đầu: [Bước 1 - Thực nghiệm cục bộ](tasks/buoc-1.md)
