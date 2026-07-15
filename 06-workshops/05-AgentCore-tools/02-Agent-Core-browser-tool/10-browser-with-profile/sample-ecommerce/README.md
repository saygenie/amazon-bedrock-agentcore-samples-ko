# 샘플 전자상거래 사이트

localStorage를 사용하여 장바구니 상태를 유지하는 간단한 티셔츠 정적 전자상거래 사이트입니다.

## 로컬에서 실행

```bash
cd sample-ecommerce
python3 -m http.server 8000
```

그런 다음 다음 URL을 엽니다: http://localhost:8000

## CloudFormation으로 AWS에 배포

### 빠른 배포

```bash
chmod +x deploy.sh
./deploy.sh
```

스크립트는 다음 작업을 자동으로 수행합니다.
- Amazon S3 버킷 생성(이름이 충돌하면 기존 버킷 사용)
- CloudFront가 포함된 CloudFormation 스택 배포
- 웹사이트 파일 업로드
- CloudFront 캐시 무효화
- CloudFront URL 표시

### 기존 배포 업데이트

```bash
./update.sh
```

인프라를 변경하지 않고 Amazon S3의 파일을 업데이트하고 CloudFront 캐시를 무효화합니다.

### 수동 배포

```bash
# Bucket 생성
BUCKET_NAME="sample-ecommerce-static-site-$(date +%s)"
aws s3 mb s3://$BUCKET_NAME --region us-east-1

# CloudFormation 배포
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name sample-ecommerce-stack \
  --parameter-overrides BucketName=$BUCKET_NAME \
  --region us-east-1

# 파일 업로드
aws s3 sync . s3://$BUCKET_NAME/ \
  --exclude "*.yaml" --exclude "*.sh" --exclude "*.md"

# CloudFront URL 확인
aws cloudformation describe-stacks \
  --stack-name sample-ecommerce-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' \
  --output text
```

### 스택 삭제(버킷 유지)

```bash
./delete.sh
```

또는 다음 명령으로 직접 삭제합니다.
```bash
aws cloudformation delete-stack --stack-name sample-ecommerce-stack --region us-east-1
```

Amazon S3 버킷은 CloudFormation에서 관리하지 않으므로 스택을 삭제한 후에도 유지됩니다.

## Amazon S3에 배포(간단한 방식 - CloudFront 미사용)

```bash
# Bucket 생성
aws s3 mb s3://your-bucket-name

# 파일 업로드
aws s3 sync . s3://your-bucket-name --acl public-read

# 정적 웹 사이트 hosting 활성화
aws s3 website s3://your-bucket-name --index-document index.html
```

사이트를 사용할 수 있는 URL은 다음과 같습니다: http://your-bucket-name.s3-website-[region].amazonaws.com

## 기능

- 이미지가 포함된 티셔츠 상품 6개
- 장바구니에 상품 추가
- 썸네일 및 합계와 함께 장바구니 보기
- 상품 제거
- 브라우저에서 장바구니 유지(localStorage)
- 자동화를 위한 명확한 URL 경로(#home, #cart)

## Playwright 탐색

```python
# Page로 이동
page.goto("http://localhost:8000/#home")
page.goto("http://localhost:8000/#cart")

# 또는 selector 사용
page.locator('[data-page="home"]')
page.locator('[data-page="cart"]')
```
