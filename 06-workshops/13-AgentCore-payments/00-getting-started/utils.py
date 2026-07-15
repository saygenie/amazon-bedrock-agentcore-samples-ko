"""
AgentCore payments — 튜토리얼 Utility

AgentCore SDK에서 제공하지 않는 다음 기능만 포함합니다.
- Environment load 및 validation
- IAM role assumption
- Async resource polling(wait_for_status)
- Idempotent resource 생성
- Cognito 설정(Gateway 통합용)
- 튜토리얼 간 config 유지(.env 사용)
- Observability 설정(vended log + X-Ray)
- Privy 전용 helper
- Display helper
"""

import json
import os
import time
import uuid

import boto3
import botocore.exceptions
from dotenv import load_dotenv


# ── 고정 IAM Role 이름 ─────────────────────────────────────────
CONTROL_PLANE_ROLE = "AgentCorePaymentsControlPlaneRole"
MANAGEMENT_ROLE = "AgentCorePaymentsManagementRole"
PROCESS_PAYMENT_ROLE = "AgentCorePaymentsProcessPaymentRole"
RESOURCE_RETRIEVAL_ROLE = "AgentCorePaymentsResourceRetrievalRole"


# ═════════════════════════════════════════════════════════════════
# 환경
# ═════════════════════════════════════════════════════════════════


def load_payment_env(env_file=".env"):
    """.env 파일을 load하고 config dict를 반환합니다."""
    load_dotenv(env_file, override=True)
    return {
        "region": os.environ.get("AWS_REGION", "us-west-2"),
        "cp_endpoint": os.environ.get(
            "PAYMENTS_CP_ENDPOINT",
            f"https://bedrock-agentcore-control.{os.environ.get('AWS_REGION', 'us-west-2')}.amazonaws.com",
        ),
        "dp_endpoint": os.environ.get(
            "PAYMENTS_DP_ENDPOINT",
            f"https://bedrock-agentcore.{os.environ.get('AWS_REGION', 'us-west-2')}.amazonaws.com",
        ),
        "cred_endpoint": os.environ.get(
            "CREDENTIAL_PROVIDER_ENDPOINT",
            os.environ.get(
                "PAYMENTS_CP_ENDPOINT",
                f"https://bedrock-agentcore-control.{os.environ.get('AWS_REGION', 'us-west-2')}.amazonaws.com",
            ),
        ),
    }


def require_env(key):
    """필수 environment variable을 가져오거나 명확한 메시지와 함께 예외를 발생시킵니다."""
    val = os.environ.get(key, "").strip()
    if not val or val.startswith("<"):
        raise ValueError(f"Missing or placeholder value for {key} in .env")
    return val


# ═════════════════════════════════════════════════════════════════
# IAM role assume
# ═════════════════════════════════════════════════════════════════


def assume_role(session, role_arn, session_name="tutorial-session"):
    """IAM role을 assume하고 새 boto3 Session을 반환합니다.

    Assume한 identity를 즉시 검증하며 실패하면 예외를 발생시킵니다.

    인수:
        session: 기존 boto3.Session(STS 호출에 사용)
        role_arn: Assume할 role의 전체 ARN
        session_name: STS session name

    반환:
        Temporary credentials가 있는 boto3.Session
    """
    sts = session.client("sts")
    creds = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)["Credentials"]

    new_session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=session.region_name,
    )

    assumed_arn = new_session.client("sts").get_caller_identity()["Arn"]
    print(f"  Assumed: {assumed_arn}")
    return new_session


# ═════════════════════════════════════════════════════════════════
# IAM Role 설정(role을 inline으로 생성하므로 외부 script 불필요)
# ═════════════════════════════════════════════════════════════════

