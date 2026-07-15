#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# 인증 흐름을 테스트할 데모 사용자를 EntraID tenant에 생성합니다.
#
# 사용법:
#   ./create-demo-user.sh --tenant-id <id> --domain <domain> <username> [password]
#
# 예:
#   ./create-demo-user.sh --tenant-id abc123 --domain contoso.onmicrosoft.com demo1
#   ./create-demo-user.sh --tenant-id abc123 --domain contoso.onmicrosoft.com demo2 MyP@ssw0rd123
#
# 사전 요구 사항:
#   1. Azure CLI 설치 및 로그인:
#        az login --tenant <tenant-id> --allow-no-subscriptions
#      (CIAM 전용 tenant에는 --allow-no-subscriptions가 필요함)
#      로그인한 사용자에게 User Administrator(또는 Global Admin) 역할이 있어야 함
#   2. jq 설치
#
# 이 스크립트는 Azure CLI 토큰(`az login`에서 가져옴)을 사용하여 Graph API를 호출합니다.
# 관리자 사용자 ID로 실행되므로 애플리케이션 권한은 필요하지 않습니다.
# =============================================================================

set -euo pipefail

# --- 인자 파싱 ---
TENANT_ID=""
DOMAIN=""
USERNAME=""
PASSWORD=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --tenant-id) TENANT_ID="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *)
      if [ -z "$USERNAME" ]; then
        USERNAME="$1"
      elif [ -z "$PASSWORD" ]; then
        PASSWORD="$1"
      fi
      shift ;;
  esac
done

if [ -z "$TENANT_ID" ] || [ -z "$DOMAIN" ] || [ -z "$USERNAME" ]; then
  echo "Usage: $0 --tenant-id <id> --domain <domain> <username> [password]"
  echo ""
  echo "Creates a demo user: <username>@<domain>"
  echo "If no password is given, one is auto-generated."
  echo ""
  echo "Prerequisite: az login --tenant <tenant-id> --allow-no-subscriptions"
  exit 1
fi

# 암호가 제공되지 않으면 자동 생성
if [ -z "$PASSWORD" ]; then
  PASSWORD="Demo$(date +%s | shasum | head -c 8)!Aa1"  # pragma: allowlist secret
fi

EMAIL="${USERNAME}@${DOMAIN}"

echo "Creating user: ${EMAIL}"
echo "Password: ${PASSWORD}"
echo ""

# --- 1단계: Azure CLI에서 Graph API 토큰 가져오기 ---
echo "→ Getting Graph API token from Azure CLI..."
ACCESS_TOKEN=$(az account get-access-token \
  --resource https://graph.microsoft.com \
  --tenant "${TENANT_ID}" \
  --query accessToken -o tsv 2>/dev/null) || {
  echo "✗ Failed to get token. Are you logged in?"
  echo ""
  echo "Run:  az login --tenant ${TENANT_ID} --allow-no-subscriptions"
  echo "  (--allow-no-subscriptions is needed for CIAM-only tenants)"
  echo "The account must have User Administrator or Global Admin role."
  exit 1
}

echo "✓ Got Graph API token (via az cli)"

# --- 2단계: Graph API를 통해 사용자 생성 ---
echo "→ Creating user..."
CREATE_RESPONSE=$(curl -s -X POST \
  "https://graph.microsoft.com/v1.0/users" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"displayName\": \"Demo User (${USERNAME})\",
    \"identities\": [
      {
        \"signInType\": \"emailAddress\",
        \"issuer\": \"${DOMAIN}\",
        \"issuerAssignedId\": \"${EMAIL}\"
      }
    ],
    \"mail\": \"${EMAIL}\",
    \"passwordProfile\": {
      \"password\": \"${PASSWORD}\",
      \"forceChangePasswordNextSignIn\": false
    },
    \"passwordPolicies\": \"DisablePasswordExpiration\"
  }")

USER_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')

if [ "$USER_ID" = "null" ] || [ -z "$USER_ID" ]; then
  ERROR_CODE=$(echo "$CREATE_RESPONSE" | jq -r '.error.code // empty')
  ERROR_MSG=$(echo "$CREATE_RESPONSE" | jq -r '.error.message // empty')
  echo "✗ Failed to create user:"
  echo "  Error: ${ERROR_CODE}"
  echo "  Message: ${ERROR_MSG}"
  exit 1
fi

echo "✓ User created"
echo ""
echo "=== Demo User Details ==="
echo "  Email:    ${EMAIL}"
echo "  Password: ${PASSWORD}"
echo "  User ID:  ${USER_ID}"
echo "  Display:  Demo User (${USERNAME})"
