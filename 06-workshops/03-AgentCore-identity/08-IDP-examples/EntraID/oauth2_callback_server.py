"""
Amazon Bedrock AgentCore Identity와 Authorization Code 흐름을 사용하는 OAuth2 콜백 서버 샘플입니다.

이 모듈은 AgentCore Identity의 OAuth2 3-legged(3LO) 인증 흐름을 처리하는 로컬 콜백 서버를 구현합니다.
사용자의 브라우저, 외부 OAuth 공급자(예: Google, Entra 등), AgentCore Identity 서비스 사이에서
중개자 역할을 합니다.

주요 구성 요소:
- 로컬에서 실행되는 FastAPI 서버
- 외부 공급자의 OAuth2 콜백 리디렉션 처리
- 사용자 식별자 저장 및 세션 완료 관리
- 준비 상태 확인을 위한 상태 확인 엔드포인트 제공

사용 맥락:
이 서버는 인증된 사용자를 대신해 외부 리소스(예: Google Calendar, Microsoft Entra)에 액세스해야 하는
AgentCore Runtime의 에이전트와 함께 사용됩니다.

일반적인 흐름:
  1. 에이전트가 외부 리소스에 대한 액세스를 요청합니다.
  2. 사용자가 동의를 위해 OAuth 공급자로 리디렉션됩니다.
  3. 공급자가 이 콜백 서버로 다시 리디렉션합니다.
  4. 서버가 AgentCore Identity를 통해 인증 흐름을 완료합니다.
"""

import time
import json
import uvicorn
import logging
import argparse
import requests

from typing import Annotated, Optional
from datetime import datetime, timedelta, timezone
from fastapi import Cookie, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from bedrock_agentcore.services.identity import IdentityClient, UserIdIdentifier


# OAuth2 콜백 서버 구성 상수
OAUTH2_CALLBACK_SERVER_PORT = 9090  # 콜백 서버가 수신 대기하는 포트
PING_ENDPOINT = "/ping"  # 상태 확인 엔드포인트
OAUTH2_CALLBACK_ENDPOINT = "/oauth2/callback"  # 공급자 리디렉션을 위한 OAuth2 콜백 엔드포인트
USER_IDENTIFIER_ENDPOINT = "/userIdentifier/userId"  # userId 식별자를 저장하는 엔드포인트

logger = logging.getLogger(__name__)


