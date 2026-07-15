#!/bin/sh

# 엄격한 오류 처리를 활성화합니다.
set -euo pipefail

# ----- 구성 -----
BUCKET_NAME=${1:-customersupport112}
INFRA_STACK_NAME=${2:-CustomerSupportStackInfra}
COGNITO_STACK_NAME=${3:-CustomerSupportStackCognito}
INFRA_TEMPLATE_FILE="prerequisite/infrastructure.yaml"
COGNITO_TEMPLATE_FILE="prerequisite/cognito.yaml"

# 먼저 환경 변수에서 region을 가져옵니다.
if [ -z "${AWS_REGION-}" ]; then
    # AWS_REGION이 설정되지 않았으면 AWS CLI config에서 가져옵니다.
    REGION=$(aws configure get region 2>/dev/null || echo "us-west-2")
    # 환경 변수로 export합니다.
    export AWS_REGION="${REGION}"
fi
echo "Region is set to: ${AWS_REGION}"
export REGION="${AWS_REGION}"
    

# 적절한 오류 처리와 함께 AWS account ID를 가져옵니다.
echo "🔍 Getting AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>&1)
if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ Failed to get AWS Account ID. Please check your AWS credentials and network connectivity."
    echo "Error: $ACCOUNT_ID"
    exit 1
fi

FULL_BUCKET_NAME="${BUCKET_NAME}-${ACCOUNT_ID}-${REGION}"
ZIP_FILE="lambda.zip"
LAYER_ZIP_FILE="ddgs-layer.zip"
LAYER_SOURCE="prerequisite/lambda/python"
S3_LAYER_KEY="${LAYER_ZIP_FILE}"
LAMBDA_SRC="prerequisite/lambda/python"
S3_KEY="${ZIP_FILE}"

USER_POOL_NAME="CustomerSupportGatewayPool" 
MACHINE_APP_CLIENT_NAME="CustomerSupportMachineClient" 
WEB_APP_CLIENT_NAME="CustomerSupportWebClient"

echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
# ----- 1. S3 bucket 생성 -----
echo "🪣 Using S3 bucket: $FULL_BUCKET_NAME"
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket \
    --bucket "$FULL_BUCKET_NAME" \
    2>/dev/null || echo "ℹ️ Bucket may already exist or be owned by you."
else
  aws s3api create-bucket \
    --bucket "$FULL_BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" \
    2>/dev/null || echo "ℹ️ Bucket may already exist or be owned by you."
fi

# ----- S3 bucket 소유권 확인 -----
echo "🔍 Verifying S3 bucket ownership..."
aws s3api head-bucket --bucket "$FULL_BUCKET_NAME" --expected-bucket-owner "$ACCOUNT_ID"
if [ $? -ne 0 ]; then
    echo "❌ S3 bucket $FULL_BUCKET_NAME is not owned by account $ACCOUNT_ID"
    exit 1
fi
echo "✅ S3 bucket ownership verified"

# ----- 2. Lambda 코드 압축 -----
sudo apt install zip
echo "📦 Zipping contents of $LAMBDA_SRC into $ZIP_FILE..."
cd "$LAMBDA_SRC"
zip -r "../../../$ZIP_FILE" . > /dev/null

cd - > /dev/null

# ----- 3. S3에 업로드 -----
echo "☁️ Uploading $ZIP_FILE to s3://$FULL_BUCKET_NAME/$S3_KEY..."
aws s3api put-object --bucket "$FULL_BUCKET_NAME" --key "$S3_KEY" --body "$ZIP_FILE" --expected-bucket-owner "$ACCOUNT_ID"

echo "☁️ Uploading $LAYER_ZIP_FILE to s3://$FULL_BUCKET_NAME/$S3_LAYER_KEY..."
cd "$LAMBDA_SRC"
aws s3api put-object --bucket "$FULL_BUCKET_NAME" --key "$S3_LAYER_KEY" --body "$LAYER_ZIP_FILE" --expected-bucket-owner "$ACCOUNT_ID"
cd - > /dev/null
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
    --s3-bucket "$FULL_BUCKET_NAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    "${params[@]}" 2>&1)

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

# ----- 두 stack 실행 -----
echo "🔧 Starting deployment of infrastructure stack with LambdaS3Bucket = $FULL_BUCKET_NAME..."
deploy_stack "$INFRA_STACK_NAME" "$INFRA_TEMPLATE_FILE" --parameter-overrides LambdaS3Bucket="$FULL_BUCKET_NAME" LambdaS3Key="$S3_KEY" LayerS3Key="$S3_LAYER_KEY"
infra_exit_code=$?

echo "🔧 Starting deployment of Cognito stack..."
deploy_stack "$COGNITO_STACK_NAME" "$COGNITO_TEMPLATE_FILE" --parameter-overrides UserPoolName="$USER_POOL_NAME" MachineAppClientName="$MACHINE_APP_CLIENT_NAME" WebAppClientName="$WEB_APP_CLIENT_NAME"
cognito_exit_code=$?

echo "✅ Deployment complete."
