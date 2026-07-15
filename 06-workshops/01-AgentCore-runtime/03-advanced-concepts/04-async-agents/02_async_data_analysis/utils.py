# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import boto3
import json
import time
import logging
import yaml
import uuid
from datetime import datetime
from boto3.session import Session
from typing import Optional


def generate_unique_agent_name(base_name: str = "async_data_analysis_agent") -> str:
    """AWS 제약 조건을 준수하는 고유 Agent 이름을 생성합니다.

    AWS 패턴: [a-zA-Z][a-zA-Z0-9_]{0,47}
    - 문자로 시작해야 함
    - 문자, 숫자, 밑줄만 허용
    - 전체 최대 48자
    """
    # 48자 제한에 맞도록 더 짧은 타임스탬프와 UUID 사용
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 하이픈 대신 밑줄 사용
    short_uuid = str(uuid.uuid4()).replace("-", "")[:8]  # UUID에서 하이픈 제거

    # AWS 제약 조건에 맞는 기본 이름 생성
    if base_name.startswith("async_data_analysis_agent"):
        # 제한에 맞도록 기본 이름 축약
        base = "async_data_agent"
    else:
        base = base_name[:15]  # 기본 이름 길이 제한

    unique_name = f"{base}_{timestamp}_{short_uuid}"

    # 48자 제한에 맞는지 확인
    if len(unique_name) > 48:
        # 필요한 경우 자르기
        available_chars = 48 - len(f"_{timestamp}_{short_uuid}")
        base = base[:available_chars]
        unique_name = f"{base}_{timestamp}_{short_uuid}"

    return unique_name


def update_agent_name_in_config(config_path: str = ".bedrock_agentcore.yaml", new_name: str = None):
    """구성에서 고유 이름을 사용하도록 Agent 이름을 업데이트합니다."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if not new_name:
            new_name = generate_unique_agent_name()

        # 기본 Agent 이름 업데이트
        config["default_agent"] = new_name

        # Agent 구성 업데이트
        if "agents" in config:
            old_agents = dict(config["agents"])
            config["agents"] = {}

            for old_name, agent_config in old_agents.items():
                # 새 고유 이름 사용
                config["agents"][new_name] = agent_config
                config["agents"][new_name]["name"] = new_name

                # 새 배포를 위해 Agent ID 재설정
                if "bedrock_agentcore" in agent_config:
                    agent_config["bedrock_agentcore"]["agent_id"] = None
                    agent_config["bedrock_agentcore"]["agent_arn"] = None
                    agent_config["bedrock_agentcore"]["agent_session_id"] = None

                break  # 첫 번째 Agent만 업데이트

        # 업데이트된 구성을 다시 쓰기
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        logging.info(f"✅ Updated agent name to: {new_name}")
        return new_name

    except Exception as e:
        logging.error(f"❌ Failed to update agent name: {e}")
        return None


def reset_agent_configuration(config_path: str = ".bedrock_agentcore.yaml"):
    """새 배포가 가능하도록 Agent 구성을 동적으로 재설정합니다."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Agent별 필드 재설정
        if "agents" in config:
            for agent_name, agent_config in config["agents"].items():
                if "bedrock_agentcore" in agent_config:
                    agent_config["bedrock_agentcore"]["agent_id"] = None
                    agent_config["bedrock_agentcore"]["agent_arn"] = None
                    agent_config["bedrock_agentcore"]["agent_session_id"] = None

        # 업데이트된 구성을 다시 쓰기
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        logging.info(f"✅ Agent configuration reset in {config_path}")
        return True

    except Exception as e:
        logging.error(f"❌ Failed to reset agent configuration: {e}")
        return False


