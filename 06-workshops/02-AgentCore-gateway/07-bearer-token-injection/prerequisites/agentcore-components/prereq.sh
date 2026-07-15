#!/bin/sh

# 엄격한 오류 처리 활성화
set -euo pipefail

# ----- 구성 -----
BUCKET_NAME=${1:-asanaintegrationdemo111}
INFRA_STACK_NAME=${2:-AsanaIntegrationStackInfra}
COGNITO_STACK_NAME=${3:-AsanaIntegrationStackCognito}
INFRA_TEMPLATE_FILE="infrastructure_all.yaml"
COGNITO_TEMPLATE_FILE="cognito.yaml"
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")


# 적절한 오류 처리와 함께 AWS Account ID 가져오기
echo "🔍 Getting AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>&1)
if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ Failed to get AWS Account ID. Please check your AWS credentials and network connectivity."
    echo "Error: $ACCOUNT_ID"
    exit 1
fi


USER_POOL_NAME="AsanaIntegrationGWPool" 
MACHINE_APP_CLIENT_NAME="AsanaIntegrationGWMachineClient" 
WEB_APP_CLIENT_NAME="AsanaIntegrationGWWebClient"

echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
# ----- 1. S3 bucket 생성 -----
# ----- 4. CloudFormation 배포 -----
deploy_stack() {
  set +e

  local stack_name=$1
  local template_file=$2
  shift 2
  local params=("$@")

  echo "🚀 Deploying CloudFormation stack: $stack_name"

  output=$(aws cloudformation deploy \
    --stack-name "$stack_name" \
    --template-file "$template_file" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" 2>&1)

  exit_code=$?

  echo "$output"

  if [ $exit_code -ne 0 ]; then
    if echo "$output" | grep -qi "No changes to deploy"; then
      echo "ℹ️ No updates for stack $stack_name, continuing..."
      return 0
    else
      echo "❌ Error deploying stack $stack_name:"
      echo "$output"
      return $exit_code
    fi
  else
    echo "✅ Stack $stack_name deployed successfully."
    return 0
  fi
}

# ----- 두 스택 모두 실행 -----
echo "🔧 Starting deployment of infrastructure stack"
deploy_stack "$INFRA_STACK_NAME" "$INFRA_TEMPLATE_FILE"
infra_exit_code=$?

echo "✅ Deployment complete for API stack."


echo "🔧 Starting deployment of infrastructure stack"
deploy_stack "$COGNITO_STACK_NAME" "$COGNITO_TEMPLATE_FILE"
cognito_exit_code=$?

echo "✅ Deployment complete for Cognito stack."

echo "✅ Deployment complete both prerequisite stacks."

# cd ../../

# echo "✅ Back to Bearer token injection home directory."
