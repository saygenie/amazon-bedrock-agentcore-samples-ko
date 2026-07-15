import os
import json
import boto3
from boto3.session import Session
from typing import Optional


SAMPLE_ROLE_NAME = "BrowserOSActAgentCoreRole"
POLICY_NAME = "BrowserOSActAgentCorePolicy"


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def create_agentcore_execution_role(role_name: str) -> Optional[str]:
    """AgentCore Runtime 실행용 IAM 역할을 생성한다."""
    iam = boto3.client("iam")
    boto_session = Session()
    region = boto_session.region_name
    account_id = get_aws_account_id()

    # 신뢰 관계 정책
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": ["bedrock-agentcore.amazonaws.com"]},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {"aws:SourceArn": (f"arn:aws:bedrock-agentcore:{region}:{account_id}:*")},
                },
            }
        ],
    }

    # IAM 정책 문서
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowAgentToUseBrowser",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeBrowser",
                    "bedrock-agentcore:StartBrowserSession",
                    "bedrock-agentcore:StopBrowserSession",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"],
            }
        ],
    }

    try:
        # 역할이 이미 존재하는지 확인
        try:
            existing_role = iam.get_role(RoleName=role_name)
            print(f"ℹ️ Role {role_name} already exists")
            print(f"Role ARN: {existing_role['Role']['Arn']}")
            return existing_role["Role"]["Arn"]
        except iam.exceptions.NoSuchEntityException:
            pass

        # IAM 역할 생성
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=("IAM role for Amazon Bedrock AgentCore with required permissions"),
        )

        print(f"✅ Created IAM role: {role_name}")
        print(f"Role ARN: {role_response['Role']['Arn']}")

        # 정책이 이미 존재하는지 확인
        policy_arn = f"arn:aws:iam::{account_id}:policy/{POLICY_NAME}"

        try:
            iam.get_policy(PolicyArn=policy_arn)
            print(f"ℹ️ Policy {POLICY_NAME} already exists")
        except iam.exceptions.NoSuchEntityException:
            # 정책 생성
            policy_response = iam.create_policy(
                PolicyName=POLICY_NAME,
                PolicyDocument=json.dumps(policy_document),
                Description="Policy for Amazon Bedrock AgentCore permissions",
            )
            print(f"✅ Created policy: {POLICY_NAME}")
            policy_arn = policy_response["Policy"]["Arn"]

        # 역할에 정책 연결
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Attached policy to role")
        except iam.exceptions.ClientError as e:
            if "already attached" in str(e).lower():
                print("ℹ️ Policy already attached to role")
            else:
                raise

        print(f"Policy ARN: {policy_arn}")
        return role_response["Role"]["Arn"]

    except iam.exceptions.ClientError as e:
        print(f"❌ Error creating IAM role: {str(e)}")
        return None


def delete_agentcore_execution_role(role_name: str) -> None:
    """AgentCore Runtime 실행 역할과 관련 정책을 삭제한다."""
    iam = boto3.client("iam")

    try:
        account_id = get_aws_account_id()
        policy_arn = f"arn:aws:iam::{account_id}:policy/{POLICY_NAME}"

        # 역할에서 정책 분리
        try:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Detached policy from role")
        except iam.exceptions.ClientError:
            pass

        # 역할 삭제
        try:
            iam.delete_role(RoleName=role_name)
            print(f"✅ Deleted role: {role_name}")
        except iam.exceptions.ClientError:
            pass

        # 정책 삭제
        try:
            iam.delete_policy(PolicyArn=policy_arn)
            print(f"✅ Deleted policy: {POLICY_NAME}")
        except iam.exceptions.ClientError:
            pass

    except iam.exceptions.ClientError as e:
        print(f"❌ Error during cleanup: {str(e)}")


def local_file_cleanup() -> None:
    """튜토리얼 중 생성된 로컬 파일을 정리한다."""
    # 정리할 파일 목록
    files_to_delete = ["Dockerfile", ".dockerignore", ".bedrock_agentcore.yaml"]

    deleted_files = []
    missing_files = []

    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.unlink(file)
                deleted_files.append(file)
                print(f"  ✅ Deleted {file}")
            except OSError as e:
                print(f"  ⚠️  Error deleting {file}: {e}")
        else:
            missing_files.append(file)

    if deleted_files:
        print(f"\n📁 Successfully deleted {len(deleted_files)} files")
    if missing_files:
        print(f"ℹ️  {len(missing_files)} files were already missing: {', '.join(missing_files)}")
