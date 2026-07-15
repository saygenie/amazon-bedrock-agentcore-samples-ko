"""
AgentCore Identity Sample 12(M2M + 3LO 인증 흐름)용 Streamlit UI입니다.

두 개의 화면을 제공합니다.
  화면 1: 가운데 정렬된 로그인 카드(사이드바 없음)
  화면 2: 사이드바 흐름 선택기와 채팅 영역이 있는 대시보드

사용법:
    streamlit run streamlit_app.py
"""

import atexit
import json
import os
import re
import subprocess
import sys
import time

import boto3
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
SAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))
COGNITO_CONFIG_PATH = os.path.join(SAMPLE_DIR, "cognito_config.json")
CALLBACK_SERVER_SCRIPT = os.path.join(SAMPLE_DIR, "oauth2_callback_server.py")
CALLBACK_SERVER_PORT = 9090
CALLBACK_PING_URL = f"http://localhost:{CALLBACK_SERVER_PORT}/ping"
CALLBACK_TOKEN_URL = f"http://localhost:{CALLBACK_SERVER_PORT}/userIdentifier/token"

CONSENT_URL_PATTERN = re.compile(r"https?://[^\s'\")\]]+")

FLOW_KEYS = ["m2m", "github", "google"]
FLOW_LABELS = {
    "m2m": "M2M",
    "github": "GitHub 3LO",
    "google": "Google 3LO",
}
FLOW_HEADERS = {
    "m2m": (
        "Machine-to-Machine Flow",
        "Agent authenticates to internal APIs using client credentials",
    ),
    "github": (
        "GitHub Authorization Code Flow",
        "Agent accesses your GitHub data after you consent",
    ),
    "google": ("Google Calendar Flow", "Agent reads your calendar after you consent"),
}
PRESET_BUTTONS = {
    "m2m": "What's the weather in Seattle?",
    "github": "List my GitHub repositories",
    "google": "Show today's calendar events",
}


# ---------------------------------------------------------------------------
# 페이지 구성
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sample 12: M2M + 3LO Auth",
    page_icon="\U0001f510",
    layout="wide",
)


