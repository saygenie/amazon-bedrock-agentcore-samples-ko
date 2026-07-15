import logging
import json
import os
import boto3

# 로깅 구성
logger = logging.getLogger()
logger.setLevel(logging.INFO)

GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", None)
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "1.0")
MCP_METADATA_KEY = os.getenv("MCP_METADATA_KEY", "com.example/target")

client = boto3.client("bedrock-runtime")


def lambda_handler(event, context):
    mcp_method = None
    try:
        """
        Lambda function that handles both REQUEST and RESPONSE interceptor types.

        For REQUEST interceptors: logs the MCP method and passes request through unchanged
        For RESPONSE interceptors: passes response through unchanged
        """
    # 이벤트에서 MCP 데이터 추출
        mcp_data = event.get("mcp", {})

        logger.info(f"Received event: {json.dumps(event, indent=2)}")

    # gatewayResponse 존재 여부에 따라 REQUEST 또는 RESPONSE 인터셉터인지 확인
        if "gatewayResponse" in mcp_data and mcp_data["gatewayResponse"] is not None:
            logger.info("This is a RESPONSE interceptor")

        # 메서드를 확인하기 위해 요청 본문 가져오기(메서드는 응답이 아니라 요청에 있음)
            request_body = mcp_data.get("gatewayRequest", {}).get("body", {})
            response_body = mcp_data.get("gatewayResponse", {}).get("body", {}) or {}

            if request_body:
                mcp_method = request_body.get("method", "unknown")
                logger.info(f"Gateway request method: {mcp_method}")

            if response_body:
                logger.info(f"Gateway response body: {json.dumps(response_body, indent=2)}")

            logger.info(f"Processing RESPONSE interceptor - MCP method: {mcp_method}")

            # === _meta 기반 TOOLS/LIST 필터링 처리 ===
            if mcp_method == "tools/list" and response_body:
                logger.info("tools/list response detected in RESPONSE interceptor")

                # MCP _meta에서 target 필터 추출(사양 준수)
                target_filter = None
                meta = request_body.get("_meta", {})
                if isinstance(meta, dict):
                    target_filter = meta.get(MCP_METADATA_KEY)

                if target_filter:
                    logger.info(f"Target filter from _meta: {MCP_METADATA_KEY} = '{target_filter}'")
                    logger.info(f"Will filter tools to only those starting with '{target_filter}___'")
                else:
                    logger.info("No target filter in _meta - returning ALL tools (no filtering)")

                    # target 필터가 지정된 경우 도구 필터링
                if "result" in response_body and "tools" in response_body.get("result", {}):
                    result = response_body["result"]
                    original_tools = result.get("tools", [])

                    logger.info(f"Original tools count: {len(original_tools)}")

                    if target_filter:
                        # gateway target 이름 접두사로 필터링(형식: "target___tool")
                        filtered_tools = [
                            tool for tool in original_tools if tool.get("name", "").startswith(f"{target_filter}___")
                        ]

                        logger.info(f"Filtered to {len(filtered_tools)} tools for target '{target_filter}'")

                                # 일치하는 도구 기록
                        if filtered_tools:
                            logger.info("Matched tools:")
                            for tool in filtered_tools:
                                logger.info(f"  - {tool.get('name')}")
                        else:
                            logger.warning(f"No tools matched target '{target_filter}'")

                        # 필터링 요약 기록
                        removed = len(original_tools) - len(filtered_tools)
                        if removed > 0:
                            logger.info(f"Filtered out {removed} tools not matching target")

                        # 필터링된 응답 생성
                        filtered_body = {
                            "jsonrpc": response_body.get("jsonrpc", "2.0"),
                            "id": response_body.get("id"),
                            "result": {"tools": filtered_tools},
                        }

                        # 응답에 _meta가 있으면 유지
                        if "_meta" in response_body:
                            filtered_body["_meta"] = response_body["_meta"]

                        response = {
                            "interceptorOutputVersion": "1.0",
                            "mcp": {
                                "transformedGatewayResponse": {
                                    "body": filtered_body,
                                    "statusCode": 200,
                                }
                            },
                        }
                        logger.info("Returning filtered tools/list response")
                        return response
                    else:
                        # 필터링하지 않고 모든 도구를 기록한 뒤 변경 없이 반환
                        logger.info(f"No filtering applied - returning all {len(original_tools)} tools")
                        logger.info("Available tools:")
                        for tool in original_tools:
                            logger.info(f"  - {tool.get('name')}")

            if mcp_method == "tools/call" and response_body:
                logger.info("tools/call response detected in RESPONSE interceptor")
                content = (
                    response_body.get("result", {}).get("content", [])[0].get("text", {}) if response_body else None
                )
                if GUARDRAIL_ID:
                    gr_response = client.apply_guardrail(
                        guardrailIdentifier=GUARDRAIL_ID,
                        guardrailVersion=GUARDRAIL_VERSION,
                        source="INPUT",
                        content=[
                            {
                                "text": {
                                    "text": content,
                                    "qualifiers": ["guard_content"],
                                },
                            },
                        ],
                        outputScope="FULL",
                    )
                    if gr_response.get("action", None) == "GUARDRAIL_INTERVENED":
                        logger.warning("Guardrail intervened on the content. Details:")
                        guardrail_text = gr_response.get("outputs", [{}])[0].get("text", "")
                        logger.warning(guardrail_text)
                        body_transformed = response_body
                        body_transformed["result"]["content"][0] = {
                            "type": "text",
                            "text": guardrail_text,
                        }
                        statusCode = 403
                        response = {
                            "interceptorOutputVersion": "1.0",
                            "mcp": {
                                "transformedGatewayResponse": {
                                    "body": body_transformed,
                                    "statusCode": statusCode,
                                }
                            },
                        }
                        logger.info(
                            f"Interceptor response after guardrail intervention: {json.dumps(response, indent=2)}"
                        )
                        return response
                    else:
                        logger.info("Guardrail did not intervene. Passing through original response.")
                else:
                    logger.warning("GUARDRAIL_ID environment variable not set. Skipping guardrail application.")
            else:
                logger.info("Non tools/call method detected in RESPONSE interceptor. Passing through unchanged.")

        # RESPONSE 인터셉터
            logger.info("Processing RESPONSE interceptor - passing through unchanged")

        # 원래 요청과 응답을 변경 없이 전달
            response = {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "body": mcp_data.get("gatewayResponse", {}).get("body", {}) or {},
                        "statusCode": mcp_data.get("gatewayResponse", {}).get("statusCode", 200),
                    }
                },
            }
            logger.info(f"Interceptor response: {json.dumps(response, indent=2)}")
            return response
        else:
        # REQUEST 인터셉터
            gateway_request = mcp_data.get("gatewayRequest", {})
            request_body = gateway_request.get("body", {})
            mcp_method = request_body.get("method", "unknown")

        # MCP 메서드 기록
            logger.info(f"Processing REQUEST interceptor - MCP method: {mcp_method}")

            if mcp_method == "tools/call" and request_body:
        # REQUEST 인터셉터
                if GUARDRAIL_ID:
                    gr_response = client.apply_guardrail(
                        guardrailIdentifier=GUARDRAIL_ID,
                        guardrailVersion=GUARDRAIL_VERSION,
                        source="INPUT",
                        content=[
                            {
                                "text": {
                                    "text": json.dumps(request_body),
                                    "qualifiers": ["guard_content"],
                                },
                            },
                        ],
                        outputScope="FULL",
                    )
                    logger.info(f"Guardrail response: {gr_response}")

                    if gr_response.get("action", None) == "GUARDRAIL_INTERVENED":
                        logger.warning("Guardrail intervened on the content. Details:")
                        guardrail_text = gr_response.get("outputs", [{}])[0].get("text", "{}")
                        logger.warning(guardrail_text)

            # gateway는 본문을 문자열이 아닌 JSON 객체로 예상하므로
            # guardrail 출력을 다시 dict로 파싱
                        try:
                            transformed_body = json.loads(guardrail_text)
                        except (json.JSONDecodeError, TypeError):
                # guardrail 출력이 유효한 JSON이 아니면 원래 요청 전달
                            logger.error("Guardrail output is not valid JSON, passing through original request")
                            transformed_body = request_body

                        response = {
                            "interceptorOutputVersion": "1.0",
                            "mcp": {
                                "transformedGatewayRequest": {
                                    "body": transformed_body,
                                }
                            },
                        }
                        logger.info(f"Interceptor response after guardrail intervention: {response}")
                        return response
                    else:
                        logger.info("Guardrail did not intervene. Passing through original request.")
                else:
                    logger.warning("GUARDRAIL_ID environment variable not set. Skipping guardrail application.")
            else:
                logger.info("Non tools/call method detected in REQUEST interceptor. Passing through unchanged.")

        # 원래 요청을 변경 없이 전달
            response = {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "body": request_body,
                    }
                },
            }

        logger.info(f"Interceptor response: {json.dumps(response, indent=2)}")
        return response
    except Exception as e:
        logger.error(f"Error processing interceptor: {str(e)}")
        raise e
