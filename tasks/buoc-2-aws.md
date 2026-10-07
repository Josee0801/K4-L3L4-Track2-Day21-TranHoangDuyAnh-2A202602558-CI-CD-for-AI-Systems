# Bước 2 - AWS: S3, GitHub Actions, EC2 và API

Hướng dẫn này dành cho repo hiện tại, đã cấu hình AWS. Pipeline thực hiện:

```text
GitHub Actions -> Unit Test -> DVC pull từ S3 -> Train -> F1 quality gate
               -> Upload model lên S3 -> SSM Run Command restart API trên EC2
```

Pipeline dùng GitHub OIDC để lấy AWS credentials tạm thời, EC2 instance role để
đọc model từ S3, và Systems Manager (SSM) để deploy. Không tạo access key dài hạn
cho GitHub; không chép AWS credentials lên EC2.

## 0. Thay các giá trị mẫu và xác nhận AWS CLI

Mở PowerShell ở thư mục gốc repo. Chọn một AWS Region để dùng nhất quán cho S3,
EC2, IAM OIDC configuration của workflow, và SSM:

```powershell
$AWS_REGION = "us-east-1"
$BUCKET = "income-lab-unique-bucket-name"
$env:AWS_DEFAULT_REGION = $AWS_REGION
```

Tên bucket phải viết thường, duy nhất toàn cầu. Kiểm tra AWS CLI v2 và phiên đăng
nhập hiện tại:

```powershell
aws --version
aws sts get-caller-identity
```

Nếu chưa có credentials, ưu tiên profile AWS IAM Identity Center (SSO):

```powershell
aws configure sso --profile income-lab
aws sso login --profile income-lab
$env:AWS_PROFILE = "income-lab"
aws sts get-caller-identity
```

Identity đang dùng cần quyền tạo bucket, IAM roles/policies, EC2, security groups
và đọc/ghi object S3. Không dùng root user cho công việc thường ngày. Nếu tổ chức
cấp sẵn AWS profile/SSO, dùng profile đó thay vì tạo access key cá nhân.

## 1. Tạo bucket S3 riêng cho lab

Tạo bucket private trong Region bạn đã chọn. Với `us-east-1`:

```powershell
aws s3api create-bucket --bucket $BUCKET --region $AWS_REGION
```

Với Region khác:

```powershell
aws s3api create-bucket --bucket $BUCKET --region $AWS_REGION `
  --create-bucket-configuration "LocationConstraint=$AWS_REGION"
```

Giữ Block Public Access bật và ACL tắt:

```powershell
aws s3api put-public-access-block --bucket $BUCKET `
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
aws s3api put-bucket-ownership-controls --bucket $BUCKET `
  --ownership-controls "Rules=[{ObjectOwnership=BucketOwnerEnforced}]"
```

S3 tự mã hóa object mới bằng SSE-S3 theo mặc định. Dùng một bucket chỉ cho lab,
không thêm public bucket policy, và chỉ cấp IAM quyền trên đúng bucket/prefix.
S3 tính phí theo dung lượng lưu, request và truyền dữ liệu; xem [S3 pricing](https://aws.amazon.com/s3/pricing/).

## 2. Chuẩn bị quyền S3 cho DVC chạy trên máy cá nhân

IAM identity mà AWS CLI đang dùng cần các quyền sau trên bucket này:

- `s3:ListBucket` trên `arn:aws:s3:::<BUCKET>`.
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` trên
  `arn:aws:s3:::<BUCKET>/dvc/*`.

Nhờ administrator hoặc AWS IAM Identity Center administrator gắn policy giới
hạn như trên vào permission set/role của bạn. Không cần quyền `s3:*` hay quyền
xóa bucket. Nếu policy vừa cập nhật, đăng nhập lại bằng SSO rồi xác minh:

```powershell
aws sts get-caller-identity
aws s3api head-bucket --bucket $BUCKET
```

`dvc push` cần quyền ghi và xóa object trong prefix DVC; `dvc pull` cần quyền đọc
và liệt kê. GitHub Actions sẽ dùng IAM role khác với quyền riêng, ở mục 5.

## 3. Cấu hình DVC remote và upload data

Thực hiện trong repo, với `$env:AWS_PROFILE` và `$env:AWS_DEFAULT_REGION` đang
được đặt đúng:

```powershell
dvc remote add --force -d labstore "s3://$BUCKET/dvc"
dvc remote modify labstore region $AWS_REGION
dvc add data/train_batch1.csv
dvc add data/holdout.csv
dvc add data/train_batch2.csv
dvc push
dvc status
dvc status -c
```

