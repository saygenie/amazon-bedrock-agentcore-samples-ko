#!/usr/bin/env bash
# =============================================================
# deploy.sh - AgentCore Payments x402 content provider 배포
#
# 사용법:
#   PAY_TO=0x<your-wallet-address> bash deploy.sh
#
# 선택적 재정의:
#   PRICE_USDC_UNITS=100000   Price in USDC atomic units (default: 100000 = $0.10 USDC)
#   NETWORK=eip155:84532      CAIP-2 network (default: Base Sepolia testnet)
#   USDC_ADDRESS=0x...        USDC contract address (default: Base Sepolia USDC)
#   AWS_PROFILE=myprofile     Named AWS CLI profile to use
#
# 수행 작업:
#   1. CDK dependency 설치
#   2. AWS account/region에서 CDK bootstrap 실행(다시 실행해도 안전함)
#   3. S3 + CloudFront distribution + Lambda@Edge paywall handler 배포
#   4. CloudFront distribution URL 출력 - .env 파일에 복사
#
# 정리: cdk/ 디렉터리에서 `cdk destroy`를 실행하거나 README를 참조하세요.
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CDK_DIR="$SCRIPT_DIR/cdk"

# ── 필수 입력 검증 ──────────────────────────────────────────────────────────
if [[ -z "${PAY_TO:-}" ]]; then
  echo ""
  echo "ERROR: PAY_TO is required — set it to your merchant wallet address."
  echo "  Usage: PAY_TO=0x<your-wallet-address> bash deploy.sh"
  echo ""
  exit 1
fi

PRICE_USDC_UNITS="${PRICE_USDC_UNITS:-100000}"
NETWORK="${NETWORK:-eip155:84532}"
USDC_ADDRESS="${USDC_ADDRESS:-0x036CbD53842c5426634e7929541eC2318f3dCF7e}"

PRICE_USDC=$(python3 -c "print(f'{int('$PRICE_USDC_UNITS') / 1_000_000:.6f}')" 2>/dev/null || echo "$PRICE_USDC_UNITS atomic units")

echo ""
echo "AgentCore Payments — content provider deploy"
echo "============================================="
echo "  Pay-to wallet:   $PAY_TO"
echo "  Price:           \$${PRICE_USDC} USDC ($PRICE_USDC_UNITS atomic units)"
echo "  Network:         $NETWORK"
echo "  USDC contract:   $USDC_ADDRESS"
echo ""

# ── CDK dependency 설치 ──────────────────────────────────────────────────────
echo "Installing CDK dependencies..."
cd "$CDK_DIR"
npm install --silent

# ── CDK bootstrap(멱등성이 있어 매번 실행해도 안전함) ────────────────────────
echo "Bootstrapping CDK (us-east-1)..."
# Lambda@Edge는 us-east-1에 있어야 하므로 해당 region을 bootstrap합니다.
npx cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1 \
  ${AWS_PROFILE:+--profile "$AWS_PROFILE"} 2>&1 | tail -5

# ── 배포 ─────────────────────────────────────────────────────────────────────
echo ""
echo "Deploying stack (this takes ~5 minutes for CloudFront)..."
npx cdk deploy \
  --require-approval never \
  --context "PAY_TO=$PAY_TO" \
  --context "PRICE_USDC_UNITS=$PRICE_USDC_UNITS" \
  --context "NETWORK=$NETWORK" \
  --context "USDC_ADDRESS=$USDC_ADDRESS" \
  ${AWS_PROFILE:+--profile "$AWS_PROFILE"}

# ── distribution URL 추출 및 표시 ────────────────────────────────────────────
echo ""
DIST_URL=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreContentProvider \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='ContentDistributionUrl'].OutputValue" \
  --output text \
  ${AWS_PROFILE:+--profile "$AWS_PROFILE"})

echo "========================================================"
echo "✅ Content provider deployed!"
echo ""
echo "  CloudFront URL:  $DIST_URL"
echo "  Paywall demo:    $DIST_URL/article/paywall-demo"
echo ""
echo "Copy the CloudFront URL into your .env file:"
echo "  CONTENT_DISTRIBUTION_URL=$DIST_URL"
echo "========================================================"
