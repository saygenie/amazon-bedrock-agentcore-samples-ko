# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
elicitation 응답(-32042)을 포착하여 사용자를 인증 온보딩 앱으로 안내하는
친숙한 메시지로 다시 작성하는 Gateway RESPONSE 인터셉터입니다.

Gateway가 누락된 다운스트림 토큰을 감지하면 클라이언트에 authorization URL을
열도록 요청하는 elicitation 오류를 반환합니다. 이 3LO 흐름은 웹 앱용으로
설계되었으므로 VS Code에서는 작동하지 않습니다. 대신 이 인터셉터는 elicitation을
사람이 읽을 수 있는 메시지가 담긴 일반 tools/call 결과로 변환합니다.
"""

import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AUTH_ONBOARDING_URL = os.environ.get("AUTH_ONBOARDING_URL", "")

# elicitation용 MCP JSON-RPC 오류 코드(authorization 필요)
ELICITATION_ERROR_CODE = -32042


def lambda_handler(event, context):
    logger.info("Interceptor event: %s", json.dumps(event, default=str)[:2000])

    mcp_data = event.get("mcp", {})
    gateway_response = mcp_data.get("gatewayResponse")

    if not gateway_response:
        # 응답 인터셉터 호출이 아니면 그대로 전달
        logger.warning("No gatewayResponse in event — passing through")
        return passthrough_response(mcp_data)

    body = gateway_response.get("body") or {}

    # body가 문자열일 수 있으므로 파싱
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return passthrough_response(mcp_data)

    if not isinstance(body, dict):
        return passthrough_response(mcp_data)

    # elicitation 오류인지 확인
    error = body.get("error")
    if not error or error.get("code") != ELICITATION_ERROR_CODE:
        # elicitation이 아니면 변경 없이 전달
        return passthrough_response(mcp_data)

    # 호출자가 원본 elicitation을 명시적으로 원하는지 확인(예: 인증 온보딩 SPA)
    # SPA는 직접 elicitation을 처리하겠다는 신호로 JSON-RPC 요청에
    # _meta.rawElicitation: true를 전송
    request_body = mcp_data.get("gatewayRequest", {}).get("body", {})
    if isinstance(request_body, str):
        try:
            request_body = json.loads(request_body)
        except (json.JSONDecodeError, TypeError):
            request_body = {}

    meta = request_body.get("_meta", {}) if isinstance(request_body, dict) else {}
    if meta.get("rawElicitation"):
        logger.info("rawElicitation flag detected — passing elicitation through raw")
        return passthrough_response(mcp_data)

    logger.info("Detected elicitation response — rewriting to friendly message")

    jsonrpc_id = request_body.get("id", body.get("id", 1))

    message = (
        "\u26a0\ufe0f Authorization Required\n\n"
        "You haven't authorized access to the downstream API yet. "
        "Please visit our auth onboarding app to complete authorization:\n\n"
        f"{AUTH_ONBOARDING_URL}\n\n"
        "After completing authorization there, retry this tool call."
    )

    rewritten_body = {
        "jsonrpc": "2.0",
        "id": jsonrpc_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": message,
                }
            ]
        },
    }

    response = {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 200,
                "body": rewritten_body,
            }
        },
    }
    logger.info("Returning rewritten response: %s", json.dumps(response, default=str)[:1000])
    return response


def passthrough_response(mcp_data):
    """원래 응답을 변경 없이 전달합니다."""
    gateway_response = mcp_data.get("gatewayResponse", {})
    body = gateway_response.get("body")
    status_code = gateway_response.get("statusCode", 200)
    # Gateway가 body를 JSON 문자열로 보낼 수 있지만 반환값은 dict를 예상함
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body = {}
    # Gateway는 null body를 거부하므로 본문 없는 응답(예: 202 알림)에 빈 dict 사용
    if body is None:
        body = {}
    response = {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "body": body,
                "statusCode": status_code,
            }
        },
    }
    logger.info("Passthrough response: %s", json.dumps(response, default=str)[:1000])
    return response