`dvc remote add` lưu URL bucket, không lưu secret. Nếu dùng profile khác với
`default`, có thể đặt `$env:AWS_PROFILE = "income-lab"` trong PowerShell trước
khi chạy DVC; không ghi access key vào `.dvc/config`.

Kiểm tra trên S3 Console hoặc AWS CLI:

```powershell
aws s3 ls "s3://$BUCKET/dvc/" --recursive
```

Trong Git chỉ commit các file `.dvc`, `.dvc/config` và `.dvcignore`; không commit
CSV. DVC có thể ghi credentials cục bộ vào `.dvc/config.local`; file đó không
được commit.

## 4. Tạo IAM role cho ứng dụng EC2

Trong AWS Console → **IAM → Roles → Create role**:

1. Trusted entity type: **AWS service**; use case **EC2**.
2. Tạo role `IncomeLabEc2Role`.
3. Gắn AWS managed policy `AmazonSSMManagedInstanceCore` để EC2 xuất hiện dưới
   **Systems Manager → Fleet Manager / Managed nodes** và nhận lệnh SSM.
4. Thêm inline permission policy cho phép model được đọc, chỉ đúng object:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<BUCKET>/artifacts/current/model.joblib"
    }
  ]
}
```

Thay `<BUCKET>` bằng đúng tên bucket; không giữ dấu ngoặc nhọn. Role này phải
được attach vào EC2 như **instance profile**. Boto3 trên EC2 sẽ tự nhận temporary
credentials từ role; không đặt `AWS_ACCESS_KEY_ID` hay `AWS_SECRET_ACCESS_KEY`
trong systemd. Xem [IAM roles for EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html).

## 5. Tạo GitHub OIDC provider và role CI/CD

OIDC giúp GitHub Actions nhận credentials tạm thời thay vì cất access key trong
GitHub Secrets. Làm một lần cho AWS account:

1. IAM → **Identity providers → Add provider → OpenID Connect**.
2. Provider URL: `https://token.actions.githubusercontent.com`.
3. Audience: `sts.amazonaws.com`.
4. Nếu provider đã tồn tại thì dùng lại, không tạo bản trùng.
5. Tạo role `IncomeLabGitHubActions` cho Web identity provider vừa tạo.
6. Trust policy phải giới hạn đúng audience, repo và nhánh `main`.

Repo hiện tại có immutable GitHub owner/repository IDs. Dùng `sub` sau cho repo
này; nếu fork hoặc tạo repo mới, tra `owner.id` và `id` của repo tại GitHub API rồi
thay các ID tương ứng:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:Josee0801@200496032/K4-L3L4-Track2-Day21-TranHoangDuyAnh-2A202602558-CI-CD-for-AI-Systems@1408208794:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

`AWS_ACCOUNT_ID` lấy bằng `aws sts get-caller-identity --query Account
--output text`. Không đổi `sub` thành wildcard toàn bộ repo/branch. Nếu workflow
chạy dưới GitHub Environment hoặc claim OIDC của repo bạn khác, subject phải khớp
đúng claim đó.

