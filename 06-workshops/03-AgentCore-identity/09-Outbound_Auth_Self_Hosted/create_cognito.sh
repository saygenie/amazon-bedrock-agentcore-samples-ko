#!/bin/bash
# OAuth 권한 부여 서버로 사용할 Amazon Cognito 사용자 풀을 생성함.
# 클라이언트 ID, 클라이언트 보안 암호, 테스트 사용자가 있는 OAuth 서버를 이미 보유한 경우
# 이 스크립트를 건너뛰고 ISSUER_URL, CLIENT_ID, CLIENT_SECRET을 직접 설정.

REGION=${AWS_REGION:-$(aws configure get region 2>/dev/null)}
REGION=${REGION:-us-east-1}

USER_POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name AgentCoreIdentityQuickStartPool \
  --query 'UserPool.Id' \
  --no-cli-pager \
  --output text)

DOMAIN_NAME="agentcore-quickstart-$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 5)"

aws cognito-idp create-user-pool-domain \
  --domain $DOMAIN_NAME \
  --no-cli-pager \
  --user-pool-id $USER_POOL_ID > /dev/null

CLIENT_RESPONSE=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name AgentCoreQuickStart \
  --generate-secret \
  --callback-urls "https://bedrock-agentcore.$REGION.amazonaws.com/identities/oauth2/callback" \
  --allowed-o-auth-flows "code" \
  --allowed-o-auth-scopes "openid" "profile" "email" \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers "COGNITO" \
  --query 'UserPoolClient.{ClientId:ClientId,ClientSecret:ClientSecret}' \
  --output json)

CLIENT_ID=$(echo $CLIENT_RESPONSE | jq -r '.ClientId')
CLIENT_SECRET=$(echo $CLIENT_RESPONSE | jq -r '.ClientSecret')

USERNAME="AgentCoreTestUser$(printf "%04d" $((RANDOM % 10000)))"
PASSWORD="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16)Aa1!"

aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username $USERNAME \
  --output text > /dev/null

aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username $USERNAME \
  --password $PASSWORD \
  --output text \
  --permanent > /dev/null

ISSUER_URL="https://cognito-idp.$REGION.amazonaws.com/$USER_POOL_ID/.well-known/openid-configuration"

echo "User Pool ID: $USER_POOL_ID"
echo "Client ID: $CLIENT_ID"
echo "Client Secret: $CLIENT_SECRET"
echo "Issuer URL: $ISSUER_URL"
echo "Test User: $USERNAME"
echo "Test Password: $PASSWORD"
echo ""
echo "export USER_POOL_ID='$USER_POOL_ID'"
echo "export CLIENT_ID='$CLIENT_ID'"
echo "export CLIENT_SECRET='$CLIENT_SECRET'"
echo "export ISSUER_URL='$ISSUER_URL'"
echo "export COGNITO_USERNAME='$USERNAME'"
echo "export COGNITO_PASSWORD='$PASSWORD'"
