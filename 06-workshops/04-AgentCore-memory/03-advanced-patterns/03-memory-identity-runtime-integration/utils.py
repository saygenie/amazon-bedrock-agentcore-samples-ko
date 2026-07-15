import boto3
import json
import time
from boto3.session import Session


def setup_cognito_user_pool(region):
    # Cognito 클라이언트 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)
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
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = app_client_response["UserPoolClient"]["ClientId"]

        # 사용자 1 생성
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username="testuser1",
            TemporaryPassword="Temp123!",  # pragma: allowlist secret
            MessageAction="SUPPRESS",
        )
        # 사용자 1의 영구 암호 설정
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username="testuser1",
            Password="MyPassword123!",  # pragma: allowlist secret
            Permanent=True,
        )

        # 사용자 2 생성
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username="testuser2",
            TemporaryPassword="Temp123!",  # pragma: allowlist secret
            MessageAction="SUPPRESS",
        )
        # 사용자 2의 영구 암호 설정
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username="testuser2",
            Password="MyPassword456!",  # pragma: allowlist secret
            Permanent=True,
        )

        # 사용자 1을 인증하고 Access Token 가져오기
        auth_response1 = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "testuser1", "PASSWORD": "MyPassword123!"},  # pragma: allowlist secret
        )
        bearer_token1 = auth_response1["AuthenticationResult"]["AccessToken"]

        # 사용자 2를 인증하고 Access Token 가져오기
        auth_response2 = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "testuser2", "PASSWORD": "MyPassword456!"},
        )
        bearer_token2 = auth_response2["AuthenticationResult"]["AccessToken"]

        # 필요한 값 출력
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"Client ID: {client_id}")
        print(f"User 1 Bearer Token: {bearer_token1}")
        print(f"User 2 Bearer Token: {bearer_token2}")

        # 후속 처리에 필요할 수 있는 값 반환
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "bearer_tokens": {"testuser1": bearer_token1, "testuser2": bearer_token2},
            "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
        }
    except Exception as e:
        print(f"Error: {e}")
        return None


def reauthenticate_users(client_id, region, users=None):
    """
    한 명 이상의 Cognito 사용자를 다시 인증하고 Access Token을 가져옵니다.

    매개변수:
    - client_id: Cognito App Client ID
    - region: AWS 리전
    - users: 인증할 사용자 이름과 암호 쌍의 딕셔너리입니다. None이면 testuser1과 testuser2를 기본값으로 사용합니다.

    반환값:
    - 사용자 이름을 해당 Access Token에 매핑한 딕셔너리
    """
    # 지정하지 않은 경우 기본 사용자 사용
    if users is None:
        users = {"testuser1": "MyPassword123!", "testuser2": "MyPassword456!"}

    # Cognito 클라이언트 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)

    # 각 사용자의 토큰 저장
    tokens = {}

    # 각 사용자를 인증하고 Access Token 가져오기
    for username, password in users.items():
        try:
            auth_response = cognito_client.initiate_auth(
                ClientId=client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
            tokens[username] = auth_response["AuthenticationResult"]["AccessToken"]
            print(f"Successfully authenticated {username}")
        except Exception as e:
            print(f"Error authenticating {username}: {str(e)}")
            tokens[username] = None

    return tokens


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
                "Resource": "*",
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
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
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*",
                ],
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
    # Lambda 함수용 IAM Role 생성
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

        # Role이 생성될 때까지 잠시 대기
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