class OAuth2CallbackServer:
    """
    AgentCore Identity를 사용하는 3-legged OAuth 흐름의 OAuth2 콜백 서버입니다.

    이 서버는 사용자 인증 후 외부 OAuth 공급자(예: Google, GitHub)가 리디렉션하는
    로컬 콜백 엔드포인트 역할을 합니다. AgentCore Identity 서비스와 연동하여
    OAuth 흐름의 완료를 관리합니다.

    서버가 유지하는 항목:
    - API 통신을 위한 AgentCore Identity 클라이언트
    - 세션 바인딩을 위한 UserId 식별자
    - 라우트가 구성된 FastAPI 애플리케이션
    """

    def __init__(self, region: str):
        """
        OAuth2 콜백 서버를 초기화합니다.

        인수:
            region (str): AgentCore Identity 서비스가 배포된 AWS 리전
        """
        # 지정된 리전의 AgentCore Identity 클라이언트 초기화
        self.identity_client = IdentityClient(region=region)
        self.user_id_identifier = None

        self.app = FastAPI()

        # 모든 HTTP 라우트 구성
        self._setup_routes()

    def _setup_routes(self):
        """
        OAuth2 콜백 서버의 FastAPI 라우트를 구성합니다.

        다음 세 가지 엔드포인트를 설정합니다.
        1. POST /userIdentifier/userId - 세션 바인딩을 위한 userId 식별자 저장
        2. GET /ping - 상태 확인 엔드포인트
        3. GET /oauth2/callback - 공급자 리디렉션을 위한 OAuth2 콜백 핸들러
        """

        @self.app.post(USER_IDENTIFIER_ENDPOINT)
        async def _store_user_id(
            user_id_identifier_value: UserIdIdentifier,
        ) -> JSONResponse:
            """
            OAuth 세션 바인딩을 위한 userId 식별자를 저장합니다.

            시작될 OAuth 세션을 특정 사용자와 연결하기 위해 OAuth 흐름을 시작하기 전에
            이 엔드포인트를 호출합니다.

            인수:
                user_id_identifier_value: 사용자 식별 정보가 포함된 UserIdIdentifier 객체
            """
            if not user_id_identifier_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user_identifier value",
                )

            self.user_id_identifier = user_id_identifier_value
            response = JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success"})
            response.set_cookie(
                key="user_id_identifier",
                value=user_id_identifier_value.user_id,
                secure=True,
                httponly=True,
                expires=datetime.now(timezone.utc) + timedelta(hours=1),
            )

            return response

        @self.app.get(PING_ENDPOINT)
        async def _handle_ping() -> JSONResponse:
            """
            서버의 준비 상태를 확인하는 상태 확인 엔드포인트입니다.

            반환값:
                dict: 서버가 작동 중임을 나타내는 간단한 상태 응답
            """
            return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "success"})

        def _try_parse_identity_sdk_config() -> Optional[str]:
            try:
                with open(".agentcore.json", encoding="utf-8") as agent_config:
                    config = json.load(agent_config)
                    return config.get("user_id")
            except Exception as e:
                logger.debug(f"Failed to parse identity SDK config from '.agentcore.json': {repr(e)}")
                return None

        def _get_user_identifier(
            user_id_identifier: Optional[str] = None,
        ) -> Optional[UserIdIdentifier]:
            """
            대체 로직을 적용해 사용자 식별자를 가져옵니다.

            우선순위:
            1. 브라우저 쿠키 값(매개변수로 전달)
            2. 서버 메모리 값(인스턴스 속성)
            3. Identity SDK 구성 파싱

            인수:
                user_id_identifier: 브라우저 쿠키의 선택적 사용자 ID

            반환값:
                UserIdIdentifier 인스턴스. 유효한 식별자가 없으면 None
            """
            if user_id_identifier:
                return UserIdIdentifier(user_id=user_id_identifier)

            if self.user_id_identifier:
                return self.user_id_identifier

            user_id = _try_parse_identity_sdk_config()
            if user_id:
                return UserIdIdentifier(user_id=user_id)

            return None

        @self.app.get(OAUTH2_CALLBACK_ENDPOINT)
        async def _handle_oauth2_callback(
            session_id: str, user_id_identifier: Annotated[str | None, Cookie()] = None
        ) -> HTMLResponse:
            """
            외부 공급자의 OAuth2 콜백을 처리합니다.

            사용자 인증 후 외부 OAuth 공급자(예: Google, GitHub)가 리디렉션하는 핵심 엔드포인트입니다.
            session_id 매개변수를 받아 AgentCore Identity를 통한 OAuth 흐름을 완료하는 데 사용합니다.

            OAuth 흐름:
            1. 사용자가 AgentCore Identity에서 생성한 인증 URL을 클릭합니다.
            2. 사용자가 외부 공급자(예: Google, GitHub)에서 액세스를 승인합니다.
            3. 공급자가 session_id와 함께 이 콜백으로 리디렉션합니다.
            4. 이 핸들러가 AgentCore Identity를 호출하여 흐름을 완료합니다.

            인수:
                session_id (str): OAuth 공급자 리디렉션의 세션 식별자
                user_id_identifier (str): 브라우저 쿠키에 저장된 UserId

            반환값:
                dict: OAuth 흐름 완료를 나타내는 성공 메시지

            예외:
                HTTPException: session_id가 없거나 user_id_identifier가 설정되지 않은 경우
            """
            # session_id 매개변수가 있는지 검증
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing session_id url query parameter",
                )

            # 브라우저 쿠키 값이 있으면 사용하고, 없으면 서버 메모리 또는 구성에 저장된 값 사용
            user_identifier = _get_user_identifier(user_id_identifier)

            # OAuth 세션을 올바른 사용자에게 바인딩하는 데 필요
            if not user_identifier:
                logger.error("No configured user identifier")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No user identifier configured",
                )

            # AgentCore Identity 서비스를 호출하여 OAuth 흐름 완료
            # OAuth 세션을 사용자와 연결하고 액세스 토큰을 가져옴
            self.identity_client.complete_resource_token_auth(session_uri=session_id, user_identifier=user_identifier)

            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>OAuth2 Success</title>
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                        height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        font-family: Arial, sans-serif;
                        background-color: #f5f5f5;
                    }
                    .container {
                        text-align: center;
                        padding: 2rem;
                        background-color: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    }
                    h1 {
                        color: #28a745;
                        margin: 0;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Completed OAuth2 3LO flow successfully</h1>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=200)

    def get_app(self) -> FastAPI:
        """
        구성된 FastAPI 애플리케이션 인스턴스를 가져옵니다.

        반환값:
            FastAPI: 모든 라우트가 설정된 애플리케이션
        """
        return self.app