Gắn vào role `IncomeLabGitHubActions` một permissions policy sau. Thay
`<AWS_REGION>`, `<AWS_ACCOUNT_ID>`, `<BUCKET>` bằng giá trị thật. Policy chỉ cho
đọc cache DVC, ghi model cụ thể, và chạy duy nhất AWS-RunShellScript trên EC2 có
tag `Name=income-api`; việc đọc kết quả SSM được giới hạn ở API status:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<BUCKET>"
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<BUCKET>/dvc/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::<BUCKET>/artifacts/current/model.joblib"
    },
    {
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": "arn:aws:ssm:<AWS_REGION>::document/AWS-RunShellScript"
    },
    {
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": "arn:aws:ec2:<AWS_REGION>:<AWS_ACCOUNT_ID>:instance/*",
      "Condition": {
        "StringEquals": {
          "ssm:resourceTag/Name": "income-api"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "ssm:GetCommandInvocation",
      "Resource": "*"
    }
  ]
}
```

AWS yêu cầu tách quyền dùng SSM document và quyền target instance; điều kiện tag
chặn role gửi lệnh đến EC2 khác. `GetCommandInvocation` cần truy vấn ID lệnh được
tạo ngẫu nhiên ở mỗi lần chạy. Xem hướng dẫn chính thức về
[Run Command và tag-based access](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command-setting-up.html).

## 6. Tạo EC2 và security group

Tạo security group riêng, ví dụ `income-api-sg`, trong Region đã chọn. Inbound:

| Port | Source | Ghi chú |
|---|---|---|
| TCP 8080 | IP công khai hiện tại của bạn `/32` | Chỉ để thử API từ máy cá nhân |
| TCP 22 | IP công khai hiện tại của bạn `/32` | Tạm thời để copy source/key; xóa rule sau khi setup |

Không mở SSH hoặc API tới `0.0.0.0/0`. GitHub Actions không dùng SSH; deploy qua
SSM nên không cần mở port 22 cho runner.

Trong EC2 Console → **Launch instance**:

1. Name: `income-api` (tag key `Name`, value `income-api`, cần cho policy SSM).
2. AMI: Ubuntu Server 22.04 LTS, architecture x86_64.
3. Instance type: chọn loại nhỏ phù hợp lab; `t3.small` là điểm bắt đầu cho API
   demo. T3 dùng CPU credits; sustained CPU ở Unlimited mode có thể tạo surplus
   credit charges. Xem [EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/).
4. Tạo/download key pair PEM, giữ ngoài repo, ví dụ
   `$HOME\Downloads\income-api.pem`.
5. Network: chọn VPC có public subnet và public IPv4 để gọi API.
6. Security group: chọn `income-api-sg`.
7. Advanced details → IAM instance profile: chọn `IncomeLabEc2Role`.
8. Metadata version: yêu cầu IMDSv2; bật EBS encryption.
9. Launch instance và đợi **2/2 status checks passed**.

Lưu lại **Instance ID**, **Public IPv4 address**, và tên key pair. EC2 phát sinh
chi phí khi chạy; EBS vẫn có thể tính phí sau khi stop instance. Xem [EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/).

## 7. Cài FastAPI service trên Ubuntu EC2

Tạm thời kết nối SSH từ PowerShell, dùng key pair và IP của bạn:

```powershell
ssh -i "$HOME\Downloads\income-api.pem" ubuntu@<EC2_PUBLIC_IP>
```

Trên EC2:

```bash
sudo apt update
sudo apt install -y python3-venv
mkdir -p ~/models ~/src
python3 -m venv ~/income-venv
~/income-venv/bin/python -m pip install --upgrade pip
~/income-venv/bin/pip install fastapi==0.111.0 uvicorn==0.29.0 scikit-learn==1.4.2 pandas==2.2.2 joblib==1.4.2 boto3==1.34.131
```

Thoát SSH; từ PowerShell trong repo, chép API code lên instance:

```powershell
scp -i "$HOME\Downloads\income-api.pem" .\src\serve.py ubuntu@<EC2_PUBLIC_IP>:/home/ubuntu/src/serve.py
```

Đăng nhập SSH lại và tạo systemd unit. Thay bucket và Region bằng giá trị thật:

```bash
sudo tee /etc/systemd/system/income-api.service > /dev/null <<'EOF'
[Unit]
Description=Income Model Inference Server
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment="ARTIFACT_BUCKET=<BUCKET>"
Environment="AWS_DEFAULT_REGION=<AWS_REGION>"
ExecStart=/home/ubuntu/income-venv/bin/python /home/ubuntu/src/serve.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Sửa placeholders trong file bằng bucket/Region thật rồi chạy:

```bash
sudo systemctl daemon-reload
sudo systemctl enable income-api
```

Chưa start service. Chưa có model trên S3 cho đến khi job Release chạy thành công.
Xác nhận EC2 xuất hiện ở **Systems Manager → Fleet Manager → Managed nodes**.
Nếu không thấy, kiểm tra role `IncomeLabEc2Role`, outbound HTTPS/network tới SSM,
và SSM Agent; cài/khởi động agent theo
[hướng dẫn cài SSM Agent](https://docs.aws.amazon.com/systems-manager/latest/userguide/ssm-agent.html).

Sau khi setup xong, xóa inbound rule TCP 22 khỏi security group. Có thể giữ TCP
8080 giới hạn IP cá nhân để thử API; đóng rule này khi không còn cần truy cập.

## 8. Tạo GitHub Actions secrets

Mở repo GitHub → **Settings → Secrets and variables → Actions**, thêm repository
secrets:

| Secret | Giá trị |
|---|---|
| `AWS_ROLE_ARN` | ARN role `IncomeLabGitHubActions` |
| `AWS_REGION` | Region đã dùng tạo bucket và EC2 |
| `ARTIFACT_BUCKET` | Tên bucket, không có `s3://` |
| `SERVER_INSTANCE_ID` | EC2 instance ID, ví dụ bắt đầu `i-...` |

Không cần `STORAGE_CREDENTIALS`, AWS access key, `SERVER_SSH_KEY` hoặc public IP
trong Secrets. GitHub Actions dùng OIDC; EC2 dùng instance role.

## 9. Kiểm tra và chạy pipeline

Trong PowerShell repo, kiểm tra file CSV không bị stage:

```powershell
git status --short
```

Stage metadata và code (không stage CSV/PEM/credentials):

```powershell
git add .github/workflows/cicd.yml .gitignore .dvc/config .dvcignore `
  params.yaml requirements.txt src tests data/*.dvc README.md tasks
git status --short
```

Danh sách staged chỉ nên có source, test, YAML/Markdown, `.dvc` pointers, `.dvc/config`
và `.dvcignore`. Không được có `data/*.csv`, `.pem`, hay file credentials. Commit
và push lên branch `main`:

```powershell
git commit -m "feat: configure AWS CI/CD with S3 and EC2"
git push origin main
```

Mở **GitHub → Actions**. Bốn jobs phải theo thứ tự:

1. **Unit Test** – chạy test trên dữ liệu tạm.
2. **Train** – lấy role credentials bằng OIDC, `dvc pull` train/holdout từ S3,
   train và upload report/model thành workflow artifacts.
3. **Quality Gate** – chỉ pass nếu F1 >= 0.65.
4. **Release** – sau khi gate pass, upload model lên S3 rồi gọi SSM Run Command
   để restart API và retry `/healthz`.

Model đã thử trên máy có F1 0.7149, nhưng CI sẽ tự tính lại. Nếu gate fail thì
Release được bỏ qua; đây là hành vi đúng.

Sau khi workflow thành công, kiểm tra các object:

```powershell
aws s3 ls "s3://$BUCKET/dvc/" --recursive
aws s3 ls "s3://$BUCKET/artifacts/current/"
```

## 10. Kiểm tra API

Từ PowerShell:

```powershell
$VM_IP = "<EC2_PUBLIC_IP>"
curl.exe "http://${VM_IP}:8080/healthz"
curl.exe -X POST "http://${VM_IP}:8080/score" `
  -H "Content-Type: application/json" `
  -d '{"features":[28,2,14,2,11,0,1,0,0,45]}'
```

Kết quả `/healthz` mong đợi là `{"status":"ok"}`. `/score` trả `prediction` 0
hoặc 1 cùng nhãn `thu_nhap_thap` hoặc `thu_nhap_cao`.

Nếu lỗi, kiểm tra:

```powershell
aws ssm describe-instance-information `
  --filters "Key=InstanceIds,Values=<EC2_INSTANCE_ID>"
```

Các nguyên nhân phổ biến: instance chưa Managed trong SSM; instance role thiếu
`s3:GetObject`; bucket/Region sai; model chưa upload; role OIDC `sub`/audience không
khớp; job không dùng nhánh `main`; hoặc security group chưa cho IP của bạn vào 8080.
Để xem log service mà không SSH, dùng **Systems Manager → Run Command** trên EC2
đúng tag `Name=income-api`, với document `AWS-RunShellScript` và lệnh
`sudo systemctl status income-api --no-pager; sudo journalctl -u income-api -n 50 --no-pager`.

## Bằng chứng, monitoring và chi phí

Chụp thật các màn hình sau khi chạy thành công:

- `02-actions-buoc-2.png`: bốn GitHub Actions jobs đều xanh.
- `04-curl-api.png`: hai lệnh curl cùng kết quả và IP EC2.
- `05-cloud-storage.png`: bucket/prefix `dvc/` và `artifacts/current/model.joblib`.

Không để ảnh chứa credentials, account secrets hay private keys. Để quan sát hoạt
động S3, có thể bật CloudTrail S3 data events, CloudWatch request metrics và S3
server access logging; data events/metrics/log storage có thể phát sinh phí.
Xem [S3 monitoring](https://docs.aws.amazon.com/AmazonS3/latest/userguide/monitoring-overview.html)
và [S3 security best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).

Sau khi nộp bài, dừng EC2 nếu không còn dùng. Dừng instance không xóa EBS volume
hay S3 data; chúng có thể tiếp tục phát sinh chi phí. Xóa tài nguyên chỉ sau khi
đã tải/lưu bằng chứng cần thiết.
