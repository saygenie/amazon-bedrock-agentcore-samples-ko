"""
DynamoDB 도구 권한 필터링을 사용하는 Lambda 인터셉터입니다.

이 Lambda 함수는 Gateway MCP RESPONSE를 가로채 DynamoDB에 저장된 클라이언트
권한을 기준으로 도구를 필터링합니다. tools/list 응답을 필터링하는 RESPONSE
인터셉터로 구성됩니다. 클라이언트에 접근 권한이 있는 도구만 반환됩니다.

인터셉터는 Authorization 헤더의 JWT token에서 client_id를 추출합니다.
"""

import json
import boto3
import os
import base64
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError

# 환경 변수(배포 중 설정)
TABLE_NAME = os.environ.get("PERMISSIONS_TABLE_NAME", "ClientToolPermissions")
REGION = os.environ.get("DYNAMODB_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# DynamoDB 리소스 초기화
dynamodb = boto3.resource("dynamodb", region_name=REGION)
permissions_table = dynamodb.Table(TABLE_NAME)


def extract_client_id_from_jwt(token: str) -> Optional[str]:
    """
    JWT token payload에서 client_id를 추출합니다.

    인자:
        token: JWT token 문자열('Bearer ' 접두사 포함 여부와 무관)

    반환:
        token payload의 client_id이며, 추출에 실패하면 None
    """
    try:
        # 'Bearer ' 접두사가 있으면 제거
        if token.startswith("Bearer "):
            token = token[7:]

        # token을 부분별로 분할
        parts = token.split(".")
        if len(parts) != 3:
            print(f"Invalid JWT format: expected 3 parts, got {len(parts)}")
            return None

        # payload 디코딩(두 번째 부분)
        payload = parts[1]

        # 필요한 경우 padding 추가
        payload += "=" * (4 - len(payload) % 4)

        # base64 디코딩
        decoded = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded)

        # client_id 추출(민감한 데이터가 있을 수 있으므로 전체 payload는 기록하지 않음)
        client_id = payload_data.get("client_id")

        if client_id:
            print("Successfully extracted client_id from JWT")
        else:
            print("WARNING: No client_id found in JWT payload")

        return client_id

    except Exception as e:
        print(f"Error extracting client_id from JWT: {e}")
        return None


def get_client_permissions(client_id: str) -> List[str]:
    """
    DynamoDB를 쿼리하여 특정 클라이언트에 허용된 모든 도구를 가져옵니다.

    인자:
        client_id: 조회할 클라이언트 ID

    반환:
        클라이언트에 접근이 허용된 도구 이름 목록
    """
    try:
        print(f"Querying permissions for client: {client_id}")

        response = permissions_table.query(
            KeyConditionExpression="ClientID = :client_id",
            ExpressionAttributeValues={":client_id": client_id},
        )

        # 허용된 도구만 필터링
        allowed_tools = [item["ToolName"] for item in response.get("Items", []) if item.get("Allowed", False)]

        print(f"Found {len(allowed_tools)} allowed tools for client {client_id}: {allowed_tools}")
        return allowed_tools

    except ClientError as e:
        print(f"Error querying DynamoDB: {e}")
        print(f"Error details: {e.response}")
        # 오류 발생 시 빈 목록 반환(모든 도구 거부)
        return []
    except Exception as e:
        print(f"Unexpected error getting permissions: {e}")
        return []


def extract_tool_name(gateway_tool_name: str) -> str:
    """
    Gateway 이름 형식에서 실제 도구 이름을 추출합니다.
    Gateway 반환값: 'target-name___tool_name'
    필요한 값: 'tool_name'

    인자:
        gateway_tool_name: Gateway 형식의 도구 이름

    반환:
        추출된 도구 이름
    """
    if "___" in gateway_tool_name:
        return gateway_tool_name.split("___")[1]
    return gateway_tool_name


def filter_tools(tools: List[Dict[str, Any]], allowed_tools: List[str]) -> List[Dict[str, Any]]:
    """
    클라이언트에 접근이 허용된 도구만 포함하도록 도구 목록을 필터링합니다.
    Gateway의 'target-name___tool_name' 이름 형식을 처리합니다.

    인자:
        tools: Gateway의 도구 dictionary 목록
        allowed_tools: DynamoDB의 허용된 도구 이름 목록

    반환:
        필터링된 도구 목록
    """
    if not tools:
        return []

    # 더 빠른 조회를 위해 allowed_tools를 set으로 변환
    allowed_set = set(allowed_tools)

    filtered = []
    for tool in tools:
        gateway_name = tool.get("name", "")
        extracted_name = extract_tool_name(gateway_name)

        if extracted_name in allowed_set:
            filtered.append(tool)

    print(f"Filtered {len(tools)} tools down to {len(filtered)} allowed tools")

    # 필터링된 도구 기록
    filtered_out = []
    for tool in tools:
        gateway_name = tool.get("name", "")
        extracted_name = extract_tool_name(gateway_name)
        if extracted_name not in allowed_set:
            filtered_out.append(gateway_name)

    if filtered_out:
        print(f"Filtered out tools: {filtered_out}")

    return filtered


