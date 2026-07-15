#!/usr/bin/env bash
# Pay for API buyer agent runtime과 CloudFormation stack을 제거합니다.
#
# deploy-agent.sh가 생성한 CDK venv를 사용합니다. 독립 실행에 필요하면 새로
# 생성합니다. 멱등성이 있어 재실행해도 안전하며, stack이 이미 없으면 CDK가
# "No stacks match the name pattern"을 보고하고 정상 종료합니다.
#
# 사용법(어느 경로에서나 실행 가능):
#   bash test/integration/destroy-agent.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CDK_DIR="${USE_CASE_ROOT}/agent/cdk"

# deploy-agent.sh가 만든 CDK venv를 활성화합니다. 사용자가 artifact를 정리하는 등
# venv가 없으면 `cdk destroy`가 Python app을 synth할 수 있도록 다시 생성합니다.
if [ ! -d "${CDK_DIR}/.venv" ]; then
    echo "Creating Python venv for CDK..."
    python3 -m venv "${CDK_DIR}/.venv"
    # shellcheck disable=SC1091
    source "${CDK_DIR}/.venv/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet -r "${CDK_DIR}/requirements.txt"
else
    # shellcheck disable=SC1091
    source "${CDK_DIR}/.venv/bin/activate"
fi

echo "Destroying AgentCorePaymentsBuyerAgentStack..."
(cd "${CDK_DIR}" && cdk destroy --force)

echo ""
echo "✅ Agent runtime stack destroyed."
