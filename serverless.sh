# 1. 기존 credentials 백업 (있으면)
mkdir -p ~/.aws_backup
[ -f ~/.aws/credentials ] && mv ~/.aws/credentials ~/.aws_backup/credentials.bak.$(date +%s)

# 2. 새 credentials 파일 생성 + 접근 차단
touch ~/.aws/credentials
chmod 000 ~/.aws/credentials

# 3. 혹시 남아있는 AWS 환경변수 제거
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE AWS_DEFAULT_PROFILE

# 4. EC2 IAM Role로 인증되는지 확인
echo "=== STS CHECK ==="
aws sts get-caller-identity || echo "❌ STS FAILED"

# 5. credential source 확인
echo "=== CONFIG CHECK ==="
aws configure list

# 6. Serverless deploy 실행
echo "=== DEPLOY START ==="
npx serverless@3 deploy
