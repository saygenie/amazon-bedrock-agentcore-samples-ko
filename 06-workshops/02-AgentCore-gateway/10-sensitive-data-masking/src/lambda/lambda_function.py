"""
Bedrock Guardrails를 사용하는 Gateway MCP 응답용 PII 마스킹 인터셉터

이 Lambda 함수는 Gateway MCP tools/call 응답을 가로채 모든 도구 응답의
민감한 PII 데이터를 Amazon Bedrock Guardrails API로 마스킹합니다.
모든 도구 응답을 변환하는 응답 인터셉터로 구성됩니다.
"""

import json
import os
import boto3
from typing import Any, Dict

# Bedrock Runtime 클라이언트 초기화
bedrock_runtime = boto3.client("bedrock-runtime")

# 환경 변수에서 Guardrail 구성 가져오기
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")


def mask_pii_with_guardrails(text: str) -> str:
    """
    Bedrock Guardrails를 사용해 텍스트의 PII를 마스킹합니다.

    인자:
        text: PII가 포함될 수 있는 텍스트 콘텐츠

    반환:
        Guardrails로 PII를 마스킹하거나 익명화한 텍스트
    """
    print(f"[DEBUG] mask_pii_with_guardrails - INPUT text (first 200 chars): {text[:200]}")

    if not GUARDRAIL_ID:
        print("[DEBUG] WARNING: GUARDRAIL_ID not configured, skipping PII masking")
        print("[DEBUG] mask_pii_with_guardrails - RETURNING original text (no guardrail)")
        return text

    try:
        print(f"[DEBUG] Calling Bedrock Guardrails API with ID: {GUARDRAIL_ID}, Version: {GUARDRAIL_VERSION}")

        # 텍스트에 Guardrail 적용
        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source="OUTPUT",  # 도구 출력을 필터링
            outputScope="FULL",
            content=[{"text": {"text": text}}],
        )

        print(f"[DEBUG] Guardrails API response received: {json.dumps(response, default=str)}")

        # 응답에서 마스킹된 텍스트 추출
        outputs = response.get("outputs", [])
        if outputs and len(outputs) > 0:
            masked_text = outputs[0].get("text", text)
            print(f"[DEBUG] Extracted masked_text (first 200 chars): {masked_text[:200]}")

            # PII 탐지 세부 정보 로깅
            usage = response.get("usage", {})
            assessments = response.get("assessments", [])

            if usage.get("contentPolicyUnits", 0) > 0:
                print("[DEBUG] PII detected and anonymized by Guardrails")

                # 탐지된 PII 유형 로깅
                if assessments:
                    for assessment in assessments:
                        sensitive_info = assessment.get("sensitiveInformationPolicy", {})
                        pii_entities = sensitive_info.get("piiEntities", [])
                        if pii_entities:
                            detected_types = [entity.get("type") for entity in pii_entities]
                            print(f"[DEBUG]   Detected PII types: {', '.join(detected_types)}")

            print("[DEBUG] mask_pii_with_guardrails - RETURNING masked_text")
            return masked_text

        print("[DEBUG] No outputs from Guardrails, RETURNING original text")
        return text

    except Exception as e:
        error_message = str(e)
        print(f"[DEBUG] ERROR applying Guardrails: {error_message}")
        print(f"[DEBUG]   Guardrail ID: {GUARDRAIL_ID}")
        print(f"[DEBUG]   Guardrail Version: {GUARDRAIL_VERSION}")

        # 존재하지 않는 Guardrail에 대한 검증 오류인지 확인
        if "does not exist" in error_message or "ValidationException" in error_message:
            print("[DEBUG]   ⚠ The Guardrail ID or version is invalid or doesn't exist")
            print("[DEBUG]   ⚠ Make sure Step 1.3 was run successfully to create the Guardrail")
            print("[DEBUG]   ⚠ Verify the Lambda environment variables are set correctly")

        # 오류 발생 시 차단을 피하도록 원본 텍스트 반환(fail open)
        print("[DEBUG] mask_pii_with_guardrails - RETURNING original text (error occurred)")
        return text


