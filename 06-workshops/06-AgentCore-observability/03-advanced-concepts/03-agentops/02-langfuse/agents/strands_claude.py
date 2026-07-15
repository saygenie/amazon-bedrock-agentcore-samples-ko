from bedrock_agentcore.runtime import BedrockAgentCoreApp
import os
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from langfuse import get_client


streamable_http_mcp_client = MCPClient(lambda: streamablehttp_client("https://langfuse.com/api/mcp"))


# Bedrock 모델 초기화 함수
def get_bedrock_model():
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")

    bedrock_model = BedrockModel(model_id=model_id, region_name=region, temperature=0.0, max_tokens=4096)
    return bedrock_model


# Bedrock 모델 초기화
bedrock_model = get_bedrock_model()

# 에이전트의 시스템 프롬프트 정의(AWS 샘플 원문 그대로 사용)
system_prompt = os.getenv("SYSTEM_PROMPT", "You are an experienced agent supporting developers.")
env = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "DEV")

app = BedrockAgentCoreApp()


@app.entrypoint
def strands_agent_bedrock(payload):
    """
    페이로드로 에이전트를 호출합니다.
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")
    print("User input:", user_input)

    # Strands 텔레메트리를 초기화하고 OTLP 내보내기 도구 설정
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()

    # MCP 도구를 사용하는 에이전트 생성
    with streamable_http_mcp_client:
        mcp_tools = streamable_http_mcp_client.list_tools_sync()

        # 에이전트 생성
        agent = Agent(model=bedrock_model, system_prompt=system_prompt, tools=mcp_tools)
        # DEV 및 TST 환경에서 AgentCore와 Langfuse 실험의 트레이스를 통합하도록 OTEL 분산 추적 스팬을 다시 엶
        if env == "DEV" or env == "TST":
            with get_client().start_as_current_observation(
                name="strands-agent",
                trace_context={
                    "trace_id": trace_id,
                    "parent_observation_id": parent_obs_id,
                },
            ):
                response = agent(user_input)
        else:
            response = agent(user_input)

    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
