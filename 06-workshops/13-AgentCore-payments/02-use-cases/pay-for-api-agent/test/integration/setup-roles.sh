#!/usr/bin/env bash
# setup-roles.sh - Notebook에서 assume할 네 개의 IAM role을 생성합니다.
#
# 다음 role을 멱등 방식으로 생성합니다.
#   AgentCorePaymentsControlPlaneRole      - Manager/Connector/CredentialProvider 관리
#   AgentCorePaymentsManagementRole        - Instrument/Session 관리(ProcessPayment 명시적 거부)
#   AgentCorePaymentsProcessPaymentRole    - 결제 서명, Instrument/Session 조회
#   AgentCorePaymentsResourceRetrievalRole - service가 assume하고 runtime에 credential 조회
#
# Policy는 AgentCore Payments에서 권장하는 네 role 직무 분리 모델
# (ControlPlane/Management/ProcessPayment/ResourceRetrieval)을 기반으로 합니다.
# 전체 policy 내용은 기본 README를 참조하세요. Role 생성 후 Notebook이 추가
# 편집 없이 읽을 수 있도록 ARN을 use case의 .env에 기록합니다.
#
# 재실행해도 안전합니다. 기존 role은 유지하면서 policy를 제자리에서 업데이트하고
# .env 값이 비어 있을 때만 기록합니다.
#
# 사용법:
#   bash test/integration/setup-roles.sh

set -euo pipefail

# ── 경로 처리 ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${USE_CASE_ROOT}/.env"
TEMPLATE="${USE_CASE_ROOT}/env-sample.txt"

# ── 사전 요구 사항 ─────────────────────────────────────────────────────
command -v aws >/dev/null 2>&1 || {
    echo "❌ aws CLI not found — install AWS CLI v2 first." >&2
    exit 1
}

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
if [ -z "${ACCOUNT_ID}" ] || [ "${ACCOUNT_ID}" = "None" ]; then
    echo "❌ Could not resolve AWS account. Run 'aws configure' first." >&2
    exit 1
fi

echo "✅ Account: ${ACCOUNT_ID}"
echo

# ── Role 정의 ─────────────────────────────────────────────────────────
CP_ROLE="AgentCorePaymentsControlPlaneRole"
MGMT_ROLE="AgentCorePaymentsManagementRole"
PP_ROLE="AgentCorePaymentsProcessPaymentRole"
RR_ROLE="AgentCorePaymentsResourceRetrievalRole"

# 이 account의 모든 IAM principal이 role을 assume할 수 있게 하는 표준 account
# trust policy입니다. 자습서에는 충분하지만 production에서는 범위를 강화하세요.
ACCOUNT_TRUST_POLICY=$(cat <<JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "arn:aws:iam::${ACCOUNT_ID}:root"},
            "Action": "sts:AssumeRole"
        }
    ]
}
JSON
)

# ResourceRetrievalRole용 service trust policy입니다. Service는 작업 중인
# Payment Manager를 대신해 이 role을 assume하며 condition key가 이 account로
# 액세스 범위를 제한합니다.
SERVICE_TRUST_POLICY=$(cat <<JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": "${ACCOUNT_ID}"}
            }
        }
    ]
}
JSON
)

# ── ControlPlaneRole policy ───────────────────────────────────────────
RR_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${RR_ROLE}"

