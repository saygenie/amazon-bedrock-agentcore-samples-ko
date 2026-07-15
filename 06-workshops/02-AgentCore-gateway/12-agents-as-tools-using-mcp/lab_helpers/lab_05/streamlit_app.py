"""
SRE AI Agent - Streamlit 채팅 애플리케이션
스트리밍을 지원하는 Strands supervisor agent용 채팅 인터페이스입니다.
모든 종속성을 인라인으로 포함한 독립 실행형 버전입니다.
"""

import streamlit as st
import json

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import boto3


# ============================================================================
# MCP 클라이언트 설정 함수(mcp_client_setup.py에서 인라인으로 가져옴)
# ============================================================================


def load_gateway_config():
    """
    gateway_config.json에서 Gateway 구성을 불러옵니다.

    반환:
        dict: Gateway 구성
    """
    with open("gateway_config.json", "r") as f:
        return json.load(f)


def get_access_token(config):
    """
    boto3를 직접 호출해 Cognito에서 OAuth 액세스 토큰을 가져옵니다.

    인자:
        config: Gateway 구성 딕셔너리

    반환:
        str: 액세스 토큰
    """
    client_info = config["client_info"]
    cognito = boto3.client("cognito-idp", region_name=config["region"])

    try:
        response = cognito.initiate_auth(
            ClientId=client_info["client_id"],
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": client_info["username"],
                "PASSWORD": client_info["password"],
            },
        )
        return response["AuthenticationResult"]["AccessToken"]
    except Exception as e:
        raise Exception(f"Failed to get access token: {str(e)}")


def create_mcp_client(gateway_url, access_token):
    """
    OAuth 인증을 사용하는 MCP 클라이언트를 생성합니다.

    인자:
        gateway_url: Gateway MCP 엔드포인트 URL
        access_token: Cognito의 OAuth 액세스 토큰

    반환:
        MCPClient: 구성된 MCP 클라이언트
    """
    return MCPClient(lambda: streamablehttp_client(gateway_url, headers={"Authorization": f"Bearer {access_token}"}))


def get_all_tools(mcp_client):
    """
    페이지네이션을 지원하며 Gateway의 모든 도구를 조회합니다.

    인자:
        mcp_client: MCPClient 인스턴스

    반환:
        list: 사용 가능한 모든 MCP 도구
    """
    tools = []
    pagination_token = None

    while True:
        result = mcp_client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(result)

        if result.pagination_token is None:
            break
        pagination_token = result.pagination_token

    return tools


# ============================================================================
# SUPERVISOR AGENT 함수(supervisor_agent.py에서 인라인으로 가져옴)
# ============================================================================


def create_supervisor_agent(model_id, tools, region="us-west-2"):
    """
    스트리밍이 활성화된 Strands supervisor agent를 생성합니다.

    인자:
        model_id: Bedrock 모델 식별자 또는 inference profile ARN
        tools: MCP 도구 목록
        region: AWS 리전

    반환:
        Agent: 구성된 Strands agent
    """
    # Claude 3.7 Sonnet용 cross-region inference profile 사용
    inference_profile = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

    model = BedrockModel(
        model_id=inference_profile,
        streaming=True,  # 스트리밍 활성화
    )

    system_prompt = """
        # Supervisor Agent System Prompt

You are an expert SRE Supervisor Agent that orchestrates three specialized sub-agents to provide complete infrastructure troubleshooting solutions.

## Sub-Agent Tools

### 1. Diagnostic Agent 
- Analyzes AWS infrastructure to identify root causes
- Provides detailed diagnostic information
- Identifies performance bottlenecks and configuration issues

### 2. Remediation Agent 
- Executes infrastructure fixes and remediation scripts
- Implements corrective actions with approval workflows
- Uses AgentCore Code Interpreter for secure execution

### 3. Prevention Agent 
- Researches AWS best practices and preventive measures
- Provides proactive recommendations
- Uses AgentCore Browser for real-time documentation

## Orchestration Workflow

For each user request:
1. **Diagnose**: Use diagnostic tools to identify issues
2. **Remediate**: Execute approved remediation steps
3. **Prevent**: Provide preventive recommendations
4. If the issues does not exist, Do NOT drift in finding other issues

## Response Structure

Always provide:
- **Summary**: Brief overview of the issue
- **Diagnostic Results**: What was found
- **Remediation Actions**: What was fixed (if applicable)
- **Prevention Recommendations**: How to avoid future issues

## Tool Usage Guidelines

- Use diagnostic tools to analyze and identify problems
- Use remediation tools for fixes (requires approval)
- Use prevention tools for best practices and research
- Coordinate across agents for comprehensive solutions

## Safety Rules

- Always validate environment before making changes
- Require explicit approval for remediation actions
- Provide clear explanations of all actions taken
- Include risk assessments for remediation steps
"""

    return Agent(model=model, tools=tools, system_prompt=system_prompt)


