import json
import time
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

LAMBDA_EXECUTION_ROLE_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
LAMBDA_RUNTIME = "python3.12"
LAMBDA_HANDLER = "lambda_function_code.lambda_handler"
LAMBDA_PACKAGE_TYPE = "Zip"

IAM_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# AgentCore Gateway IAM 역할 상수
GATEWAY_AGENTCORE_ROLE_NAME = "GatewaySearchAgentCoreRole"
GATEWAY_AGENTCORE_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

GATEWAY_AGENTCORE_POLICY_NAME = "BedrockAgentPolicy"

# Cognito 구성 상수
COGNITO_POOL_NAME = "MCPServerPool"
COGNITO_CLIENT_NAME = "MCPServerPoolClient"
COGNITO_PASSWORD_MIN_LENGTH = 8
COGNITO_DEFAULT_USERNAME = "testuser"
COGNITO_DEFAULT_TEMP_PASSWORD = "Temp123!"  # pragma: allowlist secret
COGNITO_DEFAULT_PASSWORD = "MyPassword123!"  # pragma: allowlist secret

COGNITO_AUTH_FLOWS = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]

COGNITO_PASSWORD_POLICY = {"PasswordPolicy": {"MinimumLength": COGNITO_PASSWORD_MIN_LENGTH}}


def _format_error_message(error: ClientError) -> str:
    """ClientError의 오류 메시지를 구성합니다."""
    return f"{error.response['Error']['Code']}-{error.response['Error']['Message']}"


