# AgentCore Runtime에서 MCP 서버 호스팅

## 개요

이 세션에서는 Amazon Bedrock AgentCore Runtime에서 MCP 도구를 호스팅하는 방법을 설명합니다.

Amazon Bedrock AgentCore Python SDK를 사용하여 에이전트 함수를 Amazon Bedrock AgentCore와 호환되는 MCP 서버로 감쌉니다.
SDK가 MCP 서버의 세부 사항을 처리하므로 에이전트의 핵심 기능에 집중할 수 있습니다.

Amazon Bedrock AgentCore Python SDK는 AgentCore Runtime에서 실행할 수 있도록 에이전트 또는 도구 코드를 준비합니다.

코드를 AgentCore 표준 HTTP 프로토콜 또는 MCP 프로토콜 계약으로 변환합니다. 이를 통해 기존 요청/응답 패턴(HTTP 프로토콜)의 직접 REST API 엔드포인트 통신이나 도구 및 에이전트 서버용 Model Context Protocol(MCP Protocol)을 사용할 수 있습니다.

도구를 호스팅하면 Amazon Bedrock AgentCore Python SDK가 [Stateless Streamable HTTP] 전송 프로토콜을 구현하고 [세션 격리](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#session-management)를 위해 `MCP-Session-Id` 헤더를 사용합니다. 서버는 플랫폼이 생성한 Mcp-Session-Id 헤더를 거부하지 않도록 stateless 작업을 지원해야 합니다.
MCP 서버는 포트 `8000`에서 호스팅되며 하나의 호출 경로인 `mcp-POST`를 제공합니다. 이 상호 작용 엔드포인트는 MCP RPC 메시지를 수신하고 도구 기능을 통해 처리합니다. 응답 content type으로 application/json과 text/event-stream을 모두 지원합니다.

AgentCore 프로토콜을 MCP로 설정하면 AgentCore Runtime은 MCP 서버 컨테이너가 `0.0.0.0:8000/mcp` 경로에 있을 것으로 예상합니다. 이 경로는 대부분의 공식 MCP 서버 SDK가 지원하는 기본 경로입니다.

AgentCore Runtime은 기본적으로 session isolation을 제공하고 헤더가 없는 모든 요청에 Mcp-Session-Id 헤더를 자동으로 추가하므로 stateless streamable-http 서버를 호스팅해야 합니다. 이를 통해 MCP 클라이언트는 동일한 Amazon Bedrock AgentCore Runtime 세션 ID로 연결을 이어갈 수 있습니다.

`InvokeAgentRuntime` API의 payload는 완전히 그대로 전달되므로 MCP 같은 프로토콜의 RPC 메시지를 쉽게 proxy할 수 있습니다.

이 자습서에서는 다음 내용을 학습합니다.

* 도구가 포함된 MCP 서버를 생성하는 방법
* 로컬에서 서버를 테스트하는 방법
* AWS에 서버를 배포하는 방법
* 배포된 서버를 호출하는 방법

### 자습서 세부 정보

| 정보                | 세부 정보                                                 |
|:--------------------|:----------------------------------------------------------|
| 자습서 유형         | 도구 호스팅                                               |
| 도구 유형           | MCP 서버                                                  |
| 자습서 구성 요소    | AgentCore Runtime에서 도구 호스팅, MCP 서버 생성          |
| 자습서 분야         | 여러 산업 분야                                            |
| 예제 난이도         | 쉬움                                                      |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 MCP Client          |

### 자습서 아키텍처
이 자습서에서는 기존 MCP 서버를 AgentCore Runtime에 배포하는 방법을 설명합니다.

데모를 위해 `add_numbers`, `multiply_numbers`, `greet_users`라는 3개의 도구가 포함된 간단한 MCP 서버를 사용합니다.

![MCP architecture](images/hosting_mcp_server.png)

### 자습서 주요 기능

* MCP 서버 호스팅
