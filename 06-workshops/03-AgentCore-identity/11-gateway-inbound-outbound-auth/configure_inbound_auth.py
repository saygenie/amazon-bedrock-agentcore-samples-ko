"""
배포 후 스크립트: 런타임에 JWT 인바운드 인증을 적용하고, Gateway URL 환경 변수를
설정하고, 아웃바운드 자격 증명 조회용 IAM 권한을 연결하고, 관리형 Gateway 자격 증명이
있는지 확인합니다.

참고: CLI는 독립 실행형 런타임(samples 09, 11)에 authorizerConfiguration을 올바르게
적용하지만, 프로젝트에 에이전트와 Gateway가 모두 있으면 배포 중 에이전트의 인증 구성이
적용되지 않습니다. 이 스크립트는 해당 문제를 우회합니다.

'agentcore deploy -y' 실행 후 이 스크립트를 한 번 실행합니다.

사용법:
    python configure_inbound_auth.py
"""

import boto3
import json
import os
import sys


def find_project_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    for entry in os.listdir(base):
        candidate = os.path.join(base, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "agentcore")):
            return candidate
    raise FileNotFoundError("No agentcore project directory found. Run 'agentcore create' first.")


def _find_in_json(obj, key):
    """중첩된 JSON에서 키를 재귀적으로 검색합니다."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _find_in_json(v, key)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_in_json(item, key)
            if result:
                return result
    return None


def get_runtime_id() -> str:
    """deployed-state.json에서 배포된 런타임 ID를 읽습니다.

    CLI 버전에 관계없이 동작하도록 runtimeId를 재귀적으로 검색합니다.
    """
    project_dir = find_project_dir()
    state_file = os.path.join(project_dir, "agentcore", ".cli", "deployed-state.json")
    if not os.path.exists(state_file):
        raise FileNotFoundError("No deployed-state.json found. Run 'agentcore deploy -y' first.")
    with open(state_file) as f:
        state = json.load(f)
    rid = _find_in_json(state, "runtimeId")
    if rid:
        return rid
    raise ValueError("No deployed agent found. Run 'agentcore deploy -y' first.")


def get_gateway_url(region: str) -> str:
    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    gateways = ctrl.list_gateways()
    for gw in gateways.get("items", []):
        if "GatewayAuthDemo" in gw.get("name", ""):
            detail = ctrl.get_gateway(gatewayIdentifier=gw["gatewayId"])
            return detail.get("gatewayUrl", "")
    raise ValueError("GatewayAuthDemo gateway not found. Run 'agentcore deploy -y' first.")


def main():
    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    region = config["region"]
    runtime_id = get_runtime_id()
    print(f"Configuring runtime: {runtime_id}")

    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    iam = boto3.client("iam")
    sts = boto3.client("sts")
    account = sts.get_caller_identity()["Account"]

    current = ctrl.get_agent_runtime(agentRuntimeId=runtime_id)
    role_name = current["roleArn"].split("/")[-1]

    # 환경 변수로 설정할 Gateway URL 가져오기
    gateway_url = get_gateway_url(region)
    print(f"Gateway URL: {gateway_url}")

    # JWT 인바운드 인증 및 Gateway URL 환경 변수 구성
    # 참고: CLI가 agentcore.json의 authorizerConfiguration을 적용해야 하지만
    # 현재는 프로젝트에 Gateway도 포함된 경우 적용하지 않음
    ctrl.update_agent_runtime(
        agentRuntimeId=runtime_id,
        agentRuntimeArtifact=current["agentRuntimeArtifact"],
        roleArn=current["roleArn"],
        networkConfiguration=current["networkConfiguration"],
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": config["discovery_url"],
                "allowedClients": [config["user_client_id"]],
            }
        },
        environmentVariables={"AGENTCORE_GATEWAY_URL": gateway_url},
    )
    print("JWT inbound auth and gateway URL configured.")

    # Cognito 에이전트 클라이언트 OAuth 설정 수정(CDK 배포 시 재설정됨)
    cognito = boto3.client("cognito-idp", region_name=region)
    print("Fixing Cognito agent client OAuth config...")
    cognito.update_user_pool_client(
        UserPoolId=config["pool_id"],
        ClientId=config["agent_client_id"],
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=["https://gateway.demo.internal/access"],
        AllowedOAuthFlowsUserPoolClient=True,
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )
    print("Cognito agent client OAuth config fixed.")

    # AgentCore Identity 아웃바운드 자격 증명 조회용 IAM 정책 연결
    print(f"Attaching IAM policy to role: {role_name}")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="AgentCoreIdentityOutbound",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock-agentcore:GetResourceApiKey",
                            "bedrock-agentcore:GetResourceOauth2Token",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["secretsmanager:GetSecretValue"],
                        "Resource": f"arn:aws:secretsmanager:{region}:{account}:secret:bedrock-agentcore*",
                    },
                ],
            }
        ),
    )
    print("IAM policy attached.")

    # 관리형 Gateway 자격 증명 확인(없으면 다시 생성)
    providers = ctrl.list_oauth2_credential_providers()
    existing = {p["name"] for p in providers.get("credentialProviders", [])}
    if "MyGateway-oauth" not in existing:
        print("Recreating managed gateway credential 'MyGateway-oauth'...")
        ctrl.create_oauth2_credential_provider(
            name="MyGateway-oauth",
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": {
                    "clientId": config["agent_client_id"],
                    "clientSecret": config["agent_client_secret"],
                    "oauthDiscovery": {
                        "discoveryUrl": config["discovery_url"],
                    },
                }
            },
        )
        print("  MyGateway-oauth created.")
    else:
        print("  MyGateway-oauth credential exists.")

    print("\nWait ~30s for changes to propagate, then run: python invoke.py")


if __name__ == "__main__":
    main()
