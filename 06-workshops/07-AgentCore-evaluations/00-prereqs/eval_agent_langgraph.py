from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import operator
import math

app = BedrockAgentCoreApp()


# 계산기 도구 생성
@tool
def calculator(expression: str) -> str:
    """
    Calculate the result of a mathematical expression.

    Args:
        expression: A mathematical expression as a string (e.g., "2 + 3 * 4", "sqrt(16)", "sin(pi/2)")

    Returns:
        The result of the calculation as a string
    """
    try:
        # 표현식에서 사용할 수 있는 안전한 함수 정의
        safe_dict = {
            "__builtins__": {},
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            # 수학 함수
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
            "ceil": math.ceil,
            "floor": math.floor,
            "degrees": math.degrees,
            "radians": math.radians,
            # 기본 연산자(명시적 사용용)
            "add": operator.add,
            "sub": operator.sub,
            "mul": operator.mul,
            "truediv": operator.truediv,
        }

        # 표현식을 안전하게 평가
        result = eval(expression, safe_dict)  # nosec B307
        return str(result)

    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: Invalid value - {str(e)}"
    except SyntaxError:
        return "Error: Invalid mathematical expression"
    except Exception as e:
        return f"Error: {str(e)}"


# 사용자 지정 날씨 도구 생성
@tool
def weather():
    """Get weather"""  # 더미 구현
    return "sunny"


# LangGraph를 직접 구성하여 에이전트 정의
def create_agent():
    """LangGraph agent를 생성하고 구성합니다."""
    from langchain_aws import ChatBedrock

    # LLM 초기화(필요에 따라 모델과 파라미터 조정)
    llm = ChatBedrock(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",  # 또는 선호하는 모델
        model_kwargs={"temperature": 0.1},
    )

    # LLM에 도구 바인딩
    tools = [calculator, weather]
    llm_with_tools = llm.bind_tools(tools)

    # 시스템 메시지
    system_message = "You're a helpful assistant. You can do simple math calculation, and tell the weather."

    # 챗봇 노드 정의
    def chatbot(state: MessagesState):
        # 시스템 메시지가 아직 없으면 추가
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_message)] + messages

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # 그래프 생성
    graph_builder = StateGraph(MessagesState)

    # 노드 추가
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))

    # 엣지 추가
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")

    # 진입점 설정
    graph_builder.set_entry_point("chatbot")

    # 그래프 컴파일
    return graph_builder.compile()


# 에이전트 초기화
agent = create_agent()


@app.entrypoint
def langgraph_bedrock(payload):
    """
    페이로드로 에이전트를 호출합니다.
    """
    user_input = payload.get("prompt")

    # LangGraph가 요구하는 형식으로 입력 생성
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    # 최종 메시지 내용 추출
    return response["messages"][-1].content


if __name__ == "__main__":
    app.run()
