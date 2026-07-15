#!/bin/bash

set -e
set -o pipefail

NAMESPACE="/app/customersupport"
REGION=$(aws configure get region)

echo "🔍 Listing SSM parameters under namespace: $NAMESPACE/*"
echo "📍 Region: $REGION"
echo ""

# 지정된 path 아래의 모든 parameter를 pagination으로 가져옵니다.
aws ssm get-parameters-by-path \
  --path "$NAMESPACE" \
  --recursive \
  --with-decryption \
  --region "$REGION" \
  --query "Parameters[*].{Name:Name,Value:Value}" \
  --output table
