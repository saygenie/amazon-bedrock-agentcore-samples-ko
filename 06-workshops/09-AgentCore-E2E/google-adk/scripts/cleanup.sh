#!/bin/bash

set -e
set -o pipefail

# ----- 구성 -----
BUCKET_NAME=${1:-customersupport}
INFRA_STACK_NAME=${2:-CustomerSupportStackInfra}
COGNITO_STACK_NAME=${3:-CustomerSupportStackCognito}
REGION=$(aws configure get region)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FULL_BUCKET_NAME="${BUCKET_NAME}-${ACCOUNT_ID}"
ZIP_FILE="lambda.zip"
S3_KEY="lambda.zip"

if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ Failed to get AWS Account ID. Please check your AWS credentials and network connectivity."
    echo "Error: $ACCOUNT_ID"
    exit 1
fi

# ----- 삭제 확인 -----
read -p "⚠️ Are you sure you want to delete stacks '$INFRA_STACK_NAME', '$COGNITO_STACK_NAME' and clean up S3? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "❌ Cleanup cancelled."
  exit 1
fi

# ----- 1. CloudFormation stack 삭제 -----
echo "🧨 Deleting stack: $INFRA_STACK_NAME..."
aws cloudformation delete-stack --stack-name "$INFRA_STACK_NAME" --region "$REGION"
echo "⏳ Waiting for $INFRA_STACK_NAME to be deleted..."
aws cloudformation wait stack-delete-complete --stack-name "$INFRA_STACK_NAME" --region "$REGION"
echo "✅ Stack $INFRA_STACK_NAME deleted."

echo "🧨 Deleting stack: $COGNITO_STACK_NAME..."
aws cloudformation delete-stack --stack-name "$COGNITO_STACK_NAME" --region "$REGION"
echo "⏳ Waiting for $COGNITO_STACK_NAME to be deleted..."
aws cloudformation wait stack-delete-complete --stack-name "$COGNITO_STACK_NAME" --region "$REGION"
echo "✅ Stack $COGNITO_STACK_NAME deleted."

# ----- 2. S3에서 zip 파일 삭제 -----
echo "🧹 Deleting all contents of s3://$FULL_BUCKET_NAME..."
aws s3 rm "s3://$FULL_BUCKET_NAME" --recursive || echo "⚠️ Failed to clean bucket or it is already empty."

# ----- 3. 선택적으로 bucket 삭제 -----
read -p "🪣 Do you want to delete the bucket '$FULL_BUCKET_NAME'? (y/N): " delete_bucket
if [[ "$delete_bucket" == "y" || "$delete_bucket" == "Y" ]]; then
  echo "🚮 Deleting bucket $FULL_BUCKET_NAME..."
  aws s3 rb "s3://$FULL_BUCKET_NAME" --force
  echo "✅ Bucket deleted."
else
  echo "🪣 Bucket retained: $FULL_BUCKET_NAME"
fi

# ----- 4. 로컬 zip 파일 정리 -----
echo "🗑️ Removing local file $ZIP_FILE..."
rm -f "$ZIP_FILE"

echo "✅ Deployment complete."
