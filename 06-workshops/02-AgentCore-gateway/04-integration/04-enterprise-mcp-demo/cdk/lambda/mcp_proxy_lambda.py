"""
MCP OAuth 프록시 Lambda - OAuth 메타데이터, 콜백 가로채기, 토큰 프록시, MCP 전달을 처리합니다.

이 Lambda 함수는 로컬 mcp_oauth_proxy.py 스크립트를 대체하여 서버리스 배포를 지원합니다.
"""

import json
import os
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
import logging
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import boto3

# 로깅 구성
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 환경 변수에서 가져오는 구성
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
CALLBACK_LAMBDA_URL = os.environ.get("CALLBACK_LAMBDA_URL", "")
RESOURCE_SERVER_ID = os.environ.get("RESOURCE_SERVER_ID", "")
MCP_METADATA_KEY = os.environ.get("MCP_METADATA_KEY", "com.example/target")

# OAuth 콜백에 허용되는 redirect URI로, CDK에서 JSON 인코딩된 목록으로 전달됨
# open redirect 공격을 방지하려면 Cognito 클라이언트에 등록된 callbackUrls와
# 일치해야 함
ALLOWED_REDIRECT_URIS = json.loads(os.environ.get("ALLOWED_REDIRECT_URIS", "[]"))


def sign_request(request):
    """AWS SigV4로 HTTP 요청에 서명합니다."""
    session = boto3.Session()
    credentials = session.get_credentials()
    region = session.region_name or "us-east-1"

    aws_request = AWSRequest(
        method=request.get_method(),
        url=request.get_full_url(),
        data=request.data,
        headers=request.headers,
    )
    SigV4Auth(credentials, "bedrock-agentcore", region).add_auth(aws_request)

    # 원래 요청 헤더 업데이트
    for key, value in aws_request.headers.items():
        request.add_header(key, value)


def lambda_handler(event, context):
    """경로에 따라 요청을 라우팅하는 기본 Lambda 핸들러입니다."""
    logger.debug(f"Event: {json.dumps(event)}")

    # ALB와 API Gateway v2(HTTP API) 이벤트를 모두 지원
    # ALB 사용 필드: path, httpMethod
    # HTTP API 사용 필드: rawPath, requestContext.http.method
    path = event.get("path") or event.get("rawPath", "/")
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")

    logger.debug(f"Method: {method}, Path: {path}")

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {"Allow": "OPTIONS, GET, POST"},
            "body": "",
        }
    # 적절한 핸들러로 라우팅
    if path == "/ping":
        return handle_ping(event)
    elif path.startswith("/.well-known/oauth-authorization-server"):
        return handle_oauth_metadata(event)
    elif path == "/.well-known/oauth-protected-resource" or path == "/.well-known/oauth-protected-resource/mcp":
        return handle_protected_resource_metadata(event)
    elif path == "/authorize":
        return handle_authorize(event)
    elif path == "/callback":
        return handle_callback(event)
    elif path == "/token" and method == "POST":
        return handle_token(event)
    elif path == "/register" and method == "POST":
        return handle_dcr(event)
    elif path == "/mcp" or path.endswith("/mcp"):
        return proxy_to_gateway(event)
    else:
        return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