# Role 정의 — persona별 권한
# ProcessPaymentRole에는 Strands plugin이 runtime에 필요한 read action이 포함됨
#
# 이 role은 AgentCore payments operation만 포함함
# Infrastructure action(CloudWatch, X-Ray, Cognito, Gateway)은 이 role이 아니라
# caller의 기본 AWS credentials로 실행됨
# 자세한 내용은 Tutorial 00의 8b단계와 Tutorial 04의 사전 요구 사항 참조
PAYMENT_ROLE_DEFINITIONS = {
    CONTROL_PLANE_ROLE: {
        "description": "AgentCore payments: control plane operations",
        "trust": "account",
        "allow": [
            "bedrock-agentcore:CreatePaymentManager",
            "bedrock-agentcore:GetPaymentManager",
            "bedrock-agentcore:ListPaymentManagers",
            "bedrock-agentcore:DeletePaymentManager",
            "bedrock-agentcore:UpdatePaymentManager",
            "bedrock-agentcore:CreatePaymentConnector",
            "bedrock-agentcore:GetPaymentConnector",
            "bedrock-agentcore:ListPaymentConnectors",
            "bedrock-agentcore:DeletePaymentConnector",
            "bedrock-agentcore:UpdatePaymentConnector",
            "bedrock-agentcore:CreatePaymentCredentialProvider",
            "bedrock-agentcore:GetPaymentCredentialProvider",
            "bedrock-agentcore:ListPaymentCredentialProviders",
            "bedrock-agentcore:DeletePaymentCredentialProvider",
            "bedrock-agentcore:UpdatePaymentCredentialProvider",
            "bedrock-agentcore:CreateTokenVault",
            "bedrock-agentcore:AllowVendedLogDeliveryForResource",
        ],
        "pass_role": True,
        "secrets_manager_write": True,
    },
    MANAGEMENT_ROLE: {
        "description": "AgentCore payments: data plane management (instruments, sessions)",
        "trust": "account",
        "allow": [
            "bedrock-agentcore:CreatePaymentInstrument",
            "bedrock-agentcore:GetPaymentInstrument",
            "bedrock-agentcore:ListPaymentInstruments",
            "bedrock-agentcore:DeletePaymentInstrument",
            "bedrock-agentcore:GetPaymentInstrumentBalance",
            "bedrock-agentcore:CreatePaymentSession",
            "bedrock-agentcore:GetPaymentSession",
            "bedrock-agentcore:ListPaymentSessions",
            "bedrock-agentcore:UpdatePaymentSession",
        ],
        "deny": ["bedrock-agentcore:ProcessPayment"],
    },
    PROCESS_PAYMENT_ROLE: {
        "description": "AgentCore payments: agent runtime (ProcessPayment + read queries)",
        "trust": "account",
        "allow": [
            "bedrock-agentcore:ProcessPayment",
            "bedrock-agentcore:GetPaymentInstrument",
            "bedrock-agentcore:GetPaymentInstrumentBalance",
            "bedrock-agentcore:GetPaymentSession",
        ],
    },
    RESOURCE_RETRIEVAL_ROLE: {
        "description": "AgentCore payments: service role for credential retrieval",
        "trust": "service",
        "allow": [
            "bedrock-agentcore:GetWorkloadAccessToken",
            "bedrock-agentcore:CreateWorkloadIdentity",
            "bedrock-agentcore:GetResourcePaymentToken",
        ],
        "secrets_manager": True,
    },
}


