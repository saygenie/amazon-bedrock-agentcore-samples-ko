"""
AgentCore Gateway를 통해 도구를 호출하는 AgentCore Runtime 에이전트입니다.

- 인바운드 인증: 런타임 엔드포인트가 Cognito JWT로 보호됩니다.
                  호출자는 유효한 bearer token을 제시해야 합니다.
- 아웃바운드 인증: 에이전트가 관리형 OAuth2 자격 증명
                   (CLI의 --agent-client-id/secret으로 생성)을 사용해 Gateway에 인증합니다.
                   그런 다음 Gateway가 업스트림 MCP 서버에 인증합니다.

에이전트는 AgentCore Identity(@requires_access_token)를 통해 Gateway용 bearer token을
가져온 다음, httpx로 Gateway의 MCP 엔드포인트를 호출하여 도구를 검색하고 실행합니다.
"""

import os

import httpx
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token

app = BedrockAgentCoreApp()
_model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")

_gateway_token_cache: dict = {}


@requires_access_token(
    provider_name="MyGateway-oauth",
    auth_flow="M2M",
    scopes=[],
)
async def _fetch_gateway_token(*, access_token: str) -> None:
    """AgentCore Identity에서 Gateway용 관리형 bearer token을 가져옵니다."""
    _gateway_token_cache["token"] = access_token


async def _call_mcp(method: str, params: dict) -> dict:
    """관리형 자격 증명으로 AgentCore Gateway MCP 엔드포인트를 호출합니다."""
    if "token" not in _gateway_token_cache:
        await _fetch_gateway_token(access_token="")

    gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
    if not gateway_url:
        raise ValueError("AGENTCORE_GATEWAY_URL is not set.")

    token = _gateway_token_cache["token"]
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            gateway_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json().get("result", {})


@tool
async def get_time() -> str:
    """Get the current UTC time from the gateway."""
    result = await _call_mcp("tools/call", {"name": "MyTools___get_time", "arguments": {}})
    content = result.get("content", [])
    return content[0].get("text", str(result)) if content else str(result)


@tool
async def echo(message: str) -> str:
    """Echo a message back through the gateway.

    Args:
        message: The message to echo
    """
    result = await _call_mcp("tools/call", {"name": "MyTools___echo", "arguments": {"message": message}})
    content = result.get("content", [])
    return content[0].get("text", str(result)) if content else str(result)


_agent: Agent | None = None


@app.entrypoint
async def handler(payload: dict) -> str:
    global _agent

    if _agent is None:
        _agent = Agent(
            model=_model,
            tools=[get_time, echo],
            system_prompt=(
                "You are a helpful assistant with access to two gateway tools: "
                "get_time (returns current UTC time) and echo (echoes a message). "
                "The gateway handles all authentication to the upstream service."
            ),
        )

    user_input = payload.get("prompt", "")
    response = _agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
