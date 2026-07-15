#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# 전체 자동 설정: EntraID 앱 등록 + AWS 배포
#
# EntraID 앱 등록(App A + App B)과 AWS OAuth credential provider를 생성하고,
# CDK 스택을 배포한 다음 모든 요소(redirect URI, workload identity return URL)를
# 연결합니다.
#
# 사용법:
#   ./setup.sh \
#     --tenant-id <entra-tenant-id> \
#     --tenant-type <ciam|standard> \
#     --ciam-domain <domain>          # ciam tenant에만 사용 \
#     --region <aws-region> \
#     --stack-name <cfn-stack-name> \
#     --suffix <resource-suffix>       # 선택 사항, 병렬 배포용
#
# 예(CIAM tenant):
#   ./setup.sh \
#     --tenant-id 00000000-0000-0000-0000-000000000000 \
#     --tenant-type ciam \
#     --ciam-domain your-domain \
#     --region us-east-1 \
#     --stack-name MyEntraIdStack \
#     --suffix v2
#
# 예(표준 tenant):
#   ./setup.sh \
#     --tenant-id abcd1234-... \
#     --tenant-type standard \
#     --region us-east-1 \
#     --stack-name EntraIdProd
#
# 사전 요구 사항:
#   - Azure CLI: az login --tenant <tenant-id> --allow-no-subscriptions
#   - 자격 증명이 구성된 AWS CLI v2
#   - Node.js 18+, npm, CDK CLI
#   - jq 설치
# =============================================================================

set -euo pipefail

# --- 기본값 ---
TENANT_ID=""
TENANT_TYPE="standard"
CIAM_DOMAIN=""
AWS_REGION=""
STACK_NAME=""
SUFFIX=""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CDK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- 인자 파싱 ---
while [[ $# -gt 0 ]]; do
  case $1 in
    --tenant-id) TENANT_ID="$2"; shift 2 ;;
    --tenant-type) TENANT_TYPE="$2"; shift 2 ;;
    --ciam-domain) CIAM_DOMAIN="$2"; shift 2 ;;
    --region) AWS_REGION="$2"; shift 2 ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --suffix) SUFFIX="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# --- 검증 ---
if [ -z "$TENANT_ID" ] || [ -z "$AWS_REGION" ] || [ -z "$STACK_NAME" ]; then
  echo "Usage: $0 --tenant-id <id> --region <region> --stack-name <name> [--tenant-type ciam|standard] [--ciam-domain <domain>] [--suffix <suffix>]"
  exit 1
fi

if [ "$TENANT_TYPE" = "ciam" ] && [ -z "$CIAM_DOMAIN" ]; then
  echo "Error: --ciam-domain is required for CIAM tenants"
  exit 1
fi

# authority host 파생
if [ "$TENANT_TYPE" = "ciam" ]; then
  AUTHORITY_HOST="${CIAM_DOMAIN}.ciamlogin.com"
else
  AUTHORITY_HOST="login.microsoftonline.com"
fi
DISCOVERY_URL="https://${AUTHORITY_HOST}/${TENANT_ID}/v2.0/.well-known/openid-configuration"

PROVIDER_NAME="entraid-weather-3lo"
if [ -n "$SUFFIX" ]; then
  PROVIDER_NAME="entraid-weather-3lo-${SUFFIX}"
fi

echo "============================================="
echo "  EntraID + AWS Setup"
echo "============================================="
echo "  Tenant ID:     $TENANT_ID"
echo "  Tenant type:   $TENANT_TYPE"
echo "  Authority:     $AUTHORITY_HOST"
echo "  AWS Region:    $AWS_REGION"
echo "  Stack name:    $STACK_NAME"
echo "  Suffix:        ${SUFFIX:-<none>}"
echo "  Provider name: $PROVIDER_NAME"
echo "============================================="
echo ""

# --- 헬퍼: Graph API 토큰 가져오기 ---
get_graph_token() {
  az account get-access-token --resource https://graph.microsoft.com --tenant "$TENANT_ID" --query accessToken -o tsv 2>/dev/null
}

# --- 1단계: App A 생성(SPA, public client) ---
echo "=== Step 1: Create App A (inbound auth, SPA) ==="
TOKEN=$(get_graph_token)

