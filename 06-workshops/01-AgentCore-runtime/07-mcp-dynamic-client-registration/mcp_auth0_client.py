import asyncio
import httpx
import os
import threading
import time
import webbrowser
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# 요청 수준에서 httpx를 패치하여 User-Agent header 주입
# 이렇게 하면 OAuth discovery 호출을 포함한 모든 HTTP 요청에 User-Agent header가 포함됨
_original_httpx_request = httpx.Request.__init__


def _patched_httpx_request_init(self, method, url, *args, **kwargs):
    """모든 HTTP 요청에 User-Agent header를 주입하도록 패치한 Request.__init__입니다."""
    # Header를 가져오거나 생성
    headers = kwargs.get("headers")
    if headers is None:
        headers = {}
        kwargs["headers"] = headers

    # 필요한 경우 변경 가능한 dict로 변환
    if not isinstance(headers, dict):
        headers = dict(headers)
        kwargs["headers"] = headers

    # User-Agent가 없으면 주입(대소문자 구분 없이 확인)
    if "User-Agent" not in headers and "user-agent" not in headers:
        headers["User-Agent"] = "python-mcp-sdk/1.0 (BedrockAgentCore-Runtime)"

    # 원본 __init__ 호출
    _original_httpx_request(self, method, url, *args, **kwargs)


# MCP module을 import하기 전에 전역으로 패치 적용
httpx.Request.__init__ = _patched_httpx_request_init

# 이제 MCP module import - 패치된 httpx를 사용함
from mcp.client.auth import OAuthClientProvider, TokenStorage  # noqa: E402
from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.sse import sse_client  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken  # noqa: E402


class InMemoryTokenStorage(TokenStorage):
    """간단한 in-memory token storage 구현입니다."""

    def __init__(self):
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


class CallbackHandler(BaseHTTPRequestHandler):
    """OAuth callback을 캡처하는 간단한 HTTP handler입니다."""

    def __init__(self, request, client_address, server, callback_data):
        """Callback data storage로 초기화합니다."""
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def do_GET(self):
        """OAuth redirect의 GET 요청을 처리합니다."""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        # print(f'Query Params parsed: {query_params}')

        if "code" in query_params:
            self.callback_data["authorization_code"] = query_params["code"][0]
            self.callback_data["state"] = query_params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>setTimeout(() => window.close(), 2000);</script>
            </body>
            </html>
            """)
        elif "error" in query_params:
            self.callback_data["error"] = query_params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
            <html>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {query_params["error"][0]}</p>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """.encode()
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """기본 logging을 억제합니다."""
        pass


class CallbackServer:
    """OAuth callback을 처리하는 간단한 server입니다."""

    def __init__(self, port=3030):
        self.port = port
        self.server = None
        self.thread = None
        self.callback_data = {"authorization_code": None, "state": None, "error": None}

    def _create_handler_with_data(self):
        """Callback data에 액세스할 수 있는 handler class를 생성합니다."""
        callback_data = self.callback_data

        class DataCallbackHandler(CallbackHandler):
            def __init__(self, request, client_address, server):
                super().__init__(request, client_address, server, callback_data)

        return DataCallbackHandler

    def start(self):
        """Background thread에서 callback server를 시작합니다."""
        handler_class = self._create_handler_with_data()
        self.server = HTTPServer(("localhost", self.port), handler_class)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"🖥️  Started callback server on http://localhost:{self.port}")

    def stop(self):
        """Callback server를 중지합니다."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout=300):
        """Timeout 동안 OAuth callback을 기다립니다."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise Exception(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
        raise Exception("Timeout waiting for OAuth callback")

    def get_state(self):
        """수신한 state parameter를 가져옵니다."""
        return self.callback_data["state"]


