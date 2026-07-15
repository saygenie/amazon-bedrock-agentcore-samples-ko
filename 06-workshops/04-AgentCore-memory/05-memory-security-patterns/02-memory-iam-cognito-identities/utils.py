import jwt
import boto3
import json
import time
from jwt import PyJWKClient


def setup_cognito_user_pool(region, memory_id):
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
        id_token1 = auth_response1["AuthenticationResult"]["IdToken"]

        # 사용자 2를 인증하고 Access Token 가져오기
        auth_response2 = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "testuser2", "PASSWORD": "MyPassword456!"},
        )
        bearer_token2 = auth_response2["AuthenticationResult"]["AccessToken"]
        id_token2 = auth_response2["AuthenticationResult"]["IdToken"]

        # User Pool과 연동된 Identity Pool 생성
        identity_pool_info = create_cognito_identity_pool(pool_id, client_id, region, memory_id)

        # 필요한 값 출력
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"Client ID: {client_id}")
        print(f"Identity Pool ID: {identity_pool_info['identity_pool_id']}")
        print(f"User 1 Bearer Token: {bearer_token1}")
        print(f"User 2 Bearer Token: {bearer_token2}")
        print(f"User 1 Id Token: {id_token1}")
        print(f"User 2 Id Token: {id_token2}")

        # 후속 처리에 사용할 값 반환
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "identity_pool_id": identity_pool_info["identity_pool_id"],
            "authenticated_role_arn": identity_pool_info["authenticated_role_arn"],
            "bearer_tokens": {"testuser1": bearer_token1, "testuser2": bearer_token2},
            "id_tokens": {"testuser1": id_token1, "testuser2": id_token2},
            "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
        }
    except Exception as e:
        print(f"Error: {e}")
        return None


def reauthenticate_users(client_id, region, users=None):
    """
    한 명 이상의 Cognito 사용자를 다시 인증하고 Access Token과 ID Token을 가져옵니다.

    매개변수:
    - client_id: Cognito App Client ID
    - region: AWS 리전
    - users: 인증할 사용자 이름과 암호 쌍의 딕셔너리입니다. None이면 testuser1과 testuser2를 기본값으로 사용합니다.

    반환값:
    - 각 사용자의 access_tokens와 id_tokens를 담은 딕셔너리
    """
    # 지정하지 않은 경우 기본 사용자 사용
    if users is None:
        users = {"testuser1": "MyPassword123!", "testuser2": "MyPassword456!"}

    # Cognito 클라이언트 초기화
    cognito_client = boto3.client("cognito-idp", region_name=region)

    # 각 사용자의 토큰 저장
    result = {"access_tokens": {}, "id_tokens": {}}

    # 각 사용자를 인증하고 토큰 가져오기
    for username, password in users.items():
        try:
            auth_response = cognito_client.initiate_auth(
                ClientId=client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
            result["access_tokens"][username] = auth_response["AuthenticationResult"]["AccessToken"]
            result["id_tokens"][username] = auth_response["AuthenticationResult"]["IdToken"]
            print(f"Successfully authenticated {username}")
        except Exception as e:
            print(f"Error authenticating {username}: {str(e)}")
            result["access_tokens"][username] = None
            result["id_tokens"][username] = None

    return result


def get_user_sub(access_token: str, region: str, user_pool_id: str) -> str:
    """
    JWKS를 사용하여 Cognito Access Token을 검증하고 사용자의 sub(고유 ID)를 반환합니다.

    :param access_token: JWT Access Token 문자열
    :param region: Cognito User Pool의 AWS 리전
    :param user_pool_id: Cognito User Pool ID
    :return: 토큰이 유효한 경우 사용자의 'sub' 클레임
    :raises jwt.InvalidTokenError: 검증에 실패한 경우
    """
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    jwks_client = PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(access_token)

    decoded = jwt.decode(
        access_token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}",
        options={"require": ["exp", "iat", "iss", "token_use"]},
    )

    if decoded.get("token_use") != "access":
        raise jwt.InvalidTokenError("Token is not an access token")

    return decoded["sub"]