APP_A_NAME="agentcore-gateway-inbound"
if [ -n "$SUFFIX" ]; then
  APP_A_NAME="agentcore-gateway-inbound-${SUFFIX}"
fi

echo "→ Creating app registration: $APP_A_NAME"
APP_A_RESPONSE=$(curl -s -X POST "https://graph.microsoft.com/v1.0/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"displayName\": \"$APP_A_NAME\",
    \"signInAudience\": \"AzureADMyOrg\",
    \"api\": {
      \"requestedAccessTokenVersion\": 2
    },
    \"spa\": {
      \"redirectUris\": [\"http://localhost:33418\"]
    }
  }")

APP_A_OBJECT_ID=$(echo "$APP_A_RESPONSE" | jq -r '.id')
APP_A_CLIENT_ID=$(echo "$APP_A_RESPONSE" | jq -r '.appId')

if [ "$APP_A_OBJECT_ID" = "null" ] || [ -z "$APP_A_OBJECT_ID" ]; then
  echo "✗ Failed to create App A:"
  echo "$APP_A_RESPONSE" | jq .
  exit 1
fi
echo "✓ App A created: $APP_A_CLIENT_ID (object: $APP_A_OBJECT_ID)"

# Application ID URI를 설정하고 gateway.access scope 공개
echo "→ Setting Application ID URI and exposing gateway.access scope..."
sleep 2  # 앱 생성 후 Graph API에 잠시 시간이 필요함

curl -s -X PATCH "https://graph.microsoft.com/v1.0/applications/$APP_A_OBJECT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"identifierUris\": [\"api://$APP_A_CLIENT_ID\"],
    \"api\": {
      \"requestedAccessTokenVersion\": 2,
      \"oauth2PermissionScopes\": [
        {
          \"id\": \"$(uuidgen | tr '[:upper:]' '[:lower:]')\",
          \"adminConsentDescription\": \"Allows access to the AgentCore Gateway API\",
          \"adminConsentDisplayName\": \"Access MCP Gateway\",
          \"isEnabled\": true,
          \"type\": \"User\",
          \"userConsentDescription\": \"Allow access to the MCP Gateway\",
          \"userConsentDisplayName\": \"Access MCP Gateway\",
          \"value\": \"gateway.access\"
        }
      ]
    }
  }" > /dev/null

echo "✓ Exposed scope: api://$APP_A_CLIENT_ID/gateway.access"

# App A의 service principal 생성(토큰 발급에 필요)
echo "→ Creating service principal for App A..."
curl -s -X POST "https://graph.microsoft.com/v1.0/servicePrincipals" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"appId\": \"$APP_A_CLIENT_ID\"}" > /dev/null 2>&1 || true
echo "✓ Service principal created"

echo ""

# --- 2단계: App B 생성(Web, confidential client) ---
echo "=== Step 2: Create App B (outbound auth, confidential) ==="

APP_B_NAME="agentcore-weather-api"
if [ -n "$SUFFIX" ]; then
  APP_B_NAME="agentcore-weather-api-${SUFFIX}"
fi

echo "→ Creating app registration: $APP_B_NAME"
APP_B_RESPONSE=$(curl -s -X POST "https://graph.microsoft.com/v1.0/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"displayName\": \"$APP_B_NAME\",
    \"signInAudience\": \"AzureADMyOrg\",
    \"api\": {
      \"requestedAccessTokenVersion\": 2
    }
  }")

APP_B_OBJECT_ID=$(echo "$APP_B_RESPONSE" | jq -r '.id')
APP_B_CLIENT_ID=$(echo "$APP_B_RESPONSE" | jq -r '.appId')

if [ "$APP_B_OBJECT_ID" = "null" ] || [ -z "$APP_B_OBJECT_ID" ]; then
  echo "✗ Failed to create App B:"
  echo "$APP_B_RESPONSE" | jq .
  exit 1
fi
echo "✓ App B created: $APP_B_CLIENT_ID (object: $APP_B_OBJECT_ID)"

# Application ID URI를 설정하고 weather.read scope 공개
echo "→ Setting Application ID URI and exposing weather.read scope..."
sleep 2