CP_POLICY=$(cat <<JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowPaymentManagerOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreatePaymentManager",
                "bedrock-agentcore:GetPaymentManager",
                "bedrock-agentcore:ListPaymentManagers",
                "bedrock-agentcore:DeletePaymentManager",
                "bedrock-agentcore:UpdatePaymentManager"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*"]
        },
        {
            "Sid": "AllowPaymentConnectorOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreatePaymentConnector",
                "bedrock-agentcore:GetPaymentConnector",
                "bedrock-agentcore:ListPaymentConnectors",
                "bedrock-agentcore:DeletePaymentConnector",
                "bedrock-agentcore:UpdatePaymentConnector"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*/connector/*"]
        },
        {
            "Sid": "AllowCredentialProviderOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreatePaymentCredentialProvider",
                "bedrock-agentcore:GetPaymentCredentialProvider",
                "bedrock-agentcore:ListPaymentCredentialProviders",
                "bedrock-agentcore:DeletePaymentCredentialProvider",
                "bedrock-agentcore:UpdatePaymentCredentialProvider"
            ],
            "Resource": ["arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:token-vault/*/paymentcredentialprovider/*"]
        },
        {
            "Sid": "AllowVendedLogDelivery",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:AllowVendedLogDeliveryForResource"],
            "Resource": ["arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*"]
        },
        {
            "Sid": "AllowPassResourceRetrievalRole",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "${RR_ROLE_ARN}",
            "Condition": {
                "StringEquals": {"iam:PassedToService": "bedrock-agentcore.amazonaws.com"}
            }
        }
    ]
}
JSON
)

# ── ManagementRole policy ─────────────────────────────────────────────
# 이 role은 account의 모든 PaymentManager/Instrument/Session을 관리합니다.
# Role 생성 시점에는 Manager ID가 없으므로(Notebook이 4절에서 생성) Resource의
# wildcard는 account 범위로만 제한되고 특정 Manager로는 제한되지 않습니다.
#
# Production에서는 Manager ID가 안정된 후 `*` segment를 구체적인 ID(예:
# `payment-manager/${MANAGER_ID}`)로 바꾸거나
# `"Condition": {"StringLike": {"aws:ResourceTag/Project": "pay-for-api"}}`와
# 같은 tag 기반 condition을 추가해 role을 tag가 지정된 resource로 제한하세요.
MGMT_POLICY=$(cat <<JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowPaymentManagement",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreatePaymentInstrument",
                "bedrock-agentcore:GetPaymentInstrument",
                "bedrock-agentcore:GetPaymentInstrumentBalance",
                "bedrock-agentcore:ListPaymentInstruments",
                "bedrock-agentcore:DeletePaymentInstrument",
                "bedrock-agentcore:CreatePaymentSession",
                "bedrock-agentcore:GetPaymentSession",
                "bedrock-agentcore:ListPaymentSessions",
                "bedrock-agentcore:UpdatePaymentSession",
                "bedrock-agentcore:DeletePaymentSession"
            ],
            "Resource": [
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*/instrument/*",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*/session/*"
            ]
        },
        {
            "Sid": "DenyProcessPayment",
            "Effect": "Deny",
            "Action": "bedrock-agentcore:ProcessPayment",
            "Resource": "*"
        }
    ]
}
JSON
)

# ── ProcessPaymentRole policy ─────────────────────────────────────────
PP_POLICY=$(cat <<JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowProcessPayment",
            "Effect": "Allow",
            "Action": "bedrock-agentcore:ProcessPayment",
            "Resource": ["arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*/session/*"]
        },
        {
            "Sid": "AllowPaymentReadOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetPaymentInstrument",
                "bedrock-agentcore:GetPaymentInstrumentBalance",
                "bedrock-agentcore:GetPaymentSession"
            ],
            "Resource": [
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*/instrument/*",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:payment-manager/*/session/*"
            ]
        }
    ]
}
JSON
)

# ── ResourceRetrievalRole policy ──────────────────────────────────────
# 기본 권한만 포함합니다. Manager에 connector를 추가하면 connector별 권한은
# service가 직접 추가합니다.
RR_POLICY=$(cat <<JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "WorkloadIdentityCreation",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:CreateWorkloadIdentity"],
            "Resource": [
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default/workload-identity/*"
            ]
        },
        {
            "Sid": "WorkloadIdentityAccess",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:GetWorkloadAccessToken"],
            "Resource": [
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default/workload-identity/*"
            ]
        },
        {
            "Sid": "PaymentTokenBaseAccess",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:GetResourcePaymentToken"],
            "Resource": [
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:token-vault/default",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default",
                "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:workload-identity-directory/default/workload-identity/*"
            ]
        }
    ]
}
JSON
)

# ── Helper ────────────────────────────────────────────────────────────
role_exists() {
    aws iam get-role --role-name "$1" >/dev/null 2>&1
}

create_or_update_role() {
    local name="$1"
    local trust="$2"
    local policy_name="$3"
    local policy_doc="$4"

    if role_exists "${name}"; then
        echo "  ↺ ${name} already exists — updating trust + policy"
        aws iam update-assume-role-policy \
            --role-name "${name}" \
            --policy-document "${trust}" >/dev/null
    else
        echo "  + Creating ${name}"
        aws iam create-role \
            --role-name "${name}" \
            --assume-role-policy-document "${trust}" \
            --description "AgentCore Payments tutorial role" >/dev/null
    fi

    aws iam put-role-policy \
        --role-name "${name}" \
        --policy-name "${policy_name}" \
        --policy-document "${policy_doc}" >/dev/null
    echo "    ↳ policy ${policy_name} applied"
}

# ── Role 생성/업데이트 ────────────────────────────────────────────────
echo "=== Creating / updating IAM roles ==="
create_or_update_role "${CP_ROLE}"   "${ACCOUNT_TRUST_POLICY}" "ControlPlanePolicy"     "${CP_POLICY}"
create_or_update_role "${MGMT_ROLE}" "${ACCOUNT_TRUST_POLICY}" "ManagementPolicy"       "${MGMT_POLICY}"
create_or_update_role "${PP_ROLE}"   "${ACCOUNT_TRUST_POLICY}" "ProcessPaymentPolicy"   "${PP_POLICY}"
create_or_update_role "${RR_ROLE}"   "${SERVICE_TRUST_POLICY}" "ResourceRetrievalPolicy" "${RR_POLICY}"
echo

CP_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${CP_ROLE}"
MGMT_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${MGMT_ROLE}"
PP_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${PP_ROLE}"

echo "=== Role ARNs ==="
echo "  CONTROL_PLANE_ROLE_ARN:      ${CP_ROLE_ARN}"
echo "  MANAGEMENT_ROLE_ARN:         ${MGMT_ROLE_ARN}"
echo "  PROCESS_PAYMENT_ROLE_ARN:    ${PP_ROLE_ARN}"
echo "  RESOURCE_RETRIEVAL_ROLE_ARN: ${RR_ROLE_ARN}"
echo

# ── ARN을 .env에 다시 기록 ────────────────────────────────────────────
# 값이 비어 있거나 <ACCOUNT_ID> placeholder가 있는 키만 설정합니다.
# 직접 편집한 값은 덮어쓰지 않습니다.
if [ ! -f "${ENV_FILE}" ]; then
    if [ -f "${TEMPLATE}" ]; then
        cp "${TEMPLATE}" "${ENV_FILE}"
        echo "  Seeded ${ENV_FILE} from env-sample.txt"
    else
        touch "${ENV_FILE}"
        echo "  Created empty ${ENV_FILE}"
    fi
fi

write_env_var() {
    local key="$1"
    local value="$2"
    # KEY=, KEY=<…>, KEY=arn:aws:iam::<ACCOUNT_ID>:… 형식을 찾습니다.
    local current
    current="$(awk -F '=' -v k="${key}" '$1 == k { sub(/^[^=]+=/, ""); print; exit }' "${ENV_FILE}" 2>/dev/null || true)"

    case "${current}" in
        "" | "<"* | *"<ACCOUNT_ID>"*)
            if grep -q "^${key}=" "${ENV_FILE}"; then
                # sed -i 종류에 의존하지 않도록 임시 파일로 제자리 업데이트합니다.
                awk -F '=' -v k="${key}" -v v="${value}" \
                    '{ if ($1 == k) print k "=" v; else print $0 }' "${ENV_FILE}" > "${ENV_FILE}.tmp"
                mv "${ENV_FILE}.tmp" "${ENV_FILE}"
            else
                echo "${key}=${value}" >> "${ENV_FILE}"
            fi
            echo "  ✅ Wrote ${key} to .env"
            ;;
        *)
            echo "  ↷ ${key} already set — leaving alone (${current})"
            ;;
    esac
}

echo "=== Updating ${ENV_FILE} ==="
write_env_var "CONTROL_PLANE_ROLE_ARN"      "${CP_ROLE_ARN}"
write_env_var "MANAGEMENT_ROLE_ARN"         "${MGMT_ROLE_ARN}"
write_env_var "PROCESS_PAYMENT_ROLE_ARN"    "${PP_ROLE_ARN}"
write_env_var "RESOURCE_RETRIEVAL_ROLE_ARN" "${RR_ROLE_ARN}"

echo
echo "✅ Done. Next: run the §2 setup cell in the notebook to fill in credentials"
