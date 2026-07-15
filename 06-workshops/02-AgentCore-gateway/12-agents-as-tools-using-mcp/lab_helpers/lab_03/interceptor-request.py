import json
import base64


def get_user_groups(jwt_token):
    """JWT 토큰에서 사용자 그룹을 추출합니다.

    인자:
        jwt_token: 'Bearer ' 접두사가 있거나 없는 JWT 토큰 문자열

    반환:
        list: 사용자 그룹(예: ['sre'] 또는 ['approvers'])
    """
    try:
        # 'Bearer ' 접두사가 있으면 제거
        token = jwt_token.replace("Bearer ", "").strip()

        # JWT 형식: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            return []

        # 페이로드 디코딩(필요한 경우 패딩 추가)
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)

        # cognito:groups claim 추출
        groups = claims.get("cognito:groups", [])
        return groups
    except Exception as e:
        print(f"Error extracting groups from JWT: {e}")
        return []


def lambda_handler(event, context):
    try:
        print("=" * 80)
        print("INTERCEPTOR LAMBDA - FULL REQUEST DUMP")
        print("=" * 80)
        print(json.dumps(event, indent=2))
        print("=" * 80)

        # 올바른 구조에서 Gateway 요청 추출
        mcp_data = event.get("mcp", {})
        gateway_request = mcp_data.get("gatewayRequest", {})
        headers = gateway_request.get("headers", {})
        body = gateway_request.get("body", {})

        # 오류 처리와 함께 본문을 JSON으로 파싱
        try:
            body_json = json.loads(body) if isinstance(body, str) else body
        except json.JSONDecodeError as e:
            print(f"Error parsing body JSON: {e}")
            return _deny_request(None, message="Invalid JSON in request body")

        # Authorization 헤더 추출
        auth_header = headers.get("authorization", "") or headers.get("Authorization", "")
        print(f"Authorization header received: {auth_header[:50]}..." if auth_header else "No Authorization header")

        # JWT에서 사용자 그룹 추출
        user_groups = get_user_groups(auth_header)
        print(f"User groups: {user_groups}")

        # JSON-RPC 메서드 및 ID 추출
        method = body_json.get("method")
        rpc_id = body_json.get("id")

        # 도구 호출이 아니면 항상 통과(예: 초기화, 상태 확인)
        if method not in ("tools/call", "tools/list"):
            print(f"Non-tool method '{method}', passing through")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": {
                            "Authorization": headers.get("Authorization", ""),
                            "Content-Type": "application/json",
                            "AgentID": headers.get("AgentID", ""),
                        },
                        "body": body_json,
                    }
                },
            }

        # tools/list는 일반적으로 AgentID 없이 허용
        if method == "tools/list":
            print("Allowing tools/list")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": {
                            "Authorization": headers.get("Authorization", ""),
                            "Content-Type": "application/json",
                        },
                        "body": body_json,
                    }
                },
            }

        # tools/call은 사용자 그룹을 기준으로 권한 확인
        if method == "tools/call":
            try:
                # params에서 도구 이름과 인자 추출
                tool_name = body_json.get("params", {}).get("name", "")
                tool_arguments = body_json.get("params", {}).get("arguments", {})
                print(f"Tool call requested: {tool_name}")

                # 권한 확인
                if "sre" in user_groups:
                    # SRE는 action_type="only_plan"만 사용 가능
                    action_type = tool_arguments.get("action_type", "")
                    if action_type != "only_plan":
                        print(f"SRE user not authorized for action_type: {action_type}")
                        return _deny_request(
                            rpc_id,
                            message="SRE users can only use action_type='only_plan'",
                        )
                    print("SRE user authorized with action_type=only_plan")
                elif "approvers" in user_groups:
                    # Approver는 모든 도구를 호출할 수 있음
                    print(f"Approver authorized for tool: {tool_name}")
                else:
                    print(f"User has no recognized groups: {user_groups}")
                    return _deny_request(
                        rpc_id,
                        message="User does not belong to authorized groups (sre or approvers)",
                    )

                # 권한이 있으면 통과
                return {
                    "interceptorOutputVersion": "1.0",
                    "mcp": {
                        "transformedGatewayRequest": {
                            "headers": {
                                "Authorization": headers.get("Authorization", ""),
                                "Content-Type": "application/json",
                            },
                            "body": body_json,
                        }
                    },
                }
            except Exception as e:
                print(f"Error processing tools/call: {e}")
                return _deny_request(rpc_id, message=f"Error processing tool call: {str(e)}")

        # 그 밖의 메서드는 통과
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayRequest": {
                    "headers": {
                        "Authorization": headers.get("Authorization", ""),
                        "Content-Type": "application/json",
                    },
                    "body": body_json,
                }
            },
        }

    except Exception as e:
        print(f"Unexpected error in lambda_handler: {e}")
        # 안전한 오류 응답 반환
        return _deny_request(None, message=f"Internal error: {str(e)}")


def _deny_request(rpc_id, message: str):
    """유효한 MCP/JSON-RPC 오류 응답을 구성합니다."""
    print(f"Denying request: {message}")
    error_rpc = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        },
    }
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": error_rpc,
            }
        },
    }