def setup_payment_roles(region=None):
    """AgentCore payments 튜토리얼에 필요한 IAM role 4개를 생성합니다.

    각 role의 존재 여부를 먼저 확인하고 누락된 항목만 생성합니다.
    Idempotent하므로 여러 번 안전하게 실행할 수 있습니다.

    참고: 명시적으로 삭제할 때까지 유지되는 IAM role을 생성합니다. 더 이상
    필요하지 않으면 Tutorial 00의 cleanup 셀을 실행하여 제거하세요.

    인수:
        region: AWS region. 기본값은 AWS_REGION env var 또는 us-west-2입니다.

    반환:
        Short name을 role ARN에 매핑한 dict
        {
            "control_plane": "arn:aws:iam::...:role/AgentCorePaymentsControlPlaneRole",
            "management": "arn:aws:iam::...:role/AgentCorePaymentsManagementRole",
            "process_payment": "arn:aws:iam::...:role/AgentCorePaymentsProcessPaymentRole",
            "resource_retrieval": "arn:aws:iam::...:role/AgentCorePaymentsResourceRetrievalRole",
        }
    """
    region = region or os.environ.get("AWS_REGION", "us-west-2")
    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    iam = session.client("iam")

    identity = sts.get_caller_identity()
    account_id = identity["Account"]
    caller_arn = identity["Arn"]

    # Caller를 base role ARN으로 resolve(assumed-role 형식 처리)
    caller_role_arn = None
    if ":assumed-role/" in caller_arn:
        role_name = caller_arn.split(":")[-1].split("/")[1]
        try:
            caller_role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        except Exception:
            caller_role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    # Trust policy 구성
    account_principal = f"arn:aws:iam::{account_id}:root"
    principals = [account_principal]
    if caller_role_arn:
        principals.append(caller_role_arn)

    account_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": principals},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    service_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"aws:SourceAccount": account_id}},
            },
        ],
    }

    created_count = 0
    role_arns = {}
    short_names = {
        CONTROL_PLANE_ROLE: "control_plane",
        MANAGEMENT_ROLE: "management",
        PROCESS_PAYMENT_ROLE: "process_payment",
        RESOURCE_RETRIEVAL_ROLE: "resource_retrieval",
    }

    for role_name, config in PAYMENT_ROLE_DEFINITIONS.items():
        short = short_names[role_name]
        trust = service_trust if config["trust"] == "service" else account_trust

        # Role 존재 여부 확인
        try:
            existing = iam.get_role(RoleName=role_name)
            role_arn = existing["Role"]["Arn"]
            role_arns[short] = role_arn
            # Trust policy와 권한 업데이트(idempotent)
            iam.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust),
            )
        except iam.exceptions.NoSuchEntityException:
            # Role 생성
            resp = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust),
                Description=config["description"],
            )
            role_arn = resp["Role"]["Arn"]
            role_arns[short] = role_arn
            created_count += 1

        # Allow policy 연결
        allow_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Allow",
                    "Effect": "Allow",
                    "Action": config["allow"],
                    "Resource": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*",
                }
            ],
        }

        # ControlPlaneRole에 SecretsManager write access 추가
        # CreateSecret은 아직 존재하지 않는 secret을 대상으로 하므로 Resource는 "*"여야 함
        if config.get("secrets_manager_write"):
            allow_policy["Statement"].append(
                {
                    "Sid": "SecretsManagerWrite",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:CreateSecret",
                        "secretsmanager:PutSecretValue",
                        "secretsmanager:UpdateSecret",
                        "secretsmanager:DeleteSecret",
                        "secretsmanager:TagResource",
                    ],
                    "Resource": "*",
                }
            )

        # ResourceRetrievalRole에 SecretsManager access 추가
        if config.get("secrets_manager"):
            allow_policy["Statement"].append(
                {
                    "Sid": "SecretsManagerAccess",
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": f"arn:aws:secretsmanager:*:{account_id}:secret:*",
                }
            )
            allow_policy["Statement"].append(
                {
                    "Sid": "StsSetContext",
                    "Effect": "Allow",
                    "Action": "sts:SetContext",
                    "Resource": f"arn:aws:sts::{account_id}:self",
                }
            )

        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="AllowPolicy",
            PolicyDocument=json.dumps(allow_policy),
        )

        # 지정된 경우 deny policy 연결
        if config.get("deny"):
            deny_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "Deny",
                        "Effect": "Deny",
                        "Action": config["deny"],
                        "Resource": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*",
                    }
                ],
            }
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName="DenyPolicy",
                PolicyDocument=json.dumps(deny_policy),
            )

        # ControlPlaneRole에 PassRole 연결
        # 문서의 best practice에 따라 ResourceRetrievalRole + condition으로 scope 제한
        if config.get("pass_role"):
            rr_arn = f"arn:aws:iam::{account_id}:role/{RESOURCE_RETRIEVAL_ROLE}"
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName="PassRolePolicy",
                PolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "iam:PassRole",
                                "Resource": rr_arn,
                                "Condition": {
                                    "StringEquals": {"iam:PassedToService": "bedrock-agentcore.amazonaws.com"}
                                },
                            }
                        ],
                    }
                ),
            )

    # 새 role이 생성된 경우 IAM propagation 대기
    if created_count > 0:
        print(f"  Created {created_count} new role(s). Waiting for IAM propagation...")
        time.sleep(10)

    print(f"  ✅ IAM roles ready ({len(role_arns)} roles)")
    for short, arn in role_arns.items():
        print(f"     {short}: {arn}")

    return role_arns


# ═════════════════════════════════════════════════════════════════
# 비동기 resource polling
# ═════════════════════════════════════════════════════════════════


def wait_for_status(client_fn, expected_status, poll_interval=5, timeout=120, **kwargs):
    """Resource가 expected_status에 도달할 때까지 Get* API를 polling합니다.

    Top-level ``status`` 또는 nested ``paymentInstrument.status``에서 status를
    resolve합니다. Timeout 내에 도달하지 못하면 TimeoutError를 발생시키고,
    terminal failure state(*_FAILED)에서는 즉시 RuntimeError를 발생시킵니다.
    """
    deadline = time.time() + timeout
    while True:
        resp = client_fn(**kwargs)
        status = resp.get("status") or resp.get("paymentInstrument", {}).get("status")
        print(f"   Status: {status}")
        if isinstance(status, str) and status.endswith("_FAILED"):
            raise RuntimeError(f"Resource reached failure state: '{status}'")
        if status == expected_status:
            return resp
        if time.time() >= deadline:
            raise TimeoutError(f"Resource still in '{status}' after {timeout}s")
        time.sleep(poll_interval)


# ═════════════════════════════════════════════════════════════════
# Idempotent Resource 생성
# ═════════════════════════════════════════════════════════════════