def _create_or_get_iam_role(iam_client, role_name: str) -> str:
    """IAM 역할을 생성하거나 기존 역할 ARN을 반환합니다."""
    try:
        print("Creating IAM role for lambda function")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(IAM_TRUST_POLICY),
            Description="IAM role to be assumed by lambda function",
        )
        role_arn = response["Role"]["Arn"]

        print("Attaching policy to the IAM role")
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
        )

        print(f"Role '{role_name}' created successfully: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            print(f"IAM role {role_name} already exists. Using the same ARN {role_arn}")
            return role_arn
        else:
            raise error


def _create_or_get_lambda_function(lambda_client, function_name: str, role_arn: str, code: bytes) -> str:
    """Lambda 함수를 생성하거나 기존 함수 ARN을 반환합니다."""
    try:
        print("Creating lambda function")
        response = lambda_client.create_function(
            FunctionName=function_name,
            Role=role_arn,
            Runtime=LAMBDA_RUNTIME,
            Handler=LAMBDA_HANDLER,
            Code={"ZipFile": code},
            Description="Lambda function example for Bedrock AgentCore Gateway",
            PackageType=LAMBDA_PACKAGE_TYPE,
        )
        return response["FunctionArn"]

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceConflictException":
            response = lambda_client.get_function(FunctionName=function_name)
            lambda_arn = response["Configuration"]["FunctionArn"]
            print(f"AWS Lambda function {function_name} already exists. Using the same ARN {lambda_arn}")
            return lambda_arn
        else:
            raise error


def create_gateway_lambda(lambda_function_code_path: str, lambda_function_name: str) -> Dict[str, Union[str, int]]:
    """AgentCore Gateway용 IAM 역할이 있는 AWS Lambda 함수를 생성합니다.

    인수:
        lambda_function_code_path: Lambda 함수 코드 zip 파일 경로
        lambda_function_name: Lambda 함수 이름

    반환값:
        'lambda_function_arn' 및 'exit_code' 키가 있는 딕셔너리
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    role_name = f"{lambda_function_name}_lambda_iamrole"

    print("Reading code from zip file")
    with open(lambda_function_code_path, "rb") as f:
        lambda_function_code = f.read()

    try:
        role_arn = _create_or_get_iam_role(iam_client, role_name)
        time.sleep(20)
        try:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )
        except ClientError:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )

        return {"lambda_function_arn": lambda_arn, "exit_code": 0}

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Error: {error_message}")
        return {"lambda_function_arn": error_message, "exit_code": 1}
    except Exception as error:
        print(f"Unexpected error: {str(error)}")
        return {"lambda_function_arn": str(error), "exit_code": 1}


def _create_cognito_user_pool(cognito_client, pool_name: str) -> str:
    """Cognito User Pool을 생성하고 풀 ID를 반환합니다."""
    print(f"Creating Cognito User Pool: {pool_name}")
    response = cognito_client.create_user_pool(PoolName=pool_name, Policies=COGNITO_PASSWORD_POLICY)
    pool_id = response["UserPool"]["Id"]
    print(f"User Pool created with ID: {pool_id}")
    return pool_id


def _create_cognito_app_client(cognito_client, pool_id: str, client_name: str) -> str:
    """Cognito App Client를 생성하고 클라이언트 ID를 반환합니다."""
    print(f"Creating Cognito App Client: {client_name}")
    response = cognito_client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=False,
        ExplicitAuthFlows=COGNITO_AUTH_FLOWS,
    )
    client_id = response["UserPoolClient"]["ClientId"]
    print(f"App Client created with ID: {client_id}")
    return client_id


def _create_cognito_user(
    cognito_client,
    pool_id: str,
    username: str,
    temp_password: str,
    permanent_password: str,
) -> None:
    """임시 암호로 Cognito 사용자를 생성하고 영구 암호를 설정합니다."""
    print(f"Creating Cognito user: {username}")
    cognito_client.admin_create_user(
        UserPoolId=pool_id,
        Username=username,
        TemporaryPassword=temp_password,
        MessageAction="SUPPRESS",
    )

    print(f"Setting permanent password for user: {username}")
    cognito_client.admin_set_user_password(
        UserPoolId=pool_id,
        Username=username,
        Password=permanent_password,
        Permanent=True,
    )


def _authenticate_user(cognito_client, client_id: str, username: str, password: str) -> str:
    """사용자를 인증하고 액세스 토큰을 반환합니다."""
    print(f"Authenticating user: {username}")
    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return auth_response["AuthenticationResult"]["AccessToken"]


def get_bearer_token(client_id: str, username: str, password: str, region: Optional[str] = None) -> Optional[str]:
    """기존 Cognito User Pool에서 bearer token을 가져옵니다.

    인수:
        client_id: Cognito App Client ID
        username: 인증할 사용자 이름
        password: 사용자 암호
        region: AWS 리전(None이면 세션 기본값 사용)

    반환값:
        bearer token 문자열. 인증에 실패하면 None
    """
    if not region:
        session = boto3.Session()
        region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        print(f"Authenticating user: {username}")
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        print("Bearer token obtained successfully")
        return bearer_token

    except ClientError as error:
        if error.response["Error"]["Code"] == "NotAuthorizedException":
            print(f"Authentication failed: Invalid credentials for user {username}")
        elif error.response["Error"]["Code"] == "UserNotFoundException":
            print(f"Authentication failed: User {username} not found")
        elif error.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Authentication failed: Client ID {client_id} not found")
        else:
            error_message = _format_error_message(error)
            print(f"Cognito Client Error: {error_message}")
        return None
    except Exception as error:
        print(f"Unexpected error getting bearer token: {str(error)}")
        return None


def create_gateway_iam_role(
    lambda_arns: List[str],
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> Optional[str]:
    """Lambda 호출 권한이 있는 AgentCore Gateway용 IAM 역할을 생성합니다.

    인수:
        lambda_arns: 호출 권한을 부여할 Lambda 함수 ARN 목록
        role_name: IAM 역할 이름
        policy_name: 인라인 정책 이름

    반환값:
        역할 ARN 문자열. 생성에 실패하면 None
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # IAM 역할 생성
        print(f"Creating IAM role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(GATEWAY_AGENTCORE_TRUST_POLICY),
            Description="IAM role for AgentCore Gateway to invoke Lambda functions",
        )
        role_arn = response["Role"]["Arn"]

        # 인라인 정책 문서 생성
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeFunction",
                    "Effect": "Allow",
                    "Action": "lambda:InvokeFunction",
                    "Resource": lambda_arns,
                }
            ],
        }

        # 인라인 정책 연결
        print(f"Attaching policy: {policy_name}")
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

        print(f"Gateway IAM role created successfully: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"IAM role {role_name} already exists. Retrieving existing role...")
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]

            # 역할이 있으면 정책 업데이트
            try:
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "InvokeFunction",
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": lambda_arns,
                        }
                    ],
                }

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document),
                )
                print(f"Updated policy for existing role: {role_arn}")

            except ClientError as policy_error:
                print(f"Warning: Could not update policy: {_format_error_message(policy_error)}")

            return role_arn
        else:
            error_message = _format_error_message(error)
            print(f"Error creating IAM role: {error_message}")
            return None
    except Exception as error:
        print(f"Unexpected error creating IAM role: {str(error)}")
        return None


