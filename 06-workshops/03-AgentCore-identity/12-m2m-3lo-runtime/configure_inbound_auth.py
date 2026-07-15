"""
배포 후 스크립트: 아웃바운드 자격 증명 조회용 IAM 권한과 토큰 볼트용 KMS 액세스를
연결하고, 3LO 흐름의 OAuth2 콜백 URL을 등록합니다.

이제 CLI가 agentcore.json을 통해 JWT 인바운드 인증을 기본으로 처리합니다.

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


def main():
    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    runtime_id = get_runtime_id()
    print(f"Configuring post-deploy permissions on runtime: {runtime_id}")

    ctrl = boto3.client("bedrock-agentcore-control", region_name=config["region"])

    # 역할 ARN을 추출하기 위해 현재 런타임 구성 가져오기
    current = ctrl.get_agent_runtime(agentRuntimeId=runtime_id)

    # AgentCore Identity 아웃바운드 자격 증명 조회용 IAM 정책 연결
    region = config["region"]
    account = boto3.client("sts").get_caller_identity()["Account"]
    role_name = current["roleArn"].split("/")[-1]
    iam = boto3.client("iam")
    print(f"\nAttaching IAM policy to role: {role_name}")
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

    # 런타임이 USER_FEDERATION 흐름의 토큰 볼트 CMK를 사용하도록 KMS 정책 연결
    tv = boto3.client("bedrock-agentcore-control", region_name=region).get_token_vault(tokenVaultId="default")
    kms_key_arn = tv.get("kmsConfiguration", {}).get("kmsKeyArn", "")
    if kms_key_arn:
        print(f"Attaching KMS policy for token vault key: {kms_key_arn}")
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="AgentCoreKMSAccess",
            PolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "kms:Decrypt",
                                "kms:GenerateDataKey",
                                "kms:DescribeKey",
                            ],
                            "Resource": kms_key_arn,
                        }
                    ],
                }
            ),
        )
        print("KMS policy attached.")

    # 워크로드 자격 증명에 허용된 콜백 URL 등록
    # USER_FEDERATION(3LO) 흐름에 필요
    callback_url = os.environ.get("CALLBACK_URL", "http://localhost:9090/oauth2/callback")
    print(f"\nRegistering callback URL in workload identity: {callback_url}")
    ctrl.update_workload_identity(
        name=runtime_id,
        allowedResourceOauth2ReturnUrls=[callback_url],
    )
    print("Callback URL registered.")
    print("\nWait ~30s for changes to propagate, then run: python invoke.py")


if __name__ == "__main__":
    main()
