"""
IAM 인증을 사용하는 A2A Agent를 AgentCore Runtime에 배포

이 스크립트는 Agent를 Amazon Bedrock AgentCore Runtime에 배포합니다.
다음 작업을 수행합니다.
1. Docker 이미지를 빌드하여 ECR에 푸시
2. 필요한 권한이 있는 실행 역할 생성
3. Agent를 AgentCore Runtime에 배포

참고: 자동 생성된 실행 역할에 권한이 없으면 첫 배포가 실패할 수 있습니다.
이 경우 execution-role-policy.json의 권한을 역할에 직접 추가하고
다시 실행합니다.
"""

from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session

# 설정
boto_session = Session()
region = boto_session.region_name
account_id = boto_session.client("sts").get_caller_identity()["Account"]

print(f"Deploying to region: {region}")
print(f"Account ID: {account_id}")

agentcore_runtime = Runtime()

# 구성
agentcore_runtime.configure(
    entrypoint="agent.py",
    auto_create_execution_role=True,
    auto_create_ecr=True,
    requirements_file="requirements.txt",
    region=region,
    protocol="A2A",
    agent_name="a2a_agent_iam",
)

# 시작(몇 분 정도 소요)
print("\nStarting deployment (this may take several minutes)...")
launch_result = agentcore_runtime.launch()

print("\n" + "=" * 60)
print("Deployment successful!")
print(f"Agent ARN: {launch_result.agent_arn}")
print("\nTo test the agent, run:")
print(f"  export AGENT_ARN='{launch_result.agent_arn}'")
print("  python client.py")
print("=" * 60)