def create_agentcore_role(agent_name, region):
    iam_client = boto3.client("iam")
    agentcore_role_name = f"agentcore-{agent_name}-role"
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowAgentToAssumeRole",
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": f"arn:aws:iam::{account_id}:role/cognito_authenticated_*",
            },
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
            {
                "Sid": "CognitoIdentityPoolAccess",
                "Effect": "Allow",
                "Action": [
                    "cognito-identity:GetId",
                    "cognito-identity:GetCredentialsForIdentity",
                ],
                "Resource": "*",
            },
            {
                "Sid": "CognitoUserPoolAccess",
                "Effect": "Allow",
                "Action": ["cognito-idp:GetUser"],
                "Resource": [f"arn:aws:cognito-idp:{region}:{account_id}:userpool/*"],
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
    # AgentCore Runtime용 IAM Role 생성
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

    # AgentCore 정책 연결
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


def create_cognito_identity_pool(user_pool_id, client_id, region, memory_id="*"):
    """
    User Pool과 연동된 Cognito Identity Pool을 생성합니다.

    인수:
        user_pool_id: Cognito User Pool ID
        client_id: Cognito User Pool Client ID
        region: AWS 리전
        memory_id: 선택 사항 - 액세스를 제한할 특정 Memory ID(기본값 "*"는 모든 Memory)
    """
    identity_client = boto3.client("cognito-identity", region_name=region)

    # AWS 계정 ID 가져오기
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    # User Pool을 인증 공급자로 사용하는 Identity Pool 생성
    response = identity_client.create_identity_pool(
        IdentityPoolName="MemoryAgentIdentityPool",
        AllowUnauthenticatedIdentities=False,
        CognitoIdentityProviders=[
            {
                "ProviderName": f"cognito-idp.{region}.amazonaws.com/{user_pool_id}",
                "ClientId": client_id,
                "ServerSideTokenCheck": True,
            }
        ],
    )

    identity_pool_id = response["IdentityPoolId"]

    # Identity Pool ID의 마지막 부분만 사용하여 짧고 고유한 Role 이름 생성
    # 64자 제한을 넘지 않도록 함
    short_id = identity_pool_id.split(":")[-1][-12:].replace("-", "")  # 하이픈을 제외한 마지막 12자
    authenticated_role_name = f"cognito_auth_{short_id}"

    # 인증된 사용자용 Role 생성
    iam_client = boto3.client("iam")

    authenticated_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:ListActors",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:ListMemoryRecords",
                    "bedrock-agentcore:ListSessions",
                    "bedrock-agentcore:DeleteEvent",
                    "bedrock-agentcore:DeleteMemoryRecord",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:memory/{memory_id}"],
                "Condition": {"StringEquals": {"bedrock-agentcore:actorId": "${cognito-identity.amazonaws.com:sub}"}},
            },
            {
                "Effect": "Allow",
                "Action": ["mobileanalytics:PutEvents", "cognito-sync:*"],
                "Resource": "*",
            },
        ],
    }

    trust_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": "cognito-identity.amazonaws.com"},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {"cognito-identity.amazonaws.com:aud": identity_pool_id},
                    "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "authenticated"},
                },
            }
        ],
    }

    # 인증된 사용자용 Role 생성
    try:
        auth_role = iam_client.create_role(
            RoleName=authenticated_role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy_document),
            Description=f"Role for Identity Pool {identity_pool_id}",
        )

        # 정책 이름도 짧게 생성
        auth_policy_name = f"AuthPolicy_{short_id}"
        auth_policy = iam_client.create_policy(
            PolicyName=auth_policy_name,
            PolicyDocument=json.dumps(authenticated_policy_document),
        )

        iam_client.attach_role_policy(RoleName=authenticated_role_name, PolicyArn=auth_policy["Policy"]["Arn"])
    except iam_client.exceptions.EntityAlreadyExistsException:
        # Role이 이미 있으면 해당 ARN 가져오기
        response = iam_client.get_role(RoleName=authenticated_role_name)
        auth_role = response

    # Identity Pool Role 설정
    identity_client.set_identity_pool_roles(
        IdentityPoolId=identity_pool_id,
        Roles={"authenticated": auth_role["Role"]["Arn"]},
    )

    return {
        "identity_pool_id": identity_pool_id,
        "authenticated_role_arn": auth_role["Role"]["Arn"],
    }


def get_aws_credentials_for_identity(identity_pool_id, id_token, region, user_pool_id):
    """
    User Pool ID Token을 사용하여 Cognito Identity의 임시 AWS 자격 증명을 가져옵니다.

    인수:
        identity_pool_id: Cognito Identity Pool ID
        id_token: Cognito User Pool 인증에서 발급된 ID Token
        region: AWS 리전
        user_pool_id: Cognito User Pool ID

    반환값:
        AWS 자격 증명을 담은 딕셔너리
    """
    identity_client = boto3.client("cognito-identity", region_name=region)

    # Identity Pool에서 ID 가져오기
    get_id_response = identity_client.get_id(
        IdentityPoolId=identity_pool_id,
        Logins={f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": id_token},
    )
    identity_id = get_id_response["IdentityId"]

    # Identity의 자격 증명 가져오기
    get_credentials_response = identity_client.get_credentials_for_identity(
        IdentityId=identity_id,
        Logins={f"cognito-idp.{region}.amazonaws.com/{user_pool_id}": id_token},
    )

    # 임시 자격 증명 반환
    credentials = get_credentials_response["Credentials"]
    return {
        "access_key_id": credentials["AccessKeyId"],
        "secret_key": credentials["SecretKey"],
        "session_token": credentials["SessionToken"],
        "expiration": credentials["Expiration"],
        "identity_id": identity_id,
    }
