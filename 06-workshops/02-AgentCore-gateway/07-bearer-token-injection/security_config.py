"""
bearer token 주입 데모를 위한 보안 구성 및 검증 유틸리티입니다.

이 모듈은 bearer token과 API 요청을 안전하게 처리하도록 보안 중심의
구성 및 검증 함수를 제공합니다.
"""

import re
import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse


class SecurityConfig:
    """보안 구성 상수와 검증 메서드입니다."""

    # 최대 요청 본문 크기(1MB)
    MAX_REQUEST_BODY_SIZE = 1024 * 1024

    # 최대 토큰 길이
    MAX_TOKEN_LENGTH = 2048

    # 허용되는 도구 이름 패턴(영숫자, 하이픈, 밑줄)
    TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    # 필수 보안 헤더
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    # API 속도 제한
    DEFAULT_RATE_LIMIT = 100
    DEFAULT_BURST_LIMIT = 200
    DEFAULT_DAILY_QUOTA = 1000

    @staticmethod
    def validate_bearer_token(token: str) -> bool:
        """
        bearer token 형식과 길이를 검증합니다.

        인자:
            token: 검증할 bearer token

        반환:
            토큰이 유효하면 True, 아니면 False
        """
        if not token or not isinstance(token, str):
            return False

        # 'Bearer ' 접두사가 있으면 제거
        if token.startswith("Bearer "):
            token = token[7:]

        # 길이 확인
        if len(token) > SecurityConfig.MAX_TOKEN_LENGTH:
            return False

        # 기본 형식 검증(base64와 유사한 문자)
        if not re.match(r"^[A-Za-z0-9+/=_-]+$", token):
            return False

        return True

    @staticmethod
    def validate_tool_name(tool_name: str) -> bool:
        """
        도구 이름 형식을 검증합니다.

        인자:
            tool_name: 검증할 도구 이름

        반환:
            도구 이름이 유효하면 True, 아니면 False
        """
        if not tool_name or not isinstance(tool_name, str):
            return False

        if len(tool_name) > 100:  # 적정 길이 제한
            return False

        return bool(SecurityConfig.TOOL_NAME_PATTERN.match(tool_name))

    @staticmethod
    def validate_url(url: str, require_https: bool = True) -> bool:
        """
        URL 형식과 보안 요구 사항을 검증합니다.

        인자:
            url: 검증할 URL
            require_https: HTTPS 프로토콜 필수 여부

        반환:
            URL이 유효하면 True, 아니면 False
        """
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)

            if require_https and parsed.scheme != "https":
                return False

            if not parsed.netloc:
                return False

            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        민감한 정보를 제거하여 로깅용 데이터를 정제합니다.

        인자:
            data: 정제할 데이터 dictionary

        반환:
            정제된 데이터 dictionary
        """
        sensitive_keys = {
            "token",
            "password",
            "secret",
            "key",
            "authorization",
            "x-asana-token",
            "bearer",
            "api_key",
            "access_token",
        }

        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = SecurityConfig.sanitize_log_data(value)
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def get_environment_config() -> Dict[str, str]:
        """
        보안 관련 환경 구성을 가져옵니다.

        반환:
            환경 구성 dictionary
        """
        return {
            "DEMO_USERNAME": os.environ.get("DEMO_USERNAME", "testuser"),
            "DEMO_SECRET_NAME": os.environ.get("DEMO_SECRET_NAME", "asana_integration_demo_agent"),
            "ROLE_NAME": os.environ.get("ROLE_NAME", "AgentCoreGwyAsanaIntegrationRole"),
            "POLICY_NAME": os.environ.get("POLICY_NAME", "AgentCoreGwyAsanaIntegrationPolicy"),
            "MAX_REQUEST_SIZE": os.environ.get("MAX_REQUEST_SIZE", str(SecurityConfig.MAX_REQUEST_BODY_SIZE)),
            "RATE_LIMIT": os.environ.get("RATE_LIMIT", str(SecurityConfig.DEFAULT_RATE_LIMIT)),
        }


def validate_request_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    수신 요청 payload에 보안 문제가 있는지 검증합니다.

    인자:
        payload: 검증할 요청 payload

    반환:
        (is_valid, error_message) tuple
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"

    # tool_name 검증
    tool_name = payload.get("tool_name")
    if not SecurityConfig.validate_tool_name(tool_name):
        return False, "Invalid tool_name format"

    # 문자열 필드에 의심스러운 내용이 없는지 검증
    string_fields = ["name", "notes", "project", "task_gid", "workspace"]
    for field in string_fields:
        value = payload.get(field)
        if value is not None:
            if not isinstance(value, str):
                return False, f"Field {field} must be a string"

            if len(value) > 1000:  # 적정 길이 제한
                return False, f"Field {field} is too long"

            # 기본 XSS 방지
            if any(char in value for char in ["<", ">", '"', "'"]):
                return False, f"Field {field} contains invalid characters"

    return True, None


def create_secure_response_headers() -> Dict[str, str]:
    """
    안전한 HTTP 응답 헤더를 생성합니다.

    반환:
        보안 헤더 dictionary
    """
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Headers": "Content-Type,X-Asana-Token,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }

    # 보안 헤더 추가
    headers.update(SecurityConfig.SECURITY_HEADERS)

    # 참고: 프로덕션에서는 CORS origin을 제한
    # 데모 목적상 모든 origin을 허용
    headers["Access-Control-Allow-Origin"] = "*"

    return headers
