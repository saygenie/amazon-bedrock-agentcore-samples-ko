#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# setup.sh에서 생성한 .env 파일을 사용하여 CDK 스택을 다시 배포합니다.
#
# 사용법:
#   ./scripts/redeploy-cdk.sh .env.MyStack
#   ./scripts/redeploy-cdk.sh                  # .env.* 파일이 하나뿐이면 자동 감지
#
# 환경 파일은 setup.sh 끝에서 생성되며 전체 재배포에 필요한 모든 CDK context 변수를
# 포함합니다. 개발 중 Lambda 코드, CDK 스택 또는 OpenAPI spec을 변경했을 때 사용합니다.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CDK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- 환경 파일 찾기 ---
ENV_FILE="${1:-}"

if [ -z "$ENV_FILE" ]; then
  # 자동 감지: CDK_DIR에서 .env.* 파일 찾기
  ENV_FILES=("$CDK_DIR"/.env.*)
  if [ ${#ENV_FILES[@]} -eq 0 ] || [ ! -f "${ENV_FILES[0]}" ]; then
    echo "No .env.* file found in $CDK_DIR"
    echo "Usage: $0 <env-file>"
    echo "Run setup.sh first to generate one."
    exit 1
  elif [ ${#ENV_FILES[@]} -eq 1 ]; then
    ENV_FILE="${ENV_FILES[0]}"
    echo "Auto-detected: $ENV_FILE"
  else
    echo "Multiple env files found:"
    for f in "${ENV_FILES[@]}"; do echo "  $(basename "$f")"; done
    echo ""
    echo "Usage: $0 <env-file>"
    exit 1
  fi
fi

if [ ! -f "$ENV_FILE" ]; then
  # CDK_DIR 기준 상대 경로 시도
  if [ -f "$CDK_DIR/$ENV_FILE" ]; then
    ENV_FILE="$CDK_DIR/$ENV_FILE"
  else
    echo "File not found: $ENV_FILE"
    exit 1
  fi
fi

# --- 환경 파일 로드 ---
set -a
source "$ENV_FILE"
set +a

echo "=== Redeploying $STACK_NAME ==="
echo "  Region:  $AWS_REGION"
echo "  Tenant:  $ENTRA_TENANT_ID ($ENTRA_TENANT_TYPE)"
echo ""

# --- CDK context 구성 ---
CDK_CONTEXT="-c stackName=$STACK_NAME"
CDK_CONTEXT="$CDK_CONTEXT -c entra:tenantId=$ENTRA_TENANT_ID"
CDK_CONTEXT="$CDK_CONTEXT -c entra:appAClientId=$ENTRA_APP_A_CLIENT_ID"
CDK_CONTEXT="$CDK_CONTEXT -c entra:appBClientId=$ENTRA_APP_B_CLIENT_ID"
CDK_CONTEXT="$CDK_CONTEXT -c entra:tenantType=$ENTRA_TENANT_TYPE"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:providerArn=$OAUTH_PROVIDER_ARN"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:secretArn=$OAUTH_SECRET_ARN"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:callbackUrl=$OAUTH_CALLBACK_URL"
CDK_CONTEXT="$CDK_CONTEXT -c oauth:providerName=$OAUTH_PROVIDER_NAME"

if [ -n "${ENTRA_CIAM_DOMAIN:-}" ]; then
  CDK_CONTEXT="$CDK_CONTEXT -c entra:ciamDomain=$ENTRA_CIAM_DOMAIN"
fi
if [ -n "${RESOURCE_SUFFIX:-}" ]; then
  CDK_CONTEXT="$CDK_CONTEXT -c resourceSuffix=$RESOURCE_SUFFIX"
fi
if [ -n "${OPENAPI_PATH:-}" ]; then
  # CDK_DIR을 기준으로 상대 경로 확인
  if [[ "$OPENAPI_PATH" != /* ]]; then
    OPENAPI_PATH="$CDK_DIR/$OPENAPI_PATH"
  fi
  CDK_CONTEXT="$CDK_CONTEXT -c openapi:path=$OPENAPI_PATH"
fi
if [ -n "${OIDC_PROVIDER_ARN:-}" ]; then
  CDK_CONTEXT="$CDK_CONTEXT -c oidc:providerArn=$OIDC_PROVIDER_ARN"
fi

# --- 배포 ---
CDK_DEFAULT_REGION="$AWS_REGION" npx cdk deploy "$STACK_NAME" \
  --require-approval never \
  $CDK_CONTEXT \
  --app "npx ts-node --prefer-ts-exts bin/cdk.ts" \
  --output "cdk.out-${STACK_NAME}"

echo ""
echo "✓ Redeployed $STACK_NAME"
echo "  Endpoint: ${API_ENDPOINT:-<check CloudFormation outputs>}"
