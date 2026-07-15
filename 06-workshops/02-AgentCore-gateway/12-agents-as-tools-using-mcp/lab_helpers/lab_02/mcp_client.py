#!/usr/bin/env python3
"""
Lab 02: MCP 클라이언트 헬퍼

AgentCore Gateway에 연결하고 Cognito JWT 인증으로 MCP 도구를 호출하는
간단한 MCP 클라이언트를 제공합니다.

주요 기능:
- Cognito JWT 인증
- MCP 프로토콜(initialize, tools/list, tools/call)
- Gateway 연결 관리
- 간단한 도구 호출 인터페이스

사용법:
    from lab_helpers.lab_02.mcp_client import MCPClient

    client = MCPClient(gateway_url, cognito_token)
    client.initialize()
    tools = client.list_tools()
    result = client.call_tool("tool_name", {"arg": "value"})
"""

import requests
import json
from typing import Dict, List, Any, Optional


class MCPClient:
    """
    AgentCore Gateway에 연결하는 MCP 클라이언트입니다.

    이 클라이언트는 다음을 처리합니다.
    - Cognito 토큰을 사용한 JWT 인증
    - MCP 프로토콜(JSON-RPC 2.0)
    - 세션 초기화
    - 도구 검색 및 호출
    """

    def __init__(self, gateway_url: str, access_token: str, timeout: int = 900):
        """
        MCP 클라이언트를 초기화합니다.

        인자:
            gateway_url: Gateway MCP 엔드포인트 URL
            access_token: Cognito JWT 액세스 토큰
            timeout: 요청 제한 시간(초)(기본값: 30)
        """
        self.gateway_url = gateway_url
        self.access_token = access_token
        self.timeout = timeout
        self.request_id = 0
        self.initialized = False
        self.server_info = {}

    def _next_request_id(self) -> int:
        """다음 JSON-RPC 요청 ID를 생성합니다."""
        self.request_id += 1
        return self.request_id

    def _mcp_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Gateway에 MCP JSON-RPC 요청을 보냅니다.

        인자:
            method: MCP 메서드 이름(예: "initialize", "tools/list", "tools/call")
            params: 메서드 파라미터(선택 사항)

        반환:
            딕셔너리 형식의 JSON-RPC 응답

        예외:
            requests.HTTPError: HTTP 요청이 실패한 경우
            ValueError: 응답에 오류가 포함된 경우
        """
        request_payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method,
        }

        if params is not None:
            request_payload["params"] = params

        response = requests.post(
            self.gateway_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            json=request_payload,
            timeout=self.timeout,
        )

        response.raise_for_status()
        result = response.json()

        # JSON-RPC 오류 확인
        if "error" in result:
            error = result["error"]
            raise ValueError(f"MCP Error [{error.get('code')}]: {error.get('message')}")

        return result

    def initialize(
        self,
        client_name: str = "aiml301-diagnostics-mcp-client",
        client_version: str = "1.0.0",
    ) -> Dict[str, Any]:
        """
        Gateway와의 MCP 세션을 초기화합니다.

        다른 MCP 작업보다 먼저 호출해야 합니다.

        인자:
            client_name: 클라이언트 애플리케이션 이름
            client_version: 클라이언트 버전 문자열

        반환:
            initialize 응답의 서버 정보

        예:
            >>> client.initialize()
            {'name': 'aiml301-diagnostics-gateway', 'version': '1.0.0'}
        """
        print("🚀 Initializing MCP session...")

        response = self._mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": client_name, "version": client_version},
            },
        )

        if "result" in response:
            self.server_info = response["result"].get("serverInfo", {})
            self.initialized = True

            print("  ✅ Session initialized")
            print(f"     Server: {self.server_info.get('name', 'Unknown')}")
            print(f"     Version: {self.server_info.get('version', 'Unknown')}")

            return self.server_info
        else:
            raise ValueError("Initialize failed: No result in response")

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Gateway에서 사용 가능한 모든 MCP 도구를 나열합니다.

        반환:
            이름, 설명 및 스키마가 포함된 도구 정의 목록

        예:
            >>> tools = client.list_tools()
            >>> print(f"Found {len(tools)} tools")
            >>> for tool in tools:
            >>>     print(f"  - {tool['name']}: {tool['description']}")
        """
        if not self.initialized:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        print("\n🔧 Listing available tools...")

        response = self._mcp_request(method="tools/list", params={})

        if "result" in response:
            tools = response["result"].get("tools", [])
            print(f"  ✅ Found {len(tools)} tool(s)")

            for i, tool in enumerate(tools, 1):
                tool_name = tool.get("name", "unnamed")
                # 설명의 첫 줄 가져오기
                description = tool.get("description", "No description")
                first_line = description.split("\n")[0]
                print(f"     {i}. {tool_name}")
                print(f"        {first_line[:80]}...")

            return tools
        else:
            raise ValueError("List tools failed: No result in response")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        인자를 사용해 MCP 도구를 호출합니다.

        인자:
            tool_name: 호출할 도구 이름
            arguments: 딕셔너리 형식의 도구 인자

        반환:
            도구 실행 결과

        예:
            >>> result = client.call_tool(
            ...     "strands-diagnostics-agent___invoke_diagnostics_agent",
            ...     {"query": "What are the main issues?"}
            ... )
            >>> print(result)
        """
        if not self.initialized:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        print(f"\n🔨 Calling tool: {tool_name}")
        print(f"   Arguments: {json.dumps(arguments, indent=2)}")

        response = self._mcp_request(method="tools/call", params={"name": tool_name, "arguments": arguments})

        if "result" in response:
            result = response["result"]
            print("  ✅ Tool execution successful")

            # 콘텐츠 추출 및 표시 시도
            if "content" in result:
                for content_item in result["content"]:
                    if content_item.get("type") == "text":
                        try:
                            # 더 읽기 쉽게 표시하도록 JSON 파싱 시도
                            text_content = content_item["text"]
                            parsed = json.loads(text_content)
                            print("\n  📋 Result:")
                            print(f"     {json.dumps(parsed, indent=6)}")
                        except (json.JSONDecodeError, KeyError):
                            print(f"\n  📋 Result: {content_item['text'][:500]}...")

            return result
        else:
            raise ValueError("Tool call failed: No result in response")

    def close(self):
        """MCP 세션을 닫습니다(필요한 경우 정리)."""
        self.initialized = False
        print("\n✅ MCP session closed")


def create_mcp_client(gateway_url: str, cognito_token: str) -> MCPClient:
    """
    MCP 클라이언트를 생성하고 초기화하는 팩토리 함수입니다.

    인자:
        gateway_url: Gateway MCP 엔드포인트 URL
        cognito_token: Cognito JWT 액세스 토큰

    반환:
        초기화된 MCPClient 인스턴스

    예:
        >>> from lab_helpers.lab_02.mcp_client import create_mcp_client
        >>> client = create_mcp_client(gateway_url, token)
        >>> tools = client.list_tools()
    """
    client = MCPClient(gateway_url, cognito_token)
    client.initialize()
    return client