def idempotent_create(create_fn, conflict_msg="Resource already exists", **kwargs):
    """create_fn을 호출하고 ConflictException을 문제없이 처리합니다.

    성공하면 API response를 반환하고 resource가 이미 있으면 None을 반환합니다.
    """
    try:
        return create_fn(**kwargs)
    except botocore.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "ConflictException":
            print(f"  ⚠️  {conflict_msg} — skipping create")
            return None
        raise


# ═════════════════════════════════════════════════════════════════
# Cognito(Gateway 통합 전용)
# ═════════════════════════════════════════════════════════════════


def setup_cognito_user_pool(pool_name="AgentCorePaymentsPool"):
    """Gateway 통합을 위한 M2M client가 있는 Cognito user pool을 생성합니다.

    pool_id, client_id, client_secret, token_url이 있는 dict를 반환합니다.
    """
    session = boto3.Session()
    region = session.region_name
    cognito = boto3.client("cognito-idp", region_name=region)

    pool_resp = cognito.create_user_pool(
        PoolName=pool_name,
        Policies={"PasswordPolicy": {"MinimumLength": 8}},
    )
    pool_id = pool_resp["UserPool"]["Id"]

    domain = pool_id.replace("_", "").lower()
    cognito.create_user_pool_domain(Domain=domain, UserPoolId=pool_id)

    resource_server_id = "agentcore-payments"
    cognito.create_resource_server(
        UserPoolId=pool_id,
        Identifier=resource_server_id,
        Name="AgentCore payments",
        Scopes=[{"ScopeName": "payments", "ScopeDescription": "Payment operations"}],
    )

    client_resp = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName="PaymentsTutorialClient",
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[f"{resource_server_id}/payments"],
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
    )

    token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
    print(f"Cognito pool created: {pool_id}")

    return {
        "pool_id": pool_id,
        "client_id": client_resp["UserPoolClient"]["ClientId"],
        "client_secret": client_resp["UserPoolClient"]["ClientSecret"],
        "token_url": token_url,
    }


def get_oauth_token(token_url, client_id, client_secret):
    """Client credentials를 OAuth2 access token으로 교환합니다."""
    import requests

    resp = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ═════════════════════════════════════════════════════════════════
# Config 유지(.env 사용 — payment_config.json 대체)
# ═════════════════════════════════════════════════════════════════

# Tutorial 00은 resource ID를 .env에 기록함. 이후 모든 튜토리얼은
# load_dotenv() + os.environ으로 이를 읽으며 JSON이나 custom loader는 사용하지 않음

TUTORIAL_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def save_tutorial_config(config_dict, env_path=None):
    """이후 튜토리얼을 위해 Tutorial 00의 resource ID를 .env에 기록합니다.

    Provider credentials와 AWS config가 이미 있는 기존 .env에 추가합니다.
    Idempotent upsert를 위해 update_env_file()을 사용합니다.

    인수:
        config_dict: 기록할 {ENV_VAR: value} pair의 dict
            예상 key: PAYMENT_MANAGER_ARN, PAYMENT_MANAGER_ID,
            PAYMENT_CONNECTOR_ID, CREDENTIAL_PROVIDER_ARN, USER_ID,
            INSTRUMENT_ID, WALLET_ADDRESS, SESSION_ID, CREDENTIAL_PROVIDER_TYPE, etc.
        env_path: .env 파일 path. 기본값은 00-getting-started/.env입니다.

    예:
        save_tutorial_config({
            "PAYMENT_MANAGER_ARN": manager_arn,
            "PAYMENT_CONNECTOR_ID": connector_id,
            "USER_ID": "test-user-001",
            "INSTRUMENT_ID": instrument_id,
            "SESSION_ID": session_id,
        })
    """
    path = env_path or TUTORIAL_ENV_FILE
    update_env_file(path, config_dict)
    print(f"  ✅ Tutorial config saved to {os.path.basename(path)}")


