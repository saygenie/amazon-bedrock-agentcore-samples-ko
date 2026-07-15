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

# 환경 변수에서 가져오는 구성
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
CALLBACK_LAMBDA_URL = os.environ.get("CALLBACK_LAMBDA_URL", "")


def lambda_handler(event, context):
    """경로에 따라 요청을 라우팅하는 기본 Lambda 핸들러입니다."""
    path = event.get("rawPath", event.get("path", "/"))
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    # 적절한 핸들러로 라우팅
    if path == "/.well-known/oauth-authorization-server":
        return handle_oauth_metadata(event)
    elif path == "/.well-known/oauth-protected-resource":
        return handle_protected_resource_metadata(event)
    elif path == "/authorize":
        return handle_authorize(event)
    elif path == "/callback":
        return handle_callback(event)
    elif path == "/token" and method == "POST":
        return handle_token(event)
    elif path == "/register" and method == "POST":
        return handle_dcr(event)
    else:
        return proxy_to_gateway(event)


def handle_oauth_metadata(event):
    """OAuth Authorization Server Metadata(RFC 8414)를 제공합니다."""
    api_url = get_api_url(event)

    metadata = {
        "issuer": api_url,
        "authorization_endpoint": f"{api_url}/authorize",
        "token_endpoint": f"{api_url}/token",
        "registration_endpoint": f"{api_url}/register",
        "scopes_supported": ["openid", "profile", "email"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    }

    return json_response(200, metadata)


def handle_protected_resource_metadata(event):
    """OAuth Protected Resource Metadata(RFC 9728)를 제공합니다.

    클라이언트 관점에서는 프록시가 MCP 서버 역할을 하므로 리소스 식별자는
    기반 AgentCore Gateway URL이 아니라 프록시 URL(API Gateway)이어야 합니다.
    이렇게 하면 OAuth 토큰 요청의 'resource' 파라미터가 이 메타데이터와 일치하여
    리소스 불일치 오류를 방지할 수 있습니다.

    참고: 여기서는 의도적으로 AgentCore Gateway의 메타데이터를 프록시하지 않습니다.
    프록시하면 Gateway URL이 리소스로 반환되어 클라이언트(VS Code)가 토큰 요청에
    프록시 URL을 사용할 때 불일치가 발생하기 때문입니다.
    """
    api_url = get_api_url(event)
    return json_response(
        200,
        {
            "resource": api_url,
            "authorization_servers": [api_url],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["openid", "profile", "email"],
        },
    )


def handle_authorize(event):
    """콜백을 가로채면서 /authorize를 Cognito로 리디렉션합니다.

    Lambda는 상태 비저장 방식이므로 여러 Lambda 호출에서도 유지되도록 원래
    redirect_uri를 state 파라미터에 인코딩합니다.
    """
    params = event.get("queryStringParameters", {}) or {}

    # client_id 재정의
    params["client_id"] = CLIENT_ID

    # 원래 redirect_uri와 state를 새 state 파라미터에 함께 인코딩
    original_redirect_uri = params.get("redirect_uri", "")
    original_state = params.get("state", "")

    if original_redirect_uri:
        # 복합 state 생성: base64(json({original_state, original_redirect_uri}))
        compound_state = {
            "state": original_state,
            "redirect_uri": urllib.parse.unquote(original_redirect_uri),
        }
        encoded_state = base64.urlsafe_b64encode(json.dumps(compound_state).encode()).decode()
        params["state"] = encoded_state

        # redirect_uri를 이 프록시의 콜백으로 교체
        api_url = get_api_url(event)
        params["redirect_uri"] = f"{api_url}/callback"

    redirect_url = f"{COGNITO_DOMAIN.rstrip('/')}/oauth2/authorize?{urllib.parse.urlencode(params)}"

    return {"statusCode": 302, "headers": {"Location": redirect_url}, "body": ""}


def handle_callback(event):
    """Cognito의 OAuth 콜백을 처리하여 VS Code로 전달합니다.

    복합 state 파라미터를 디코딩하여 원래 redirect_uri와 state를 추출합니다.
    """
    params = event.get("queryStringParameters", {}) or {}
    code = params.get("code", "")
    encoded_state = params.get("state", "")
    error = params.get("error", "")

    if error:
        return json_response(400, {"error": error})

    # 복합 state를 디코딩하여 원래 redirect_uri와 state 가져오기
    try:
        # URL 인코딩 문제 처리(공백이 + 또는 %20으로 변환됨)
        encoded_state_clean = encoded_state.replace(" ", "+")
        # 필요한 경우 패딩 추가
        padding = 4 - len(encoded_state_clean) % 4
        if padding != 4:
            encoded_state_clean += "=" * padding

        decoded = base64.urlsafe_b64decode(encoded_state_clean).decode()
        compound_state = json.loads(decoded)
        original_state = compound_state.get("state", "")
        original_redirect_uri = compound_state.get("redirect_uri", "")
    except Exception as e:
        print(f"Error decoding state: {e}, state={encoded_state}")
        return json_response(400, {"error": "Invalid state parameter"})

    if not original_redirect_uri:
        return json_response(400, {"error": "Missing redirect_uri in state"})

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
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )


