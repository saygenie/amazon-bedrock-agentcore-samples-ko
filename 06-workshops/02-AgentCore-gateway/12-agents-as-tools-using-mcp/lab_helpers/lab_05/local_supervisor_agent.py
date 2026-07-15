"""
Lab 05용 로컬 Supervisor Agent
파라미터화된 Gateway URL과 액세스 토큰으로 Notebook에서 Strands agent를 로컬 실행합니다.
"""

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import logging

# 로깅 구성
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()])


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


def create_supervisor_agent(model_id, tools, region="us-west-2"):
    """
    Strands supervisor agent를 생성합니다.

    인자:
        model_id: Bedrock 모델 식별자 또는 inference profile ARN
        tools: MCP 도구 목록
        region: AWS 리전

    반환:
        Agent: 구성된 Strands agent
    """
    system_prompt = """
# Supervisor Agent System Prompt

You are an expert SRE Supervisor Agent that orchestrates three specialized sub-agents to provide complete infrastructure troubleshooting solutions.

## Sub-Agent Tools

### 1. Diagnostic Agent 
- Analyzes AWS infrastructure to identify root causes
- Provides detailed diagnostic information
- Identifies performance bottlenecks and configuration issues

### 2. Infrastructure Agent 
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

## CRITICAL - Ensure when calling Infrastructure / Remediation Agent always use only_execute

## Safety Rules

- Always validate environment before making changes
- Require explicit approval for remediation actions
- Provide clear explanations of all actions taken
- Include risk assessments for remediation steps

Note: After every tool call, provide a short summary of what you did with that tool call.
"""

    model = BedrockModel(
        model_id=model_id,
        streaming=True,
    )

    return Agent(model=model, tools=tools, system_prompt=system_prompt)


def run_supervisor_agent(
    gateway_url,
    access_token,
    prompt,
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
):
    """
    파라미터화된 구성으로 Supervisor Agent를 실행합니다.

    인자:
        gateway_url: Gateway MCP 엔드포인트 URL
        access_token: Cognito의 OAuth 액세스 토큰
        prompt: Agent에 전달할 사용자 prompt/query
        model_id: Bedrock 모델 식별자(기본값: Claude Haiku 4.5)

    반환:
        str: Agent 응답 텍스트
    """
    try:
        mcp_client = create_mcp_client(gateway_url, access_token)

        with mcp_client:
            tools = get_all_tools(mcp_client)
            print(f":white_check_mark: Retrieved {len(tools)} tools from gateway")

            agent = create_supervisor_agent(model_id, tools)
            print(f":white_check_mark: Created supervisor agent with model: {model_id}")
            print(f":robot_face: Processing: {prompt}\n")

            response = agent(prompt)

            # 응답에서 텍스트 추출
            content = response.message.get("content", [])
            if isinstance(content, list) and len(content) > 0:
                text = content[0].get("text", str(response))
            else:
                text = str(content)

            return text
    except Exception as e:
        print(f":x: Supervisor Agent Failed: {e}")
        raise
