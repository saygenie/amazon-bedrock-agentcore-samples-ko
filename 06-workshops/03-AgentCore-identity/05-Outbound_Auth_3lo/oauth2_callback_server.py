"""
Amazon Bedrock AgentCore Identity에서 Authorization Code 흐름(3LO)을 사용하는 샘플 OAuth2 콜백 서버

이 모듈은 AgentCore Identity의 OAuth2 3-legged(3LO) 인증 흐름을 처리하는 로컬 콜백 서버를 구현한다.
사용자 브라우저, Google 및 GitHub 같은 외부 OAuth 공급자, AgentCore Identity 서비스 사이에서
중개자 역할을 한다.

주요 구성 요소:
- localhost:9090에서 실행되는 FastAPI 서버
- 외부 공급자의 OAuth2 콜백 리디렉션 처리
- 사용자 토큰 저장 및 세션 완료 관리
- 준비 상태 확인을 위한 상태 확인 엔드포인트 제공

사용 맥락:
이 서버는 인증된 사용자를 대신하여 Google Calendar나 GitHub 저장소 같은 외부 리소스에 접근해야 하는
AgentCore Runtime의 에이전트와 함께 사용한다. 일반적인 흐름은 다음과 같다.
1. 에이전트가 외부 리소스에 대한 접근 요청
2. 사용자가 동의할 수 있도록 OAuth 공급자로 리디렉션
3. 공급자가 이 콜백 서버로 다시 리디렉션
4. 서버가 AgentCore Identity를 사용하여 인증 흐름 완료
"""

import time
import uvicorn
import logging
import argparse
import requests
import json

from datetime import timedelta
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from bedrock_agentcore.services.identity import IdentityClient, UserTokenIdentifier

# OAuth2 콜백 서버 설정 상수
OAUTH2_CALLBACK_SERVER_PORT = 9090  # 콜백 서버가 수신하는 포트
PING_ENDPOINT = "/ping"  # 상태 확인 엔드포인트
OAUTH2_CALLBACK_ENDPOINT = "/oauth2/callback"  # 공급자 리디렉션용 OAuth2 콜백 엔드포인트
USER_IDENTIFIER_ENDPOINT = "/userIdentifier/token"  # 사용자 토큰 식별자 저장 엔드포인트

logger = logging.getLogger(__name__)


def _is_workshop_studio() -> bool:
    """
    SageMaker Workshop Studio 환경에서 실행 중인지 확인한다.

    반환값:
        bool: Workshop Studio에서 실행 중이면 True, 아니면 False
    """
    try:
        with open("/opt/ml/metadata/resource-metadata.json", "r") as file:
            json.load(file)
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def get_oauth2_callback_base_url() -> str:
    """
    외부 OAuth 공급자 리디렉션에 사용할 브라우저 접근 가능 기본 URL을 가져온다.

    GitHub이나 Google 같은 외부 OAuth 공급자가 리디렉션할 URL이다.
    OAuth 세션 바인딩이 작동하려면 사용자 브라우저에서 이 URL에 접근할 수 있어야 한다.

    환경 감지:
    - Workshop Studio: SageMaker 프록시 URL 반환(https://domain.studio.sagemaker.aws/proxy/9090)
    - 로컬 개발: localhost URL 반환(http://localhost:9090)

    반환값:
        str: OAuth 콜백에 사용할 브라우저 접근 가능 기본 URL

    용도:
        이 URL은 다음에 사용한다.
        1. 워크로드 자격 증명의 allowedResourceOauth2ReturnUrls 등록
        2. 에이전트 데코레이터의 callback_url 파라미터
        3. 사용자 브라우저에서 콜백 서버에 연결해야 하는 모든 시나리오
    """
    if not _is_workshop_studio():
        base_url = f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}"
        logger.info(
            f"External OAuth callback base URL (local): {base_url}"
        )  # codeql[py/clear-text-logging-sensitive-data]
        return base_url

    try:
        import boto3

        with open("/opt/ml/metadata/resource-metadata.json", "r") as file:
            data = json.load(file)
            domain_id = data["DomainId"]
            space_name = data["SpaceName"]

        sagemaker_client = boto3.client("sagemaker")
        response = sagemaker_client.describe_space(DomainId=domain_id, SpaceName=space_name)
        base_url = response["Url"] + f"/proxy/{OAUTH2_CALLBACK_SERVER_PORT}"
        logger.info(
            f"External OAuth callback base URL (SageMaker): {base_url}"
        )  # codeql[py/clear-text-logging-sensitive-data]
        return base_url
    except Exception as e:
        logger.warning(f"Error getting SageMaker proxy URL: {e}. Falling back to localhost")
        return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}"