curl -s -X PATCH "https://graph.microsoft.com/v1.0/applications/$APP_B_OBJECT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"identifierUris\": [\"api://$APP_B_CLIENT_ID\"],
    \"api\": {
      \"requestedAccessTokenVersion\": 2,
      \"oauth2PermissionScopes\": [
        {
          \"id\": \"$(uuidgen | tr '[:upper:]' '[:lower:]')\",
          \"adminConsentDescription\": \"Allows reading weather data from the Weather API\",
          \"adminConsentDisplayName\": \"Read weather data\",
          \"isEnabled\": true,
          \"type\": \"User\",
          \"userConsentDescription\": \"Allow this app to read weather data on your behalf\",
          \"userConsentDisplayName\": \"Read weather data\",
          \"value\": \"weather.read\"
        }
      ]
    }
  }" > /dev/null

echo "✓ Exposed scope: api://$APP_B_CLIENT_ID/weather.read"

# App B의 client secret 생성
echo "→ Creating client secret for App B..."
SECRET_RESPONSE=$(curl -s -X POST "https://graph.microsoft.com/v1.0/applications/$APP_B_OBJECT_ID/addPassword" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"passwordCredential\": {\"displayName\": \"agentcore-3lo-secret\"}}")

APP_B_SECRET=$(echo "$SECRET_RESPONSE" | jq -r '.secretText')  # pragma: allowlist secret
if [ "$APP_B_SECRET" = "null" ] || [ -z "$APP_B_SECRET" ]; then
  echo "✗ Failed to create client secret:"
  echo "$SECRET_RESPONSE" | jq .
  exit 1
fi
echo "✓ Client secret created"

# App B의 service principal 생성
echo "→ Creating service principal for App B..."
curl -s -X POST "https://graph.microsoft.com/v1.0/servicePrincipals" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"appId\": \"$APP_B_CLIENT_ID\"}" > /dev/null 2>&1 || true
echo "✓ Service principal created"

echo ""

# --- 3단계: OAuth Credential Provider 생성(AWS) ---
echo "=== Step 3: Create OAuth Credential Provider ==="

# tenant 유형에 따라 provider 구성
if [ "$TENANT_TYPE" = "ciam" ]; then
  VENDOR="CustomOauth2"
  PROVIDER_CONFIG="{\"customOauth2ProviderConfig\":{\"oauthDiscovery\":{\"discoveryUrl\":\"$DISCOVERY_URL\"},\"clientId\":\"$APP_B_CLIENT_ID\",\"clientSecret\":\"$APP_B_SECRET\"}}"
else
  VENDOR="CustomOauth2"
  # 표준 tenant에서도 discovery URL을 명시적으로 제어하기 위해 CustomOauth2 사용
  PROVIDER_CONFIG="{\"customOauth2ProviderConfig\":{\"oauthDiscovery\":{\"discoveryUrl\":\"$DISCOVERY_URL\"},\"clientId\":\"$APP_B_CLIENT_ID\",\"clientSecret\":\"$APP_B_SECRET\"}}"
fi

echo "→ Creating credential provider: $PROVIDER_NAME (vendor: $VENDOR)"
CRED_RESPONSE=$(aws bedrock-agentcore-control create-oauth2-credential-provider \
  --name "$PROVIDER_NAME" \
  --credential-provider-vendor "$VENDOR" \
  --oauth2-provider-config-input "$PROVIDER_CONFIG" \
  --region "$AWS_REGION" \
  --output json 2>&1)

OAUTH_PROVIDER_ARN=$(echo "$CRED_RESPONSE" | jq -r '.credentialProviderArn')
OAUTH_SECRET_ARN=$(echo "$CRED_RESPONSE" | jq -r '.clientSecretArn.secretArn')
OAUTH_CALLBACK_URL=$(echo "$CRED_RESPONSE" | jq -r '.callbackUrl')

if [ "$OAUTH_PROVIDER_ARN" = "null" ] || [ -z "$OAUTH_PROVIDER_ARN" ]; then
  echo "✗ Failed to create credential provider:"
  echo "$CRED_RESPONSE"
  exit 1
fi
echo "✓ Credential provider created"
echo "  ARN:      $OAUTH_PROVIDER_ARN"
echo "  Secret:   $OAUTH_SECRET_ARN"
echo "  Callback: $OAUTH_CALLBACK_URL"

echo ""

# --- 4단계: App B에 OAuth 콜백 URL 등록 ---
echo "=== Step 4: Register callback URL in App B ==="
TOKEN=$(get_graph_token)

