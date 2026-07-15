"""
Lab 05: Supervisor Runtime IAM 설정

다음 권한이 포함된 Supervisor Agent Runtime용 IAM 역할을 생성합니다.
- 오케스트레이션을 위한 Bedrock 모델 호출
- JWT 토큰 전파를 사용해 세 개의 하위 Agent Gateway 호출
- Parameter Store에서 Gateway URL 조회
- CloudWatch에 로그 쓰기
"""

import json
import boto3
import logging
from typing import Dict
from botocore.exceptions import ClientError

from lab_helpers.config import AWS_REGION

logger = logging.getLogger(__name__)


def create_supervisor_runtime_iam_role(role_name: str, region: str = AWS_REGION, account_id: str = None) -> Dict:
    """
    Multi-Gateway 오케스트레이션 권한이 포함된 Supervisor Runtime용 IAM 역할을 생성합니다.

    Supervisor Runtime에는 다음 권한이 필요합니다.
    1. 서로 다른 세 개의 Agent Gateway(Diagnostics, Remediation, Prevention) 연결
    2. 여러 Agent에 걸친 요청 오케스트레이션
    3. LLM 기반 오케스트레이션 로직을 위한 Bedrock 모델 호출
    4. Parameter Store에서 Gateway URL 조회
    5. CloudWatch에 로그 쓰기

    인증에는 JWT 토큰 전파를 사용합니다.
    - 사용자가 Authorization 헤더에 JWT 토큰 제공
    - Supervisor Runtime이 JWT를 추출해 Gateway 연결로 전파
    - M2M 자격 증명이나 토큰 조회가 필요하지 않음

    인자:
        role_name: IAM 역할 이름
        region: AWS 리전(기본값: 구성에서 가져옴)
        account_id: AWS 계정 ID(제공하지 않으면 자동 감지)

    반환:
        role_name, role_arn 및 정책 세부 정보가 포함된 딕셔너리
    """
    iam = boto3.client("iam", region_name=region)
    sts = boto3.client("sts", region_name=region)

    # 계정 ID 조회
    if not account_id:
        account_id = sts.get_caller_identity()["Account"]

    logger.info(f"Creating supervisor runtime IAM role: {role_name}")
    logger.info("Authentication: JWT token propagation (User JWT → Supervisor → Gateways)")

    # 신뢰 정책: bedrock-agentcore 서비스가 역할을 수임하도록 허용
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"},
                },
            }
        ],
    }

    # 역할 생성
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="IAM role for Lab 05 Supervisor Agent Runtime - Multi-agent orchestration",
            Tags=[
                {"Key": "Workshop", "Value": "AIML301"},
                {"Key": "Lab", "Value": "Lab-05"},
                {"Key": "Component", "Value": "SupervisorRuntime"},
            ],
        )
        role_arn = response["Role"]["Arn"]
        logger.info(f"✅ Role created: {role_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            logger.warning(f"⚠️ Role {role_name} already exists, using existing role")
            response = iam.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
        else:
            logger.error(f"❌ Failed to create role: {e}")
            raise

    # Supervisor 전용 권한을 위한 인라인 정책
    policy_name = f"{role_name}-policy"
    supervisor_policy = {
        "Version": "2012-10-17",
        "Statement": [
            # 1. Bedrock 모델 호출(오케스트레이션 로직용)
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",  # Cross-region 모델 ID(예: us.anthropic.claude-*)
                    f"arn:aws:bedrock:{region}:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:us-east-2:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:us-west-2:{account_id}:inference-profile/*",
                ],
            },
            # 2. CloudWatch Logs(Runtime 로깅)
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/*"],
            },
            # 2b. X-Ray 추적(Runtime 관찰성 및 추적)
            {
                "Sid": "XRayTracing",
                "Effect": "Allow",
                "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                "Resource": "*",
            },
            # 3. Gateway 접근(하위 Agent Gateway 호출)
            {
                "Sid": "GatewayAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeGateway",
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:ListGateways",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/*"],
            },
            # 6. Parameter Store(구성 및 Gateway URL 조회)
            {
                "Sid": "ParameterStoreRead",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                "Resource": [f"arn:aws:ssm:{region}:{account_id}:parameter/*"],
            },
            # 7. KMS(보안 암호 및 파라미터 복호화)
            {
                "Sid": "KMSDecrypt",
                "Effect": "Allow",
                "Action": ["kms:Decrypt", "kms:DescribeKey"],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "kms:ViaService": [
                            f"secretsmanager.{region}.amazonaws.com",
                            f"ssm.{region}.amazonaws.com",
                        ]
                    }
                },
            },
            # 8. ECR 접근(컨테이너 이미지 가져오기)
            {
                "Sid": "ECRAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                "Resource": "*",
            },
        ],
    }

    # 인라인 정책 연결
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(supervisor_policy),
        )
        logger.info(f"✅ Inline policy attached: {policy_name}")
    except ClientError as e:
        logger.error(f"❌ Failed to attach policy: {e}")
        raise

    # 역할 정보 반환
    return {
        "role_name": role_name,
        "role_arn": role_arn,
        "policy_name": policy_name,
        "region": region,
        "account_id": account_id,
        "permissions": {
            "bedrock_models": "InvokeModel and streaming",
            "gateways": "Call 3 sub-agent gateways with JWT propagation",
            "cloudwatch_logs": "Runtime logging",
            "parameter_store": "Gateway URL retrieval (/aiml301/lab-0X/gateway-id)",
            "kms": "Decrypt parameters",
            "ecr": "Pull container images",
        },
    }


def delete_supervisor_runtime_iam_role(role_name: str, region: str = AWS_REGION) -> bool:
    """
    Supervisor Runtime IAM 역할과 관련 정책을 삭제합니다.

    인자:
        role_name: 삭제할 IAM 역할 이름
        region: AWS 리전(기본값: 구성에서 가져옴)

    반환:
        삭제에 성공하면 True, 그렇지 않으면 False
    """
    iam = boto3.client("iam", region_name=region)

    logger.info(f"Deleting supervisor runtime IAM role: {role_name}")

    try:
        # 인라인 정책을 나열하고 삭제
        response = iam.list_role_policies(RoleName=role_name)
        for policy_name in response.get("PolicyNames", []):
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            logger.info(f"✅ Deleted inline policy: {policy_name}")

        # 관리형 정책을 나열하고 분리
        response = iam.list_attached_role_policies(RoleName=role_name)
        for policy in response.get("AttachedPolicies", []):
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
            logger.info(f"✅ Detached managed policy: {policy['PolicyName']}")

        # 역할 삭제
        iam.delete_role(RoleName=role_name)
        logger.info(f"✅ Deleted role: {role_name}")

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            logger.warning(f"⚠️ Role {role_name} does not exist")
            return True
        else:
            logger.error(f"❌ Failed to delete role: {e}")
            return False
