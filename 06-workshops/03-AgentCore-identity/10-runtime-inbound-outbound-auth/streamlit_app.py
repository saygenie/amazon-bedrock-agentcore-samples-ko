"""
AgentCore Identity Sample 10(Runtime 인바운드 + 아웃바운드 인증)용 Streamlit UI입니다.

Cognito JWT bearer token을 사용하거나 사용하지 않고 AgentCore Runtime을 호출하는 방법을 보여줍니다.

사용법:
    streamlit run streamlit_app.py
"""

import json
import os
import time

import boto3
import streamlit as st

# ---------------------------------------------------------------------------
# 페이지 구성
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sample 10: Runtime Auth",
    page_icon="\U0001f510",
    layout="wide",
)

SAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 보조 함수(독립 구성, invoke.py 패턴과 동일)
# ---------------------------------------------------------------------------


def _load_cognito_config() -> dict | None:
    """샘플 디렉터리에서 cognito_config.json을 불러옵니다."""
    path = os.path.join(SAMPLE_DIR, "cognito_config.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _find_project_dir() -> str:
    """agentcore/를 포함하는 하위 디렉터리에서 agentcore 프로젝트를 찾습니다."""
    for entry in os.listdir(SAMPLE_DIR):
        candidate = os.path.join(SAMPLE_DIR, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "agentcore")):
            return candidate
    raise FileNotFoundError("No agentcore project directory found. Run 'agentcore create' first.")