def _extract_function_name_from_arn(lambda_arn: str) -> str:
    """Lambda ARN에서 함수 이름을 추출합니다.

    인수:
        lambda_arn: Lambda 함수 ARN

    반환값:
        ARN에서 추출한 함수 이름

    예:
        arn:aws:lambda:us-east-1:123456789012:function:my-function -> my-function
    """
    # ARN 형식: arn:aws:lambda:region:account:function:function-name
    if lambda_arn.startswith("arn:aws:lambda:"):
        return lambda_arn.split(":")[-1]
    else:
    # 이미 함수 이름이면 그대로 반환
        return lambda_arn


def delete_gateway_lambda(lambda_function_arn: str) -> bool:
    """Lambda 함수와 연결된 IAM 역할을 삭제합니다.

    인수:
        lambda_function_arn: 삭제할 Lambda 함수의 ARN 또는 이름

    반환값:
        삭제에 성공하면 True, 그렇지 않으면 False
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

        # ARN에서 함수 이름 추출
    lambda_function_name = _extract_function_name_from_arn(lambda_function_arn)
    role_name = f"{lambda_function_name}_lambda_iamrole"

    try:
        # Lambda 함수 삭제(ARN 또는 이름 사용 가능)
        print(f"Deleting Lambda function: {lambda_function_name}")
        lambda_client.delete_function(FunctionName=lambda_function_arn)
        print(f"Lambda function {lambda_function_name} deleted successfully")

        # IAM 역할 삭제 및 정책 분리
        try:
            print(f"Detaching policies from IAM role: {role_name}")
            iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
            )

            print(f"Deleting IAM role: {role_name}")
            iam_client.delete_role(RoleName=role_name)
            print(f"IAM role {role_name} deleted successfully")

        except ClientError as role_error:
            if role_error.response["Error"]["Code"] == "NoSuchEntity":
                print(f"IAM role {role_name} not found, skipping")
            else:
                print(f"Warning: Could not delete IAM role: {_format_error_message(role_error)}")

        return True

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Lambda function {lambda_function_name} not found")
            return False
        else:
            error_message = _format_error_message(error)
            print(f"Error deleting Lambda function: {error_message}")
            return False
    except Exception as error:
        print(f"Unexpected error deleting Lambda function: {str(error)}")
        return False


def delete_gateway_iam_role(
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> bool:
    """AgentCore Gateway용 IAM 역할을 삭제합니다.

    인수:
        role_name: 삭제할 IAM 역할 이름
        policy_name: 삭제할 인라인 정책 이름

    반환값:
        삭제에 성공하면 True, 그렇지 않으면 False
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # 인라인 정책을 먼저 삭제
        print(f"Deleting inline policy: {policy_name}")
        iam_client.delete_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
        )
        print(f"Inline policy {policy_name} deleted successfully")

        # IAM 역할 삭제
        print(f"Deleting IAM role: {role_name}")
        iam_client.delete_role(RoleName=role_name)
        print(f"IAM role {role_name} deleted successfully")

        return True

    except ClientError as error:
        if error.response["Error"]["Code"] == "NoSuchEntity":
            print(f"IAM role {role_name} or policy {policy_name} not found")
            return False
        else:
            error_message = _format_error_message(error)
            print(f"Error deleting IAM role: {error_message}")
            return False
    except Exception as error:
        print(f"Unexpected error deleting IAM role: {str(error)}")
        return False


