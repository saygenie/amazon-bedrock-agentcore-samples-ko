"""
AgentCore Gateway 생성 모듈입니다.

이 모듈은 target 구성 및 자격 증명 관리를 포함하여 Asana 통합용
AWS Bedrock AgentCore gateway의 생성과 구성을 처리합니다.
"""

import json
import os
import sys

import boto3

# utils를 import하도록 상위 디렉터리를 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, "..", "..")
sys.path.insert(0, parent_dir)

try:
    from utils import get_ssm_parameter, put_ssm_parameter
except ImportError as e:
    print(f"Error importing utils: {e}")
    print(f"Current directory: {current_dir}")
    print(f"Parent directory: {parent_dir}")
    print(f"Python path: {sys.path}")
    raise

STS_CLIENT = boto3.client("sts")

# AWS 계정 세부 정보 가져오기
REGION = boto3.session.Session().region_name

GATEWAY_CLIENT = boto3.client(
    "bedrock-agentcore-control",
    region_name=REGION,
)

print("✅ Fetching AgentCore gateway!")

GATEWAY_NAME = "agentcore-gw-asana-integration"


def create_agentcore_gateway():
    """AgentCore gateway를 생성하거나 기존 gateway를 가져옵니다.

    반환:
        gateway 정보(id, name, url, arn)가 포함된 dictionary

    예외:
        ValueError: 필수 SSM 파라미터가 누락된 경우
        Exception: gateway 생성 또는 조회에 실패한 경우
    """
    try:
        # 필수 SSM 파라미터가 있는지 검증
        machine_client_id = get_ssm_parameter("/app/asana/demo/agentcoregwy/machine_client_id")
        cognito_discovery_url = get_ssm_parameter("/app/asana/demo/agentcoregwy/cognito_discovery_url")
        gateway_iam_role = get_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_iam_role")

        if not all([machine_client_id, cognito_discovery_url, gateway_iam_role]):
            raise ValueError("Required SSM parameters are missing or empty")

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [machine_client_id],
                "discoveryUrl": cognito_discovery_url,
            }
        }

        # 새 gateway 생성
        print(f"Creating gateway in region {REGION} with name: {GATEWAY_NAME}")

        create_response = GATEWAY_CLIENT.create_gateway(
            name=GATEWAY_NAME,
            roleArn=gateway_iam_role,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            description="Asana Integration Demo AgentCore Gateway",
        )

        gateway_id = create_response["gatewayId"]

        gateway_info = {
            "id": gateway_id,
            "name": GATEWAY_NAME,
            "gateway_url": create_response["gatewayUrl"],
            "gateway_arn": create_response["gatewayArn"],
        }
        put_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id", gateway_id)

        print(f"✅ Gateway created successfully with ID: {gateway_id}")

        return gateway_info

    except (
        GATEWAY_CLIENT.exceptions.ConflictException,
        GATEWAY_CLIENT.exceptions.ValidationException,
    ) as exc:
        # gateway가 있으면 SSM에서 기존 gateway ID 수집
        print(f"Gateway creation failed: {exc}")
        try:
            existing_gateway_id = get_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id")
            if not existing_gateway_id:
                raise ValueError("Gateway ID parameter exists but is empty") from exc

            print(f"Found existing gateway with ID: {existing_gateway_id}")

            # 기존 gateway 세부 정보 가져오기
            gateway_response = GATEWAY_CLIENT.get_gateway(gatewayIdentifier=existing_gateway_id)
            gateway_info = {
                "id": existing_gateway_id,
                "name": gateway_response["name"],
                "gateway_url": gateway_response["gatewayUrl"],
                "gateway_arn": gateway_response["gatewayArn"],
            }
            return gateway_info
        except ValueError as ve:
            raise ve
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve existing gateway: {str(e)}") from e
    except ValueError as ve:
        raise ve
    except Exception as e:
        raise RuntimeError(f"Unexpected error in gateway creation: {str(e)}") from e


