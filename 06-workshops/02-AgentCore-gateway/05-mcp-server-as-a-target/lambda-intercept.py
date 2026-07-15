"""문서 사양을 엄격히 따르는 AgentCore Gateway passthrough 인터셉터입니다.

AgentCore Gateway 문서의 response streaming 계약을 구현합니다.

  - REQUEST 인터셉터:
      `transformedGatewayRequest.body`를 변경 없이 반환합니다.
  - RESPONSE 인터셉터(non-streaming, `isStreamingResponse`가 False이거나 없음):
      `headers`, `statusCode`, `body`가 변경되지 않은
      `transformedGatewayResponse`를 반환합니다.
  - RESPONSE 인터셉터(streaming, `isStreamingResponse=True`):
      첫 이벤트(입력에 statusCode가 있음)는 headers, statusCode, body를 재정의할 수
      있으며 여기서는 변경 없이 전달합니다. 이후 이벤트(입력에 statusCode가 없음)는
      `body`만 반환할 수 있고, headers와 statusCode가 있어도 무시됩니다.

로그에는 실행된 분기와 기반 MCP method/ID를 기록하여 CloudWatch trace를
gateway의 request ID와 연계할 수 있게 합니다.
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    mcp = event.get("mcp", {}) or {}
    gateway_request = mcp.get("gatewayRequest") or {}
    gateway_response = mcp.get("gatewayResponse")

    if gateway_response is not None:
        return _handle_response(gateway_request, gateway_response)
    return _handle_request(gateway_request)


def _handle_request(gateway_request):
    body = gateway_request.get("body") or {}
    method = body.get("method") if isinstance(body, dict) else None
    msg_id = body.get("id") if isinstance(body, dict) else None
    has_result = isinstance(body, dict) and "result" in body
    has_error = isinstance(body, dict) and "error" in body
    kind = "request"
    if has_result:
        kind = "response"
    elif has_error:
        kind = "error"
    logger.info(
        "REQUEST interceptor: kind=%s method=%r id=%r passing through",
        kind,
        method,
        msg_id,
    )
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {"transformedGatewayRequest": {"body": body}},
    }


def _handle_response(gateway_request, gateway_response):
    body = gateway_response.get("body") or {}
    is_streaming = bool(gateway_response.get("isStreamingResponse"))
    has_status_in_input = "statusCode" in gateway_response
    has_headers_in_input = "headers" in gateway_response

    inbound_method = (gateway_request.get("body") or {}).get("method")
    msg_method = body.get("method") if isinstance(body, dict) else None
    msg_id = body.get("id") if isinstance(body, dict) else None

    if not is_streaming:
        logger.info(
            "RESPONSE interceptor (non-streaming): inbound_method=%r "
            "outbound_method=%r id=%r passing through",
            inbound_method,
            msg_method,
            msg_id,
        )
        out = {"body": body}
        if has_status_in_input:
            out["statusCode"] = gateway_response.get("statusCode", 200)
        if has_headers_in_input:
            out["headers"] = gateway_response.get("headers", {})
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {"transformedGatewayResponse": out},
        }

    is_first_event = has_status_in_input
    if is_first_event:
        logger.info(
            "RESPONSE interceptor (streaming, first event): inbound_method=%r "
            "outbound_method=%r id=%r passing through",
            inbound_method,
            msg_method,
            msg_id,
        )
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "body": body,
                    "statusCode": gateway_response.get("statusCode", 200),
                    "headers": gateway_response.get("headers", {}),
                }
            },
        }

    logger.info(
        "RESPONSE interceptor (streaming, subsequent event): inbound_method=%r "
        "outbound_method=%r id=%r passing through (body only)",
        inbound_method,
        msg_method,
        msg_id,
    )
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {"transformedGatewayResponse": {"body": body}},
    }
