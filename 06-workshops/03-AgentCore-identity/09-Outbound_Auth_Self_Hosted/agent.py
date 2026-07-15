import json
import os
import sys
import base64
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import boto3

# ---------------------------------------------------------------------------
# 설정 - 모든 값은 환경 변수로 재정의할 수 있음
# ---------------------------------------------------------------------------
REGION = os.environ.get("AWS_REGION", "us-east-1")
CREDENTIAL_PROVIDER = os.environ.get("CREDENTIAL_PROVIDER_NAME", "AgentCoreIdentityStandaloneProvider")
USER_ID = os.environ.get("AGENT_USER_ID", "quickstart-user")
CALLBACK_PORT = int(os.environ.get("CALLBACK_PORT", "8080"))
CALLBACK_URL = f"http://127.0.0.1:{CALLBACK_PORT}/callback"

# 컨트롤 플레인 클라이언트는 자격 증명 공급자와 워크로드 자격 증명 같은
# 수명이 긴 리소스를 관리
control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)

# 데이터 플레인 클라이언트는 워크로드 토큰 발급, OAuth 흐름 시작,
# 액세스 토큰 가져오기 같은 런타임 작업을 처리
data_client = boto3.client("bedrock-agentcore", region_name=REGION)

# 공유 플래그 - 사용자가 브라우저에서 권한 부여를 완료하면 콜백 핸들러가
# 이 값을 True로 설정하여 에이전트가 폴링을 중지할 수 있게 함
authorization_complete = threading.Event()


