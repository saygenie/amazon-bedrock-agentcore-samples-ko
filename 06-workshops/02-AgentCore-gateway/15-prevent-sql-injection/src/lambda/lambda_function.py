"""
SQL Injection 방지 인터셉터(Gateway 요청 인터셉터)

목적
- MCP tools/call 요청을 가로채 도구 인자가 백엔드 데이터베이스 도구에 도달하기 전에 평가합니다.
- 안전하지 않은 SQL 실행을 방지하는 결정론적 도구 수준 제어를 제공합니다.
- fail closed 방식으로 동작하여 의심스러운 패턴이 탐지되거나 검증 및 분석이 실패하면 요청을 차단합니다.

범위
- 원래 사용자 prompt가 아닌 도구 인자(도구 입력)를 대상으로 동작합니다.
- 데이터베이스 상호작용 전에 도구 경계에서 실행됩니다.
- 에이전트나 호출자가 원시 또는 안전하지 않은 SQL 콘텐츠를 데이터베이스 도구에
  전달하지 못하게 합니다.

확장성
이 제어는 AWS Lambda로 구현되어 다음 항목을 통합할 수 있습니다.
- 스키마 및 계약 검증 라이브러리
- policy engine 및 권한 부여 검사(tenant, 역할, 작업 allow list)
- 내부 보안 서비스 및 규정 준수 로직
- SDK 또는 API 호출을 통한 서드 파티 유료 보안 서비스(예: 위험 점수, DLP,
  위협 인텔리전스, API 보안 플랫폼)
- 감사 및 인시던트 대응용 중앙 집중식 로깅·모니터링 시스템

프로덕션 고려 사항
이 구현은 일반적인 SQL Injection 기법을 식별하기 위해 휴리스틱 패턴 탐지를 사용합니다.
프로덕션 시스템에서는 에이전트의 원시 SQL을 허용하지 말고 다음 방식을 우선 사용합니다.
- 구조화된 도구 계약(query template 또는 typed parameter가 있는 JSON intent)
- allow list에 등록된 작업, 테이블 및 필드
- 엄격한 스키마 검증 및 범위 검사
- tenant 격리 및 최소 권한 접근
- 데이터베이스 계층의 parameterized query / prepared statement
"""

import re
import hashlib
from typing import Any, Dict, Tuple, List

STRICT_MODE = False
MAX_STRING_LENGTH = 10000

SQL_INJECTION_PATTERNS = [
    (
        r";[\s\n]*\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE)\b",
        "STACKED_QUERY",
    ),
    (r"\b(DROP|TRUNCATE)\b[\s\n]+\b(TABLE|DATABASE|SCHEMA)\b", "DANGEROUS_DDL"),
    (r"--", "SQL_COMMENT_DASH"),
    (r"/\*", "SQL_COMMENT_OPEN"),
    (r"\*/", "SQL_COMMENT_CLOSE"),
    (r"\bUNION\b[\s\n]+\bSELECT\b", "UNION_SELECT"),
    (r"\bUNION\b[\s\n]+\bALL\b[\s\n]+\bSELECT\b", "UNION_ALL_SELECT"),
    (r"\bOR\b[\s\n]+1[\s\n]*=[\s\n]*1", "TAUTOLOGY_OR"),
    (r"\bAND\b[\s\n]+1[\s\n]*=[\s\n]*1", "TAUTOLOGY_AND"),
    (r"\bSLEEP\b[\s\n]*\(", "TIME_SLEEP"),
    (r"\bWAITFOR\b[\s\n]+\bDELAY\b", "TIME_WAITFOR"),
    (r"\bBENCHMARK\b[\s\n]*\(", "TIME_BENCHMARK"),
    (r"\b(EXEC|EXECUTE|sp_executesql)\b", "DYNAMIC_SQL"),
    (
        r"\b(ALTER|RENAME|GRANT|REVOKE)\b[\s\n]+\b(TABLE|DATABASE|USER)\b",
        "DANGEROUS_DDL_EXTENDED",
    ),
    (r"\bCONCAT\b[\s\n]*\(", "STRING_CONCAT"),
    (r"\bCHR\b[\s\n]*\(|\bCHAR\b[\s\n]*\(", "CHAR_ENCODING"),
    (r"\bSUBSTRING\b[\s\n]*\(|\bSUBSTR\b[\s\n]*\(", "SUBSTRING_PROBE"),
    (r"\bCONVERT\b[\s\n]*\(|\bCAST\b[\s\n]*\(", "TYPE_CONVERSION"),
    (r"0x[0-9a-fA-F]+", "HEX_ENCODING"),
    (r"\bINFORMATION_SCHEMA\b", "SCHEMA_ENUMERATION"),
    (r"\bLOAD_FILE\b|\bINTO\b[\s\n]+\bOUTFILE\b", "FILE_OPERATIONS"),
]

COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), rule_id) for pattern, rule_id in SQL_INJECTION_PATTERNS
]


def normalize_string(s: str) -> str:
    normalized = re.sub(r"\s+", " ", s)
    return normalized.lower()


def compute_query_hash(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()[:16]


def extract_all_strings(obj: Any, path: str = "") -> List[Tuple[str, str]]:
    strings = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key
            strings.extend(extract_all_strings(value, new_path))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            new_path = f"{path}[{idx}]"
            strings.extend(extract_all_strings(item, new_path))
    elif isinstance(obj, str):
        strings.append((path, obj))

    return strings


def detect_sql_injection(value: str, field_path: str = "") -> Tuple[bool, str, str]:
    if not value:
        return False, "", ""

    if len(value) > MAX_STRING_LENGTH:
        return True, "STRING_TOO_LONG", "INVALID_INPUT"

    normalized = normalize_string(value)

    for pattern, rule_id in COMPILED_PATTERNS:
        if pattern.search(normalized):
            return True, rule_id, "SQL_INJECTION_DETECTED"

    return False, "", ""


def analyze_arguments_for_sql_injection(
    arguments: Dict[str, Any],
) -> Tuple[bool, str, str]:
    all_strings = extract_all_strings(arguments)

    if not all_strings:
        return True, "", ""

    for field_path, value in all_strings:
        is_malicious, rule_id, category = detect_sql_injection(value, field_path)

        if is_malicious:
            value_hash = compute_query_hash(value)
            print(f"[SECURITY] SQL injection detected | field={field_path} | rule={rule_id} | hash={value_hash}")
            return False, rule_id, category

    return True, "", ""


def create_blocked_response(category: str, request_id: Any) -> Dict[str, Any]:
    generic_message = "Request blocked by security policy"

    blocked_response = {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 403,
                "headers": {
                    "Content-Type": "application/json",
                    "X-Security-Status": "BLOCKED",
                },
                "body": {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": generic_message,
                        "data": {
                            "category": category,
                            "security_policy": "sql_injection_prevention",
                        },
                    },
                },
            }
        },
    }

    return blocked_response


def lambda_handler(event, context):
    try:
        mcp_data = event.get("mcp", {})
        gateway_request = mcp_data.get("gatewayRequest", {})
        request_body = gateway_request.get("body", {})

        method = request_body.get("method", "")
        request_id = request_body.get("id", "unknown")

        print(f"[INFO] Interceptor invoked | request_id={request_id} | method={method}")

        if method != "tools/call":
            print(f"[INFO] Method not tools/call, passing through | request_id={request_id}")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": gateway_request.get("headers", {}),
                        "body": request_body,
                    }
                },
            }

        params = request_body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        print(f"[INFO] Analyzing tool call | request_id={request_id} | tool={tool_name}")

        if STRICT_MODE:
            if "query" in arguments or "sql" in arguments:
                print(f"[SECURITY] STRICT MODE: Raw SQL field rejected | request_id={request_id} | tool={tool_name}")
                return create_blocked_response("RAW_SQL_NOT_ALLOWED", request_id)

        is_safe, rule_id, category = analyze_arguments_for_sql_injection(arguments)

        if is_safe:
            print(f"[INFO] Request allowed | request_id={request_id} | tool={tool_name}")

            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": gateway_request.get("headers", {}),
                        "body": request_body,
                    }
                },
            }
        else:
            print(f"[SECURITY] Request blocked | request_id={request_id} | tool={tool_name} | rule={rule_id}")
            return create_blocked_response(category, request_id)

    except Exception as e:
        print(f"[ERROR] Interceptor error | request_id={request_body.get('id', 'unknown')} | error={str(e)[:100]}")
        return create_blocked_response("INTERCEPTOR_ERROR", request_body.get("id", "unknown"))
