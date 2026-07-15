#!/usr/bin/env bash
# Fun Facts seller stack을 제거합니다.
#
# 사용법(어느 경로에서나 실행 가능):
#   bash test/integration/destroy-seller.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script는 <use-case>/test/integration/에 있으므로 ../../로 use case root를
# 확인합니다.
USE_CASE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CDK_DIR="${USE_CASE_ROOT}/seller/cdk"

if [ -d "${CDK_DIR}/.venv" ]; then
    # shellcheck disable=SC1091
    source "${CDK_DIR}/.venv/bin/activate"
fi

echo "Destroying AgentCorePaymentsFunFactsSellerStack..."
(cd "${CDK_DIR}" && cdk destroy --force)

echo ""
echo "✅ Seller stack destroyed."