def load_tutorial_env(env_path=None):
    """.env를 load하고 plugin config용 표준 field가 있는 dict를 반환합니다.

    이후 튜토리얼(01~07) 상단에서 호출하여 AgentCorePaymentsPluginConfig에
    필요한 값을 가져옵니다.

    인수:
        env_path: .env 파일 path. 기본값은 00-getting-started/.env입니다.

    반환:
        다음 항목이 있는 dict: payment_manager_arn, user_id, instrument_id, session_id,
        connector_id, region, provider_type, wallet_address.
        Multi-provider 설정(Tutorial 07)에서는 multi_provider=True와
        instruments/connectors dict도 포함합니다. 누락된 key는 예외를
        발생시키지 않고 None이 됩니다.

    예:
        cfg = load_tutorial_env()
        plugin = AgentCorePaymentsPlugin(config=AgentCorePaymentsPluginConfig(
            payment_manager_arn=cfg["payment_manager_arn"],
            user_id=cfg["user_id"],
            payment_instrument_id=cfg["instrument_id"],
            payment_session_id=cfg["session_id"],
            region=cfg["region"],
        ))
    """
    path = env_path or TUTORIAL_ENV_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"{os.path.basename(path)} not found. Run Tutorial 00 first.\n  Expected at: {path}")
    load_dotenv(path, override=True)

    result = {
        "payment_manager_arn": os.environ.get("PAYMENT_MANAGER_ARN"),
        "payment_manager_id": os.environ.get("PAYMENT_MANAGER_ID"),
        "connector_id": os.environ.get("PAYMENT_CONNECTOR_ID"),
        "credential_provider_arn": os.environ.get("CREDENTIAL_PROVIDER_ARN"),
        "user_id": os.environ.get("USER_ID"),
        "instrument_id": os.environ.get("INSTRUMENT_ID"),
        "wallet_address": os.environ.get("WALLET_ADDRESS"),
        "session_id": os.environ.get("SESSION_ID"),
        "region": os.environ.get("AWS_REGION", "us-west-2"),
        "provider_type": os.environ.get("CREDENTIAL_PROVIDER_TYPE"),
    }

    # Multi-provider 지원(Tutorial 07)
    coinbase_instr = os.environ.get("COINBASE_INSTRUMENT_ID")
    privy_instr = os.environ.get("PRIVY_INSTRUMENT_ID")

    if coinbase_instr and privy_instr:
        result["multi_provider"] = True
        result["instruments"] = {
            "coinbase": {
                "instrument_id": coinbase_instr,
                "connector_id": os.environ.get("COINBASE_CONNECTOR_ID"),
                "wallet_address": os.environ.get("COINBASE_WALLET_ADDRESS"),
            },
            "stripe_privy": {
                "instrument_id": privy_instr,
                "connector_id": os.environ.get("PRIVY_CONNECTOR_ID"),
                "wallet_address": os.environ.get("PRIVY_WALLET_ADDRESS"),
            },
        }
    else:
        result["multi_provider"] = False

    return result


# ═════════════════════════════════════════════════════════════════
# 출력 helper
# ═════════════════════════════════════════════════════════════════


def pp(label, response):
    """ResponseMetadata를 제거하고 API response를 보기 좋게 출력합니다."""
    data = {k: v for k, v in response.items() if k != "ResponseMetadata"}
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(json.dumps(data, indent=2, default=str))