def lambda_handler(event, context):
    """
    Gateway RESPONSE 인터셉터의 기본 Lambda 핸들러입니다.

    예상 이벤트 구조(Gateway RESPONSE):
    {
        "mcp": {
            "gatewayResponse": {
                "headers": {
                    "content-type": "application/json",
                    ...
                },
                "body": {
                    "jsonrpc": "2.0",
                    "result": {
                        "tools": [...]  # Gateway target의 도구 목록
                    },
                    "id": 1
                }
            },
            "gatewayRequest": {
                "headers": {
                    "authorization": "Bearer <JWT_TOKEN>",
                    ...
                }
            }
        }
    }

    필터링된 도구가 포함된 변환 응답을 반환합니다.
    """
    print(f"Received event: {json.dumps(event, default=str)}")

    try:
        # 요청(Authorization 헤더용)과 응답(도구용)을 모두 추출
        mcp_data = event.get("mcp", {})
        gateway_response = mcp_data.get("gatewayResponse", {})
        gateway_request = mcp_data.get("gatewayRequest", {})

        # Authorization용 요청 헤더 가져오기
        request_headers = gateway_request.get("headers", {})

        # 응답 데이터 가져오기
        response_headers = gateway_response.get("headers", {})
        response_body = gateway_response.get("body", {})

        # Authorization 헤더 추출(대소문자 구분 없는 조회)
        auth_header = None
        for key, value in request_headers.items():
            if key.lower() == "authorization":
                auth_header = value
                break

        print(f"Authorization header present: {bool(auth_header)}")

        # JWT token에서 client_id 추출
        client_id = None
        if auth_header:
            client_id = extract_client_id_from_jwt(auth_header)

        print(f"Extracted client_id: {client_id}")

        # client_id를 추출하지 못하면 모든 도구 거부(보안: fail closed)
        if not client_id:
            print("ERROR: No client_id found in JWT token, denying all tools")
            # 도구를 비운 채 원래 응답 구조 유지 시도
            denied_body = {
                "jsonrpc": "2.0",
                "result": {
                    "tools": []  # client_id가 누락되면 모든 도구 거부
                },
            }
            # 원래 응답에 id 필드가 있으면 유지
            if isinstance(response_body, dict) and "id" in response_body:
                denied_body["id"] = response_body["id"]

            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": {
                            "Content-Type": "application/json",
                            "X-Auth-Error": "MissingClientId",
                        },
                        "body": denied_body,
                    }
                },
            }

        # DynamoDB에서 이 클라이언트에 허용된 도구 가져오기
        allowed_tools = get_client_permissions(client_id)

        # tools/list 응답인지 확인(MCP JSON-RPC 형식)
        # 응답 본문 형식: {"jsonrpc": "2.0", "result": {"tools": [...]}, "id": 1}
        if "result" in response_body and "tools" in response_body.get("result", {}):
            result = response_body["result"]
            original_tools = result.get("tools", [])

            # 권한을 기준으로 도구 필터링
            filtered_tools = filter_tools(original_tools, allowed_tools)

            # 필터링된 도구로 응답 업데이트
            filtered_body = response_body.copy()
            filtered_body["result"] = result.copy()
            filtered_body["result"]["tools"] = filtered_tools

            # 권한 적용 기록
            print("Permission enforcement summary:")
            print(f"  - Client ID: {client_id}")
            print(f"  - Original tools count: {len(original_tools)}")
            print(f"  - Filtered tools count: {len(filtered_tools)}")
            print(f"  - Tools removed: {len(original_tools) - len(filtered_tools)}")

            # 필터링된 도구가 포함된 변환 응답 반환
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": response_headers,
                        "body": filtered_body,
                    }
                },
            }
        else:
            # tools/list 응답이 아니면 변경 없이 전달
            print("Not a tools/list response, passing through unchanged")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": response_headers,
                        "body": response_body,
                    }
                },
            }

    except Exception as e:
        print(f"ERROR in lambda_handler: {e}")
        print(f"Exception type: {type(e).__name__}")

        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        # 오류 발생 시 도구가 없는 최소 안전 응답 반환
        error_response = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Error": "InterceptorError",
                    },
                    "body": {
                        "jsonrpc": "2.0",
                        "result": {
                            "tools": []  # 안전한 기본값: 오류 발생 시 도구 없음
                        },
                        "id": 1,
                    },
                }
            },
        }

        return error_response
