#!/usr/bin/env bash
# AWS CDK를 통해 Pay for API buyer agent를 AgentCore Runtime에 배포합니다.
#
# Agent 컨테이너 image는 로컬 장비가 아닌 AWS CodeBuild에서 build하므로 Docker를
# 설치할 필요가 없습니다. `cdk deploy`가 agent/container/를 S3 asset으로
# 업로드하면 CodeBuild가 이를 가져와 build한 뒤 ECR로 push하고, Runtime
# resource가 호출 시 ECR에서 가져옵니다.
#
# 사전 요구 사항:
#   - AWS CLI v2 configured (aws configure)
#   - AWS CDK v2 installed (npm install -g aws-cdk)
#   - Python 3.10+ with pip (for the CDK Python dependencies)
#
# 사용법(어느 경로에서나 실행 가능):
#   bash test/integration/deploy-agent.sh
#
# 출력을 agent/cdk/outputs.json에 기록합니다. Notebook 8절은 이 파일에서
# Runtime ARN을 읽습니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CDK_DIR="${USE_CASE_ROOT}/agent/cdk"
CONTAINER_DIR="${USE_CASE_ROOT}/agent/container"

# Notebook에서 provisioning한 값과 일치하도록 .env에서 region을 가져옵니다.
if [ -f "${USE_CASE_ROOT}/.env" ]; then
    # env-sample.txt에서 교체되지 않은 placeholder가 있는지 확인합니다.
    if grep -q "<ACCOUNT_ID>" "${USE_CASE_ROOT}/.env"; then
        echo "❌ ${USE_CASE_ROOT}/.env still contains <ACCOUNT_ID> placeholders." >&2
        echo "   Run:  bash test/integration/setup-roles.sh" >&2
        echo "   before deploying the agent." >&2
        exit 1
    fi
    set -a
    # shellcheck disable=SC1091
    source "${USE_CASE_ROOT}/.env"
    set +a
fi

REGION="${AWS_REGION:-us-west-2}"

echo "── Pay for API — Agent Deploy ─────────────────────────────"
echo "Region:    ${REGION}"
echo "CDK:       ${CDK_DIR}"
echo "Container: ${CONTAINER_DIR}"
echo ""
echo "The container image is built in AWS CodeBuild (no Docker needed on"
echo "this machine). First run can take 4–6 minutes for the build; subsequent"
echo "deploys only rebuild if agent/container/ changed."
echo ""

# ── 1. CDK Python venv ──
if [ ! -d "${CDK_DIR}/.venv" ]; then
    echo "Creating Python venv for CDK..."
    python3 -m venv "${CDK_DIR}/.venv"
fi
# shellcheck disable=SC1091
source "${CDK_DIR}/.venv/bin/activate"

echo "Installing CDK Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "${CDK_DIR}/requirements.txt"

# ── 2. Bootstrap(멱등) ──
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "${REGION}" >/dev/null 2>&1; then
    echo ""
    echo "Bootstrapping CDK for ${ACCOUNT_ID}/${REGION}..."
    (cd "${CDK_DIR}" && cdk bootstrap "aws://${ACCOUNT_ID}/${REGION}")
else
    echo "CDK already bootstrapped for ${ACCOUNT_ID}/${REGION}."
fi

# ── 3. 배포 ──
echo ""
echo "Deploying AgentCorePaymentsBuyerAgentStack..."
echo "(CDK synth + asset upload + CodeBuild run — typically 5–8 min on the"
echo " first deploy, ~2 min on subsequent runs if nothing changed.)"
(cd "${CDK_DIR}" && cdk deploy --require-approval never --outputs-file ./outputs.json)

RUNTIME_ARN="$(python3 -c 'import json; print(json.load(open("'"${CDK_DIR}"'/outputs.json"))["AgentCorePaymentsBuyerAgentStack"]["AgentRuntimeArn"])')"
RUNTIME_ID="$(python3 -c 'import json; print(json.load(open("'"${CDK_DIR}"'/outputs.json"))["AgentCorePaymentsBuyerAgentStack"]["AgentRuntimeId"])')"

echo ""
echo "── Deploy Complete ─────────────────────────────────────────"
echo "✅ AgentRuntimeArn: ${RUNTIME_ARN}"
echo "   AgentRuntimeId: ${RUNTIME_ID}"
echo ""
echo "The notebook §8 reads agent/cdk/outputs.json to pick up these values."
