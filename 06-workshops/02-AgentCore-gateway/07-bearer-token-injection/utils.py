"""
Asana Integration Demo의 AgentCore 설정 및 관리를 위한 유틸리티 함수입니다.

이 모듈은 다음 작업을 위한 헬퍼 함수를 제공합니다.
- AWS SSM 파라미터 관리
- Cognito user pool 설정 및 인증
- AgentCore용 IAM role 및 정책 생성
- DynamoDB 작업
- AWS Secrets Manager 작업
- 리소스 정리 함수
"""

import json
import os

import boto3
import requests
import time

STS_CLIENT = boto3.client("sts")

# AWS 계정 세부 정보 가져오기
REGION = boto3.session.Session().region_name

# 구성 상수 - 프로덕션에서는 환경 변수 사용
USERNAME = os.environ.get("DEMO_USERNAME", "testuser")
SECRET_NAME = os.environ.get("DEMO_SECRET_NAME", "asana_integration_demo_agent")

ROLE_NAME = os.environ.get("ROLE_NAME", "AgentCoreGwyAsanaIntegrationRole")
POLICY_NAME = os.environ.get("POLICY_NAME", "AgentCoreGwyAsanaIntegrationPolicy")


def load_api_spec(file_path: str) -> list:
    """JSON 파일에서 API specification을 로드합니다.

    인자:
        file_path: API specification이 포함된 JSON 파일 경로

    반환:
        API specification 데이터가 포함된 목록

    예외:
        ValueError: JSON 파일에 목록이 없거나 유효하지 않은 경우
        FileNotFoundError: 파일이 없는 경우
        json.JSONDecodeError: 파일에 유효하지 않은 JSON이 포함된 경우
    """
    # 파일 경로 검증
    if not file_path or not isinstance(file_path, str):
        raise ValueError("file_path must be a non-empty string")

    # 파일이 있고 읽을 수 있는지 확인
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"API specification file not found: {file_path}")

    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Cannot read API specification file: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in API specification file: {e}", e.doc, e.pos)

    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")

    # API spec 구조의 기본 검증
    if not data:
        raise ValueError("API specification list cannot be empty")

    return data


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """AWS Systems Manager Parameter Store에서 파라미터 값을 가져옵니다.

    인자:
        name: 가져올 파라미터 이름
        with_decryption: secure string 파라미터 복호화 여부

    반환:
        문자열 형태의 파라미터 값
    """
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]


def put_ssm_parameter(name: str, value: str, parameter_type: str = "String", with_encryption: bool = False) -> None:
    """AWS Systems Manager Parameter Store에 파라미터 값을 저장합니다.

    인자:
        name: 저장할 파라미터 이름
        value: 저장할 파라미터 값
        parameter_type: 파라미터 유형(String, StringList, SecureString)
        with_encryption: 파라미터를 SecureString으로 암호화할지 여부
    """
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


def get_cognito_client_secret() -> str:
    """Cognito user pool client secret을 가져옵니다.

    반환:
        Cognito user pool client의 client secret 문자열
    """
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/asana/demo/agentcoregwy/userpool_id"),
        ClientId=get_ssm_parameter("/app/asana/demo/agentcoregwy/machine_client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def fetch_access_token(client_id, client_secret, token_url):
    """client credentials flow를 사용하여 OAuth access token을 가져옵니다.

    인자:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint URL

    반환:
        Access token 문자열

    예외:
        ValueError: 필수 파라미터가 누락되거나 유효하지 않은 경우
        requests.RequestException: HTTP 요청이 실패한 경우
        KeyError: 응답에 access token이 없는 경우
    """
    # 입력 검증
    if not all([client_id, client_secret, token_url]):
        raise ValueError("client_id, client_secret, and token_url are required")

    if not token_url.startswith(("https://", "http://")):
        raise ValueError("token_url must be a valid HTTP/HTTPS URL")

    data = f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}"

    try:
        response = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
            verify=True,  # SSL 검증 활성화 보장
        )
        response.raise_for_status()  # 잘못된 상태 코드에 대해 예외 발생

        response_data = response.json()

        if "access_token" not in response_data:
            raise KeyError("Response does not contain 'access_token' field")

        return response_data["access_token"]

    except requests.exceptions.Timeout:
        raise requests.RequestException("Request timed out while fetching access token")
    except requests.exceptions.ConnectionError:
        raise requests.RequestException("Connection error while fetching access token")
    except requests.exceptions.HTTPError as e:
        raise requests.RequestException(f"HTTP error while fetching access token: {e}")
    except json.JSONDecodeError:
        raise requests.RequestException("Invalid JSON response from token endpoint")


def delete_gateway(gateway_client, gateway_name):
    """AgentCore gateway와 모든 target을 삭제합니다.

    인자:
        gateway_client: bedrock-agentcore-control용 Boto3 클라이언트
        gateway_id: 삭제할 gateway ID
    """
    gateway_id = get_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id")

    print("Deleting all targets for gateway", gateway_id)
    list_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id, maxResults=100)
    for item in list_response["items"]:
        target_id = item["targetId"]
        print("Deleting target ", target_id)
        gateway_client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
    # 30초 동안 대기
    time.sleep(30)

    list_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id, maxResults=100)
    if len(list_response["items"]) > 0:
        print(f"{len(list_response['items'])} targets not deleted successfully)")
    else:
        print("All targets deleted successfully)")

    print("Deleting gateway ", gateway_id)
    gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
