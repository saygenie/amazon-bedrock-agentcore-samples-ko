# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""에이전트 도구의 공용 예외."""


class AuthorizationRequiredError(Exception):
    """공급자에 대한 OAuth 권한 부여가 필요할 때 발생한다."""

    def __init__(self, provider: str, auth_url: str) -> None:
        """공급자 이름과 권한 부여 URL로 초기화한다."""
        self.provider = provider
        self.auth_url = auth_url
        super().__init__(f"Please authorize {provider} access: {auth_url}")


class ApiError(Exception):
    """외부 API 호출이 실패할 때 발생한다."""

    def __init__(self, provider: str, message: str, status_code: int | None = None) -> None:
        """공급자, 메시지, 선택적 상태 코드로 초기화한다."""
        self.provider = provider
        self.status_code = status_code
        msg = f"{provider} API error: {message}"
        if status_code:
            msg += f" (HTTP {status_code})"
        super().__init__(msg)