# 페이지 구성
st.set_page_config(
    page_title="SRE AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 더 나은 스타일을 위한 사용자 지정 CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .status-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .status-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .status-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .status-info {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .thinking-indicator {
        font-style: italic;
        color: #6c757d;
        padding: 0.5rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_agent():
    """Agent를 초기화하고 세션 상태에 저장합니다."""
    if "agent_initialized" not in st.session_state:
        with st.spinner("🔧 Initializing SRE AI Agent..."):
            try:
                # 구성 불러오기
                config = load_gateway_config()
                st.session_state.config = config

                # OAuth 토큰 가져오기
                access_token = get_access_token(config)
                st.session_state.access_token = access_token

                # JWT 토큰에서 이메일 추출
                import base64

                try:
                    # JWT 페이로드 디코딩(두 번째 부분)
                    payload = access_token.split(".")[1]
                    # 필요한 경우 패딩 추가
                    payload += "=" * (4 - len(payload) % 4)
                    decoded = base64.b64decode(payload)
                    token_data = json.loads(decoded)
                    st.session_state.user_email = token_data.get("email", token_data.get("username", "Unknown"))
                except Exception:
                    st.session_state.user_email = config["client_info"]["username"]

                # MCP 클라이언트 생성
                try:
                    mcp_client = create_mcp_client(config["gateway_url"], access_token)
                    st.session_state.mcp_client = mcp_client

                    # MCP 클라이언트 컨텍스트 초기화
                    st.session_state.mcp_client.__enter__()

                    # 도구 가져오기
                    tools = get_all_tools(mcp_client)
                    st.session_state.tools = tools
                except Exception as mcp_error:
                    raise Exception(f"MCP client initialization failed: {str(mcp_error)}")

                # Agent 생성
                model_id = "anthropic.claude-3-7-sonnet-20250219-v1:0"
                agent = create_supervisor_agent(model_id, tools, config["region"])
                st.session_state.agent = agent

                st.session_state.agent_initialized = True
                st.session_state.initialization_error = None

            except FileNotFoundError:
                st.session_state.agent_initialized = False
                st.session_state.initialization_error = (
                    "gateway_config.json not found. Please run Section 9.1 in the notebook first."
                )
            except Exception as e:
                st.session_state.agent_initialized = False
                import traceback

                st.session_state.initialization_error = f"{str(e)}\n\nDetails:\n{traceback.format_exc()}"


def stream_agent_response(prompt: str, message_placeholder) -> str:
    """
    콜백 핸들러를 사용해 Agent 응답을 스트리밍합니다.

    인자:
        prompt: 사용자 입력 prompt
        message_placeholder: 화면 업데이트용 Streamlit placeholder

    반환:
        str: 전체 응답 텍스트
    """
    agent = st.session_state.agent
    response_data = {
        "text": "",
        "last_update": 0,
        "tools_shown": set(),
        "in_tool_construction": False,
        "tool_start_times": {},
    }

    def streaming_callback(**kwargs):
        """Agent 스레드에서 실행되는 스트리밍 이벤트 콜백 핸들러입니다."""
        import time

        # 텍스트 스트리밍 처리
        if "data" in kwargs:
            data = kwargs["data"]

            # 도구 입력 구성 단계인지 감지
            if data.strip().startswith("{") or data.strip().startswith('"'):
                response_data["in_tool_construction"] = True
                return  # JSON 구성 건너뛰기
            elif response_data["in_tool_construction"] and not data.strip().endswith("}"):
                return  # 아직 JSON 구성 중
            else:
                response_data["in_tool_construction"] = False
                response_data["text"] += data
                response_data["last_update"] = time.time()

        # 도구 사용 처리: 도구 실행이 시작되면 표시(toolUseId가 있는 경우)
        elif "current_tool_use" in kwargs:
            tool_use = kwargs["current_tool_use"]
            tool_id = tool_use.get("toolUseId")
            tool_name = tool_use.get("name")

            # ID와 이름이 모두 있을 때만 표시(도구 실행 시작)
            if tool_id and tool_name and tool_id not in response_data["tools_shown"]:
                response_data["tools_shown"].add(tool_id)
                response_data["tool_start_times"][tool_id] = time.time()
                tool_text = f"\n\n🔧 **Using tool:** `{tool_name}`\n\n"
                response_data["text"] += tool_text
                response_data["last_update"] = time.time()
                response_data["in_tool_construction"] = False

        # 도구 완료 처리(도구 사용 후 메시지가 생성될 때)
        elif "message" in kwargs:
            message = kwargs["message"]
            if message.get("role") == "user":
                # 메시지에서 도구 결과 확인
                content = message.get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_id = item.get("tool_use_id")
                        if tool_id in response_data["tool_start_times"]:
                            elapsed = time.time() - response_data["tool_start_times"][tool_id]
                            timing_text = f"⏱️ *Completed in {elapsed:.2f}s*\n\n"
                            response_data["text"] += timing_text
                            response_data["last_update"] = time.time()
                            del response_data["tool_start_times"][tool_id]

    try:
        import time
        import threading

        # 백그라운드 스레드에서 Agent 시작
        agent_thread = threading.Thread(target=lambda: agent(prompt, callback_handler=streaming_callback))
        agent_thread.start()

        # Agent 실행 중 메인 스레드에서 UI 업데이트
        while agent_thread.is_alive():
            if response_data["text"]:
                message_placeholder.markdown(response_data["text"] + "▌")
            time.sleep(0.1)

        # 스레드 완료 대기
        agent_thread.join()

        # 커서 없이 최종 응답 표시
        final_response = response_data["text"]
        message_placeholder.markdown(final_response)
        return final_response

    except Exception as e:
        import traceback

        error_msg = f"\n\n❌ Error: {str(e)}\n```\n{traceback.format_exc()}\n```"
        message_placeholder.markdown(error_msg)
        return error_msg


def main():
    """메인 애플리케이션 함수입니다."""

    # 헤더
    st.markdown('<div class="main-header">🤖 SRE AI Agent</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Agent 초기화
    initialize_agent()

    # 사이드바
    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown("""
        **SRE AI Agent** is a Strands-based supervisor agent that orchestrates three specialized agents.
        
        **Features:**
        - 🔍 Diagnostics Agent - Analyzes logs and metrics
        - 🔧 Remediation Agent - Executes fixes with Code Interpreter
        - 🛡️ Prevention Agent - Researches best practices with Browser
        - 🔄 Real-time streaming responses
        - 🔐 OAuth authentication via Cognito
        """)

        st.markdown("---")

        # 상태 정보
        if st.session_state.get("agent_initialized"):
            st.markdown(
                '<div class="status-box status-success">✅ Agent Ready</div>',
                unsafe_allow_html=True,
            )

            config = st.session_state.config
            st.markdown("**Configuration:**")
            st.text(f"Gateway: {config['gateway_id']}")
            st.text(f"Region: {config['region']}")

            # JWT 토큰의 로그인 사용자 표시
            st.markdown("**Logged in as:**")
            user_email = st.session_state.get("user_email", "Unknown")
            st.text(f"👤 {user_email}")

            if "tools" in st.session_state:
                st.markdown(f"**Tools Available:** {len(st.session_state.tools)}")
                for tool in st.session_state.tools:
                    st.text(f"  • {tool.tool_name}")
        else:
            error = st.session_state.get("initialization_error", "Unknown error")
            st.markdown(
                f'<div class="status-box status-error">❌ Initialization Failed<br/>{error}</div>',
                unsafe_allow_html=True,
            )

            if "gateway_config.json not found" in error:
                st.info("💡 Run `python setup_gateway.py` to create the Gateway infrastructure.")

        st.markdown("---")

        # 채팅 지우기 버튼
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()

    # 채팅 기록 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 채팅 입력
    if st.session_state.get("agent_initialized"):
        if prompt := st.chat_input(
            "Ask about your infrastructure (e.g., 'What issues do you see in the CRM application?')..."
        ):
            # 채팅 기록에 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})

            # 사용자 메시지 표시
            with st.chat_message("user"):
                st.markdown(prompt)

            # Assistant 응답을 스트리밍으로 표시
            with st.chat_message("assistant"):
                message_placeholder = st.empty()

                # 콜백 핸들러를 사용해 응답 스트리밍
                with st.spinner("🤔 Thinking..."):
                    full_response = stream_agent_response(prompt, message_placeholder)

            # 채팅 기록에 Assistant 응답 추가
            st.session_state.messages.append({"role": "assistant", "content": full_response})
    else:
        st.error("⚠️ Agent not initialized. Please check the sidebar for details.")
        st.info("Make sure you have run `python setup_gateway.py` to set up the Gateway infrastructure.")


if __name__ == "__main__":
    main()
