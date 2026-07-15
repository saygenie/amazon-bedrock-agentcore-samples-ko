"""
Travel Agent: 웹 검색 기능을 갖춘 Strands 기반 에이전트입니다.
직접 호출할 수 있는 표준 AgentCore Runtime 엔드포인트로 노출됩니다.
"""

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from ddgs import DDGS
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = BedrockAgentCoreApp()

MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")


# --- 도구 정의 ---
@tool
def web_search(query: str) -> str:
    """Search the web for travel information."""
    logger.info(f"Searching for: {query}")
    results = DDGS().text(query, max_results=3)
    return "\n".join([f"- {r['title']}: {r['body']}" for r in results])


# --- 에이전트 정의 ---
model = BedrockModel(model_id=MODEL_ID)
agent = Agent(
    name="Travel Agent",
    model=model,
    tools=[web_search],
    system_prompt="You are a travel expert. Help users with destinations, attractions, and travel tips. Use the web_search tool to find current information.",
)


@app.entrypoint
def invoke(payload, context):
    """직접 호출을 위한 기본 진입점입니다."""
    prompt = payload.get("prompt", "")

    session_id = getattr(context, "session_id", "no-session")
    logger.info(f"Travel Agent received: {prompt}, session: {session_id}")

    response = agent(prompt)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
