"""
도구를 사용하는 에이전트 모듈

이 모듈은 AgentCore Gateway를 통해 보험 인수 도구에 접근하는
에이전트를 생성하고 상호 작용하는 함수를 제공합니다.
"""

import json
import os
import requests
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client


def load_config():
    """config.json에서 구성을 로드합니다."""
    config_path = Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\nPlease run deploy_lambdas.py and setup_gateway.py first."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 필수 필드 검증
    if "gateway" not in config:
        raise ValueError("Gateway configuration not found in config.json\nPlease run setup_gateway.py first.")

    return config


def create_streamable_http_transport(mcp_url: str, access_token: str):
    """MCP 클라이언트용 Streamable HTTP 전송을 생성합니다."""
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})


def fetch_access_token(client_id, client_secret, token_url):
    """Cognito에서 액세스 토큰을 가져옵니다."""
    response = requests.post(
        token_url,
        data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if response.status_code != 200:
        raise Exception(f"Failed to get access token: {response.text}")

    return response.json()["access_token"]


def list_available_tools(gateway_url: str, access_token: str):
    """Gateway에서 사용 가능한 모든 도구를 나열합니다."""
    try:
        mcp_client = MCPClient(lambda: create_streamable_http_transport(gateway_url, access_token))
        with mcp_client:
            tools_list = mcp_client.list_tools_sync()
            # MCPAgentTool에 description 속성이 없을 수 있으므로 기본값과 함께 getattr 사용
            return [(tool.tool_name, getattr(tool, "description", "")) for tool in tools_list]
    except Exception as e:
        print(f"⚠️  Could not list tools: {e}")
        return []


class AgentSession:
    """
    MCP 클라이언트 수명 주기를 올바르게 처리하는 에이전트 세션 컨텍스트 관리자입니다.

    사용법:
        with AgentSession() as session:
            response = session.invoke("What tools do you have?")
    """

    def __init__(self, model_id="us.amazon.nova-lite-v1:0", verbose=True):
        self.model_id = model_id
        self.verbose = verbose
        self.mcp_client = None
        self.agent = None
        self.config = None
        self.gateway_url = None
        self.access_token = None

    def __enter__(self):
        """에이전트 세션을 설정합니다."""
        # 구성 로드
        if self.verbose:
            print("📦 Loading configuration...")
        self.config = load_config()

        gateway_config = self.config["gateway"]
        client_info = gateway_config["client_info"]

        CLIENT_ID = client_info["client_id"]
        CLIENT_SECRET = client_info["client_secret"]
        TOKEN_URL = client_info["token_endpoint"]
        self.gateway_url = gateway_config["gateway_url"]
        region = self.config.get("region")

        # AWS 리전 설정
        os.environ["AWS_DEFAULT_REGION"] = region

        if self.verbose:
            print("✅ Configuration loaded")
            print(f"   Gateway: {gateway_config.get('gateway_name', 'N/A')}")
            print(f"   Region: {region}")

        # 액세스 토큰 가져오기
        if self.verbose:
            print("\n🔑 Authenticating...")
        self.access_token = fetch_access_token(CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
        if self.verbose:
            print("✅ Authentication successful")

        # 사용 가능한 도구 나열
        if self.verbose:
            print("\n📋 Listing available tools...")
        tool_info = list_available_tools(self.gateway_url, self.access_token)

        if tool_info and self.verbose:
            print(f"✅ Found {len(tool_info)} tool(s):")
            for tool_name, tool_desc in tool_info:
                print(f"   • {tool_name}")
                if tool_desc:
                    print(f"     {tool_desc}")

        # Bedrock 모델 설정
        if self.verbose:
            print(f"\n🤖 Setting up model: {self.model_id}")
        bedrockmodel = BedrockModel(
            model_id=self.model_id,
            streaming=True,
        )

        # MCP 클라이언트 생성
        self.mcp_client = MCPClient(lambda: create_streamable_http_transport(self.gateway_url, self.access_token))

        # MCP 클라이언트 컨텍스트 진입
        self.mcp_client.__enter__()

        # MCP 클라이언트에서 도구 가져오기
        tools = self.mcp_client.list_tools_sync()

        # 시스템 프롬프트를 사용하는 에이전트 생성
        system_prompt = """You are a helpful AI assistant for insurance underwriting operations.

You have access to tools from the gateway. The gateway is configured with policies which restrict 
tool access. Only use the tools provided by the gateway. Do not make up any information.

When using tools, show which tool you invoked, what you're doing and the results.
If a tool call fails, explain the error clearly to the user."""

        self.agent = Agent(model=bedrockmodel, tools=tools, system_prompt=system_prompt)

        if self.verbose:
            print("✅ Agent ready!\n")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """에이전트 세션을 정리합니다."""
        if self.mcp_client:
            try:
                self.mcp_client.__exit__(exc_type, exc_val, exc_tb)
                if self.verbose:
                    print("✅ Agent session closed")
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Error closing agent session: {e}")

    def invoke(self, prompt, verbose=None):
        """
        프롬프트로 에이전트를 호출합니다.

        인수:
            prompt: 사용자 프롬프트/질문
            verbose: 프롬프트 출력 여부(기본값: 세션의 verbose 설정 사용)

        반환값:
            str: 에이전트의 응답
        """
        if verbose is None:
            verbose = self.verbose

        if verbose:
            print(f"💬 Prompt: {prompt}\n")
            print("🤔 Thinking...\n")

        try:
            response = self.agent(prompt)

            # 응답 콘텐츠 추출
            if hasattr(response, "message"):
                content = response.message.get("content", str(response))
            else:
                content = str(response)

            if verbose:
                print(f"🤖 Agent: {content}\n")

            return content

        except Exception as e:
            error_msg = f"Error: {e}"
            if verbose:
                print(f"❌ {error_msg}\n")
            return error_msg


# 사용 예시 함수
def example_usage():
    """이 모듈의 사용 예시를 보여 줍니다."""
    print("=" * 70)
    print("🚀 Insurance Underwriting Agent Example")
    print("=" * 70)
    print()

    # 에이전트 세션 컨텍스트 관리자 사용
    with AgentSession() as session:
        # 프롬프트 예시
        prompts = [
            "What tools do you have access to?",
            "Create an application for US region with $50000 coverage",
        ]

        print("=" * 70)
        print("📝 Running example prompts...")
        print("=" * 70)
        print()

        for prompt in prompts:
            session.invoke(prompt)
            print("-" * 70)
            print()

    print("✅ Done!")


if __name__ == "__main__":
    example_usage()
