#!/usr/bin/env bash
# AWS CDK를 통해 Fun Facts x402 seller stack을 배포합니다.
#
# Lambda는 node_modules가 미리 설치된 Node.js를 사용합니다
# (agentcore-payments seller와 같은 패턴). 따라서 `cdk deploy`가 asset을
# package하기 전에 이 script가 seller/lambda/에서 `npm install`을 실행합니다.
#
# 사전 요구 사항:
#   - AWS CLI v2 configured (aws configure)
#   - AWS CDK v2 installed (npm install -g aws-cdk)
#   - Node.js 20+ and npm
#   - Python 3.10+ with pip (for the CDK Python dependencies)
#
# 선택 사항:
#   - SELLER_WALLET_ADDRESS=0x…            # EVM (Base Sepolia) payout wallet
#   - SELLER_SOLANA_WALLET_ADDRESS=…       # Solana (Devnet) payout wallet
#   - X402_FACILITATOR_URL=…               # Override facilitator (defaults to x402.org)
#
# 사용법(어느 경로에서나 실행 가능):
#   bash test/integration/deploy-seller.sh
#
# 배포 후 출력된 SellerApiUrl을 .env의 SELLER_API_URL로 복사하세요.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script는 <use-case>/test/integration/에 있으므로 ../../로 seller/와 .env의
# 기준인 use case root를 확인합니다.
USE_CASE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LAMBDA_DIR="${USE_CASE_ROOT}/seller/lambda"
CDK_DIR="${USE_CASE_ROOT}/seller/cdk"

# Notebook 2절에서 입력받은 값이 CDK 배포에 전달되도록 .env에서 payout wallet과
# region을 가져옵니다. 현재 session에 이미 설정된 shell 환경 변수가 우선합니다.
if [ -f "${USE_CASE_ROOT}/.env" ]; then
    # "<ACCOUNT_ID>"처럼 교체되지 않은 placeholder를 확인합니다. Bash는 source할 때
    # `<ACCOUNT_ID>`를 redirection으로 해석해 "No such file or directory" 오류를
    # 낼 수 있으므로 사용자에게 원인을 명확히 안내합니다.
    if grep -q "<ACCOUNT_ID>" "${USE_CASE_ROOT}/.env"; then
        echo "❌ ${USE_CASE_ROOT}/.env still contains <ACCOUNT_ID> placeholders." >&2
        echo "   Run:  bash test/integration/setup-roles.sh" >&2
        echo "   (or re-run §2 in the notebook) before deploying." >&2
        exit 1
    fi
    set -a
    # shellcheck disable=SC1091
    source "${USE_CASE_ROOT}/.env"
    set +a
fi

REGION="${AWS_REGION:-us-west-2}"

echo "── Pay for API — Seller Deploy ────────────────────────────"
echo "Region:   ${REGION}"
echo "Lambda:   ${LAMBDA_DIR}"
echo "CDK:      ${CDK_DIR}"
echo ""

# ── 0. Wallet 기본 확인 ──
warn=()
if [ -z "${SELLER_WALLET_ADDRESS:-}" ]; then
    warn+=("  • SELLER_WALLET_ADDRESS (EVM) — required for Base Sepolia payments")
fi
if [ -z "${SELLER_SOLANA_WALLET_ADDRESS:-}" ]; then
    warn+=("  • SELLER_SOLANA_WALLET_ADDRESS (Solana) — required for Solana Devnet payments")
fi
if [ ${#warn[@]} -gt 0 ]; then
    echo "⚠️  One or more payout wallets are not set:"
    for line in "${warn[@]}"; do
        echo "${line}"
    done
    echo ""
    echo "   Without a payout wallet for a given network the seller emits an"
    echo "   invalid 402 for that network and the agent cannot pay on it."
    echo "   At minimum you need SELLER_WALLET_ADDRESS for the §8 EVM run."
    echo ""
    echo "   Set the missing ones in .env and re-run this script, e.g.:"
    echo "     export SELLER_WALLET_ADDRESS=0xYourBaseSepoliaAddress"
    echo "     export SELLER_SOLANA_WALLET_ADDRESS=YourSolanaDevnetAddress"
    echo ""
    read -r -p "   Continue anyway? [y/N] " ok
    case "${ok}" in
        y|Y|yes|YES) ;;
        *) echo "   Aborted."; exit 1 ;;
    esac
    echo ""
fi

# ── 1. Lambda node_modules 설치 ──
echo "Installing Lambda node_modules..."
(cd "${LAMBDA_DIR}" && npm install --silent --omit=dev)

# ── 2. CDK Python venv ──
if [ ! -d "${CDK_DIR}/.venv" ]; then
    echo "Creating Python venv for CDK..."
    python3 -m venv "${CDK_DIR}/.venv"
fi
# shellcheck disable=SC1091
source "${CDK_DIR}/.venv/bin/activate"

echo "Installing CDK Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "${CDK_DIR}/requirements.txt"

# ── 3. Bootstrap(멱등) ──
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "${REGION}" >/dev/null 2>&1; then
    echo ""
    echo "Bootstrapping CDK for ${ACCOUNT_ID}/${REGION}..."
    (cd "${CDK_DIR}" && cdk bootstrap "aws://${ACCOUNT_ID}/${REGION}")
fi

# ── 4. 배포 ──
echo ""
echo "Deploying AgentCorePaymentsFunFactsSellerStack..."
(cd "${CDK_DIR}" && cdk deploy --require-approval never --outputs-file ./outputs.json)

API_URL="$(python3 -c 'import json; print(json.load(open("'"${CDK_DIR}"'/outputs.json"))["AgentCorePaymentsFunFactsSellerStack"]["SellerApiUrl"])')"
EVM_WALLET="$(python3 -c 'import json; print(json.load(open("'"${CDK_DIR}"'/outputs.json"))["AgentCorePaymentsFunFactsSellerStack"]["SellerEvmWallet"])')"
SVM_WALLET="$(python3 -c 'import json; print(json.load(open("'"${CDK_DIR}"'/outputs.json"))["AgentCorePaymentsFunFactsSellerStack"]["SellerSolanaWallet"])')"

echo ""
echo "── Deploy Complete ─────────────────────────────────────────"
echo "✅ SellerApiUrl:        ${API_URL}"
echo "   EVM payout wallet:   ${EVM_WALLET}"
echo "   Solana payout wallet: ${SVM_WALLET}"
echo ""

# 사용자가 직접 편집하지 않아도 다음 load_dotenv()에서 Notebook 3/5/7절이
# 자동으로 읽도록 SELLER_API_URL을 .env에 upsert합니다. 주석과 다른 줄은
# 보존합니다.
ENV_FILE="${USE_CASE_ROOT}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    cp "${USE_CASE_ROOT}/env-sample.txt" "${ENV_FILE}"
fi
python3 - <<PY
import pathlib
path = pathlib.Path("${ENV_FILE}")
lines = path.read_text().splitlines() if path.exists() else []
out, replaced = [], False
for line in lines:
    if line.startswith("SELLER_API_URL="):
        out.append(f"SELLER_API_URL=${API_URL}")
        replaced = True
    else:
        out.append(line)
if not replaced:
    out.append(f"SELLER_API_URL=${API_URL}")
path.write_text("\n".join(out) + "\n")
PY
echo "💾 .env updated: SELLER_API_URL=${API_URL}"