echo "→ Adding redirect URI to App B: $OAUTH_CALLBACK_URL"
curl -s -X PATCH "https://graph.microsoft.com/v1.0/applications/$APP_B_OBJECT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"web\": {\"redirectUris\": [\"$OAUTH_CALLBACK_URL\"]}}" > /dev/null

echo "✓ Redirect URI registered in App B"
echo ""

# --- 5단계: CDK 스택 배포 ---
echo "=== Step 5: Deploy CDK Stack ==="
echo "→ Installing dependencies..."
npm install --prefix "$CDK_DIR" --silent 2>/dev/null

# 자리 표시자 URL로 배포별 OpenAPI spec 생성(배포 후 업데이트)
OPENAPI_SOURCE="$CDK_DIR/openapi/weather-api.json"
OPENAPI_FILE="$CDK_DIR/openapi/weather-api-${STACK_NAME}.json"

INIT_SPEC=$(jq --arg tenant_id "$TENANT_ID" \
  --arg authority_host "$AUTHORITY_HOST" \
  --arg app_b_id "$APP_B_CLIENT_ID" \
  '.servers[0].url = "https://placeholder.execute-api.region.amazonaws.com" |
   .components.securitySchemes.entraId.flows.authorizationCode.authorizationUrl = "https://\($authority_host)/\($tenant_id)/oauth2/v2.0/authorize" |
   .components.securitySchemes.entraId.flows.authorizationCode.tokenUrl = "https://\($authority_host)/\($tenant_id)/oauth2/v2.0/token" |
   .components.securitySchemes.entraId.flows.authorizationCode.scopes = {"api://\($app_b_id)/weather.read": "Read weather data"} |
   .paths["/weather"].get.security[0].entraId = ["api://\($app_b_id)/weather.read"]' \
  "$OPENAPI_SOURCE")
echo "$INIT_SPEC" > "$OPENAPI_FILE"

echo "→ Deploying stack: $STACK_NAME"

# CDK context 인자 구성
CDK_CONTEXT="-c stackName=$STACK_NAME"
CDK_CONTEXT="$CDK_CONTEXT -c entra:tenantId=$TENANT_ID"
CDK_CONTEXT="$CDK_CONTEXT -c entra:appAClientId=$APP_A_CLIENT_ID"
CDK_CONTEXT="$CDK_CONTEXT -c entra:appBClientId=$APP_B_CLIENT_ID"
CDK_CONTEXT="$CDK_CONTEXT -c entra:tenantType=$TENANT_TYPE"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:providerArn=$OAUTH_PROVIDER_ARN"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:secretArn=$OAUTH_SECRET_ARN"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:callbackUrl=$OAUTH_CALLBACK_URL"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:providerName=$PROVIDER_NAME"

if [ -n "$CIAM_DOMAIN" ]; then
  CDK_CONTEXT="$CDK_CONTEXT -c entra:ciamDomain=$CIAM_DOMAIN"
fi
if [ -n "$SUFFIX" ]; then
  CDK_CONTEXT="$CDK_CONTEXT -c resourceSuffix=$SUFFIX"
fi

CDK_CONTEXT="$CDK_CONTEXT -c openapi:path=$OPENAPI_FILE"

# 이 issuer의 OIDC provider가 이미 있는지 확인(같은 tenant = 같은 issuer)
ISSUER_HOST_FOR_OIDC=""
if [ "$TENANT_TYPE" = "ciam" ]; then
  ISSUER_HOST_FOR_OIDC="${TENANT_ID}.ciamlogin.com"
else
  ISSUER_HOST_FOR_OIDC="login.microsoftonline.com"
fi
OIDC_ISSUER_URL="${ISSUER_HOST_FOR_OIDC}/${TENANT_ID}/v2.0"

EXISTING_OIDC_ARN=$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text --region "$AWS_REGION" 2>/dev/null | tr '\t' '\n' | while read arn; do
  URL=$(aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$arn" --query "Url" --output text 2>/dev/null)
  if [ "$URL" = "$OIDC_ISSUER_URL" ]; then
    echo "$arn"
    break
  fi
done)

if [ -n "$EXISTING_OIDC_ARN" ]; then
  echo "  (Reusing existing OIDC provider: $EXISTING_OIDC_ARN)"
  CDK_CONTEXT="$CDK_CONTEXT -c oidc:providerArn=$EXISTING_OIDC_ARN"
  # OIDC provider의 audience 목록에 App A client ID가 있는지 확인
  aws iam add-client-id-to-open-id-connect-provider \
    --open-id-connect-provider-arn "$EXISTING_OIDC_ARN" \
    --client-id "$APP_A_CLIENT_ID" \
    --region "$AWS_REGION" 2>/dev/null || true
  echo "  (Ensured App A client ID in OIDC audience list)"
fi

# 배포
CDK_DEFAULT_REGION="$AWS_REGION" npx cdk deploy $STACK_NAME --require-approval never $CDK_CONTEXT --app "npx ts-node --prefer-ts-exts bin/cdk.ts" --output "cdk.out-${STACK_NAME}" 2>&1 | tee /tmp/cdk-deploy-$$.log

# CloudFormation에서 출력 추출
echo ""
echo "→ Reading stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs" --output json)