def get_oauth2_callback_url() -> str:
    """
    외부 공급자용 전체 OAuth2 콜백 URL을 생성합니다.

    이 URL은 외부 OAuth 공급자(예: Google, GitHub)에 리디렉션 URI로 등록됩니다.
    사용자 인증 후 공급자는 session_id 매개변수와 함께 사용자의 브라우저를 이 URL로
    리디렉션합니다.

    반환값:
        str: 전체 콜백 URL(예: "http://localhost:9090/oauth2/callback")

    사용처:
        일반적으로 다음 작업에 이 URL을 사용합니다.
        1. AgentCore Identity에서 OAuth2 자격 증명 공급자 구성
        2. 외부 OAuth 공급자에 리디렉션 URI 등록
        3. 워크로드 자격 증명에 허용된 반환 URL 설정
    """
    return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{OAUTH2_CALLBACK_ENDPOINT}"


def store_user_id_in_oauth2_callback_server(user_id_value: str):
    if user_id_value:
        response = requests.post(
            f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{USER_IDENTIFIER_ENDPOINT}",
            json={"user_id": user_id_value},
            timeout=2,
        )
        response.raise_for_status()
    else:
        logger.error("Ignoring: invalid user_id provided...")


def wait_for_oauth2_server_to_be_ready(
    duration: timedelta = timedelta(seconds=40),
) -> bool:
    """
    OAuth2 콜백 서버가 준비되고 응답할 때까지 기다립니다.

    이 함수는 서버가 정상 응답하거나 제한 시간에 도달할 때까지 상태 확인 엔드포인트를
    폴링합니다. OAuth 흐름을 시작하기 전에 서버가 준비되었는지 확인하는 데 필요합니다.

    인수:
        duration (timedelta): 서버 준비를 기다리는 최대 시간
                              기본값은 40초

    반환값:
        bool: 제한 시간 내에 서버가 준비되면 True, 그렇지 않으면 False

    사용 맥락:
        OAuth2 콜백 서버 프로세스를 시작한 후 호출합니다. OAuth 흐름을 유발할 수 있는
        에이전트 호출을 진행하기 전에 서버가 OAuth 콜백을 처리할 준비가 되었는지 확인합니다.

    예:
        # 서버 프로세스 시작
        server_process = subprocess.Popen([...])

        # 준비될 때까지 대기
        if wait_for_oauth2_server_to_be_ready():
            # OAuth 지원 작업 진행
            invoke_agent()
        else:
            # 서버 시작 실패 처리
            server_process.terminate()
    """
    logger.info("Waiting for OAuth2 callback server to be ready...")
    timeout_in_seconds = duration.seconds

    start_time = time.time()
    while time.time() - start_time < timeout_in_seconds:
        try:
            # 서버의 상태 확인 엔드포인트 호출
            response = requests.get(
                f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{PING_ENDPOINT}",
                timeout=2,
            )
            if response.status_code == status.HTTP_200_OK:
                logger.info("OAuth2 callback server is ready!")
                return True
        except requests.exceptions.RequestException:
            # 서버가 아직 준비되지 않았으므로 계속 대기
            pass

        time.sleep(2)
        elapsed = int(time.time() - start_time)

        # 아직 대기 중임을 알리기 위해 10초마다 진행 상황 기록
        if elapsed % 10 == 0 and elapsed > 0:
            logger.info(f"Still waiting... ({elapsed}/{timeout_in_seconds}s)")

    logger.error(f"Timeout: OAuth2 callback server not ready after {timeout_in_seconds} seconds")
    return False


def main():
    """
    OAuth2 콜백 서버를 독립 실행형 애플리케이션으로 실행하는 기본 진입점입니다.

    명령줄 인수를 파싱하고 uvicorn을 사용해 FastAPI 서버를 시작합니다.
    서버는 localhost:9090에서 실행되며 지정된 AWS 리전의 OAuth2 콜백을 처리합니다.

    명령줄 사용법:
        python oauth2_callback_server.py --region us-east-1

    서버는 수동으로 종료할 때까지 실행되며, 지정된 리전의 모든 AgentCore 에이전트에 대한
    OAuth2 콜백을 처리합니다.
    """
    parser = argparse.ArgumentParser(description="OAuth2 Callback Server")
    parser.add_argument("-r", "--region", type=str, required=True, help="AWS Region (e.g. us-east-1)")

    args = parser.parse_args()
    oauth2_callback_server = OAuth2CallbackServer(region=args.region)

    # uvicorn을 사용해 FastAPI 서버 시작
    # 보안을 위해 서버는 localhost에서만 실행되며 외부에 노출되지 않음
    uvicorn.run(
        oauth2_callback_server.get_app(),
        host="127.0.0.1",
        port=OAUTH2_CALLBACK_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
