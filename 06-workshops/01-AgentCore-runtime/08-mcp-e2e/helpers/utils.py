import os
import base64
import hashlib
import hmac
import json
import boto3
from boto3.session import Session
from typing import Optional


username = "testuser"
sm_name = "mcp_sample_agent"

SAMPLE_ROLE_NAME = "MCPDemoBedrockAgentCoreRole"
POLICY_NAME = "AWSMCPtBedrockAgentCorePolicy"


def get_customer_support_secret():
    """AWS Secrets Manager에서 secret 값을 가져옵니다."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        response = secrets_client.get_secret_value(SecretId=sm_name)
        return response["SecretString"]
    except Exception as e:
        print(f"❌ Error getting secret: {str(e)}")
        return None


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_cognito_secret() -> Optional[str]:
    """AWS Secrets Manager에서 secret 값을 가져옵니다."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        response = secrets_client.get_secret_value(SecretId=sm_name)
        return response["SecretString"]
    except secrets_client.exceptions.ClientError as e:
        print(f"❌ Error getting secret: {str(e)}")
        return None


def save_customer_support_secret(secret_value):
    """AWS Secrets Manager에 secret을 저장합니다."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)

    try:
        secrets_client.create_secret(
            Name=sm_name,
            SecretString=secret_value,
            Description="Secret containing the Cognito Configuration for the Customer Support Agent",
        )
        print("✅ Created secret")
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.update_secret(SecretId=sm_name, SecretString=secret_value)
        print("✅ Updated existing secret")
    except Exception as e:
        print(f"❌ Error saving secret: {str(e)}")
        return False
    return True


def get_or_create_cognito_pool(refresh_token=False):
    boto_session = Session()
    region = boto_session.region_name
    # Cognito client 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        # 기존 Cognito pool 확인
        cognito_config_str = get_customer_support_secret()
        cognito_config = json.loads(cognito_config_str)
        if refresh_token:
            cognito_config["bearer_token"] = reauthenticate_user(
                cognito_config["client_id"], cognito_config["client_secret"]
            )
        return cognito_config
    except Exception:
        print("No existing cognito config found. Creating a new one..")

    try:
        # User Pool 생성
        user_pool_response = cognito_client.create_user_pool(
            PoolName="MCPServerPool", Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]
        # App Client 생성
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="MCPServerPoolClient",
            GenerateSecret=True,
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
                "ALLOW_USER_SRP_AUTH",
            ],
        )
        print(app_client_response["UserPoolClient"])
        client_id = app_client_response["UserPoolClient"]["ClientId"]
        client_secret = app_client_response["UserPoolClient"]["ClientSecret"]

        # 사용자 생성
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            TemporaryPassword="Temp123!",  # pragma: allowlist secret
            MessageAction="SUPPRESS",
        )

        # 영구 password 설정
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password="MyPassword123!",  # pragma: allowlist secret
            Permanent=True,
        )

        message = bytes(username + client_id, "utf-8")
        key = bytes(client_secret, "utf-8")
        secret_hash = base64.b64encode(hmac.new(key, message, digestmod=hashlib.sha256).digest()).decode()

        # 사용자 인증 후 Access Token 가져오기
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": "MyPassword123!",  # pragma: allowlist secret
                "SECRET_HASH": secret_hash,
            },
        )
        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        # 필요한 값 출력
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: {discovery_url}")
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        # 후속 처리에 필요한 경우 값 반환
        cognito_config = {
            "pool_id": pool_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "secret_hash": secret_hash,
            "bearer_token": bearer_token,
            "discovery_url": discovery_url,
        }
        save_customer_support_secret(json.dumps(cognito_config))

        return cognito_config
    except Exception as e:
        print(f"Error: {e}")
        return None


def reauthenticate_user(client_id, client_secret):
    boto_session = Session()
    region = boto_session.region_name
    # Cognito client 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)
    # 사용자 인증 후 Access Token 가져오기

    message = bytes(username + client_id, "utf-8")
    key = bytes(client_secret, "utf-8")
    secret_hash = base64.b64encode(hmac.new(key, message, digestmod=hashlib.sha256).digest()).decode()

    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": "MyPassword123!",  # pragma: allowlist secret
            "SECRET_HASH": secret_hash,
        },
    )
    bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
    return bearer_token


# AgentCore 리소스
def create_agentcore_runtime_execution_role(role_name: str) -> Optional[str]:
    """AgentCore Runtime 실행을 위한 IAM 역할을 생성합니다."""
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
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
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
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                "Resource": [f"arn:aws:ecr:{region}:{account_id}:repository/*"],
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
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": ["ecr:GetAuthorizationToken"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                "Resource": ["*"],
            },
            {
                "Effect": "Allow",
                "Resource": "*",
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
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:"
                    "workload-identity-directory/default/workload-identity/*",
                ],
            },
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ApplyGuardrail",
                    "bedrock:Retrieve",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{account_id}:*",
                ],
            },
            {
                "Sid": "AllowAgentToUseMemory",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                    "bedrock-agentcore:ListMemoryRecords",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"],
            },
            {
                "Sid": "DynamoDBAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{region}:{account_id}:table/finance_tracker",
                    f"arn:aws:dynamodb:{region}:{account_id}:table/finance_tracker/index/*",
                ],
            },
            {
                "Sid": "GetSecrets",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [f"arn:aws:secretsmanager:{region}:{account_id}:secret:{sm_name}*"],
            },
        ],
    }

    try:
        # 역할이 이미 있는지 확인
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

        # 정책이 이미 있는지 확인
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


def delete_agentcore_runtime_execution_role(role_name: str) -> None:
    """AgentCore Runtime 실행 역할 및 연결된 정책을 삭제합니다."""
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


def cleanup_cognito_resources(pool_id: str) -> bool:
    """사용자, app client 및 user pool을 포함한 Cognito 리소스를 삭제합니다."""
    try:
        # 동일한 session 구성으로 Cognito client 초기화
        boto_session = Session()
        region = boto_session.region_name
        cognito_client = boto3.client("cognito-idp", region_name=region)

        if pool_id:
            try:
                # 모든 app client를 나열하고 삭제
                clients_response = cognito_client.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)

                for client in clients_response["UserPoolClients"]:
                    print(f"Deleting app client: {client['ClientName']}")
                    cognito_client.delete_user_pool_client(UserPoolId=pool_id, ClientId=client["ClientId"])

                # 모든 사용자를 나열하고 삭제
                users_response = cognito_client.list_users(UserPoolId=pool_id, AttributesToGet=["email"])

                for user in users_response.get("Users", []):
                    print(f"Deleting user: {user['Username']}")
                    cognito_client.admin_delete_user(UserPoolId=pool_id, Username=user["Username"])

                # User pool 삭제
                print(f"Deleting user pool: {pool_id}")
                cognito_client.delete_user_pool(UserPoolId=pool_id)

                print("Successfully cleaned up all Cognito resources")
                return True

            except cognito_client.exceptions.ResourceNotFoundException:
                print(f"User pool {pool_id} not found. It may have already been deleted.")
                return True

            except cognito_client.exceptions.ClientError as e:
                print(f"Error during cleanup: {str(e)}")
                return False
        else:
            print("No matching user pool found")
            return True

    except cognito_client.exceptions.ClientError as e:
        print(f"Error initializing cleanup: {str(e)}")
        return False


def delete_cognito_secret() -> bool:
    """AWS Secrets Manager에서 secret을 삭제합니다."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        secrets_client.delete_secret(SecretId=sm_name, ForceDeleteWithoutRecovery=True)
        print("✅ Secret Deleted")
        return True
    except secrets_client.exceptions.ClientError as e:
        print(f"❌ Error deleting secret: {str(e)}")
        return False


def local_file_cleanup() -> None:
    """튜토리얼에서 생성된 로컬 파일을 정리합니다."""
    # 정리할 파일 목록
    files_to_delete = [
        "Dockerfile",
        ".dockerignore",
        ".bedrock_agentcore.yaml",
        "agents/strands_aws_docs.py",
        "agents/orchestrator.py",
        "agents/requirements.txt",
        "agents/strands_aws_blogs_news.py",
    ]

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
