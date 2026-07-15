"""
Weather Agent: 날씨 조회 기능을 갖춘 LangGraph 기반 에이전트입니다.
직접 호출할 수 있는 표준 AgentCore Runtime 엔드포인트로 노출됩니다.
"""

from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_aws import ChatBedrock
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")


# --- 도구 정의 ---
@tool
def get_weather(location: str) -> str:
    """Get current weather for a location."""
    logger.info(f"Getting weather for: {location}")
    weather_data = {
        "new york": "72°F, Partly Cloudy",
        "london": "59°F, Rainy",
        "tokyo": "68°F, Clear",
        "paris": "65°F, Overcast",
    }
    return weather_data.get(location.lower(), f"Weather for {location}: 70°F, Clear")


# --- 에이전트 정의 ---
def create_agent():
    """LangGraph 날씨 에이전트를 생성합니다."""
    llm = ChatBedrock(model_id=MODEL_ID, model_kwargs={"temperature": 0.1})
    tools = [get_weather]
    llm_with_tools = llm.bind_tools(tools)

    def chatbot(state: MessagesState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [
                SystemMessage(
                    content="You are a weather assistant. Use the get_weather tool to look up weather information for locations."
                )
            ] + messages
        return {"messages": [llm_with_tools.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", ToolNode(tools))
    graph.add_conditional_edges("chatbot", tools_condition)
    graph.add_edge("tools", "chatbot")
    graph.set_entry_point("chatbot")
    return graph.compile()


agent = create_agent()


@app.entrypoint
def invoke(payload, context):
    """직접 호출을 위한 기본 진입점입니다."""
    prompt = payload.get("prompt", "")

    logger.info(f"Weather Agent received: {prompt}, session: {context.session_id}")

    response = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    return response["messages"][-1].content


if __name__ == "__main__":
    app.run()
