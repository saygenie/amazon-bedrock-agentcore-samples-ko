# lab1

Amazon Bedrock AgentCore에 배포되는 MCP(Model Context Protocol) server입니다.

## 개요

이 프로젝트는 FastMCP를 사용하여 MCP server를 구현합니다. MCP server는 MCP client(다른 에이전트 또는 애플리케이션)가 사용할 수 있는 도구를 노출합니다.

## 로컬 개발

```bash
# 종속 항목 설치
uv sync

# MCP server 로컬 실행
uv run python main.py
```

서버는 Streamable HTTP transport를 사용하여 포트 8000에서 시작됩니다.

## 도구 추가

`main.py`에서 `@mcp.tool()` 데코레이터를 사용하여 도구를 정의합니다.

```python
@mcp.tool()
def my_tool(param: str) -> str:
    """Description of what the tool does."""
    return f"Result: {param}"
```

## 배포

```bash
agentcore deploy
```