def delete_cognito_user_pool(
    pool_name: str = COGNITO_POOL_NAME,
    username: str = COGNITO_DEFAULT_USERNAME,
) -> bool:
    """Cognito User Pool과 연결된 리소스를 삭제합니다.

    인수:
        pool_name: 삭제할 Cognito User Pool 이름
        username: 풀에서 삭제할 사용자 이름

    반환값:
        삭제에 성공하면 True, 그렇지 않으면 False
    """
    session = boto3.Session()
    region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        # 이름으로 User Pool 찾기
        print(f"Finding User Pool: {pool_name}")
        response = cognito_client.list_user_pools(MaxResults=50)

        pool_id = None
        for pool in response["UserPools"]:
            if pool["Name"] == pool_name:
                pool_id = pool["Id"]
                break

        if not pool_id:
            print(f"User Pool {pool_name} not found")
            return False

        # 사용자를 먼저 삭제
        try:
            print(f"Deleting user: {username}")
            cognito_client.admin_delete_user(
                UserPoolId=pool_id,
                Username=username,
            )
            print(f"User {username} deleted successfully")
        except ClientError as user_error:
            if user_error.response["Error"]["Code"] == "UserNotFoundException":
                print(f"User {username} not found, skipping")
            else:
                print(f"Warning: Could not delete user: {_format_error_message(user_error)}")

        # User Pool 삭제(App Client도 함께 삭제됨)
        print(f"Deleting User Pool: {pool_name}")
        cognito_client.delete_user_pool(UserPoolId=pool_id)
        print(f"User Pool {pool_name} deleted successfully")

        return True

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Error deleting Cognito User Pool: {error_message}")
        return False
    except Exception as error:
        print(f"Unexpected error deleting Cognito User Pool: {str(error)}")
        return False


def setup_cognito_user_pool(
    pool_name: str = COGNITO_POOL_NAME,
    client_name: str = COGNITO_CLIENT_NAME,
    username: str = COGNITO_DEFAULT_USERNAME,
    temp_password: str = COGNITO_DEFAULT_TEMP_PASSWORD,
    permanent_password: str = COGNITO_DEFAULT_PASSWORD,
) -> Optional[Dict[str, str]]:
    """App Client와 테스트 사용자가 있는 Cognito User Pool을 설정합니다.

    인수:
        pool_name: Cognito User Pool 이름
        client_name: App Client 이름
        username: 테스트 사용자 이름
        temp_password: 테스트 사용자의 임시 암호
        permanent_password: 테스트 사용자의 영구 암호

    반환값:
        client_id 및 discovery_url이 있는 딕셔너리. 설정에 실패하면 None
    """
    session = boto3.Session()
    region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        pool_id = _create_cognito_user_pool(cognito_client, pool_name)
        client_id = _create_cognito_app_client(cognito_client, pool_id, client_name)

        _create_cognito_user(cognito_client, pool_id, username, temp_password, permanent_password)

        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"

        # 필요한 값 출력
        print(f"Pool ID: {pool_id}")
        print(f"Discovery URL: {discovery_url}")
        print(f"Client ID: {client_id}")

        return {
            "client_id": client_id,
            "discovery_url": discovery_url,
        }

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Cognito Client Error: {error_message}")
        return None
    except Exception as error:
        print(f"Unexpected error setting up Cognito: {str(error)}")
        return None