def proxy_to_gateway(event):
    """MCP 요청을 AgentCore Gateway로 전달합니다."""
    path = event.get("rawPath", event.get("path", "/"))
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    headers = event.get("headers", {})
    body = event.get("body", "")

    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body)

    target_url = f"{GATEWAY_URL.rstrip('/')}{path}" if path != "/" else GATEWAY_URL

    # 요청 헤더 구성
    req_headers = {
        "Content-Type": headers.get("content-type", "application/json"),
        "Accept": headers.get("accept", "application/json"),
    }

    # 인증 헤더 전달
    auth = headers.get("authorization")
    if auth:
        req_headers["Authorization"] = auth

    # MCP 헤더 전달
    for h in ["mcp-protocol-version", "mcp-session-id"]:
        if headers.get(h):
            req_headers[h.title()] = headers[h]

    try:
        if method == "POST" and body:
            data = body.encode() if isinstance(body, str) else body
            req = urllib.request.Request(target_url, data=data, method="POST")
        else:
            req = urllib.request.Request(target_url, method=method)

        for k, v in req_headers.items():
            req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            resp_body = resp.read().decode()
            resp_headers = {"Content-Type": resp.headers.get("Content-Type", "application/json")}

            # 세션 ID 전달
            session_id = resp.headers.get("Mcp-Session-Id")
            if session_id:
                resp_headers["Mcp-Session-Id"] = session_id

            # 3LO elicitation을 확인하고 토큰 저장
            try:
                data = json.loads(resp_body)
                if is_elicitation(data) and CALLBACK_LAMBDA_URL:
                    store_token_for_3lo(req_headers.get("Authorization", ""))
            except (json.JSONDecodeError, KeyError):
                pass

            return {
                "statusCode": resp.status,
                "headers": resp_headers,
                "body": resp_body,
            }
    except urllib.error.HTTPError as e:
        resp_headers = {"Content-Type": "application/json"}
        if e.headers.get("WWW-Authenticate"):
            resp_headers["WWW-Authenticate"] = e.headers["WWW-Authenticate"]
        return {
            "statusCode": e.code,
            "headers": resp_headers,
            "body": e.read().decode(),
        }
    except Exception as e:
        return json_response(502, {"error": {"code": -32603, "message": str(e)}})


def is_elicitation(data):
    """응답이 3LO elicitation인지 확인합니다."""
    if not isinstance(data, dict):
        return False
    error = data.get("error", {})
    return isinstance(error, dict) and error.get("code") == -32042


def store_token_for_3lo(auth_header):
    """3LO 세션 바인딩을 위해 콜백 Lambda에 사용자 토큰을 저장합니다."""
    if not auth_header or not CALLBACK_LAMBDA_URL:
        return

    token = auth_header.removeprefix("Bearer ")
    url = f"{CALLBACK_LAMBDA_URL}/userIdentifier/token"

    try:
        data = json.dumps({"user_token": token}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)  # nosec B310
    except Exception as e:
        print(f"Error storing token for 3LO: {e}")


def get_api_url(event):
    """이벤트에서 API Gateway URL을 추출합니다."""
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