def load_api_spec(file_path: str) -> list:
    """JSON 파일에서 API specification을 로드합니다.

    인자:
        file_path: API specification이 포함된 JSON 파일 경로

    반환:
        API specification 데이터가 포함된 목록

    예외:
        ValueError: JSON 파일에 목록이 없는 경우
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def add_gateway_target(gateway_id):
    """API specification 및 자격 증명 구성으로 gateway target을 추가합니다.

    인자:
        gateway_id: target을 추가할 gateway ID
    """
    try:
        api_spec_file = "../openapi-spec/openapi_simple.json"

        # API spec 파일이 있는지 검증
        if not os.path.exists(api_spec_file):
            print(f"❌ API specification file not found: {api_spec_file}")
            sys.exit(1)

        api_spec = load_api_spec(api_spec_file)
        print(f"✅ Loaded API specification file: {api_spec}")

        # API spec 구조 검증
        if not api_spec or not isinstance(api_spec[0], dict):
            raise ValueError("Invalid API specification structure")

        if "servers" not in api_spec[0] or not api_spec[0]["servers"]:
            raise ValueError("API specification missing servers configuration")

        api_gateway_url = get_ssm_parameter("/app/asana/demo/agentcoregwy/apigateway_url")

        # API Gateway URL 검증
        if not api_gateway_url or not api_gateway_url.startswith("https://"):
            raise ValueError("Invalid API Gateway URL - must be HTTPS")

        api_spec[0]["servers"][0]["url"] = api_gateway_url

        print(f"✅ Replaced API Gateway URL: {api_gateway_url}")

        print("✅ Creating credential provider...")
        acps = boto3.client(service_name="bedrock-agentcore-control")

        credential_provider_name = "AgentCoreAPIGatewayAPIKey"

        existing_credential_provider_response = acps.get_api_key_credential_provider(name=credential_provider_name)
        provider_arn = existing_credential_provider_response["credentialProviderArn"]
        print(f"Found existing credential provider with ARN: {provider_arn}")

        if provider_arn is None:
            print(f"❌ Credential provider not found, creating new: {credential_provider_name}")
            response = acps.create_api_key_credential_provider(
                name=credential_provider_name,
                apiKey=get_ssm_parameter("/app/asana/demo/agentcoregwy/api_key"),
            )

            print(response)
            credential_provider_arn = response["credentialProviderArn"]
            print(f"Outbound Credentials provider ARN, {credential_provider_arn}")
        else:
            credential_provider_arn = provider_arn

        # API Key 자격 증명 provider 구성
        api_key_credential_config = [
            {
                "credentialProviderType": "API_KEY",
                "credentialProvider": {
                    "apiKeyCredentialProvider": {
                        # API Gateway authorizer가 예상하는 API key 이름
                        "credentialParameterName": "x-api-key",
                        "providerArn": credential_provider_arn,
                        # API key 위치 - API Gateway 예상값과 일치해야 함
                        "credentialLocation": "HEADER",
                        # "credentialPrefix": " "  # 토큰 접두사(예: "Basic")
                    }
                },
            }
        ]

        inline_spec = json.dumps(api_spec[0])
        print(f"✅ Created inline_spec: {inline_spec}")
        # OpenAPI spec 파일의 S3 URI
        agentcoregwy_openapi_target_config = {"mcp": {"openApiSchema": {"inlinePayload": inline_spec}}}
        print("✅ Creating gateway target...")
        create_target_response = GATEWAY_CLIENT.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name="AgentCoreGwyAPIGatewayTarget",
            description="APIGateway Target for Asana and other 3P APIs",
            targetConfiguration=agentcoregwy_openapi_target_config,
            credentialProviderConfigurations=api_key_credential_config,
        )

        print(f"✅ Gateway target created: {create_target_response['targetId']}")

    except GATEWAY_CLIENT.exceptions.ConflictException as exc:
        print(f"❌ Gateway target already exists: {str(exc)}")
        # 필요한 경우 기존 target을 업데이트하는 로직을 구현할 수 있음
    except GATEWAY_CLIENT.exceptions.ValidationException as exc:
        print(f"❌ Validation error creating gateway target: {str(exc)}")
        raise
    except FileNotFoundError as exc:
        print(f"❌ API specification file not found: {str(exc)}")
        raise
    except ValueError as exc:
        print(f"❌ Invalid configuration: {str(exc)}")
        raise
    except Exception as exc:
        print(f"❌ Unexpected error creating gateway target: {str(exc)}")
        raise


if __name__ == "__main__":
    gateway = create_agentcore_gateway()
    add_gateway_target(gateway["id"])
