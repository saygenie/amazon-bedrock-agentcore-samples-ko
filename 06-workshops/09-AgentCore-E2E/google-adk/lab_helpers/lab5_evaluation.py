#!/usr/bin/python
"""에이전트 역할을 조회하고 평가 정책을 연결하는 Lab 5용 AgentCore Evaluation 헬퍼."""

import json
import os

import boto3
from boto3.session import Session
from lab_helpers.utils import get_ssm_parameter

boto_session = Session()
REGION = boto_session.region_name

EVALUATION_POLICY_SUFFIX = "AgentCoreEvaluationPolicy"


def get_execution_role_arn_from_runtime():
    """AgentCore Runtime 에이전트 설정에서 실행 역할 ARN을 조회한다.

    Runtime 조회에 실패하면 SSM 파라미터를 대신 사용한다.

    반환:
        str: 실행 역할 ARN
    """
    try:
        # SSM 먼저 시도(lab04에서 create_agentcore_runtime_execution_role을 통해 저장됨)
        role_arn = get_ssm_parameter("/app/customersupport/agentcore/runtime_execution_role_arn")
        if role_arn:
            print(f"✅ Retrieved execution_role_arn from SSM: {role_arn}")
            return role_arn
    except Exception:
        pass

    # 대체 처리: Runtime 에이전트 설정에서 가져오기
    try:
        agent_arn = get_ssm_parameter("/app/customersupport/agentcore/runtime_arn")
        runtime_id = agent_arn.split(":")[-1].split("/")[-1]

        control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
        response = control_client.get_agent_runtime(agentRuntimeId=runtime_id)
        role_arn = response.get("roleArn")

        if role_arn:
            print(f"✅ Retrieved execution_role_arn from runtime config: {role_arn}")
            return role_arn
    except Exception as e:
        print(f"⚠️  Could not retrieve role from runtime: {e}")

    raise RuntimeError("Could not retrieve execution_role_arn. Please run Lab 4 first.")


def attach_evaluation_policy(execution_role_arn: str, policy_json_path: str = None):
    """에이전트 실행 역할에 AgentCore Evaluations 정책을 연결한다.

    인수:
        execution_role_arn: 정책을 연결할 IAM 역할 ARN.
        policy_json_path: 평가 정책 JSON 파일 경로.
                          기본값은 lab_helpers/lab5_evaluation/agentcore-evaluation-policy.json이다.

    반환:
        str: 연결된 정책 ARN
    """
    if not policy_json_path:
        policy_json_path = os.path.join(
            os.path.dirname(__file__),
            "lab5_evaluation",
            "agentcore-evaluation-policy.json",
        )

    # 정책 문서 로드
    with open(policy_json_path, "r") as f:
        policy_document = json.load(f)

    iam = boto3.client("iam")
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_name = execution_role_arn.split("/")[-1]
    policy_name = f"{role_name}-{EVALUATION_POLICY_SUFFIX}"
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

    # 정책이 이미 연결되어 있는지 확인
    try:
        attached = iam.list_attached_role_policies(RoleName=role_name)
        for p in attached.get("AttachedPolicies", []):
            if EVALUATION_POLICY_SUFFIX in p["PolicyName"]:
                print(f"ℹ️  Evaluation policy already attached: {p['PolicyArn']}")
                return p["PolicyArn"]
    except Exception:
        pass

    # 정책 생성 또는 업데이트
    try:
        iam.get_policy(PolicyArn=policy_arn)
        print(f"ℹ️  Policy {policy_name} already exists")
    except iam.exceptions.NoSuchEntityException:
        iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
            Description="AgentCore Evaluation permissions for online evaluation",
        )
        print(f"✅ Created policy: {policy_name}")

    # 역할에 연결
    iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    print(f"✅ Attached evaluation policy to role: {role_name}")
    return policy_arn


def ensure_evaluation_role(execution_role_arn: str = None):
    """실행 역할에 평가 권한이 있는지 확인한다.

    execution_role_arn이 None이거나 비어 있으면 Runtime에서 조회한다.
    그다음 평가 정책이 아직 연결되지 않은 경우 연결한다.

    인수:
        execution_role_arn: 선택적 역할 ARN. 비어 있거나 None이면 자동으로 조회한다.

    반환:
        str: 검증된 execution_role_arn
    """
    if not execution_role_arn or not execution_role_arn.strip():
        print("⚠️  execution_role_arn is empty, retrieving from runtime...")
        execution_role_arn = get_execution_role_arn_from_runtime()

    # 형식 검증
    if not execution_role_arn.startswith("arn:aws:iam::"):
        # 완화된 검사 - ARN처럼 보이는지만 확인
        if "arn:" not in execution_role_arn or ":role/" not in execution_role_arn:
            raise ValueError(f"Invalid execution_role_arn format: {execution_role_arn}")

    print(f"Using execution_role_arn: {execution_role_arn}")
    attach_evaluation_policy(execution_role_arn)
    return execution_role_arn