def _find_in_json(obj, key):
    """중첩된 JSON에서 키를 재귀적으로 검색합니다."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _find_in_json(v, key)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_in_json(item, key)
            if result:
                return result
    return None


def _resolve_agent_arn() -> str:
    """deployed-state.json에서 배포된 에이전트 ARN을 읽습니다.

    CLI 버전에 관계없이 동작하도록 runtimeArn을 재귀적으로 검색합니다.
    """
    project_dir = _find_project_dir()
    state_file = os.path.join(project_dir, "agentcore", ".cli", "deployed-state.json")
    if not os.path.exists(state_file):
        raise FileNotFoundError("No deployed-state.json found. Run 'agentcore deploy -y' first.")
    with open(state_file) as f:
        state = json.load(f)
    arn = _find_in_json(state, "runtimeArn")
    if arn:
        return arn
    raise ValueError("No deployed agent found. Run 'agentcore deploy -y' first.")


def _get_bearer_token(config: dict) -> str:
    """Cognito로 인증하고 액세스 토큰을 반환합니다."""
    cognito = boto3.client("cognito-idp", region_name=config["region"])
    auth = cognito.initiate_auth(
        ClientId=config["client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": config["username"],
            "PASSWORD": config["password"],
        },
    )
    return auth["AuthenticationResult"]["AccessToken"]


def _parse_event_stream(response: dict) -> str:
    """boto3 EventStream 응답에서 텍스트를 추출합니다."""
    parts: list[str] = []
    for event in response.get("response", []):
        raw = event if isinstance(event, bytes) else event.get("chunk", {}).get("bytes", b"")
        if raw:
            try:
                decoded = json.loads(raw.decode("utf-8"))
                if isinstance(decoded, str):
                    parts.append(decoded)
                elif isinstance(decoded, dict):
                    content = decoded.get("content", [])
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c["text"])
                        elif isinstance(c, str):
                            parts.append(c)
                    if not content and "message" in decoded:
                        msg = decoded["message"]
                        if isinstance(msg, dict):
                            for c in msg.get("content", []):
                                if isinstance(c, dict) and c.get("type") == "text":
                                    parts.append(c["text"])
            except Exception:
                parts.append(raw.decode("utf-8"))
    return "\n".join(parts) if parts else "(no response)"


def _invoke_agent(agent_arn: str, region: str, prompt: str, bearer_token: str | None = None) -> dict:
    """
    선택적으로 bearer token을 사용해 에이전트 런타임을 호출합니다.

    success, text, elapsed, error, status_code 키가 있는 dict를 반환합니다.
    """
    client = boto3.client("bedrock-agentcore", region_name=region)
    handler = None

    if bearer_token:

        def _inject_bearer(request, **kwargs):
            request.headers["Authorization"] = f"Bearer {bearer_token}"

        handler = _inject_bearer
        client.meta.events.register("before-send.bedrock-agentcore.InvokeAgentRuntime", handler)

    t0 = time.time()
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeUserId="testuser",
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
        )
        elapsed = time.time() - t0
        text = _parse_event_stream(resp)
        return {
            "success": True,
            "text": text,
            "elapsed": elapsed,
            "error": None,
            "status_code": resp.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        }
    except Exception as exc:
        elapsed = time.time() - t0
        return {
            "success": False,
            "text": None,
            "elapsed": elapsed,
            "error": f"{type(exc).__name__}: {exc}",
            "status_code": getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode"),
        }
    finally:
        if handler:
            client.meta.events.unregister("before-send.bedrock-agentcore.InvokeAgentRuntime", handler)


def _format_response(text: str) -> str:
    """표시를 위해 리터럴 \\n 시퀀스를 실제 줄바꿈으로 바꿉니다."""
    return text.replace("\\n", "\n")


def _truncate_arn(arn: str, max_len: int = 45) -> str:
    """사이드바 표시에 맞게 ARN을 줄입니다."""
    if len(arn) <= max_len:
        return arn
    return arn[: max_len - 3] + "..."


# ---------------------------------------------------------------------------
# 세션 상태 초기화
# ---------------------------------------------------------------------------
for key, default in {
    "logged_in": False,
    "jwt_token": None,
    "username": "",
    "chat_history": [],
    "agent_arn": None,
    "arn_error": None,
    "region": "us-east-1",
    "last_request": None,
    "login_error": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# 구성 불러오기
# ---------------------------------------------------------------------------
config = _load_cognito_config()

# ---------------------------------------------------------------------------
# 사용자 지정 CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Hide sidebar toggle when not logged in */
    .login-page [data-testid="collapsedControl"] { display: none; }

    /* Login card styling */
    .login-card {
        padding: 2rem 0;
    }
    .login-header {
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .login-subtitle {
        text-align: center;
        color: #6b7280;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .login-desc {
        text-align: center;
        color: #9ca3af;
        font-size: 0.85rem;
        margin-bottom: 2rem;
        line-height: 1.5;
    }

    /* Sidebar signed-in badge */
    .signed-in-badge {
        background: #065f46;
        color: #d1fae5;
        padding: 0.4rem 0.75rem;
        border-radius: 0.5rem;
        font-size: 0.85rem;
        font-weight: 500;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sidebar-meta {
        color: #9ca3af;
        font-size: 0.75rem;
        word-break: break-all;
        margin-bottom: 0.25rem;
    }

    /* Preset buttons row */
    .stButton > button {
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================================
# 화면 1: 로그인(전체 페이지, 가운데 정렬)
# =========================================================================
if not st.session_state.logged_in:
    # 로그인 페이지에서 사이드바 숨기기
    st.markdown(
        "<style>[data-testid='stSidebar'] { display: none; }</style>",
        unsafe_allow_html=True,
    )

    # 세로 여백
    st.markdown("")
    st.markdown("")

    # 가운데 열
    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.markdown(
            "<h1 class='login-header'>AgentCore Runtime Auth Demo</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='login-subtitle'>Sample 10: Inbound JWT + Outbound API Key</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='login-desc'>"
            "This demo shows how AgentCore Runtime validates inbound JWT tokens "
            "and retrieves outbound API keys securely."
            "</p>",
            unsafe_allow_html=True,
        )

        if not config:
            st.error("**cognito_config.json not found.** Run `python setup_cognito.py` before using this app.")
            st.stop()

        # 이전 로그인 오류 표시
        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        with st.form("login_form"):
            username = st.text_input(
                "Username",
                value=config.get("username", ""),
            )
            password = st.text_input(
                "Password",
                value=config.get("password", ""),
                type="password",
            )
            sign_in = st.form_submit_button("Sign In", use_container_width=True)

        if sign_in:
            if not username or not password:
                st.session_state.login_error = "Username and password are required."
                st.rerun()
            else:
                login_config = {**config, "username": username, "password": password}
                try:
                    with st.spinner("Authenticating with Cognito..."):
                        token = _get_bearer_token(login_config)

                    # 에이전트 ARN을 즉시 확인
                    with st.spinner("Resolving agent ARN..."):
                        try:
                            agent_arn = _resolve_agent_arn()
                        except Exception as exc:
                            agent_arn = None
                            st.session_state.arn_error = str(exc)

                    # 세션 상태에 저장
                    st.session_state.jwt_token = token
                    st.session_state.bearer_input = token  # 토큰 필드 미리 채우기
                    st.session_state.username = username
                    st.session_state.logged_in = True
                    st.session_state.agent_arn = agent_arn
                    st.session_state.region = config.get("region", "us-east-1")
                    st.session_state.login_error = None
                    st.rerun()

                except Exception as exc:
                    st.session_state.login_error = f"Login failed: {exc}"
                    st.rerun()

    st.stop()


# =========================================================================
# 화면 2: 대시보드(로그인 후)
# =========================================================================

# --- 사이드바 ---
with st.sidebar:
    st.markdown(
        f"<div class='signed-in-badge'>Signed in as {st.session_state.username}</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.agent_arn:
        st.markdown(
            f"<p class='sidebar-meta'><b>Agent:</b> {_truncate_arn(st.session_state.agent_arn)}</p>",
            unsafe_allow_html=True,
        )
    elif st.session_state.arn_error:
        st.error(st.session_state.arn_error, icon="\u26a0\ufe0f")
    else:
        st.warning("Agent ARN not resolved.")

    st.markdown(
        f"<p class='sidebar-meta'><b>Region:</b> {st.session_state.region}</p>",
        unsafe_allow_html=True,
    )

    if st.button("Sign Out", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.divider()

    # bearer token은 자동으로 채워지며, 403 테스트를 위해 사용자가 지울 수 있음
    st.markdown("**Bearer Token**")
    st.caption("Auto-filled after login. Clear to test 403 rejection.")
    bearer_input = st.text_area(
        "Bearer Token",
        height=80,
        key="bearer_input",
        label_visibility="collapsed",
    )
    if bearer_input.strip():
        st.markdown(":green-background[Token will be sent]")
    else:
        st.markdown(":red-background[No token — requests will get 403]")

# --- 기본 영역 ---
st.markdown("#### Runtime Inbound + Outbound Auth")
st.markdown("""
```
Inbound:   You ──[JWT Token]──▶ AgentCore Runtime (validates via Cognito)

Outbound:  Agent ──▶ AgentCore Identity ──▶ API Key ──▶ Weather API (wttr.in)
                     @requires_api_key()     securely
                                             retrieved
```
""")
st.caption(
    "Clear the Bearer Token in the sidebar to see a 403 rejection. The agent retrieves the API key from AgentCore Identity — never hardcoded."
)

# 채팅 기록
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(_format_response(msg["content"]))

# 사전 설정 버튼
presets = [
    "What's the weather in Seattle?",
    "Calculate 5 * 7 + 3",
    "What can you do?",
]
preset_cols = st.columns(len(presets))
prompt_to_send: str | None = None

for i, preset in enumerate(presets):
    with preset_cols[i]:
        if st.button(preset, key=f"preset_{i}", use_container_width=True):
            prompt_to_send = preset

# 채팅 입력
user_input = st.chat_input("Ask the agent...")
if user_input:
    prompt_to_send = user_input

# 프롬프트 전송
if prompt_to_send:
    if not st.session_state.agent_arn:
        st.error("Agent ARN not resolved. Deploy the agent first.")
    else:
        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": prompt_to_send,
            }
        )
        with st.chat_message("user"):
            st.markdown(prompt_to_send)

        with st.chat_message("assistant"):
            with st.spinner("Invoking agent..."):
                result = _invoke_agent(
                    st.session_state.agent_arn,
                    st.session_state.region,
                    prompt_to_send,
                    bearer_token=st.session_state.get("bearer_input", "").strip() or None,
                )

            truncated = st.session_state.jwt_token[:20] + "..."
            st.session_state.last_request = {"auth": f"Bearer {truncated}", **result}

            if result["success"]:
                display_text = _format_response(result["text"])
                st.markdown(display_text)
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": result["text"],
                    }
                )
            else:
                st.error(result["error"])
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": f"Error: {result['error']}",
                    }
                )

# 마지막 요청 세부 정보(접힌 상태)
if st.session_state.last_request:
    with st.expander("Last request details", expanded=False):
        req = st.session_state.last_request
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", "Success" if req.get("success") else "Failed")
        with col2:
            st.metric("Response Time", f"{req.get('elapsed', 0):.2f}s")
        with col3:
            st.metric("HTTP Status", str(req.get("status_code", "N/A")))
        st.code(f"Authorization: {req.get('auth', 'N/A')}", language=None)
        if req.get("error"):
            st.error(req["error"])
        if req.get("text"):
            st.code(req["text"], language=None)
