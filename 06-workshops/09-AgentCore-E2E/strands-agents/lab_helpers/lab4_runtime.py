import boto3
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp,
)  # ### AGENTCORE RUNTIME - 1번 줄 ####
from lab_helpers.lab1_strands_agent import (
    MODEL_ID,
    SYSTEM_PROMPT,
    get_product_info,
    get_return_policy,
    get_technical_support,
)
from lab_helpers.lab2_memory import (
    ACTOR_ID,
    SESSION_ID,
    CustomerSupportMemoryHooks,
    memory_client,
)
from lab_helpers.utils import get_ssm_parameter
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# boto3 클라이언트 초기화
sts_client = boto3.client("sts")

# AWS 계정 세부 정보 가져오기
REGION = boto3.session.Session().region_name

# Lab 1 가져오기: Bedrock 모델 생성
model = BedrockModel(model_id=MODEL_ID)

# Lab 2 가져오기: 후크를 통해 Memory 초기화
memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
memory_hooks = CustomerSupportMemoryHooks(memory_id, memory_client, ACTOR_ID, SESSION_ID)

# AgentCore Runtime 앱 초기화
app = BedrockAgentCoreApp()  #### AGENTCORE RUNTIME - 2번 줄 ####


@app.entrypoint  #### AGENTCORE RUNTIME - 3번 줄 ####
async def invoke(payload, context=None):
    """AgentCore Runtime 진입점 함수"""
    user_input = payload.get("prompt", "")

    # 요청 헤더에 접근하고 None인 경우 처리
    request_headers = context.request_headers or {}

    # 클라이언트 JWT 토큰 가져오기
    auth_header = request_headers.get("Authorization", "")

    print(f"Authorization header: {auth_header}")
    # Gateway ID 가져오기
    existing_gateway_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")

    # Bedrock AgentCore Control 클라이언트 초기화
    gateway_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=REGION,
    )
    # 기존 Gateway 세부 정보 가져오기
    gateway_response = gateway_client.get_gateway(gatewayIdentifier=existing_gateway_id)

    # Gateway URL 가져오기
    gateway_url = gateway_response["gatewayUrl"]

    # JWT 토큰을 사용할 수 있으면 컨텍스트 관리자 안에서 MCP 클라이언트와 에이전트 생성
    if gateway_url and auth_header:
        try:
            mcp_client = MCPClient(
                lambda: streamablehttp_client(url=gateway_url, headers={"Authorization": auth_header})
            )

            with mcp_client:
                # tools = mcp_client.list_tools_sync()
                tools = [
                    get_product_info,
                    get_return_policy,
                    get_technical_support,
                ] + mcp_client.list_tools_sync()

                # 모든 고객 지원 도구를 포함하는 에이전트 생성
                agent = Agent(
                    model=model,
                    tools=tools,
                    system_prompt=SYSTEM_PROMPT,
                    hooks=[memory_hooks],
                )
                # 에이전트 호출
                response = agent(user_input)
                return response.message["content"][0]["text"]
        except Exception as e:
            print(f"MCP client error: {str(e)}")
            return f"Error: {str(e)}"
    else:
        return "Error: Missing gateway URL or authorization header"


if __name__ == "__main__":
    app.run()  #### AGENTCORE RUNTIME - 4번 줄 ####
