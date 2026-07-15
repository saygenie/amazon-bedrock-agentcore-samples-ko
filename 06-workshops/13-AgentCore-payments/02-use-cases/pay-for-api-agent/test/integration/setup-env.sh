#!/usr/bin/env bash
# env-sample.txt를 기반으로 .env를 만들고 새 USER_ID를 생성합니다. 멱등성이 있어
# 재실행해도 기존 값을 유지합니다.
#
# 사용법:
#   bash test/integration/setup-env.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/setup_env.py"