def print_summary(title, **kwargs):
    """Notebook output용 summary block을 보기 좋게 출력합니다."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    for key, value in kwargs.items():
        label = key.replace("_", " ").title()
        print(f"  {label:30s}: {value}")
    print(f"{'=' * 60}\n")


def client_token():
    """Idempotency token을 생성합니다(33자 이상)."""
    return f"{uuid.uuid4()}-{uuid.uuid4().hex[:8]}"


# ═════════════════════════════════════════════════════════════════
# Observability(vended log + trace)
# ═════════════════════════════════════════════════════════════════


def enable_observability(resource_arn, resource_id, account_id, region="us-west-2", enable_xray_spans=False):
    """AgentCore payments resource의 CloudWatch vended log와 X-Ray trace를 활성화합니다.

    APPLICATION_LOGS와 TRACES의 delivery source, destination, delivery를
    생성합니다. 선택적으로 CloudWatch Logs로의 X-Ray span delivery를 구성합니다.

    **비용 안내:** 이 함수는 AWS 요금이 발생할 수 있는 CloudWatch log group,
    delivery source, delivery destination, X-Ray resource를 생성합니다. 작업을
    마치면 ``/aws/vendedlogs/bedrock-agentcore/<manager-id>`` log group을 삭제하세요.

    활성화 후 모든 data plane API 호출(CreateInstrument, ProcessPayment 등)이
    구성된 CloudWatch Log Group에 log와 trace data를 생성합니다.

    인수:
        resource_arn: Payment Manager의 ARN
        resource_id: Payment Manager ID(short ID)
        account_id: AWS account ID
        region: AWS region
        enable_xray_spans: True이면 X-Ray가 CloudWatch Logs로 span을 전달하도록 구성

    반환:
        logs_delivery_id와 traces_delivery_id가 있는 dict

    사전 요구 사항:
        호출 role에 다음 권한이 필요합니다.
        - logs:CreateDelivery, logs:CreateLogGroup, logs:CreateLogStream,
          logs:DeleteDelivery, logs:DeleteDeliveryDestination, logs:DeleteDeliverySource,
          logs:DescribeLogGroups, logs:DescribeResourcePolicies,
          logs:GetDelivery, logs:GetDeliveryDestination, logs:GetDeliverySource,
          logs:PutDeliveryDestination, logs:PutDeliverySource,
          logs:PutLogEvents, logs:PutResourcePolicy, logs:PutRetentionPolicy
        - xray:GetTraceSegmentDestination, xray:ListResourcePolicies,
          xray:PutResourcePolicy, xray:PutTelemetryRecords, xray:PutTraceSegments,
          xray:UpdateTraceSegmentDestination (if enable_xray_spans=True)
        - application-signals:StartDiscovery, cloudtrail:CreateServiceLinkedChannel
        - iam:CreateServiceLinkedRole (for AWSServiceRoleForCloudWatchApplicationSignals)
        - bedrock-agentcore:AllowVendedLogDeliveryForResource
    """
    # 1단계: Resource의 vended log delivery 허용
    # Bedrock AgentCore service가 account에 vended log를 게시하도록 authorize함
    # Delivery source/destination을 생성하기 전에 호출해야 함
    agentcore_client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        agentcore_client.allow_vended_log_delivery_for_resource(resourceArn=resource_arn)
        print(f"  Allowed vended log delivery for {resource_arn}")
    except agentcore_client.exceptions.ConflictException:
        print(f"  Vended log delivery already allowed for {resource_arn}")
    except Exception as e:
        # 치명적이지 않음 — 일부 account에서는 이미 활성화되었거나 아직 모든 region에서
        # API를 사용할 수 없을 수 있음
        print(f"  Note: AllowVendedLogDeliveryForResource returned: {e}")

    logs_client = boto3.client("logs", region_name=region)

    # 2단계: Log group 생성
    log_group_name = f"/aws/vendedlogs/bedrock-agentcore/{resource_id}"
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
        print(f"  Created log group: {log_group_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  Log group already exists: {log_group_name}")

    log_group_arn = f"arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}"

    # X-Ray span 설정
    if enable_xray_spans:
        _setup_xray_spans(logs_client, region)

    # 3단계: Delivery source 생성
    print("  Creating delivery sources (APPLICATION_LOGS + TRACES)...")
    logs_src = logs_client.put_delivery_source(
        name=f"{resource_id}-logs-source",
        logType="APPLICATION_LOGS",
        resourceArn=resource_arn,
    )
    traces_src = logs_client.put_delivery_source(
        name=f"{resource_id}-traces-source", logType="TRACES", resourceArn=resource_arn
    )

    # 4단계: Delivery destination 생성
    print("  Creating delivery destinations (CWL + XRAY)...")
    logs_dst = logs_client.put_delivery_destination(
        name=f"{resource_id}-logs-destination",
        deliveryDestinationType="CWL",
        deliveryDestinationConfiguration={"destinationResourceArn": log_group_arn},
    )
    traces_dst = logs_client.put_delivery_destination(
        name=f"{resource_id}-traces-destination",
        deliveryDestinationType="XRAY",
    )

    # 5단계: Source를 destination에 연결
    print("  Creating deliveries...")
    logs_delivery = logs_client.create_delivery(
        deliverySourceName=logs_src["deliverySource"]["name"],
        deliveryDestinationArn=logs_dst["deliveryDestination"]["arn"],
    )
    traces_delivery = logs_client.create_delivery(
        deliverySourceName=traces_src["deliverySource"]["name"],
        deliveryDestinationArn=traces_dst["deliveryDestination"]["arn"],
    )

    print(f"  ✅ Observability enabled for {resource_id}")
    return {
        "logs_delivery_id": logs_delivery["delivery"]["id"],
        "traces_delivery_id": traces_delivery["delivery"]["id"],
        "log_group_name": log_group_name,
    }


def _setup_xray_spans(logs_client, region):
    """X-Ray가 CloudWatch Logs로 span을 전달하도록 구성합니다."""
    import json as _json

    logs_client.put_resource_policy(
        policyName="XRaySpansPolicy",
        policyDocument=_json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "XRayAccess",
                        "Effect": "Allow",
                        "Principal": {"Service": "xray.amazonaws.com"},
                        "Action": [
                            "logs:PutLogEvents",
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                        ],
                        "Resource": "arn:aws:logs:*:*:log-group:/aws/vendedlogs/bedrock-agentcore/*",
                    }
                ],
            }
        ),
    )

    xray_client = boto3.client("xray", region_name=region)
    try:
        xray_client.update_trace_segment_destination(Destination="CloudWatchLogs")
    except xray_client.exceptions.InvalidRequestException as e:
        if "already set to CloudWatchLogs" not in str(e):
            raise
        print("  X-Ray already set to CloudWatchLogs")

    # ACTIVE가 될 때까지 대기
    for attempt in range(1, 25):
        resp = xray_client.get_trace_segment_destination()
        destination = resp.get("Destination", {})
        status = (
            destination.get("Status", resp.get("Status", "UNKNOWN"))
            if isinstance(destination, dict)
            else str(destination)
        )
        if status == "ACTIVE":
            print("  ✅ X-Ray trace segment destination ACTIVE")
            return
        time.sleep(5)
    raise RuntimeError("X-Ray trace segment destination did not become ACTIVE")


# ═════════════════════════════════════════════════════════════════
# Privy Helper(StripePrivy provider 전용)
# ═════════════════════════════════════════════════════════════════
#
# 이 helper는 public API가 있는 Privy 설정 부분을 자동화하여 개발자가 Privy dashboard에서
# 수행해야 하는 작업을 최소화함. 다음 항목은 수동으로 수행해야 함
#   1. Privy app 자체 생성(public API 없음)
#   2. 허용된 origin 추가(dashboard 전용)
#   3. 로컬 Privy reference frontend 실행(browser + localhost)
#
# P-256 keypair 생성, key quorum 등록, .env 업데이트, consent 적용 검증 등
# 나머지 모든 작업은 여기서 실행됨

PRIVY_API_BASE = "https://api.privy.io/v1"


def update_env_file(env_path_or_updates, updates=None):
    """key=value pair를 .env 파일에 idempotent하게 upsert합니다.

    파일이 없으면 생성합니다. 기존 line, comment, blank line을 보존합니다.
    ``updates``의 각 key는 이미 있으면 제자리에서 교체하고, 없으면 마지막
    block에 추가합니다.

    두 가지 호출 signature를 지원합니다.
        update_env_file('.env', {'KEY': 'val'})
        update_env_file({'KEY': 'val'})  # 기본값은 '.env'

    반환:
        보고용 ``added`` 및 ``updated`` key 목록이 있는 dict
    """
    if updates is None:
        updates = env_path_or_updates
        env_path = os.path.join(os.path.dirname(__file__), ".env")
    else:
        env_path = env_path_or_updates
    env_path = os.path.abspath(env_path)
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            existing_lines = f.readlines()

    remaining = dict(updates)
    updated_keys = []
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining.pop(key)}\n")
            updated_keys.append(key)
        else:
            new_lines.append(line)

    added_keys = list(remaining.keys())
    if added_keys:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        if new_lines:
            new_lines.append("\n")
        new_lines.append("# --- Generated by tutorial setup ---\n")
        for key, value in remaining.items():
            new_lines.append(f"{key}={value}\n")

    os.makedirs(os.path.dirname(env_path) or ".", exist_ok=True)
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    try:
        os.chmod(env_path, 0o600)
    except (OSError, NotImplementedError):
        pass

    print(f"  ✅ Updated {env_path}")
    if updated_keys:
        print(f"     replaced: {', '.join(updated_keys)}")
    if added_keys:
        print(f"     added:    {', '.join(added_keys)}")
    return {"updated": updated_keys, "added": added_keys}


def render_frontend_env_local(app_id, app_secret, signer_id, network_mode="testnet"):
    """Privy reference frontend의 ``.env.local`` 파일 내용을 구성합니다.

    Filesystem access나 shell instruction이 없는 순수 string builder입니다.
    Notebook은 반환된 string을 출력하며 개발자는 이를 로컬 machine의 Privy
    reference frontend ``.env.local``에 붙여 넣습니다.

    인수:
        app_id: Privy app ID(``NEXT_PUBLIC_PRIVY_APP_ID``)
        app_secret: Privy app secret(``PRIVY_APP_SECRET`` — server 전용)
        signer_id: Privy key quorum ID(``NEXT_PUBLIC_PRIVY_SIGNER_ID``)
        network_mode: ``testnet`` 또는 ``mainnet``

    반환:
        String 형태의 ``.env.local`` body
    """
    return (
        f"NEXT_PUBLIC_PRIVY_APP_ID={app_id}\n"
        f"PRIVY_APP_SECRET={app_secret}\n"
        f"NEXT_PUBLIC_PRIVY_SIGNER_ID={signer_id}\n"
        f"NEXT_PUBLIC_NETWORK_MODE={network_mode}\n"
    )


def save_privy_authorization_key(env_path, authorization_id, authorization_private_key):
    """wallet-auth: prefix를 제거하고 Privy authorization key credentials를 .env에 저장합니다.

    Privy dashboard는 authorization private key에 ``wallet-auth:`` prefix를
    붙여 표시합니다. 이 prefix는 key 자체의 일부가 아니므로 key를 Bedrock AgentCore
    ``authorizationPrivateKey`` field에 전달하기 전에 제거해야 합니다.
    Bedrock AgentCore validation은 prefix가 있는 형식을 거부합니다.

    인수:
        env_path: .env 파일 path
        authorization_id: Privy dashboard의 authorization ID(public identifier로 log에 안전)
        authorization_private_key: Privy dashboard에서 복사한 private key.
            ``wallet-auth:`` prefix는 있을 수도 있고 없을 수도 있으며 있으면 제거합니다.

    반환:
        :func:`update_env_file`의 결과
    """
    prefix = "wallet-auth:"
    key = authorization_private_key.strip()
    if key.startswith(prefix):
        key = key[len(prefix) :].strip()
        print("  ℹ️  Stripped 'wallet-auth:' prefix from the private key.")

    return update_env_file(
        env_path,
        {
            "PRIVY_AUTHORIZATION_ID": authorization_id,
            "PRIVY_AUTHORIZATION_PRIVATE_KEY": key,
        },
    )


def verify_privy_signer_on_wallet(app_id, app_secret, wallet_address_or_id, quorum_id):
    """Key quorum이 Privy wallet의 signer로 등록되었는지 확인합니다.

    최종 사용자가 Privy reference frontend(main setup Notebook의 7b단계)에서
    signer access를 부여하면 Privy가 key quorum을 wallet의 ``additional_signers``에
    추가합니다. ``ProcessPayment``를 시도하기 전에 이를 호출하여 consent가
    적용되었는지 확인하세요. Delegation 누락은 StripePrivy provider에서
    ProcessPayment가 실패하는 가장 일반적인 원인입니다.

    Privy wallet ID(``trv721k23pqzjd3pdqmh54o7`` 같은 CUID2) 또는 on-chain
    wallet address(EVM은 ``0x…``, Solana는 base58)를 받습니다. 각 형식에
    적합한 Privy endpoint를 사용합니다.

    - Wallet ID:  ``GET  /v1/wallets/{wallet_id}``
    - Address:    ``POST /v1/wallets/address``  (body: ``{"address": "…"}``)

    인수:
        app_id: Privy app ID(``PRIVY_APP_ID``)
        app_secret: Privy app secret(``PRIVY_APP_SECRET``)
        wallet_address_or_id: Privy wallet ID 또는 on-chain address
        quorum_id: 검색할 key quorum ID. Bedrock AgentCore
            ``PRIVY_AUTHORIZATION_ID`` field

    반환:
        ``additional_signers``에 quorum이 있으면 True, 없으면 False

    예외:
        RuntimeError: Privy가 예상하지 못한 error를 반환한 경우
    """
    import re
    import requests

    auth = (app_id, app_secret)
    headers = {"privy-app-id": app_id, "Content-Type": "application/json"}

    # Input 형식에 맞는 endpoint를 사용하여 wallet object 가져오기
    # Wallet ID는 영문자로 시작하는 24자의 소문자 alphanumeric CUID2
    # 그 외의 값은 on-chain address로 처리
    is_wallet_id = bool(re.fullmatch(r"[a-z][a-z0-9]{23}", wallet_address_or_id))

    if is_wallet_id:
        resp = requests.get(
            f"{PRIVY_API_BASE}/wallets/{wallet_address_or_id}",
            auth=auth,
            headers=headers,
            timeout=30,
        )
    else:
        resp = requests.post(
            f"{PRIVY_API_BASE}/wallets/address",
            auth=auth,
            headers=headers,
            timeout=30,
            json={"address": wallet_address_or_id},
        )

    if resp.status_code == 404:
        raise RuntimeError(
            f"Privy wallet not found for {wallet_address_or_id!r}. "
            "Check that PRIVY_APP_ID matches the app the wallet was created in, "
            "and that the wallet has been provisioned (Step 7 in the main notebook)."
        )
    if not resp.ok:
        raise RuntimeError(f"Privy wallet fetch failed ({resp.status_code}): {resp.text}")

    wallet = resp.json()
    signers = wallet.get("additional_signers") or wallet.get("additionalSigners") or []
    # Entry는 dict({"signer_id": "..."}) 또는 bare string일 수 있으므로 모두 처리
    signer_ids = {
        (s.get("signer_id") or s.get("id") or s.get("key_quorum_id")) if isinstance(s, dict) else s for s in signers
    }
    return quorum_id in signer_ids