# ---------------------------------------------------------------------------
# 사용자 지정 CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Login card styling */
    .login-card {
        background: var(--secondary-background-color);
        border-radius: 12px;
        padding: 2.5rem 2rem 2rem 2rem;
        margin-top: 6vh;
    }
    .login-title {
        text-align: center;
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .login-subtitle {
        text-align: center;
        font-size: 0.95rem;
        opacity: 0.7;
        margin-bottom: 0.5rem;
    }
    .login-desc {
        text-align: center;
        font-size: 0.85rem;
        opacity: 0.55;
        margin-bottom: 1.5rem;
    }
    /* Hide sidebar on login screen */
    .no-sidebar [data-testid="stSidebar"] { display: none; }
    .no-sidebar [data-testid="stSidebarCollapsedControl"] { display: none; }
    /* Compact sidebar badges */
    .sidebar-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-green {
        background: #16a34a22;
        color: #16a34a;
    }
    .badge-yellow {
        background: #eab30822;
        color: #ca8a04;
    }
    .badge-blue {
        background: #3b82f622;
        color: #3b82f6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 세션 상태 기본값
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "logged_in": False,
    "jwt_token": None,
    "username": None,
    "agent_arn": None,
    "chat_history": [],
    "consent_url": None,
    "consent_state": "not_started",  # 시작 전 | 대기 중 | 완료
    "callback_proc": None,
    "selected_flow": "m2m",
    "cognito_config": None,
    "last_3lo_prompt": None,
    "last_response_time": None,
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# 종료 시 콜백 서버 정리
# ---------------------------------------------------------------------------
def _cleanup_callback_server():
    proc = st.session_state.get("callback_proc")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


atexit.register(_cleanup_callback_server)


# ---------------------------------------------------------------------------
# 보조 함수: Cognito 구성 불러오기
# ---------------------------------------------------------------------------
@st.cache_data
def load_cognito_config() -> dict | None:
    if not os.path.exists(COGNITO_CONFIG_PATH):
        return None
    with open(COGNITO_CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 보조 함수: Cognito 인증
# ---------------------------------------------------------------------------
def get_bearer_token(config: dict, username: str, password: str) -> str:
    """Cognito로 인증하고 액세스 토큰을 반환합니다."""
    cognito = boto3.client("cognito-idp", region_name=config["region"])
    auth = cognito.initiate_auth(
        ClientId=config["client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return auth["AuthenticationResult"]["AccessToken"]


# ---------------------------------------------------------------------------
# 보조 함수: 배포된 에이전트 ARN 확인
# ---------------------------------------------------------------------------
def _find_project_dir() -> str:
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


def resolve_agent_arn() -> str:
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


# ---------------------------------------------------------------------------
# 보조 함수: 에이전트 스트리밍 응답 파싱
# ---------------------------------------------------------------------------
def _format_response(text: str) -> str:
    """표시할 에이전트 응답 텍스트를 정리합니다."""
    return text.replace("\\n", "\n").strip('"')


def parse_event_stream(response: dict) -> str:
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


# ---------------------------------------------------------------------------
# 보조 함수: 에이전트 호출
# ---------------------------------------------------------------------------
def invoke_agent(agent_arn: str, prompt: str, bearer_token: str, user_id: str, region: str) -> str:
    client = boto3.client("bedrock-agentcore", region_name=region)

    def _inject_bearer(request, **kwargs):
        request.headers["Authorization"] = f"Bearer {bearer_token}"

    client.meta.events.register("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer)
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeUserId=user_id,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
        )
        return parse_event_stream(resp)
    finally:
        client.meta.events.unregister("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer)


# ---------------------------------------------------------------------------
# 보조 함수: OAuth2 콜백 서버 관리
# ---------------------------------------------------------------------------
def _callback_server_running() -> bool:
    try:
        r = requests.get(CALLBACK_PING_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def start_callback_server(region: str, bearer_token: str):
    """OAuth2 콜백 서버가 실행 중이 아니면 하위 프로세스로 시작합니다."""
    proc = st.session_state.get("callback_proc")
    if proc and proc.poll() is None and _callback_server_running():
        _store_token_in_server(bearer_token)
        return

    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    st.session_state.callback_proc = subprocess.Popen(
        [sys.executable, CALLBACK_SERVER_SCRIPT, "--region", region],
        cwd=SAMPLE_DIR,
    )

    for _ in range(30):
        if _callback_server_running():
            _store_token_in_server(bearer_token)
            return
        time.sleep(0.5)

    st.error("OAuth2 callback server failed to start within 15 seconds.")


def _store_token_in_server(bearer_token: str):
    """세션 바인딩을 위해 콜백 서버에 bearer token을 POST합니다."""
    try:
        requests.post(
            CALLBACK_TOKEN_URL,
            json={"user_token": bearer_token},
            timeout=2,
        )
    except Exception as exc:
        st.warning(f"Could not store token in callback server: {exc}")


def stop_callback_server():
    proc = st.session_state.get("callback_proc")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    st.session_state.callback_proc = None


# ---------------------------------------------------------------------------
# 보조 함수: 에이전트 응답에서 동의 URL 추출
# ---------------------------------------------------------------------------
def extract_consent_url(text: str) -> str | None:
    """에이전트 응답 텍스트에서 찾은 첫 번째 동의 URL 형태의 값을 반환합니다."""
    urls = CONSENT_URL_PATTERN.findall(text)
    consent_prefixes = [
        "https://bedrock-agentcore",
        "https://accounts.google.com",
        "https://github.com/login/oauth",
    ]
    for url in urls:
        for prefix in consent_prefixes:
            if url.startswith(prefix):
                return url.rstrip(".,;")
    for url in urls:
        if "oauth" in url.lower() or "authorize" in url.lower() or "consent" in url.lower():
            return url.rstrip(".,;")
    return None


# ---------------------------------------------------------------------------
# 보조 함수: 표시할 ARN 줄이기
# ---------------------------------------------------------------------------
def _truncate_arn(arn: str, max_len: int = 45) -> str:
    if len(arn) <= max_len:
        return arn
    return arn[:20] + "..." + arn[-22:]


# ---------------------------------------------------------------------------
# 보조 함수: 로그아웃
# ---------------------------------------------------------------------------
def _sign_out():
    stop_callback_server()
    st.session_state.logged_in = False
    st.session_state.jwt_token = None
    st.session_state.username = None
    st.session_state.agent_arn = None
    st.session_state.chat_history = []
    st.session_state.consent_url = None
    st.session_state.consent_state = "not_started"
    st.session_state.last_3lo_prompt = None
    st.session_state.last_response_time = None
    st.session_state.selected_flow = "m2m"


# ===========================================================================
# 화면 1: 로그인
# ===========================================================================
if not st.session_state.logged_in:
    # 로그인 화면에서 사이드바 숨기기
    st.markdown('<div class="no-sidebar"></div>', unsafe_allow_html=True)

    config = load_cognito_config()
    if config is None:
        st.error("cognito_config.json not found. Run `python setup_cognito.py` first.")
        st.stop()

    # 가운데 정렬된 카드 레이아웃
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown(
            '<p class="login-title">AgentCore M2M + 3LO Auth Demo</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="login-subtitle">Sample 12: Client Credentials + Authorization Code Flows</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="login-desc">'
            "This demo shows M2M (machine-to-machine) and 3-legged OAuth flows "
            "for accessing external APIs on behalf of the user."
            "</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", value=config.get("username", "testuser"))
            password = st.text_input(
                "Password",
                value=config.get("password", "AgentCoreTest1!"),
                type="password",
            )
            login_btn = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if login_btn:
            with st.spinner("Authenticating..."):
                try:
                    token = get_bearer_token(config, username, password)
                    st.session_state.jwt_token = token
                    st.session_state.username = username
                    st.session_state.cognito_config = config
                    st.session_state.logged_in = True

                    # 에이전트 ARN 자동 확인
                    try:
                        arn = resolve_agent_arn()
                        st.session_state.agent_arn = arn
                    except Exception:
                        pass  # 대시보드에 경고 표시

                    st.rerun()
                except Exception as exc:
                    st.error(f"Login failed: {exc}")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()


# ===========================================================================
# 화면 2: 대시보드(로그인 상태)
# ===========================================================================
config = st.session_state.cognito_config or load_cognito_config()
if config is None:
    st.error("cognito_config.json not found.")
    st.stop()
st.session_state.cognito_config = config

flow_key = st.session_state.selected_flow
is_3lo = flow_key in ("github", "google")

# ---------------------------------------------------------------------------
# 사이드바
# ---------------------------------------------------------------------------
with st.sidebar:
    # -- 사용자 배지 --
    st.markdown(
        f'<span class="sidebar-badge badge-green">Signed in as {st.session_state.username}</span>',
        unsafe_allow_html=True,
    )
    st.caption("")  # 여백

    # -- 에이전트 ARN --
    if st.session_state.agent_arn:
        st.caption(f"Agent: `{_truncate_arn(st.session_state.agent_arn)}`")
    else:
        st.warning("Agent ARN not resolved")
        if st.button("Resolve Agent ARN", use_container_width=True):
            try:
                arn = resolve_agent_arn()
                st.session_state.agent_arn = arn
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    # -- 리전 --
    st.caption(f"Region: `{config.get('region', 'N/A')}`")

    # -- 로그아웃 --
    if st.button("Sign Out", use_container_width=True):
        _sign_out()
        st.rerun()

    st.divider()

    # -- 흐름 선택기 --
    st.markdown("**Auth Flow**")
    selected_flow = st.radio(
        "Select flow",
        FLOW_KEYS,
        format_func=lambda k: FLOW_LABELS[k],
        index=FLOW_KEYS.index(st.session_state.selected_flow) if st.session_state.selected_flow in FLOW_KEYS else 0,
        label_visibility="collapsed",
    )

    # 흐름 전환 시 동의 상태 재설정
    if selected_flow != st.session_state.selected_flow:
        st.session_state.consent_state = "not_started"
        st.session_state.consent_url = None
        st.session_state.last_3lo_prompt = None
        st.session_state.selected_flow = selected_flow
        # 3LO 흐름에서 콜백 서버 자동 시작
        if selected_flow in ("github", "google") and st.session_state.jwt_token:
            start_callback_server(config["region"], st.session_state.jwt_token)
        else:
            stop_callback_server()
        st.rerun()

    flow_key = st.session_state.selected_flow
    is_3lo = flow_key in ("github", "google")

    # -- 3LO 동의 섹션 --
    if is_3lo:
        st.divider()
        provider_label = "GitHub" if flow_key == "github" else "Google"
        state = st.session_state.consent_state

        # 상태 표시기
        if state == "not_started":
            st.markdown(
                '<span class="sidebar-badge badge-blue">Not started</span>',
                unsafe_allow_html=True,
            )
        elif state == "pending":
            st.markdown(
                '<span class="sidebar-badge badge-yellow">Pending consent</span>',
                unsafe_allow_html=True,
            )
        elif state == "completed":
            st.markdown(
                '<span class="sidebar-badge badge-green">Authorized</span>',
                unsafe_allow_html=True,
            )

        # 동의 URL 링크 버튼
        if st.session_state.consent_url and state == "pending":
            st.link_button(
                f"Authorize on {provider_label}",
                st.session_state.consent_url,
                use_container_width=True,
            )

            # 다시 호출 버튼
            if st.button("Re-invoke after consent", use_container_width=True, type="primary"):
                st.session_state.consent_state = "completed"
                if st.session_state.last_3lo_prompt and st.session_state.jwt_token and st.session_state.agent_arn:
                    prompt = st.session_state.last_3lo_prompt
                    st.session_state.chat_history.append({"role": "user", "content": f"[Re-invoke] {prompt}"})
                    try:
                        t0 = time.time()
                        result = invoke_agent(
                            st.session_state.agent_arn,
                            prompt,
                            st.session_state.jwt_token,
                            config["username"],
                            config["region"],
                        )
                        st.session_state.last_response_time = round(time.time() - t0, 2)
                        st.session_state.chat_history.append({"role": "assistant", "content": result})
                    except Exception as exc:
                        st.session_state.chat_history.append({"role": "assistant", "content": f"Error: {exc}"})
                    st.rerun()

        # 콜백 서버 표시기
        cb_running = _callback_server_running()
        st.caption(f"Callback server: {'Running' if cb_running else 'Stopped'}")

    # -- 응답 시간 --
    if st.session_state.last_response_time is not None:
        st.caption(f"Last response: {st.session_state.last_response_time}s")

# ---------------------------------------------------------------------------
# 기본 영역
# ---------------------------------------------------------------------------

# 진입 조건: 에이전트 ARN 필요
if not st.session_state.agent_arn:
    st.warning("No deployed agent found. Resolve the Agent ARN from the sidebar, or run `agentcore deploy -y`.")
    st.stop()

# -- 흐름 헤더 --
title, subtitle = FLOW_HEADERS[flow_key]
st.subheader(title)
st.caption(subtitle)

# -- 첫 렌더링 시 3LO 콜백 서버 자동 시작 --
if is_3lo and st.session_state.jwt_token and not _callback_server_running():
    start_callback_server(config["region"], st.session_state.jwt_token)

# -- 채팅 기록 --
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(_format_response(msg["content"]))

# -- 사전 설정 버튼 --
preset_prompt = None
preset_label = PRESET_BUTTONS[flow_key]
if st.button(preset_label, key=f"preset_{flow_key}", use_container_width=False):
    preset_prompt = preset_label

# -- 채팅 입력 --
user_input = st.chat_input("Type a prompt for the agent...")
prompt_to_send = preset_prompt or user_input

# -- 프롬프트 전송 --
if prompt_to_send:
    st.session_state.chat_history.append({"role": "user", "content": prompt_to_send})

    if is_3lo:
        start_callback_server(config["region"], st.session_state.jwt_token)
        st.session_state.last_3lo_prompt = prompt_to_send

    with st.chat_message("user"):
        st.markdown(prompt_to_send)

    with st.chat_message("assistant"):
        with st.spinner("Invoking agent..."):
            try:
                t0 = time.time()
                result = invoke_agent(
                    st.session_state.agent_arn,
                    prompt_to_send,
                    st.session_state.jwt_token,
                    config["username"],
                    config["region"],
                )
                st.session_state.last_response_time = round(time.time() - t0, 2)

                if is_3lo:
                    consent_url = extract_consent_url(result)
                    if consent_url:
                        st.session_state.consent_url = consent_url
                        st.session_state.consent_state = "pending"
                    elif st.session_state.consent_state != "completed":
                        st.session_state.consent_state = "completed"
                        st.session_state.consent_url = None

                st.markdown(_format_response(result))
                st.session_state.chat_history.append({"role": "assistant", "content": result})

                if is_3lo and st.session_state.consent_state == "pending" and st.session_state.consent_url:
                    provider_label = "GitHub" if flow_key == "github" else "Google"
                    st.info(
                        f"Consent required: click **Authorize on {provider_label}** in the sidebar, "
                        "then click **Re-invoke after consent** once you have authorized."
                    )

            except Exception as exc:
                error_msg = f"Error: {exc}"
                st.error(error_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

    st.rerun()
