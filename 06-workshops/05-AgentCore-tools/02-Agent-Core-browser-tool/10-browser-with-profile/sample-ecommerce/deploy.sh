#!/bin/bash

# 구성
STACK_NAME="sample-ecommerce-stack"
BUCKET_NAME="sample-ecommerce-static-site-$(date +%s)"
REGION="${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || echo us-east-1)}"

echo "Creating S3 bucket if it doesn't exist..."

# 버킷 생성(이미 존재하면 오류 무시)
aws s3 mb s3://$BUCKET_NAME --region $REGION 2>/dev/null || echo "Bucket already exists or using existing bucket"

# 버전 관리 활성화 및 퍼블릭 액세스 차단
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region $REGION 2>/dev/null || true

echo "Deploying CloudFormation stack..."

# CloudFormation 스택 배포
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name $STACK_NAME \
  --parameter-overrides BucketName=$BUCKET_NAME \
  --region $REGION \
  --no-fail-on-empty-changeset

# 스택에서 버킷 이름 가져오기
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text)

echo "Uploading website files to S3..."

# S3에 파일 업로드
aws s3 sync . s3://$BUCKET/ \
  --exclude "*.yaml" \
  --exclude "*.sh" \
  --exclude "*.md" \
  --exclude ".git/*" \
  --region $REGION

# CloudFront 배포 ID 가져오기
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
  --output text)

echo "Creating CloudFront invalidation..."

# CloudFront 캐시 무효화
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*" \
  --region $REGION

# CloudFront URL 가져오기
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' \
  --output text)

echo ""
echo "Deployment complete!"
echo "CloudFront URL: $CLOUDFRONT_URL"
echo "Bucket Name: $BUCKET"
echo ""
echo "Note: CloudFront distribution may take 10-15 minutes to fully deploy"