def get_agent_status(config_path: str = ".bedrock_agentcore.yaml"):
    """현재 Agent 배포 상태를 확인합니다."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        agents_status = {}
        if "agents" in config:
            for agent_name, agent_config in config["agents"].items():
                bedrock_config = agent_config.get("bedrock_agentcore", {})
                agent_id = bedrock_config.get("agent_id")
                agent_arn = bedrock_config.get("agent_arn")

                agents_status[agent_name] = {
                    "agent_id": agent_id,
                    "agent_arn": agent_arn,
                    "deployed": agent_id is not None and agent_arn is not None,
                }

        return agents_status

    except Exception as e:
        logging.error(f"❌ Failed to get agent status: {e}")
        return {}


def ensure_fresh_deployment(config_path: str = ".bedrock_agentcore.yaml"):
    """구성이 새 배포를 수행할 준비가 되었는지 확인합니다."""
    status = get_agent_status(config_path)

    for agent_name, info in status.items():
        if info["deployed"]:
            logging.info(f"🔄 Agent '{agent_name}' has existing deployment, resetting for fresh deployment")
            reset_agent_configuration(config_path)
            break
    else:
        logging.info("✅ Configuration ready for fresh deployment")

    return True


class SecureCodeInterpreter:
    """네트워크 격리와 제한된 S3 접근을 사용하는 Secure CodeInterpreter입니다."""

    def __init__(self, region: str, allowed_s3_buckets: Optional[list] = None):
        self.region = region
        self.allowed_s3_buckets = allowed_s3_buckets or []
        self.control_client = boto3.client("bedrock-agentcore-control", region_name=region)
        self.code_interpreter_id = None
        self.execution_role_arn = None

    def create_restricted_execution_role(self, role_name: str) -> str:
        """특정 버킷에 대한 최소 S3 권한만 있는 IAM 역할을 생성합니다."""
        iam_client = boto3.client("iam")

        # CodeInterpreter용 신뢰 정책 생성
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        # 허용된 버킷만 대상으로 최소 S3 정책 생성
        s3_resources = []
        if self.allowed_s3_buckets:
            for bucket in self.allowed_s3_buckets:
                s3_resources.extend([f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"])

        execution_policy = {
            "Version": "2012-10-17",
            "Statement": [
                (
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                        "Resource": s3_resources,
                    }
                    if s3_resources
                    else {"Effect": "Deny", "Action": "*", "Resource": "*"}
                )
            ],
        }

        try:
            # 역할 생성
            role_response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Restricted execution role for secure CodeInterpreter",
            )

            # 정책 연결
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="RestrictedS3Access",
                PolicyDocument=json.dumps(execution_policy),
            )

            role_arn = role_response["Role"]["Arn"]
            logging.info(f"Created restricted execution role: {role_arn}")
            return role_arn

        except iam_client.exceptions.EntityAlreadyExistsException:
            # 역할이 있으면 ARN 가져오기
            role_response = iam_client.get_role(RoleName=role_name)
            return role_response["Role"]["Arn"]

    def create_secure_code_interpreter(self, name: str) -> str:
        """Sandbox 모드(인터넷 접근 없음)로 CodeInterpreter를 생성합니다."""

        # 제한된 실행 역할 생성
        role_name = f"secure-code-interpreter-{name}-role"
        self.execution_role_arn = self.create_restricted_execution_role(role_name)

        # 역할을 사용할 수 있을 때까지 대기
        time.sleep(10)

        try:
            response = self.control_client.create_code_interpreter(
                name=name,
                description="Secure CodeInterpreter with network isolation",
                executionRoleArn=self.execution_role_arn,
                networkConfiguration={
                    "networkMode": "SANDBOX"  # 인터넷 접근 없이 S3와 DNS만 허용
                },
            )

            self.code_interpreter_id = response["codeInterpreterId"]
            logging.info(f"Created secure CodeInterpreter: {self.code_interpreter_id}")
            logging.info("Network mode: SANDBOX (no internet access)")
            logging.info(f"S3 access limited to buckets: {self.allowed_s3_buckets}")

            return self.code_interpreter_id

        except Exception as e:
            logging.error(f"Failed to create secure CodeInterpreter: {e}")
            raise

    def get_code_interpreter_client(self):
        """보안 실행용으로 구성된 CodeInterpreter 클라이언트를 가져옵니다."""
        if not self.code_interpreter_id:
            raise ValueError("CodeInterpreter not created. Call create_secure_code_interpreter first.")

        from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter

        # 제한된 구성을 사용하는 사용자 지정 CodeInterpreter 사용
        return CodeInterpreter(region=self.region, code_interpreter_id=self.code_interpreter_id)


def create_agentcore_role(agent_name):
    iam_client = boto3.client("iam")
    agentcore_role_name = f"agentcore-{agent_name}-role"
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": [
                    f"arn:aws:bedrock:{region}::foundation-model/us.anthropic.claude-sonnet-4-20250514-v1:0",
                    f"arn:aws:bedrock:{region}::foundation-model/us.anthropic.claude-haiku-4-5-20251001-v1:0",
                ],
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/bedrock-agentcore/*",
                    f"arn:aws:ecr:{region}:{account_id}:repository/bedrock-agentcore-*",
                ],
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": ["ecr:GetAuthorizationToken"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogGroups"],
                "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                "Resource": [f"arn:aws:xray:{region}:{account_id}:*"],
            },
            {
                "Effect": "Allow",
                "Resource": f"arn:aws:cloudwatch:{region}:{account_id}:metric/bedrock-agentcore/*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*",
                ],
            },
            {
                "Sid": "CodeInterpreterManagement",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateCodeInterpreter",
                    "bedrock-agentcore:DeleteCodeInterpreter",
                    "bedrock-agentcore:GetCodeInterpreter",
                    "bedrock-agentcore:ListCodeInterpreters",
                    "bedrock-agentcore:StartCodeInterpreterSession",
                    "bedrock-agentcore:StopCodeInterpreterSession",
                    "bedrock-agentcore:InvokeCodeInterpreter",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:code-interpreter/*"],
            },
            {
                "Sid": "IAMRoleManagement",
                "Effect": "Allow",
                "Action": [
                    "iam:CreateRole",
                    "iam:GetRole",
                    "iam:PutRolePolicy",
                    "iam:DeleteRole",
                    "iam:DeleteRolePolicy",
                    "iam:ListRolePolicies",
                ],
                "Resource": [f"arn:aws:iam::{account_id}:role/secure-code-interpreter-*"],
            },
            {
                "Sid": "STSGetCallerIdentity",
                "Effect": "Allow",
                "Action": ["sts:GetCallerIdentity"],
                "Resource": "*",
            },
        ],
    }
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": f"{account_id}"},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"},
                },
            }
        ],
    }

    assume_role_policy_document_json = json.dumps(assume_role_policy_document)
    role_policy_document = json.dumps(role_policy)
    # Lambda 함수용 IAM 역할 생성
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

    # 역할 생성을 확인하기 위해 잠시 대기
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(RoleName=agentcore_role_name, MaxItems=100)
        print("policies:", policies)
        for policy_name in policies["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=agentcore_role_name, PolicyName=policy_name)
        print(f"deleting {agentcore_role_name}")
        iam_client.delete_role(RoleName=agentcore_role_name)
        print(f"recreating {agentcore_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

    # AWSLambdaBasicExecutionRole 정책 연결
    print(f"attaching role policy {agentcore_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name,
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role
