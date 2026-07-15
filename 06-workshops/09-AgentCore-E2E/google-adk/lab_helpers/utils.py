import base64
import hashlib
import hmac
import json
import os
import time
import warnings
from typing import Any, Dict

import boto3
import yaml
from boto3.session import Session


def suppress_warnings():
    """Notebook 출력을 깔끔하게 유지하도록 불필요한 종속성 경고를 숨긴다."""
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", message=".*urllib3.*")
    warnings.filterwarnings("ignore", message=".*charset_normalizer.*")
    warnings.filterwarnings("ignore", message=".*chardet.*")
    warnings.filterwarnings("ignore", message=".*google-cloud-storage.*")


suppress_warnings()

sts_client = boto3.client("sts")

# AWS 계정 세부 정보 가져오기
REGION = boto3.session.Session().region_name

username = "testuser"
sm_name = "customer_support_agent"


role_name = f"CustomerSupportAssistantBedrockAgentCoreRole-{REGION}"
policy_name = f"CustomerSupportAssistantBedrockAgentCorePolicy-{REGION}"


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def put_ssm_parameter(name: str, value: str, parameter_type: str = "String", with_encryption: bool = False) -> None:
    ssm = boto3.client("ssm")

    put_params = {
        "Name": name,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": True,
    }

    if with_encryption:
        put_params["Type"] = "SecureString"

    ssm.put_parameter(**put_params)


def delete_ssm_parameter(name: str) -> None:
    ssm = boto3.client("ssm")
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        pass


