"""
멀티 에이전트 튜토리얼용 유틸리티 함수입니다.
bedrock-agentcore-starter-toolkit에서 제공하지 않는 기능만 포함합니다.
"""

import boto3
import json
from boto3.session import Session


def update_orchestrator_permissions(sub_agent_arns: list, orchestrator_agent_id: str, region=None):
    """
    오케스트레이터 역할에 하위 에이전트를 직접 호출할 권한을 추가합니다.

    인수:
        sub_agent_arns: 하위 에이전트 런타임 ARN 목록
        orchestrator_agent_id: 오케스트레이터의 에이전트 런타임 ID(예: 'orchestrator_a2a-eHQbJjFPxX')
        region: AWS 리전(선택 사항)
    """
    if region is None:
        region = Session().region_name

    account_id = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    iam_client = boto3.client("iam", region_name=region)
    agentcore_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # 런타임 구성에서 실행 역할 ARN 가져오기
    runtime_info = agentcore_client.get_agent_runtime(agentRuntimeId=orchestrator_agent_id)
    role_arn = runtime_info.get("roleArn") or runtime_info.get("agentRuntime", {}).get("roleArn")
    if not role_arn:
        raise ValueError(f"Could not find execution role for runtime {orchestrator_agent_id}")

    # ARN에서 역할 이름 추출(arn:aws:iam::account:role/role-name)
    orchestrator_role_name = role_arn.split("/")[-1]

    orchestrator_permissions = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeSubAgents",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                "Resource": [f"{arn}/runtime-endpoint/DEFAULT" for arn in sub_agent_arns] + sub_agent_arns,
            },
            {
                "Sid": "SSMParameterAccess",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": f"arn:aws:ssm:{region}:{account_id}:parameter/agents/*",
            },
        ],
    }

    iam_client.put_role_policy(
        RoleName=orchestrator_role_name,
        PolicyName="SubAgentPermissions",
        PolicyDocument=json.dumps(orchestrator_permissions),
    )
    print(f"Updated {orchestrator_role_name} with sub-agent permissions")


def cleanup_runtime(launch_result, agent_name, region=None):
    """
    AgentCore Runtime, ECR 리포지토리 및 IAM 역할을 정리합니다.

    인수:
        launch_result: runtime.launch()의 결과 객체
        agent_name: 에이전트 이름(IAM 역할 정리에 사용)
        region: AWS 리전(선택 사항)
    """
    if region is None:
        region = Session().region_name

    agentcore_client = boto3.client("bedrock-agentcore-control", region_name=region)
    ecr_client = boto3.client("ecr", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    # 런타임 삭제
    agentcore_client.delete_agent_runtime(agentRuntimeId=launch_result.agent_id)
    print(f"Deleted runtime: {launch_result.agent_id}")

    # ECR 리포지토리 삭제
    repo_name = launch_result.ecr_uri.split("/")[1].split(":")[0]
    ecr_client.delete_repository(repositoryName=repo_name, force=True)
    print(f"Deleted ECR repo: {repo_name}")

    # IAM 역할 삭제(auto_create_execution_role=True로 생성됨)
    # 역할 이름은 agentcore-{agent_name}-role 패턴을 따름
    role_name = f"agentcore-{agent_name}-role"
    try:
        # 먼저 모든 인라인 정책 삭제
        policies = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in policies.get("PolicyNames", []):
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

        # 그런 다음 역할 삭제
        iam_client.delete_role(RoleName=role_name)
        print(f"Deleted IAM role: {role_name}")
    except iam_client.exceptions.NoSuchEntityException:
        pass  # 역할이 없거나 이미 삭제됨


def cleanup_ssm_parameters(parameter_names: list):
    """
    SSM 파라미터를 정리합니다.

    인수:
        parameter_names: 삭제할 파라미터 이름 목록
    """
    ssm = boto3.client("ssm")
    for name in parameter_names:
        try:
            ssm.delete_parameter(Name=name)
            print(f"Deleted parameter: {name}")
        except ssm.exceptions.ParameterNotFound:
            pass
