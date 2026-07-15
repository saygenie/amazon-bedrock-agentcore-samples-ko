from strands import Agent
from strands.models import BedrockModel
from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# BedrockAgentCoreApp 초기화
app = BedrockAgentCoreApp()


# AWS Documentation MCP 서버에 연결
def create_aws_docs_client():
    return MCPClient(
        lambda: stdio_client(StdioServerParameters(command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"]))
    )


# AWS CDK MCP 서버에 연결
def create_cdk_client():
    return MCPClient(lambda: stdio_client(StdioServerParameters(command="uvx", args=["awslabs.cdk-mcp-server@latest"])))


# 두 MCP 서버의 도구를 사용하는 에이전트 생성 함수
def create_agent():
    model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    model = BedrockModel(model_id=model_id)

    aws_docs_client = create_aws_docs_client()
    cdk_client = create_cdk_client()

    with aws_docs_client, cdk_client:
        # 두 MCP 서버에서 도구 가져오기
        tools = aws_docs_client.list_tools_sync() + cdk_client.list_tools_sync()

        # 가져온 도구로 에이전트 생성
        agent = Agent(
            model=model,
            tools=tools,
            system_prompt="""You are a helpful AWS assistant with access to AWS Documentation 
            and CDK best practices. Provide concise and accurate information about AWS services 
            and infrastructure as code patterns. When asked about pricing or CDK, use your tools 
            to search for the most current information.""",
        )

    return agent, aws_docs_client, cdk_client


@app.entrypoint
def invoke_agent(payload):
    """입력 페이로드를 처리하고 에이전트의 응답을 반환합니다."""
    agent, aws_docs_client, cdk_client = create_agent()

    with aws_docs_client, cdk_client:
        user_input = payload.get("prompt")
        print(f"Processing request: {user_input}")
        response = agent(user_input)
        return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