def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def get_aws_region() -> str:
    session = Session()
    return session.region_name


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_cognito_client_secret() -> str:
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/customersupport/agentcore/pool_id"),
        ClientId=get_ssm_parameter("/app/customersupport/agentcore/client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def read_config(file_path: str) -> Dict[str, Any]:
    """
    파일 경로에서 설정을 읽는다. JSON, YAML 및 YML 형식을 지원한다.

    인수:
        file_path (str): 설정 파일 경로

    반환:
        Dict[str, Any]: 딕셔너리 형태의 설정 데이터

    예외:
        FileNotFoundError: 파일이 없는 경우
        ValueError: 파일 형식이 지원되지 않거나 유효하지 않은 경우
        yaml.YAMLError: YAML 파싱에 실패한 경우
        json.JSONDecodeError: JSON 파싱에 실패한 경우
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # 형식을 판별하기 위해 파일 확장자 가져오기
    _, ext = os.path.splitext(file_path.lower())

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if ext == ".json":
                return json.load(file)
            elif ext in [".yaml", ".yml"]:
                return yaml.safe_load(file)
            else:
                # JSON을 먼저 시도한 다음 YAML을 시도하여 형식 자동 감지
                content = file.read()
                file.seek(0)

                # JSON 먼저 시도
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # YAML 시도
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        raise ValueError(
                            f"Unsupported configuration file format: {ext}. Supported formats: .json, .yaml, .yml"
                        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")


def save_customer_support_secret(secret_value):
    """AWS Secrets Manager에 보안 암호를 저장한다."""
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


def get_customer_support_secret():
    """AWS Secrets Manager에서 보안 암호 값을 가져온다."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        response = secrets_client.get_secret_value(SecretId=sm_name)
        return response["SecretString"]
    except Exception as e:
        print(f"Error getting secret: {str(e)}")
        return None


def delete_customer_support_secret():
    """AWS Secrets Manager에서 보안 암호를 삭제한다."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        secrets_client.delete_secret(SecretId=sm_name, ForceDeleteWithoutRecovery=True)
        print("✅ Deleted secret!")
        return True
    except Exception as e:
        print(f"❌ Error deleting secret: {str(e)}")
        return False


def get_or_create_cognito_pool(refresh_token=False):
    boto_session = Session()
    region = boto_session.region_name
    # Cognito 클라이언트 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        # 기존 Cognito 풀 확인
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
        # 사용자 풀 생성
        user_pool_response = cognito_client.create_user_pool(
            PoolName="MCPServerPool", Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]
        # 앱 클라이언트 생성
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

        # 영구 암호 설정
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password="MyPassword123!",  # pragma: allowlist secret
            Permanent=True,
        )

        message = bytes(username + client_id, "utf-8")
        key = bytes(client_secret, "utf-8")
        secret_hash = base64.b64encode(hmac.new(key, message, digestmod=hashlib.sha256).digest()).decode()

        # 사용자를 인증하고 액세스 토큰 가져오기
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
        # 필수 값 출력
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: {discovery_url}")
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        # 추가 처리에 필요한 경우 값 반환
        cognito_config = {
            "pool_id": pool_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "secret_hash": secret_hash,
            "bearer_token": bearer_token,
            "discovery_url": discovery_url,
        }
        put_ssm_parameter("/app/customersupport/agentcore/client_id", client_id)
        put_ssm_parameter("/app/customersupport/agentcore/pool_id", pool_id)
        put_ssm_parameter("/app/customersupport/agentcore/cognito_discovery_url", discovery_url)
        put_ssm_parameter("/app/customersupport/agentcore/client_secret", client_secret)

        save_customer_support_secret(json.dumps(cognito_config))

        return cognito_config
    except Exception as e:
        print(f"Error: {e}")
        return None


def cleanup_cognito_resources(pool_id):
    """
    사용자, 앱 클라이언트 및 사용자 풀을 포함한 Cognito 리소스를 삭제한다.
    """
    try:
        # 동일한 세션 설정을 사용하여 Cognito 클라이언트 초기화
        boto_session = Session()
        region = boto_session.region_name
        cognito_client = boto3.client("cognito-idp", region_name=region)

        if pool_id:
            try:
                # 모든 앱 클라이언트 나열 및 삭제
                clients_response = cognito_client.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)

                for client in clients_response["UserPoolClients"]:
                    print(f"Deleting app client: {client['ClientName']}")
                    cognito_client.delete_user_pool_client(UserPoolId=pool_id, ClientId=client["ClientId"])

                # 모든 사용자 나열 및 삭제
                users_response = cognito_client.list_users(UserPoolId=pool_id, AttributesToGet=["email"])

                for user in users_response.get("Users", []):
                    print(f"Deleting user: {user['Username']}")
                    cognito_client.admin_delete_user(UserPoolId=pool_id, Username=user["Username"])

                # 사용자 풀 삭제
                print(f"Deleting user pool: {pool_id}")
                cognito_client.delete_user_pool(UserPoolId=pool_id)

                print("Successfully cleaned up all Cognito resources")
                return True

            except cognito_client.exceptions.ResourceNotFoundException:
                print(f"User pool {pool_id} not found. It may have already been deleted.")
                return True

            except Exception as e:
                print(f"Error during cleanup: {str(e)}")
                return False
        else:
            print("No matching user pool found")
            return True

    except Exception as e:
        print(f"Error initializing cleanup: {str(e)}")
        return False


def reauthenticate_user(client_id, client_secret):
    boto_session = Session()
    region = boto_session.region_name
    # Cognito 클라이언트 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)
    # 사용자를 인증하고 액세스 토큰 가져오기

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


def create_agentcore_runtime_execution_role():
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
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"},
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
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/customer_support_agent-*",
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
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                    "bedrock-agentcore:ListMemoryRecords",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"],
            },
            {
                "Sid": "GetMemoryId",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": [f"arn:aws:ssm:{region}:{account_id}:parameter/*"],
            },
            {
                "Sid": "GatewayAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:InvokeGateway",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/*"],
            },
        ],
    }

    try:
        # 역할이 이미 있는지 확인
        role_arn = None
        try:
            existing_role = iam.get_role(RoleName=role_name)
            print(f"ℹ️ Role {role_name} already exists")
            role_arn = existing_role["Role"]["Arn"]
        except iam.exceptions.NoSuchEntityException:
            # IAM 역할 생성
            role_response = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="IAM role for Amazon Bedrock AgentCore with required permissions",
            )
            print(f"✅ Created IAM role: {role_name}")
            role_arn = role_response["Role"]["Arn"]

        print(f"Role ARN: {role_arn}")

        # 정책이 이미 있는지 확인하고, 없으면 생성
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        try:
            iam.get_policy(PolicyArn=policy_arn)
            print(f"ℹ️ Policy {policy_name} already exists")
        except iam.exceptions.NoSuchEntityException:
            # 정책 생성
            policy_response = iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description="Policy for Amazon Bedrock AgentCore permissions",
            )
            print(f"✅ Created policy: {policy_name}")
            policy_arn = policy_response["Policy"]["Arn"]

        # 역할에 정책 연결
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Attached policy to role")
        except Exception as e:
            if "already attached" in str(e).lower():
                print("ℹ️ Policy already attached to role")
            else:
                raise

        print(f"Policy ARN: {policy_arn}")

        put_ssm_parameter(
            "/app/customersupport/agentcore/runtime_execution_role_arn",
            role_arn,
        )
        return role_arn

    except Exception as e:
        print(f"❌ Error creating IAM role: {str(e)}")
        return None


def delete_agentcore_runtime_execution_role():
    iam = boto3.client("iam")

    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        # 역할에서 정책 분리
        try:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Detached policy from role")
        except Exception:
            pass

        # 역할 삭제
        try:
            iam.delete_role(RoleName=role_name)
            print(f"✅ Deleted role: {role_name}")
        except Exception:
            pass

        # 정책 삭제
        try:
            iam.delete_policy(PolicyArn=policy_arn)
            print(f"✅ Deleted policy: {policy_name}")
        except Exception:
            pass

        delete_ssm_parameter("/app/customersupport/agentcore/runtime_execution_role_arn")

    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")


def agentcore_memory_cleanup(memory_id: str = None):
    """모든 Memory와 연결된 전략을 나열한다."""
    control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    if memory_id:
        response = control_client.delete_memory(memoryId=memory_id)
        print(f"✅ Successfully deleted memory: {memory_id}")
    else:
        next_token = None
        while True:
            # 요청 파라미터 구성
            params = {}
            if next_token:
                params["nextToken"] = next_token

            # Memory 나열
            try:
                response = control_client.list_memories(**params)

                # 각 Memory 처리
                for memory in response.get("memories", []):
                    memory_id = memory.get("id")
                    print(f"\nMemory ID: {memory_id}")
                    print(f"Status: {memory.get('status')}")
                    response = control_client.delete_memory(memoryId=memory_id)
                    response = control_client.list_memories(**params)
                    print(f"✅ Successfully deleted memory: {memory_id}")

                response = control_client.list_memories(**params)
                # 각 Memory 상태 처리
                for memory in response.get("memories", []):
                    memory_id = memory.get("id")
                    print(f"\nMemory ID: {memory_id}")
                    print(f"Status: {memory.get('status')}")

            except Exception as e:
                print(f"⚠️  Error getting memory details: {e}")
            # 추가 결과 확인
            next_token = response.get("nextToken")
            if not next_token:
                break


def gateway_target_cleanup(gateway_id: str = None):
    gateway_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=REGION,
    )

    if not gateway_id:
        response = gateway_client.list_gateways()
        gateway_id = response["items"][0]["gatewayId"]
    print(f"🗑️  Deleting all targets for gateway: {gateway_id}")

    # 모든 대상 나열 및 삭제
    list_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id, maxResults=100)

    targets_deleted = False
    for item in list_response["items"]:
        target_id = item["targetId"]
        print(f"   Deleting target: {target_id}")
        gateway_client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
        print(f"   ✅ Target {target_id} deleted")
        targets_deleted = True

    # 대상 삭제가 반영될 때까지 대기
    if targets_deleted:
        print("⏳ Waiting for target deletions to propagate...")
        time.sleep(5)

    # Gateway 삭제
    print(f"🗑️  Deleting gateway: {gateway_id}")
    gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
    print(f"✅ Gateway {gateway_id} deleted successfully")


def runtime_resource_cleanup(runtime_arn: str = None):
    try:
        # AWS 클라이언트 초기화
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
        ecr_client = boto3.client("ecr", region_name=REGION)
        if runtime_arn:
            runtime_id = runtime_arn.split(":")[-1].split("/")[-1]
            response = agentcore_control_client.delete_agent_runtime(agentRuntimeId=runtime_id)
            print(f"  ✅ Agent runtime deleted: {response['status']}")
        else:
            # AgentCore Runtime 삭제
            # print("  🗑️  Deleting AgentCore Runtime...")
            runtimes = agentcore_control_client.list_agent_runtimes()
            for runtime in runtimes["agentRuntimes"]:
                response = agentcore_control_client.delete_agent_runtime(agentRuntimeId=runtime["agentRuntimeId"])
                print(f"  ✅ Agent runtime deleted: {response['status']}")

        # ECR 리포지토리 삭제
        print("  🗑️  Deleting ECR repository...")
        repositories = ecr_client.describe_repositories()
        for repo in repositories["repositories"]:
            if "bedrock-agentcore-customer_support_agent" in repo["repositoryName"]:
                ecr_client.delete_repository(repositoryName=repo["repositoryName"], force=True)
                print(f"  ✅ ECR repository deleted: {repo['repositoryName']}")

    except Exception as e:
        print(f"  ⚠️  Error during runtime cleanup: {e}")


def delete_observability_resources():
    # 설정
    log_group_name = "agents/customer-support-assistant-logs"
    log_stream_name = "default"

    logs_client = boto3.client("logs", region_name=REGION)

    # 로그 그룹보다 먼저 로그 스트림 삭제
    try:
        print(f"  🗑️  Deleting log stream '{log_stream_name}'...")
        logs_client.delete_log_stream(logGroupName=log_group_name, logStreamName=log_stream_name)
        print(f"  ✅ Log stream '{log_stream_name}' deleted successfully")
    except Exception as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"  ℹ️  Log stream '{log_stream_name}' doesn't exist")
        else:
            print(f"  ⚠️  Error deleting log stream: {e}")

    # 로그 그룹 삭제
    try:
        print(f"  🗑️  Deleting log group '{log_group_name}'...")
        logs_client.delete_log_group(logGroupName=log_group_name)
        print(f"  ✅ Log group '{log_group_name}' deleted successfully")
    except Exception as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"  ℹ️  Log group '{log_group_name}' doesn't exist")
        else:
            print(f"  ⚠️  Error deleting log group: {e}")


def local_file_cleanup():
    # 정리할 파일 목록
    files_to_delete = [
        "Dockerfile",
        ".dockerignore",
        ".bedrock_agentcore.yaml",
        "customer_support_agent.py",
        "agent_runtime.py",
    ]

    deleted_files = []
    missing_files = []

    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.unlink(file)
                deleted_files.append(file)
                print(f"  ✅ Deleted {file}")
            except Exception as e:
                print(f"  ⚠️  Error deleting {file}: {e}")
        else:
            missing_files.append(file)

    if deleted_files:
        print(f"\n📁 Successfully deleted {len(deleted_files)} files")
    if missing_files:
        print(f"ℹ️  {len(missing_files)} files were already missing: {', '.join(missing_files)}")


def policy_engine_cleanup(policy_engine_id: str = None):
    policy_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=REGION,
    )

    if not policy_engine_id:
        response = policy_client.list_policy_engines()
        policy_engine_id = response["policyEngines"][0]["policyEngineId"]

    print(f"🗑️  Deleting all policies for policy engine: {policy_engine_id}")

    # 모든 정책 나열 및 삭제
    list_response = policy_client.list_policies(policyEngineId=policy_engine_id, maxResults=100)

    policies_deleted = False
    for item in list_response["policies"]:
        policy_id = item["policyId"]
        print(f"   Deleting policy: {policy_id}")
        policy_client.delete_policy(policyEngineId=policy_engine_id, policyId=policy_id)
        print(f"   ✅ Policy {policy_id} deleted")
        policies_deleted = True

    # 엔진을 삭제하기 전에 정책 삭제가 반영될 때까지 대기
    if policies_deleted:
        print("⏳ Waiting for policy deletions to propagate...")
        time.sleep(5)  # 일반적으로 5초면 충분함

    # Policy Engine 삭제
    print(f"🗑️  Deleting policy engine: {policy_engine_id}")
    policy_client.delete_policy_engine(policyEngineId=policy_engine_id)
    print(f"✅ Policy engine {policy_engine_id} deleted successfully")