API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')
GATEWAY_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="GatewayId") | .OutputValue')

if [ -z "$API_ENDPOINT" ] || [ "$API_ENDPOINT" = "null" ]; then
  echo "✗ Could not read stack outputs. Check CloudFormation console."
  exit 1
fi

echo "✓ Stack deployed"
echo "  API Endpoint: $API_ENDPOINT"
echo "  Gateway ID:   $GATEWAY_ID"
echo ""

# --- 6단계: App A에 API Gateway redirect URI 등록 ---
echo "=== Step 6: Register redirect URIs in App A ==="
TOKEN=$(get_graph_token)

# 기존 SPA redirect URI를 읽고 새 URI 추가
EXISTING_URIS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "https://graph.microsoft.com/v1.0/applications/$APP_A_OBJECT_ID" | jq -r '.spa.redirectUris // []')

NEW_URIS=$(echo "$EXISTING_URIS" | jq \
  --arg cb "$API_ENDPOINT/callback" \
  --arg auth "$API_ENDPOINT/auth" \
  '. + [$cb, $auth] | unique')

echo "→ Adding SPA redirect URIs to App A:"
echo "  - $API_ENDPOINT/callback (VS Code OAuth callback)"
echo "  - $API_ENDPOINT/auth (auth onboarding SPA)"

curl -s -X PATCH "https://graph.microsoft.com/v1.0/applications/$APP_A_OBJECT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"spa\": {\"redirectUris\": $NEW_URIS}}" > /dev/null

echo "✓ Redirect URIs registered in App A"
echo ""

# --- 7단계: workload identity return URL 업데이트 ---
echo "=== Step 7: Update workload identity return URLs ==="
echo "→ Setting allowed return URL: $API_ENDPOINT/auth/callback"

aws bedrock-agentcore-control update-workload-identity \
  --name "$GATEWAY_ID" \
  --allowed-resource-oauth2-return-urls "[\"$API_ENDPOINT/auth/callback\"]" \
  --region "$AWS_REGION" > /dev/null 2>&1

echo "✓ Workload identity updated"
echo ""

# --- 8단계: OpenAPI spec 업데이트 및 재배포 ---
echo "=== Step 8: Update OpenAPI spec with API endpoint ==="

# OpenAPI spec의 배포별 복사본 생성(원본 유지)
OPENAPI_SOURCE="$CDK_DIR/openapi/weather-api.json"
OPENAPI_FILE="$CDK_DIR/openapi/weather-api-${STACK_NAME}.json"
cp "$OPENAPI_SOURCE" "$OPENAPI_FILE"