def mask_tool_response(response_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    도구 응답의 body->result->content->text에서 텍스트를 추출하고 JSON을 파싱한 뒤,
    Bedrock Guardrails로 익명화하여 올바른 형태로 다시 구성합니다.

    인자:
        response_body: MCP JSON-RPC 응답 본문

    반환:
        text 필드의 PII가 마스킹된 응답 본문
    """
    print(f"[DEBUG] mask_tool_response - INPUT response_body: {json.dumps(response_body, default=str)}")

    # 원본을 수정하지 않도록 깊은 복사본 생성
    masked_response = json.loads(json.dumps(response_body))
    print("[DEBUG] Created deep copy of response_body")

    # body->result->content로 이동
    if "result" not in masked_response:
        print("[DEBUG] No 'result' field in response_body")
        return masked_response

    if "content" not in masked_response["result"]:
        print("[DEBUG] No 'content' field in result")
        return masked_response

    content_list = masked_response["result"]["content"]
    if not isinstance(content_list, list) or len(content_list) == 0:
        print("[DEBUG] 'content' is not a list or is empty")
        return masked_response

    print(f"[DEBUG] Processing {len(content_list)} content items")

    # 각 콘텐츠 항목 처리
    for i, content_item in enumerate(content_list):
        if content_item.get("type") != "text":
            print(f"[DEBUG] Content item {i} is not type 'text', skipping")
            continue

        text_value = content_item.get("text", "")
        if not text_value:
            print(f"[DEBUG] Content item {i} has empty text, skipping")
            continue

        print(f"[DEBUG] Content item {i} text (first 200 chars): {text_value[:200]}")

        try:
            # 텍스트를 JSON으로 파싱 시도
            parsed_json = json.loads(text_value)
            print("[DEBUG] Successfully parsed text as JSON")
            print(f"[DEBUG] Parsed JSON structure: {json.dumps(parsed_json, default=str)[:300]}")

            # Guardrails 처리를 위해 파싱한 JSON을 보기 좋은 문자열로 변환
            json_string = json.dumps(parsed_json, indent=2)
            print(f"[DEBUG] Converted to JSON string for Guardrails (first 300 chars): {json_string[:300]}")

            # JSON 콘텐츠를 익명화하도록 Bedrock Guardrails 적용
            print("[DEBUG] Applying Bedrock Guardrails to anonymize JSON content...")
            anonymized_json_string = mask_pii_with_guardrails(json_string)
            print(f"[DEBUG] Anonymized JSON string (first 300 chars): {anonymized_json_string[:300]}")

            # 익명화된 문자열을 다시 JSON 객체로 파싱
            try:
                anonymized_json = json.loads(anonymized_json_string)
                print("[DEBUG] Successfully parsed anonymized string back to JSON")
                print(f"[DEBUG] Anonymized JSON object: {json.dumps(anonymized_json, default=str)[:300]}")

                # 문자열이 아닌 JSON 객체로 직접 교체
                masked_response["result"]["content"][i]["text"] = anonymized_json
                print(f"[DEBUG] Replaced text in content item {i} with JSON object (not string)")

            except json.JSONDecodeError as e:
                print(f"[DEBUG] Failed to parse anonymized string back to JSON: {e}")
                print("[DEBUG] Using anonymized string as-is")
                masked_response["result"]["content"][i]["text"] = anonymized_json_string

        except json.JSONDecodeError:
            # JSON이 아니면 일반 텍스트로 처리
            print("[DEBUG] Text is not JSON, treating as plain text")

            # 텍스트를 익명화하도록 Bedrock Guardrails 적용
            print("[DEBUG] Applying Bedrock Guardrails to anonymize plain text...")
            anonymized_text = mask_pii_with_guardrails(text_value)
            print(f"[DEBUG] Anonymized text (first 200 chars): {anonymized_text[:200]}")

            # 응답의 텍스트 교체
            masked_response["result"]["content"][i]["text"] = anonymized_text
            print(f"[DEBUG] Replaced text in content item {i}")

    print("[DEBUG] mask_tool_response - RETURNING masked_response")
    return masked_response


def lambda_handler(event, context):
    """
    Gateway 응답 인터셉터의 기본 Lambda 핸들러입니다.

    이 핸들러는 Bedrock Guardrails를 사용해 모든 도구 응답에 PII 마스킹을 적용합니다.

    예상 이벤트 구조(tools/call에 대한 Gateway 응답):
    {
        "interceptorInputVersion": "1.0",
        "mcp": {
            "gatewayResponse": {
                "headers": {...},
                "body": {
                    "jsonrpc": "2.0",
                    "id": "invoke-tool-request",
                    "result": {
                        "isError": false,
                        "content": [
                            {
                                "type": "text",
                                "text": "{...tool data with potential PII...}"
                            }
                        ]
                    }
                },
                "statusCode": 200
            },
            "gatewayRequest": {...}
        }
    }

    모든 도구에 대해 PII가 마스킹된 변환 응답을 반환합니다.
    """
    print("[DEBUG] ========== LAMBDA HANDLER START ==========")
    print(f"[DEBUG] PII Masking Interceptor - Received event: {json.dumps(event, default=str)}")

    try:
        # MCP 데이터 추출
        mcp_data = event.get("mcp", {})
        print(f"[DEBUG] Extracted mcp_data: {json.dumps(mcp_data, default=str)}")

        gateway_response = mcp_data.get("gatewayResponse", {})
        print(f"[DEBUG] Extracted gateway_response: {json.dumps(gateway_response, default=str)}")

        gateway_request = mcp_data.get("gatewayRequest", {})
        print(f"[DEBUG] Extracted gateway_request: {json.dumps(gateway_request, default=str)}")

        # 응답 데이터 가져오기
        response_headers = gateway_response.get("headers", {})
        print(f"[DEBUG] response_headers: {response_headers}")

        response_body = gateway_response.get("body", {})
        print(f"[DEBUG] response_body: {json.dumps(response_body, default=str)}")

        status_code = gateway_response.get("statusCode", 200)
        print(f"[DEBUG] status_code: {status_code}")

        # 호출된 도구를 확인하기 위해 요청 데이터 가져오기
        request_body = gateway_request.get("body", {})
        print(f"[DEBUG] request_body: {json.dumps(request_body, default=str)}")

        method = request_body.get("method", "")
        print(f"[DEBUG] Method: {method}")

        # tools/call 응답만 처리
        if method == "tools/call":
            params = request_body.get("params", {})
            tool_name = params.get("name", "")

            print(f"[DEBUG] Tool called: {tool_name}")
            print("[DEBUG] Applying PII masking to tool response...")

            # 모든 도구의 응답에서 PII 마스킹
            masked_body = mask_tool_response(response_body)

            print(f"[DEBUG] Masked response body: {json.dumps(masked_body, default=str)}")

            # 반환 객체 구성
            return_obj = {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": response_headers,
                        "body": masked_body,
                        "statusCode": status_code,
                    }
                },
            }

            print(f"[DEBUG] lambda_handler - RETURNING (tools/call): {json.dumps(return_obj, default=str)}")
            print("[DEBUG] ========== LAMBDA HANDLER END (tools/call) ==========")
            return return_obj

        # tools/call이 아닌 응답은 변경 없이 전달
        print("[DEBUG] Method is not 'tools/call', passing through unchanged")

        passthrough_obj = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "headers": response_headers,
                    "body": response_body,
                    "statusCode": status_code,
                }
            },
        }

        print(f"[DEBUG] lambda_handler - RETURNING (passthrough): {json.dumps(passthrough_obj, default=str)}")
        print("[DEBUG] ========== LAMBDA HANDLER END (passthrough) ==========")
        return passthrough_obj

    except Exception as e:
        print(f"[DEBUG] ERROR in lambda_handler: {e}")

        import traceback

        print(f"[DEBUG] Traceback: {traceback.format_exc()}")

        # 오류 발생 시 차단하는 대신 변경 없이 전달
        error_obj = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "headers": gateway_response.get("headers", {}),
                    "body": gateway_response.get("body", {}),
                    "statusCode": gateway_response.get("statusCode", 500),
                }
            },
        }

        print(f"[DEBUG] lambda_handler - RETURNING (error): {json.dumps(error_obj, default=str)}")
        print("[DEBUG] ========== LAMBDA HANDLER END (error) ==========")
        return error_obj