def handle_ping(event):
    """ALB target group의 상태 확인 엔드포인트입니다."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": "healthy", "service": "mcp-proxy"}),
    }


def handle_oauth_metadata(event):
    """OAuth Authorization Server Metadata(RFC 8414)를 제공합니다."""
    api_url = get_api_url(event)

    metadata = {
        "issuer": api_url,
        "authorization_endpoint": f"{api_url}/authorize",
        "token_endpoint": f"{api_url}/token",
        "registration_endpoint": f"{api_url}/register",
        "scopes_supported": [
            "openid",
            "profile",
            "email",
            f"{RESOURCE_SERVER_ID}/mcp.read",
            f"{RESOURCE_SERVER_ID}/mcp.write",
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    }

    return json_response(200, metadata)


def handle_protected_resource_metadata(event):
    """OAuth Protected Resource Metadata를 제공합니다."""
    api_url = get_api_url(event)

    # RFC 9728에 따라 'resource'는 클라이언트가 서비스에 접근하는 URL과 일치해야 함
    # Gateway 엔드포인트가 아니라 ALB 엔드포인트여야 함
    return json_response(
        200,
        {
            "resource": f"{api_url}/mcp",
            "authorization_servers": [api_url],
            "bearer_methods_supported": ["header"],
            "scopes_supported": [
                "openid",
                "profile",
                "email",
                f"{RESOURCE_SERVER_ID}/mcp.read",
                f"{RESOURCE_SERVER_ID}/mcp.write",
            ],
        },
    )


def handle_authorize(event):
    """콜백을 가로채면서 /authorize를 Cognito로 리디렉션합니다.

    Lambda는 상태 비저장 방식이므로 여러 Lambda 호출에서도 유지되도록 원래
    redirect_uri를 state 파라미터에 인코딩합니다.
    """
    logger.debug("=== HANDLE_AUTHORIZE DEBUG ===")
    params = event.get("queryStringParameters", {}) or {}
    logger.debug(f"Original params: {json.dumps(params)}")

    # 지원되지 않는 파라미터 제거(Cognito는 'resource' 파라미터를 지원하지 않음)
    if "resource" in params:
        logger.debug(f"Removing 'resource' parameter: {params['resource']}")
        params.pop("resource", None)

    # scope 파라미터 수정: URL 디코딩 및 공백 정규화
    if "scope" in params:
        # 먼저 URL 디코딩(%2F 등 처리)한 후 +를 공백으로 정규화
        params["scope"] = urllib.parse.unquote(params["scope"]).replace("+", " ")
        logger.debug(f"Fixed scope parameter: {params['scope']}")

    # client_id 재정의
    logger.debug(f"Original client_id: {params.get('client_id', 'N/A')}")
    params["client_id"] = CLIENT_ID
    logger.debug(f"Overridden client_id: {CLIENT_ID}")

    # 원래 redirect_uri와 state를 새 state 파라미터에 함께 인코딩
    original_redirect_uri = params.get("redirect_uri", "")
    original_state = params.get("state", "")

    logger.debug(f"Original redirect_uri (URL encoded): {original_redirect_uri}")
    logger.debug(f"Original state (URL encoded): {original_state}")

    if original_redirect_uri:
        # 저장하기 전에 state와 redirect_uri를 모두 URL 디코딩
        decoded_state = urllib.parse.unquote(original_state)
        decoded_redirect_uri = urllib.parse.unquote(original_redirect_uri)

        logger.debug(f"Decoded state: {decoded_state}")
        logger.debug(f"Decoded redirect_uri: {decoded_redirect_uri}")

        # 복합 state 생성: base64(json({original_state, original_redirect_uri}))
        compound_state = {
            "state": decoded_state,
            "redirect_uri": decoded_redirect_uri,
        }
        encoded_state = base64.urlsafe_b64encode(json.dumps(compound_state).encode()).decode()
        params["state"] = encoded_state

        logger.debug(f"Compound state created: {json.dumps(compound_state)}")
        logger.debug(f"Encoded state: {encoded_state}")

        # redirect_uri를 이 프록시의 콜백으로 교체
        api_url = get_api_url(event)
        params["redirect_uri"] = f"{api_url}/callback"
        logger.debug(f"New redirect_uri: {params['redirect_uri']}")

    logger.debug(f"Final params being sent to Cognito: {json.dumps(params)}")
    redirect_url = f"{COGNITO_DOMAIN.rstrip('/')}/oauth2/authorize?{urllib.parse.urlencode(params)}"
    logger.debug(f"Redirect URL: {redirect_url}")
    logger.debug("=== END HANDLE_AUTHORIZE DEBUG ===")

    return {"statusCode": 302, "headers": {"Location": redirect_url}, "body": ""}


def handle_callback(event):
    """Cognito의 OAuth 콜백을 처리하여 VS Code로 전달합니다.

    복합 state 파라미터를 디코딩하여 원래 redirect_uri와 state를 추출합니다.
    """
    params = event.get("queryStringParameters", {}) or {}
    code = params.get("code", "")
    encoded_state = params.get("state", "")
    error = params.get("error", "")

    logger.debug("=== HANDLE_CALLBACK DEBUG ===")
    logger.debug(f"Code: {code}")
    logger.debug(f"State (URL encoded): {encoded_state}")
    logger.debug(f"Error: {error}")

    if error:
        return json_response(400, {"error": error})

    # 복합 state를 디코딩하여 원래 redirect_uri와 state 가져오기
    try:
        # 먼저 state 파라미터를 URL 디코딩(Cognito가 URL 인코딩하여 전송함)
        encoded_state_clean = urllib.parse.unquote(encoded_state)
        logger.debug(f"State (URL decoded): {encoded_state_clean}")

        # 남아 있는 URL 인코딩 문제 처리(공백이 + 또는 %20으로 변환됨)
        encoded_state_clean = encoded_state_clean.replace(" ", "+")

        # 이제 state는 올바른 base64이므로 패딩이 필요하지 않음
        logger.debug(f"State (ready for base64 decode): {encoded_state_clean}")
        logger.debug(f"State length: {len(encoded_state_clean)}")

        decoded = base64.urlsafe_b64decode(encoded_state_clean).decode()
        logger.debug(f"Decoded JSON: {decoded}")

        compound_state = json.loads(decoded)
        original_state = compound_state.get("state", "")
        original_redirect_uri = compound_state.get("redirect_uri", "")

        logger.debug(f"Original state: {original_state}")
        logger.debug(f"Original redirect_uri: {original_redirect_uri}")
        logger.debug("=== END HANDLE_CALLBACK DEBUG ===")
    except Exception as e:
        logger.error(f"Error decoding state: {e}, state={encoded_state}")
        logger.error("=== END HANDLE_CALLBACK DEBUG (ERROR) ===")
        return json_response(400, {"error": "Invalid state parameter"})

    if not original_redirect_uri:
        return json_response(400, {"error": "Missing redirect_uri in state"})

    # open redirect 공격을 방지하도록 allowlist를 기준으로 redirect_uri 검증
    # 검증하지 않으면 조작된 state blob이 authorization code를 공격자가 제어하는
    # URL로 리디렉션할 수 있음
    #
    # IDE 클라이언트(VS Code, Kiro)는 OAuth 콜백을 위해 임의 포트에서 임시 로컬 서버를
    # 시작하므로 포트와 관계없이 localhost URI를 허용
    normalized = original_redirect_uri.rstrip("/")
    parsed = urllib.parse.urlparse(normalized)
    is_localhost = parsed.scheme == "http" and parsed.hostname in (
        "localhost",
        "127.0.0.1",
    )
    allowed_normalized = [u.rstrip("/") for u in ALLOWED_REDIRECT_URIS]
    if not is_localhost and normalized not in allowed_normalized:
        logger.warning(f"Rejected redirect_uri not in allowlist: {original_redirect_uri}")
        logger.debug(f"Normalized redirect_uri: {normalized}")
        logger.debug(f"Allowed URIs (raw): {ALLOWED_REDIRECT_URIS}")
        logger.debug(f"Allowed URIs (normalized): {allowed_normalized}")
        return json_response(400, {"error": "invalid_redirect_uri"})

    # 원래 state와 함께 VS Code의 콜백으로 전달
    forward_params = urllib.parse.urlencode({"code": code, "state": original_state})
    forward_url = f"{original_redirect_uri}?{forward_params}"

    return {"statusCode": 302, "headers": {"Location": forward_url}, "body": ""}


def handle_token(event):
    """redirect_uri를 다시 작성하여 토큰 요청을 Cognito로 프록시합니다."""
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()

    params = dict(urllib.parse.parse_qsl(body))

    # client_id를 재정의하고 보안 암호 추가
    params["client_id"] = CLIENT_ID
    if CLIENT_SECRET:
        params["client_secret"] = CLIENT_SECRET

    # redirect_uri 다시 작성
    if "redirect_uri" in params:
        api_url = get_api_url(event)
        params["redirect_uri"] = f"{api_url}/callback"

    token_url = f"{COGNITO_DOMAIN.rstrip('/')}/oauth2/token"
    data = urllib.parse.urlencode(params).encode()

    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
            token_data = json.loads(resp.read().decode())
            if "created_at" not in token_data:
                token_data["created_at"] = int(time.time() * 1000)
            return json_response(200, token_data)
    except urllib.error.HTTPError as e:
        return json_response(e.code, {"error": e.read().decode()})


def handle_dcr(event):
    """Dynamic Client Registration을 처리하여 사전 등록된 client_id를 반환합니다."""
    return json_response(
        200,
        {
            "client_id": CLIENT_ID,
            "client_name": "VS Code Copilot MCP Client",
            "grant_types": ["authorization_code", "refresh_token"],
            "redirect_uris": [f"{get_api_url(event)}/callback"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )


def proxy_to_gateway(event):
    """선택적 target 필터링과 함께 MCP 요청을 AgentCore Gateway로 전달합니다."""
    logger.info("proxy_to_gateway")
    path = event.get("path", "/")
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    headers = event.get("headers", {})
    body = event.get("body", "")
    logger.info(f"Proxying to gateway - Method: {method}, Path: {path}")
    logger.debug(f"Headers: {json.dumps(headers)}")
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body)

    # === 경로에서 TARGET 추출 ===
    # /mcp → 필터 없음(모든 도구 반환)
    # /gitlab/mcp → 필터 = "gitlab"
    # /weather/mcp → 필터 = "weather"
    target_filter = None

    if path and path != "/mcp":
    # 앞뒤 슬래시를 제거하고 분할
        parts = path.strip("/").split("/")

    # 경로 형식이 <target>/mcp인지 확인
        if len(parts) == 2 and parts[-1] == "mcp":
            target_filter = parts[0]
            logger.info(f"Target filter extracted from path: '{target_filter}'")
        elif len(parts) > 2 and parts[-1] == "mcp":
        # /api/v1/gitlab/mcp 같은 중첩 경로 처리
            target_filter = parts[-2]
            logger.info(f"Target filter extracted from nested path: '{target_filter}'")
        else:
            logger.debug(f"Path '{path}' does not match target pattern, no filtering")
    else:
        logger.debug("Default path '/mcp' - returning all tools (no filtering)")

    # === TARGET 필터가 있는 경우에만 MCP _meta에 삽입 ===
    if method == "POST" and body:
        try:
        # MCP JSON-RPC 요청 파싱
            mcp_request = json.loads(body if isinstance(body, str) else body.decode())

        # target 필터가 있고 도구 관련 메서드인 경우에만 _meta 삽입
            if target_filter and mcp_request.get("method") in [
                "tools/list",
                "tools/call",
            ]:
            # _meta 존재 보장
                if "_meta" not in mcp_request:
                    mcp_request["_meta"] = {}

            # 역방향 DNS 표기법을 사용하여 target 필터 삽입
                mcp_request["_meta"][MCP_METADATA_KEY] = target_filter

                logger.info(f"Injected _meta: {MCP_METADATA_KEY} = '{target_filter}'")
                logger.debug(f"Modified MCP request: {json.dumps(mcp_request, indent=2)}")
            else:
                if not target_filter:
                    logger.debug("No target filter - NOT injecting _meta (will return all tools)")
                else:
                    logger.debug(f"Method '{mcp_request.get('method')}' - not injecting _meta")

        # 수정되었을 수 있는 요청을 다시 직렬화
            body = json.dumps(mcp_request).encode()

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MCP request: {e}")
        # 파싱에 실패하면 원래 본문으로 계속 진행

    # target_url = f"{GATEWAY_URL.rstrip('/mcp')}{path}" if path != "/" else GATEWAY_URL
    target_url = GATEWAY_URL
    # 요청 헤더 구성
    req_headers = {
        "Content-Type": headers.get("content-type", "application/json"),
        "Accept": headers.get("accept", "application/json"),
    }

    # MCP 헤더 전달
    for h in ["mcp-protocol-version", "mcp-session-id"]:
        if headers.get(h):
            req_headers[h.title()] = headers[h]

    logger.debug(json.dumps(req_headers))
    try:
        if method == "POST" and body:
            data = body.encode() if isinstance(body, str) else body
            req = urllib.request.Request(target_url, data=data, method="POST")
        else:
            req = urllib.request.Request(target_url, method=method)

        for k, v in req_headers.items():
            req.add_header(k, v)

    # 향후 ACG에서 IAM 인증을 통한 3LO outbound를 지원할 경우를 대비한 코드
        if os.environ.get("GATEWAY_AUTH", None) == "IAM":
        # 인바운드 authorization token에서 userId 추출
            auth = headers.get("authorization")
            if auth:
                token = auth.split(" ")[1]
                user_id = json.loads(base64.b64decode(token.split(".")[1]))["sub"]
                req.add_header("X-Amzn-Bedrock-AgentCore-Runtime-User-Id", user_id)
            sign_request(req)
        else:
    # 인증 헤더 전달
            auth = headers.get("authorization")
            if auth:
                req.add_header("Authorization", auth)

        logger.debug(
            "{}\n{}\r\n{}\r\n\r\n{}".format(
                "-----------START-----------",
                (req.method or "GET") + " " + req.full_url,
                "\r\n".join("{}: {}".format(k, v) for k, v in req.headers.items()),
                req.data,
            )
        )

        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            resp_body = resp.read().decode()
            logger.debug(resp_body)
            logger.debug(resp.headers)
            resp_headers = {"Content-Type": resp.headers.get("Content-Type", "application/json")}

        # 세션 ID 전달
            session_id = resp.headers.get("Mcp-Session-Id")
            if session_id:
                resp_headers["Mcp-Session-Id"] = session_id

        # ALB 엔드포인트를 사용하도록 WWW-Authenticate 헤더의 Gateway URL 다시 작성
            www_auth = resp.headers.get("WWW-Authenticate")
            if www_auth:
                api_url = get_api_url(event)
            # Gateway URL 참조를 ALB URL로 교체
            # /mcp 접미사를 올바르게 제거하도록 removesuffix 또는 문자열 슬라이싱 사용
                gateway_base = GATEWAY_URL[:-4] if GATEWAY_URL.endswith("/mcp") else GATEWAY_URL
                www_auth_rewritten = www_auth.replace(gateway_base, api_url)
                resp_headers["WWW-Authenticate"] = www_auth_rewritten
                logger.debug(f"Rewrote WWW-Authenticate: {www_auth} -> {www_auth_rewritten}")

            return {
                "statusCode": resp.status,
                "headers": resp_headers,
                "body": resp_body,
            }
    except urllib.error.HTTPError as e:
        error = e.read().decode()
        logger.error(f"Gateway error response: {error}")

        # 오류 응답 본문의 Gateway URL 다시 작성
        api_url = get_api_url(event)
            # /mcp 접미사를 올바르게 제거하도록 문자열 슬라이싱 사용
        gateway_base = GATEWAY_URL[:-4] if GATEWAY_URL.endswith("/mcp") else GATEWAY_URL
        error_rewritten = error.replace(gateway_base, api_url)
        if error != error_rewritten:
            logger.debug("Rewrote Gateway URL in error body")

        resp_headers = {"Content-Type": "application/json"}

        # WWW-Authenticate 헤더가 있으면 다시 작성
        www_auth = e.headers.get("WWW-Authenticate")
        if www_auth:
            www_auth_rewritten = www_auth.replace(gateway_base, api_url)
            resp_headers["WWW-Authenticate"] = www_auth_rewritten
            logger.debug(f"Rewrote WWW-Authenticate in error: {www_auth} -> {www_auth_rewritten}")

        return {
            "statusCode": e.code,
            "headers": resp_headers,
            "body": error_rewritten,
        }
    except Exception as e:
        return json_response(502, {"error": {"code": -32603, "message": str(e)}})


def is_elicitation(data):
    """응답이 3LO elicitation인지 확인합니다."""
    if not isinstance(data, dict):
        return False
    error = data.get("error", {})
    return isinstance(error, dict) and error.get("code") == -32042


def get_api_url(event):
    """이벤트에서 API URL을 추출합니다(ALB와 API Gateway 모두 지원)."""
    # ALB에서는 Host 헤더 사용
    headers = event.get("headers", {})
    host = headers.get("host") or headers.get("Host")
    if host:
        # ALB는 Host 헤더에 실제 도메인을 전달함
        return f"https://{host}"

    # API Gateway 형식으로 대체
    ctx = event.get("requestContext", {})
    domain = ctx.get("domainName", "")
    stage = ctx.get("stage", "")
    if domain and stage and stage != "$default":
        return f"https://{domain}/{stage}"
    elif domain:
        return f"https://{domain}"
    return "http://localhost"


def json_response(status_code, body):
    """JSON 응답을 생성합니다."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
