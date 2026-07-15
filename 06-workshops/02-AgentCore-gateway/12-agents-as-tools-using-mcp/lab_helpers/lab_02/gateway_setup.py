"""
Lab 02: AgentCore Gateway 서비스 역할 설정

Gateway가 Lambda 대상을 호출하는 데 필요한 IAM 서비스 역할을 생성합니다.
Lambda 실행 역할과는 별개이며, Gateway에는 자체 역할이 필요합니다.
"""

import json
import boto3
from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.parameter_store import put_parameter


def create_gateway_service_role(region_name="us-west-2", account_id=None):
    """
    AgentCore Gateway용 IAM 서비스 역할을 생성합니다.

    Gateway에는 다음 권한이 필요합니다.
    1. Lambda 함수 호출
    2. CloudWatch 로그 접근
    3. 필요에 따라 다른 서비스 호출

    인자:
        region_name: AWS 리전
        account_id: AWS 계정 ID(제공하지 않으면 조회)

    반환:
        역할 ARN 및 기타 세부 정보가 포함된 딕셔너리
    """
    iam_client = boto3.client("iam", region_name=region_name)
    sts_client = boto3.client("sts", region_name=region_name)
    ssm_client = boto3.client("ssm", region_name=region_name)  # noqa: F841

    # 제공되지 않은 경우 계정 ID 조회
    if not account_id:
        account_id = sts_client.get_caller_identity()["Account"]

    role_name = "aiml301-gateway-service-role"

    # 신뢰 관계: bedrock-agentcore 서비스가 이 역할을 수임하도록 허용
    # 보안을 위해 특정 계정 및 Gateway ARN 패턴으로 제한
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region_name}:{account_id}:gateway/*"},
                },
            }
        ],
    }

    # 권한: Gateway에서 Lambda 호출, CloudWatch 접근 및 AgentCore 리소스 관리에 필요
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeLambdaFunctions",
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": "*",
            },
            {
                "Sid": "BedrockAgentCorePermissions",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:*"],
                "Resource": "*",
            },
            {
                "Sid": "CloudWatchLogsPermissions",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                "Resource": "*",
            },
        ],
    }

    try:
        # 역할이 이미 존재하는지 확인
        try:
            role = iam_client.get_role(RoleName=role_name)
            print(f"✓ Gateway service role already exists: {role['Role']['Arn']}")
            role_arn = role["Role"]["Arn"]
        except iam_client.exceptions.NoSuchEntityException:
            print(f"Creating gateway service role: {role_name}")

            # 역할 생성
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Service role for AgentCore Gateway to invoke Lambda targets",
            )

            role_arn = response["Role"]["Arn"]
            print(f"✓ Gateway service role created: {role_arn}")

            # Lambda 호출을 위한 인라인 정책 연결
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="gateway-invoke-lambda",
                PolicyDocument=json.dumps(permissions_policy),
            )
            print("✓ Permissions policy attached")

        # 나중에 사용하도록 Parameter Store에 저장(일관성을 위해 상수 사용)
        gateway_role_arn_param = PARAMETER_PATHS["lab_02"]["gateway_role_arn"]
        put_parameter(
            gateway_role_arn_param,
            role_arn,
            description="Gateway service role ARN for Lab 02",
            region_name=region_name,
        )
        print(f"✓ Role ARN saved to Parameter Store: {gateway_role_arn_param}")

        return {
            "role_arn": role_arn,
            "role_name": role_name,
            "account_id": account_id,
            "region": region_name,
        }

    except Exception as e:
        print(f"❌ Error creating gateway service role: {e}")
        raise


if __name__ == "__main__":
    from lab_helpers.config import AWS_REGION

    print("=" * 70)
    print("Setting up AgentCore Gateway Service Role")
    print("=" * 70)
    print()

    result = create_gateway_service_role(region_name=AWS_REGION)

    print()
    print("=" * 70)
    print("✅ Gateway Service Role Setup Complete")
    print("=" * 70)
    print(f"Role ARN: {result['role_arn']}")
    print()