def add_auth0_audience_parameter(authorization_url: str, audience: str) -> str:
    """
    Authorization URL에 Auth0 'audience' parameter를 추가합니다.

    Auth0에서는 사용할 API의 token 설정을 식별하기 위해 'audience' parameter가
    필요합니다. 이 값이 없으면 Auth0가 JWT 대신 opaque token 또는 JWE를 반환합니다.

    이 함수는 기존 query parameter(OAuth 'resource' parameter 포함)를 모두
    유지하면서 audience parameter를 올바르게 추가합니다.

    인수:
        authorization_url: OAuth flow의 authorization URL
        audience: Auth0 API 식별자(예: "runtime-api")

    반환:
        Audience parameter가 추가된 URL

    참고:
        https://auth0.com/docs/secure/tokens/access-tokens/get-access-tokens
    """
    # Audience가 아직 없는 Auth0 URL에만 적용
    if "auth0.com" not in authorization_url or "audience=" in authorization_url:
        return authorization_url

    # URL 및 query parameter 파싱
    parsed = urlparse(authorization_url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # Audience parameter 추가
    query_params["audience"] = [audience]

    # 새 parameter로 URL 재구성
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


class SimpleAuthClient:
    """Auth0 OAuth를 지원하는 간단한 MCP client입니다."""

    def __init__(
        self,
        server_url: str,
        transport_type: str = "streamable-http",
        auth0_audience: str | None = None,
    ):
        self.server_url = server_url
        self.transport_type = transport_type
        self.auth0_audience = auth0_audience
        self.session: ClientSession | None = None

    async def connect(self):
        """MCP server에 연결합니다."""
        print(f"🔗 Attempting to connect to {self.server_url}...")

        try:
            callback_server = CallbackServer(port=3030)
            callback_server.start()

            async def callback_handler() -> tuple[str, str | None]:
                """OAuth callback을 기다린 후 auth code와 state를 반환합니다."""
                print("⏳ Waiting for authorization callback...")
                try:
                    auth_code = callback_server.wait_for_callback(timeout=300)
                    return auth_code, callback_server.get_state()
                finally:
                    callback_server.stop()

            client_metadata_dict = {
                "client_name": "MCP Auth0 Client",
                "redirect_uris": ["http://localhost:3030/callback"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            }

            async def redirect_handler(authorization_url: str) -> None:
                """Auth0 audience parameter가 포함된 URL을 browser에서 여는 redirect handler입니다."""
                # 구성된 경우 Auth0 audience parameter 추가
                if self.auth0_audience:
                    authorization_url = add_auth0_audience_parameter(authorization_url, self.auth0_audience)

                webbrowser.open(authorization_url)

            print("\n🔧 Creating OAuth client provider...")
            # OAuth authentication handler 생성
            # 참고: User-Agent header를 주입하도록 httpx.AsyncClient가 전역으로 패치됨
            oauth_auth = OAuthClientProvider(
                server_url=self.server_url,
                client_metadata=OAuthClientMetadata.model_validate(client_metadata_dict),
                storage=InMemoryTokenStorage(),
                redirect_handler=redirect_handler,
                callback_handler=callback_handler,
            )
            print("🔧 OAuth client provider created successfully")

            # Transport type에 따라 auth handler가 포함된 transport 생성
            if self.transport_type == "sse":
                print("📡 Opening SSE transport connection with auth...")
                async with sse_client(
                    url=self.server_url,
                    auth=oauth_auth,
                    timeout=60,
                ) as (read_stream, write_stream):
                    await self._run_session(read_stream, write_stream, None)
            else:
                print("📡 Opening StreamableHTTP transport connection with auth...")
                async with streamablehttp_client(
                    url=self.server_url,
                    auth=oauth_auth,
                    timeout=timedelta(seconds=60),
                ) as (read_stream, write_stream, get_session_id):
                    await self._run_session(read_stream, write_stream, get_session_id)

        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            import traceback

            traceback.print_exc()

    async def _run_session(self, read_stream, write_stream, get_session_id):
        """주어진 stream으로 MCP session을 실행합니다."""
        print("🤝 Initializing MCP session...")
        async with ClientSession(read_stream, write_stream) as session:
            self.session = session
            print("⚡ Starting session initialization...")
            await session.initialize()
            print("✨ Session initialization complete!")

            print(f"\n✅ Connected to MCP server at {self.server_url}")
            if get_session_id:
                session_id = get_session_id()
                if session_id:
                    print(f"Session ID: {session_id}")

            # Interactive loop 실행
            # await self.interactive_loop()
            await self.invoke_mcp_server()

    async def list_tools(self):
        """Server에서 사용 가능한 tool을 나열합니다."""
        if not self.session:
            print("❌ Not connected to server")
            return

        try:
            result = await self.session.list_tools()
            if hasattr(result, "tools") and result.tools:
                print("\n📋 Available tools:")
                for i, tool in enumerate(result.tools, 1):
                    print(f"{i}. {tool.name}")
                    if tool.description:
                        print(f"   Description: {tool.description}")
                    print()
            else:
                print("No tools available")
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None):
        """특정 tool을 호출합니다."""
        if not self.session:
            print("❌ Not connected to server")
            return

        try:
            result = await self.session.call_tool(tool_name, arguments or {})
            print(f"\n🔧 Tool '{tool_name}' result:")
            if hasattr(result, "content"):
                for content in result.content:
                    if content.type == "text":
                        print(content.text)
                    else:
                        print(content)
            else:
                print(result)
        except Exception as e:
            print(f"❌ Failed to call tool '{tool_name}': {e}")

    async def invoke_mcp_server(self):
        """MCP server 및 tool을 호출합니다."""
        print("Showing available tools: ")
        await self.list_tools()

        tool_name = "add_numbers"
        arguments = {"a": 2, "b": 2}
        print(f"Invoking {tool_name} tool, with parameters {arguments}.")
        await self.call_tool(tool_name, arguments)

        tool_name = "multiply_numbers"
        arguments = {"a": 2, "b": 4}
        print(f"Invoking {tool_name} tool, with parameters {arguments}.")
        await self.call_tool(tool_name, arguments)

        tool_name = "greet_user"
        arguments = {"name": "Somebody"}
        print(f"Invoking {tool_name} tool, with parameters {arguments}.")
        await self.call_tool(tool_name, arguments)


async def main(agent_arn, base_endpoint, auth0_audience):
    """기본 entry point입니다."""

    if not agent_arn:
        print("❌ Please set AGENT_ARN environment variable")
        print("Example: export AGENT_ARN='arn:aws:bedrock:us-west-2:123456789012:agent/ABCD1234'")
        return

    # URL에서 사용할 수 있도록 ARN encoding
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")

    # Encoding된 ARN으로 MCP URL 구성(qualifier 없음 - SDK가 PRM API에서 검색)
    server_url = f"{base_endpoint}/runtimes/{encoded_arn}/invocations"

    # 선택적 transport type 가져오기
    transport_type = os.getenv("MCP_TRANSPORT_TYPE", "streamable-http")

    print("🚀 MCP Auth0 Client")
    print(f"Agent ARN: {agent_arn}")
    print(f"Endpoint: {base_endpoint}")
    print(f"Connecting to: {server_url}")
    print(f"Transport type: {transport_type}")
    if auth0_audience:
        print(f"Auth0 audience: {auth0_audience}")

    # 연결 flow 시작 - OAuth는 자동으로 처리됨
    client = SimpleAuthClient(
        server_url,
        transport_type,
        auth0_audience,
    )
    await client.connect()


def run_test():
    """uv script용 CLI entry point입니다."""
    asyncio.run(main())


if __name__ == "__main__":
    run_test()
