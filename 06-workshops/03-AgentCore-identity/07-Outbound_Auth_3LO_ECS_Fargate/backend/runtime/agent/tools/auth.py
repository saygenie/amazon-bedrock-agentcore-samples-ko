# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""AgentCore Identity용 인증 데코레이터.

이 모듈은 공식 bedrock_agentcore.identity.auth 데코레이터의 대안으로
사용자 지정 requires_access_token 데코레이터를 제공한다.
https://github.com/aws/bedrock-agentcore-sdk-python/blob/main/src/bedrock_agentcore/identity/auth.py
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-authentication.html

공식 데코레이터를 직접 사용하지 않는 이유:
- 공식 데코레이터는 workload_access_token을 가져오기 위해 contextvars
  (BedrockAgentCoreContext)에 의존하므로 서버로 BedrockAgentCoreApp을 사용해야 한다.
- 이 구현은 workload_access_token을 명시적 파라미터로 받으므로 암시적 컨텍스트 없이
  FastAPI, Starlette 등 어떤 서버 프레임워크에서도 사용할 수 있다.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, Literal

from bedrock_agentcore.services.identity import IdentityClient, TokenPoller

logger = logging.getLogger(__name__)


def requires_access_token(
    *,
    provider_name: str,
    scopes: list[str],
    auth_flow: Literal["M2M", "USER_FEDERATION"],
    workload_access_token: str | None = None,
    session_binding_url: str | None = None,
    on_auth_url: Callable[[str], Any] | None = None,
    force_authentication: bool = False,
    token_poller: TokenPoller | None = None,
    custom_state: str | None = None,
    custom_parameters: dict[str, str] | None = None,
    into: str = "access_token",
    region: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """명시적 워크로드 토큰을 사용하여 OAuth2 액세스 토큰을 가져온다.

    인수:
        provider_name: 자격 증명 공급자 이름
        scopes: 요청할 OAuth2 범위
        auth_flow: 인증 흐름 유형("M2M" 또는 "USER_FEDERATION")
        workload_access_token: 컨텍스트가 아닌 명시적으로 전달된 워크로드 액세스 토큰
        session_binding_url: 세션 바인딩을 완료하는 고객 관리형 서비스를 가리키는 Session Binding URL
        on_auth_url: 사용자 권한 부여가 필요할 때 권한 부여 URL과 함께 호출되는 핸들러
        force_authentication: 재인증 강제 여부
        token_poller: 사용자 지정 토큰 폴러 구현
        custom_state: 콜백 검증용 상태
        custom_parameters: 추가 OAuth 파라미터
        into: 토큰을 주입할 파라미터 이름
        region: AWS 리전

    반환값:
        데코레이터 함수

    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        client = IdentityClient(region)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                if not workload_access_token:
                    raise ValueError("workload_access_token is required")
                token = await client.get_token(
                    provider_name=provider_name,
                    agent_identity_token=workload_access_token,
                    scopes=scopes,
                    auth_flow=auth_flow,
                    callback_url=session_binding_url,
                    on_auth_url=on_auth_url,
                    force_authentication=force_authentication,
                    token_poller=token_poller,
                    custom_state=custom_state,
                    custom_parameters=custom_parameters,
                )
                kwargs[into] = token
                return await func(*args, **kwargs)
            except Exception:
                logger.exception("Error in requires_access_token decorator")
                raise

        return wrapper

    return decorator