# 서버 URL 및 security scheme URL 업데이트
UPDATED_SPEC=$(jq --arg url "$API_ENDPOINT" \
  --arg tenant_id "$TENANT_ID" \
  --arg authority_host "$AUTHORITY_HOST" \
  --arg app_b_id "$APP_B_CLIENT_ID" \
  '.servers[0].url = $url |
   .components.securitySchemes.entraId.flows.authorizationCode.authorizationUrl = "https://\($authority_host)/\($tenant_id)/oauth2/v2.0/authorize" |
   .components.securitySchemes.entraId.flows.authorizationCode.tokenUrl = "https://\($authority_host)/\($tenant_id)/oauth2/v2.0/token" |
   .components.securitySchemes.entraId.flows.authorizationCode.scopes = {"api://\($app_b_id)/weather.read": "Read weather data"} |
   .paths["/weather"].get.security[0].entraId = ["api://\($app_b_id)/weather.read"]' \
  "$OPENAPI_FILE")

echo "$UPDATED_SPEC" > "$OPENAPI_FILE"
echo "✓ OpenAPI spec created: $OPENAPI_FILE"

echo "→ Redeploying stack with updated OpenAPI spec..."
CDK_DEFAULT_REGION="$AWS_REGION" npx cdk deploy $STACK_NAME --require-approval never $CDK_CONTEXT --app "npx ts-node --prefer-ts-exts bin/cdk.ts" --output "cdk.out-${STACK_NAME}" 2>&1 | tee -a /tmp/cdk-deploy-$$.log

echo "✓ Redeployment complete"
echo ""

# --- 완료 ---
echo "============================================="
echo "  Setup Complete"
echo "============================================="
echo ""
echo "  API Endpoint:    $API_ENDPOINT"
echo "  Auth Onboarding: $API_ENDPOINT/auth"
echo "  MCP Endpoint:    $API_ENDPOINT/mcp"
echo "  Gateway ID:      $GATEWAY_ID"
echo ""
echo "  App A Client ID: $APP_A_CLIENT_ID"
echo "  App B Client ID: $APP_B_CLIENT_ID"
echo "  OAuth Provider:  $PROVIDER_NAME"
echo ""
echo "  VS Code MCP config:"
echo "  {"
echo "    \"servers\": {"
echo "      \"agentcore-weather-entraid\": {"
echo "        \"type\": \"http\","
echo "        \"url\": \"$API_ENDPOINT/mcp\","
echo "        \"headers\": { \"MCP-Protocol-Version\": \"2025-11-25\" }"
echo "      }"
echo "    }"
echo "  }"
echo ""
# 데모 사용자 안내를 위한 tenant 도메인 가져오기
TENANT_DOMAIN=$(curl -s -H "Authorization: Bearer $(get_graph_token)" \
  "https://graph.microsoft.com/v1.0/domains?\$top=1" | jq -r '.value[0].id // empty')
if [ -z "$TENANT_DOMAIN" ]; then
  TENANT_DOMAIN="<your-domain>.onmicrosoft.com"
fi

echo "  To create demo users:"
echo "    ./scripts/create-demo-user.sh --tenant-id $TENANT_ID --domain $TENANT_DOMAIN <username>"
echo ""
echo "  Test at: $API_ENDPOINT/auth"
echo ""

# --- 9단계: redeploy-cdk.sh용 환경 파일 생성 ---
ENV_FILE="$CDK_DIR/.env.${STACK_NAME}"
cat > "$ENV_FILE" <<EOF
# Generated by setup.sh on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Stack: $STACK_NAME
STACK_NAME=$STACK_NAME
AWS_REGION=$AWS_REGION
ENTRA_TENANT_ID=$TENANT_ID
ENTRA_TENANT_TYPE=$TENANT_TYPE
ENTRA_CIAM_DOMAIN=$CIAM_DOMAIN
ENTRA_APP_A_CLIENT_ID=$APP_A_CLIENT_ID
ENTRA_APP_B_CLIENT_ID=$APP_B_CLIENT_ID
OAUTH_PROVIDER_ARN=$OAUTH_PROVIDER_ARN
OAUTH_SECRET_ARN=$OAUTH_SECRET_ARN
OAUTH_CALLBACK_URL=$OAUTH_CALLBACK_URL
OAUTH_PROVIDER_NAME=$PROVIDER_NAME
RESOURCE_SUFFIX=$SUFFIX
OPENAPI_PATH=$(python3 -c "import os.path; print(os.path.relpath('$OPENAPI_FILE', '$CDK_DIR'))")
OIDC_PROVIDER_ARN=${EXISTING_OIDC_ARN:-}
API_ENDPOINT=$API_ENDPOINT
GATEWAY_ID=$GATEWAY_ID
EOF

echo "  Env file: $ENV_FILE"
echo "  Redeploy: ./scripts/redeploy-cdk.sh $ENV_FILE"
echo ""
echo "============================================="
