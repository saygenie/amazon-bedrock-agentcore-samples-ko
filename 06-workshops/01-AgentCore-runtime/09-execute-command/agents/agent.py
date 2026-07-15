# Bedrock AgentCore에 필요한 library import
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

# AgentCore application 초기화
app = BedrockAgentCoreApp()

# AI agent instance 생성
agent = Agent()


@app.entrypoint
def invoke(payload, context):
    """
    Agent의 기본 entry point입니다.

    인수:
        payload: 사용자 입력이 담긴 'prompt' key를 포함하는 dictionary
        context: Runtime context 정보

    반환:
        Agent의 응답 message가 포함된 dictionary
    """
    # Payload에서 user prompt 추출
    user_message = payload.get("prompt", "Hello!")

    # Agent로 message 처리
    result = agent(user_message)

    # 예상 형식으로 응답 반환
    return {"result": result.message}


if __name__ == "__main__":
    # Agent application 실행
    app.run()