def _get_internal_base_url() -> str:
    """
    내부 통신(notebook/Streamlit → 콜백 서버)에 사용할 기본 URL을 가져온다.

    notebook/Streamlit과 OAuth2 콜백 서버는 같은 환경에서 실행되므로 항상 localhost이다.
    로컬 개발에서는 같은 시스템, SageMaker에서는 같은 컨테이너에서 실행된다.

    반환값:
        str: 서버 간 통신에 사용할 내부 기본 URL(항상 localhost)

    용도:
        이 URL은 다음에 사용한다.
        1. 사용자 토큰 저장(POST /userIdentifier/token)
        2. 상태 확인(GET /ping)
        3. 동일한 실행 환경 내부의 모든 통신
    """
    return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}"


class OAuth2CallbackServer:
    """
    AgentCore Identity의 3-legged OAuth 흐름을 처리하는 OAuth2 콜백 서버.

    사용자가 권한을 부여한 후 Google이나 GitHub 같은 외부 OAuth 공급자가 리디렉션하는
    로컬 콜백 엔드포인트 역할을 한다. AgentCore Identity 서비스와 연동하여 OAuth 흐름 완료를 관리한다.

    서버가 관리하는 항목:
    - API 통신용 AgentCore Identity 클라이언트
    - 세션 바인딩용 사용자 토큰 식별자
    - 라우트가 설정된 FastAPI 애플리케이션
    """

    def __init__(self, region: str):
        """
        OAuth2 콜백 서버를 초기화한다.

        인수:
            region (str): AgentCore Identity 서비스가 배포된 AWS 리전
        """
        # 지정한 리전의 AgentCore Identity 클라이언트 초기화
        self.identity_client = IdentityClient(region=region)

        # OAuth 세션을 특정 사용자와 바인딩하는 데 사용할 사용자 토큰 식별자 저장소
        # OAuth 흐름이 시작되기 전에 USER_IDENTIFIER_ENDPOINT를 통해 설정
        self.user_token_identifier = None

        # FastAPI 애플리케이션 인스턴스 생성
        self.app = FastAPI()

        # 모든 HTTP 라우트 설정
        self._setup_routes()

    def _setup_routes(self):
        """
        OAuth2 콜백 서버의 FastAPI 라우트를 설정한다.

        다음 세 엔드포인트를 설정한다.
        1. POST /userIdentifier/token - 세션 바인딩용 사용자 토큰 식별자 저장
        2. GET /ping - 상태 확인 엔드포인트
        3. GET /oauth2/callback - 공급자 리디렉션용 OAuth2 콜백 핸들러
        """

        @self.app.post(USER_IDENTIFIER_ENDPOINT)
        async def _store_user_token(user_token_identifier_value: UserTokenIdentifier):
            """
            Store user token identifier for OAuth session binding.

            This endpoint is called before initiating the OAuth flow to associate
            the upcoming OAuth session with a specific user. The user token identifier
            is typically derived from the user's JWT token from inbound authentication.

            Args:
                user_token_identifier_value: UserTokenIdentifier object containing
                                           user identification information
            """
            self.user_token_identifier = user_token_identifier_value

        @self.app.get(PING_ENDPOINT)
        async def _handle_ping():
            """
            Health check endpoint to verify server readiness.

            Returns:
                dict: Simple status response indicating server is operational
            """
            return {"status": "success"}

        @self.app.get(OAUTH2_CALLBACK_ENDPOINT)
        async def _handle_oauth2_callback(session_id: str):
            """
            Handle OAuth2 callback from external providers.

            This is the core endpoint that external OAuth providers (like Google, Github) redirect to
            after user authorization. It receives the session_id parameter and uses it to
            complete the OAuth flow with AgentCore Identity.

            OAuth Flow Context:
            1. User clicks authorization URL generated by AgentCore Identity
            2. User authorizes access on external provider (e.g., Google, Github)
            3. Provider redirects to this callback with session_id
            4. This handler completes the flow by calling AgentCore Identity

            Args:
                session_id (str): Session identifier from OAuth provider redirect

            Returns:
                dict: Success message indicating OAuth flow completion

            Raises:
                HTTPException: If session_id is missing or user_token_identifier not set
            """
            # session_id 파라미터가 있는지 검증
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing session_id query parameter",
                )

            # 사용자 토큰 식별자가 미리 저장되었는지 확인
            # OAuth 세션을 올바른 사용자와 바인딩하는 데 필요
            if not self.user_token_identifier:
                logger.error("No configured user token identifier")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal Server Error",
                )

            # AgentCore Identity 서비스를 호출하여 OAuth 흐름 완료
            # OAuth 세션을 사용자와 연결하고 액세스 토큰을 가져옴
            self.identity_client.complete_resource_token_auth(
                session_uri=session_id, user_identifier=self.user_token_identifier
            )

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
        설정된 FastAPI 애플리케이션 인스턴스를 가져온다.

        반환값:
            FastAPI: 모든 라우트가 설정된 애플리케이션
        """
        return self.app


def get_oauth2_callback_url() -> str:
    """
    외부 공급자에 사용할 브라우저 접근 가능 전체 OAuth2 콜백 URL을 생성한다.

    이 URL은 워크로드 자격 증명에 등록되며, OAuth 권한 부여 후 AgentCore가 사용자 브라우저를
    리디렉션하는 데 사용한다. 사용자 브라우저에서 접근할 수 있어야 한다.

    환경별 동작:
    - 로컬 개발: http://localhost:9090/oauth2/callback 반환
    - SageMaker Studio: https://domain.studio.sagemaker.aws/proxy/9090/oauth2/callback 반환

    반환값:
        str: 엔드포인트 경로를 포함한 브라우저 접근 가능 전체 콜백 URL

    용도:
        이 URL은 다음 경우에 사용한다.
        1. 워크로드 자격 증명에 allowedResourceOauth2ReturnUrls 등록
        2. @requires_access_token 데코레이터에 callback_url 전달
        3. AgentCore가 브라우저를 콜백으로 리디렉션해야 하는 모든 시나리오
    """
    base_url = get_oauth2_callback_base_url()
    return f"{base_url}{OAUTH2_CALLBACK_ENDPOINT}"


def store_token_in_oauth2_callback_server(user_token_value: str):
    """
    실행 중인 OAuth2 콜백 서버에 사용자 토큰 식별자를 저장한다(내부 통신).

    OAuth 흐름을 시작하기 전에 콜백 서버에 POST 요청을 보내 사용자의 토큰 식별자를 저장한다.
    이 토큰 식별자는 OAuth 세션을 특정 사용자와 바인딩하는 데 사용한다.

    동일한 실행 환경(같은 시스템 또는 컨테이너) 내부의 서버 간 통신이므로
    항상 localhost인 내부 기본 URL을 사용한다.

    인수:
        user_token_value (str): OAuth 흐름에서 사용자를 식별하는 데 사용하는 사용자 토큰
                                (일반적으로 Cognito의 JWT 액세스 토큰)

    사용 맥락:
        콜백 서버가 OAuth 세션의 사용자를 알 수 있도록 OAuth 흐름을 시작하기 전에 호출한다.
        다중 사용자 시나리오에서 올바른 세션 바인딩을 위해 반드시 필요하다.

    예:
        # OAuth가 필요한 에이전트를 호출하기 전
        bearer_token = reauthenticate_user(client_id)
        store_token_in_oauth2_callback_server(bearer_token)
    """
    if user_token_value:
        base_url = _get_internal_base_url()
        requests.post(
            f"{base_url}{USER_IDENTIFIER_ENDPOINT}",
            json={"user_token": user_token_value},
            timeout=2,
        )
    else:
        logger.error("Ignoring: invalid user_token provided...")


def wait_for_oauth2_server_to_be_ready(
    duration: timedelta = timedelta(seconds=40),
) -> bool:
    """
    OAuth2 콜백 서버가 준비되어 응답할 때까지 기다린다(내부 통신).

    서버의 상태 확인 엔드포인트가 성공적으로 응답하거나 제한 시간에 도달할 때까지 폴링한다.
    OAuth 흐름을 시작하기 전에 서버가 준비되었는지 확인하는 데 필요하다.

    동일한 실행 환경(같은 시스템 또는 컨테이너) 내부의 서버 간 통신이므로
    항상 localhost인 내부 기본 URL을 사용한다.

    인수:
        duration (timedelta): 서버가 준비되기를 기다릴 최대 시간
                              기본값은 40초

    반환값:
        bool: 제한 시간 내에 서버가 준비되면 True, 아니면 False

    사용 맥락:
        OAuth2 콜백 서버 프로세스를 시작한 뒤, OAuth 흐름을 트리거할 수 있는 에이전트 호출을
        진행하기 전에 서버가 OAuth 콜백을 처리할 준비가 되었는지 확인하기 위해 호출한다.

    예:
        # 서버 프로세스 시작
        server_process = subprocess.Popen([...])

        # 준비될 때까지 대기
        if wait_for_oauth2_server_to_be_ready():
            # OAuth를 사용하는 작업 진행
            invoke_agent()
        else:
            # 서버 시작 실패 처리
            server_process.terminate()
    """
    logger.info("Waiting for OAuth2 callback server to be ready...")
    base_url = _get_internal_base_url()
    timeout_in_seconds = duration.seconds

    start_time = time.time()
    while time.time() - start_time < timeout_in_seconds:
        try:
            # 서버의 상태 확인 엔드포인트 호출
            response = requests.get(
                f"{base_url}{PING_ENDPOINT}",
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

        # 계속 대기 중임을 보여 주기 위해 10초마다 진행 상황 기록
        if elapsed % 10 == 0 and elapsed > 0:
            logger.info(f"Still waiting... ({elapsed}/{timeout_in_seconds}s)")

    logger.error(f"Timeout: OAuth2 callback server not ready after {timeout_in_seconds} seconds")
    return False


def main():
    """
    OAuth2 콜백 서버를 독립 실행형 애플리케이션으로 실행하는 기본 진입점.

    명령줄 인수를 파싱하고 uvicorn으로 FastAPI 서버를 시작한다.
    서버는 지정한 AWS 리전의 OAuth2 콜백을 처리한다.

    환경별 호스트 바인딩:
    - 로컬 개발: 보안을 위해 127.0.0.1에만 바인딩
    - SageMaker Studio: 프록시가 서버에 연결할 수 있도록 0.0.0.0에 바인딩

    명령줄 사용법:
        python oauth2_callback_server.py --region us-east-1

    서버는 수동으로 종료할 때까지 실행되며 지정한 리전의 모든 AgentCore 에이전트에 대한
    OAuth2 콜백을 처리한다.
    """
    parser = argparse.ArgumentParser(description="OAuth2 Callback Server")
    parser.add_argument("-r", "--region", type=str, required=True, help="AWS Region (e.g. us-east-1)")

    args = parser.parse_args()
    oauth2_callback_server = OAuth2CallbackServer(region=args.region)

    # 환경에 따라 호스트 바인딩 결정
    # SageMaker에서는 프록시가 서버에 연결할 수 있도록 0.0.0.0에 바인딩
    # 로컬 개발에서는 보안을 위해 127.0.0.1에 바인딩
    host = "0.0.0.0" if _is_workshop_studio() else "127.0.0.1"  # nosec B104
    base_url = get_oauth2_callback_base_url()

    logger.info(
        f"Starting OAuth2 callback server on {host}:{OAUTH2_CALLBACK_SERVER_PORT}"  # codeql[py/clear-text-logging-sensitive-data]
    )
    logger.info(
        f"External callback URL: {base_url}{OAUTH2_CALLBACK_ENDPOINT}"
    )  # codeql[py/clear-text-logging-sensitive-data]

    # uvicorn으로 FastAPI 서버 시작
    uvicorn.run(
        oauth2_callback_server.get_app(),
        host=host,
        port=OAUTH2_CALLBACK_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