# ---------------------------------------------------------------------------
# 웹 애플리케이션(세션 바인딩 핸들러)
#
# 이 최소 HTTP 서버는 OAuth 콜백 리디렉션을 처리함. 사용자가 브라우저에서
# 권한을 부여하면 AgentCore Identity가 session_id와 함께 이곳으로 리디렉션함.
# 핸들러는 completeResourceTokenAuth를 호출하여 OAuth 세션을 사용자와 바인딩하므로
# 에이전트가 나중에 액세스 토큰을 가져올 수 있음.
#
# 프로덕션에서는 실제 웹 애플리케이션(예: https://myagentapp.com)이 이 역할을 담당함.
# 로컬 개발에서는 127.0.0.1의 일반 HTTP로 충분함.
# ---------------------------------------------------------------------------
class AppHandler(BaseHTTPRequestHandler):
    """AgentCore Identity의 OAuth 2.0 세션 바인딩 콜백을 처리한다."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        # AgentCore Identity는 콜백 URL에 ?session_id=...를 추가
        session_id = parse_qs(parsed.query).get("session_id", [None])[0]
        if not session_id:
            self._respond(400, "<h1>Error</h1><p>Missing session_id</p>")
            return

        try:
            # 사용자가 권한을 부여했음을 AgentCore Identity에 알려 OAuth 세션을
            # 이 사용자 ID와 바인딩하는 핵심 호출
            data_client.complete_resource_token_auth(
                sessionUri=session_id,
                userIdentifier={"userId": USER_ID},
            )
            self._respond(
                200,
                "<h1>Authorization Complete!</h1><p>Token stored in AgentCore Identity. You can close this tab.</p>",
            )
            print(f"[INFO]  Session bound for session_id={session_id[:20]}...")
            # 에이전트의 폴링 루프에 권한 부여 완료를 알림
            authorization_complete.set()
        except Exception as exc:
            self._respond(500, f"<h1>Error</h1><pre>{exc}</pre>")

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<html><body>{body}</body></html>".encode())

    def log_message(self, format, *args):
        pass  # 기본 HTTP 요청 로깅 억제


def start_app_server():
    """로컬 콜백 서버를 백그라운드에서 시작한다."""
    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), AppHandler)
    print(f"[INFO]  App server listening on http://127.0.0.1:{CALLBACK_PORT}/callback")
    server.serve_forever()


# ---------------------------------------------------------------------------
# 에이전트 로직
# ---------------------------------------------------------------------------
def ensure_workload_identity(name="standalone-agent-identity"):
    """워크로드 자격 증명이 있는지 확인하고, 없으면 생성한다."""
    try:
        control_client.get_workload_identity(name=name)
        print(f"[INFO]  Workload identity '{name}' exists - reusing.")
    except control_client.exceptions.ResourceNotFoundException:
        control_client.create_workload_identity(name=name)
        print(f"[INFO]  Workload identity '{name}' created.")
    return name


def decode_jwt(token):
    """표시 목적으로 서명을 검증하지 않고 JWT 페이로드를 디코딩한다."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def run_agent():
    print("=" * 60)
    print("  AgentCore Identity - Local Agent")
    print("=" * 60)

    # A단계: 워크로드 자격 증명이 있는지 확인
    workload_name = ensure_workload_identity()

    # B단계: 수명이 짧은 워크로드 토큰 가져오기. 이 토큰은 최종 사용자가 아닌
    # 에이전트를 식별하며 OAuth 토큰을 요청하는 데 사용
    token = data_client.get_workload_access_token_for_user_id(
        workloadName=workload_name,
        userId=USER_ID,
    )["workloadAccessToken"]

    # C단계: AgentCore Identity에 OAuth 2.0 Authorization Code 흐름 시작 요청.
    # forceAuthentication=True이므로 캐시된 토큰이 있어도 사용자가 방문해야 하는
    # authorizationUrl을 항상 반환
    response = data_client.get_resource_oauth2_token(
        workloadIdentityToken=token,
        resourceCredentialProviderName=CREDENTIAL_PROVIDER,
        scopes=["openid", "profile", "email"],
        oauth2Flow="USER_FEDERATION",
        forceAuthentication=True,
        resourceOauth2ReturnUrl=CALLBACK_URL,
    )

    auth_url = response.get("authorizationUrl")
    session_uri = response.get("sessionUri")

    if auth_url:
        # 사용자의 기본 브라우저에서 권한 부여 URL 자동 열기
        print(f"\n  Opening your browser to authorize...\n\n  {auth_url}\n")
        webbrowser.open(auth_url)

        # 사용자가 직접 Enter를 누르게 하지 않고 콜백 핸들러가 권한 부여 완료를
        # 알릴 때까지 폴링
        print("  Waiting for you to complete authorization in the browser...")
        while not authorization_complete.wait(timeout=2):
            pass  # 2초 간격으로 계속 대기

        print("[INFO]  Authorization callback received.")

    # D단계: 새 워크로드 토큰 가져오기(사용자가 브라우저에서 권한을 부여하는 동안
    # 이전 토큰이 만료되었을 수 있음)
    token = data_client.get_workload_access_token_for_user_id(
        workloadName=workload_name,
        userId=USER_ID,
    )["workloadAccessToken"]

    # E단계: 실제 OAuth 액세스 토큰 가져오기. 이번에는 forceAuthentication=False이므로
    # 사용자가 브라우저 흐름을 완료했을 때 저장된 토큰을 AgentCore가 반환
    response = data_client.get_resource_oauth2_token(
        workloadIdentityToken=token,
        resourceCredentialProviderName=CREDENTIAL_PROVIDER,
        scopes=["openid", "profile", "email"],
        oauth2Flow="USER_FEDERATION",
        forceAuthentication=False,
        resourceOauth2ReturnUrl=CALLBACK_URL,
        sessionUri=session_uri,
    )

    access_token = response.get("accessToken")
    if not access_token:
        print("[ERROR] No access token received. Re-run and complete browser authorization.")
        sys.exit(1)

    # 이제 에이전트가 사용자의 OAuth 액세스 토큰을 보유함.
    # AgentCore Identity가 Authorization Code 교환, 토큰 저장, 세션 바인딩 등
    # 전체 OAuth 흐름을 처리하므로 OAuth 코드를 직접 작성할 필요가 없음.
    print()
    print("=" * 60)
    print("  Access token retrieved!")
    print()
    print("  Your agent now has consent to act on behalf of the user.")
    print("  AgentCore Identity handled the entire OAuth flow for you -")
    print("  no OAuth code required.")
    print("=" * 60)
    print()
    print(f"  Token preview: {access_token[:50]}...{access_token[-10:]}")

    claims = decode_jwt(access_token)
    if claims:
        print()
        print(json.dumps(claims, indent=2))

    print()
    print("[INFO]  Done. The OAuth flow completed successfully.")


if __name__ == "__main__":
    # 백그라운드 스레드에서 콜백 서버를 시작한 다음 에이전트 실행
    threading.Thread(target=start_app_server, daemon=True).start()
    run_agent()
