# Amazon Bedrock AgentCore Gateway

## 개요
Bedrock AgentCore Gateway를 사용하면 인프라나 호스팅을 관리하지 않고도 기존 API와 Lambda 함수를 완전관리형 MCP 서버로 전환할 수 있습니다. 기존 API의 OpenAPI 사양이나 Smithy 모델을 가져오거나, 도구를 제공하는 Lambda 함수를 추가할 수 있습니다. Gateway는 이러한 모든 도구에 일관된 Model Context Protocol(MCP) 인터페이스를 제공합니다. Gateway는 수신 요청과 대상 리소스로 나가는 연결 모두에 안전한 액세스 제어를 보장하기 위해 이중 인증 모델을 사용합니다. 이 프레임워크는 Gateway 대상에 액세스하려는 사용자를 검증하고 권한을 부여하는 Inbound Auth와, 인증된 사용자를 대신해 Gateway가 백엔드 리소스에 안전하게 연결하도록 지원하는 Outbound Auth라는 두 가지 핵심 구성 요소로 이루어집니다. 이 두 인증 메커니즘은 IAM 자격 증명과 OAuth 기반 인증 흐름을 모두 지원하며, 사용자와 대상 리소스 사이에 안전한 연결을 제공합니다. Gateway는 MCP의 Streamable HTTP 전송 연결을 지원합니다.

![작동 방식](images/gateway-end-end-overview.png)

## 주요 개념

시작하기 전에 Amazon Bedrock AgentCore Gateway를 사용하는 데 필요한 몇 가지 주요 개념을 살펴보겠습니다.

* **Amazon Bedrock AgentCore Gateway**: 고객이 MCP 클라이언트로 호출하여 표준 MCP 작업(예: listTools, invokeTool)을 실행할 수 있는 HTTP 엔드포인트입니다. boto3와 같은 AWS SDK를 사용해 Amazon Bedrock AgentCore Gateway를 호출할 수도 있습니다.
* **Bedrock AgentCore Gateway Target**: 고객이 Amazon Bedrock AgentCore Gateway에 대상을 연결할 때 사용하는 리소스입니다. 현재 AgentCore Gateway 대상에는 다음 유형이 지원됩니다.
    * Lambda ARNs
    * API specifications → OpenAPI, Smithy
* **MCP Transport**: 클라이언트(LLM을 사용하는 애플리케이션)와 MCP 서버 간에 메시지가 이동하는 방식을 정의하는 메커니즘입니다. 현재 AgentCore Gateway는 전송 방식으로 `Streamable HTTP connections`만 지원합니다.

## 작동 방식

![작동 방식](images/gateway_how_does_it_work.png)

## 인바운드 및 아웃바운드 권한 부여
Bedrock AgentCore Gateway는 인바운드 및 아웃바운드 인증을 통해 안전한 연결을 제공합니다. 인바운드 인증에서는 호출 시 전달된 OAuth 토큰을 AgentCore Gateway가 분석하여 Gateway의 도구에 대한 액세스 허용 여부를 결정합니다. 도구가 외부 리소스에 액세스해야 하는 경우, AgentCore Gateway는 API Key, IAM 또는 OAuth Token을 통한 아웃바운드 인증으로 외부 리소스에 대한 액세스 허용 여부를 결정할 수 있습니다.

인바운드 권한 부여 흐름에서 에이전트 또는 MCP 클라이언트는 사용자의 IdP에서 생성한 OAuth 액세스 토큰을 추가하여 AgentCore Gateway의 MCP 도구를 호출합니다. 그러면 AgentCore Gateway가 OAuth 액세스 토큰을 검증하고 인바운드 권한 부여를 수행합니다.

AgentCore Gateway에서 실행되는 도구가 외부 리소스에 액세스해야 하면 OAuth는 Gateway 대상의 리소스 자격 증명 공급자를 사용해 다운스트림 리소스의 자격 증명을 가져옵니다. AgentCore Gateway는 다운스트림 API에 액세스할 수 있도록 호출자에게 권한 부여 자격 증명을 전달합니다.

![안전한 액세스](images/gateway_secure_access.png)

### MCP 권한 부여와 Gateway

Amazon Bedrock AgentCore Gateway는 수신 MCP 도구 호출의 권한 부여에 관한 [MCP 권한 부여 사양](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)을 준수합니다.

![안전한 액세스](images/oauth-flow-gateway.png)

### AgentCore Gateway와 AgentCore Identity 통합

![Gateway와 AgentCore Identity](images/end-end-auth-gateway.png)

### 도구 검색
Amazon Bedrock AgentCore Gateway에는 에이전트와 개발자가 자연어 쿼리로 가장 관련성 높은 도구를 찾을 수 있도록 지원하는 강력한 내장 semantic search 기능도 포함되어 있습니다. 이 기능은 도구 선택을 위해 에이전트에 전달되는 **컨텍스트를 줄여** 줍니다. 검색 기능은 semantic matching을 위해 벡터 임베딩을 활용하는 사전 구축 도구로 구현됩니다. 사용자는 Gateway를 생성할 때 CreateGateway API를 통해 이 기능을 활성화할 수 있습니다. 기능을 활성화하면 이후의 CreateTarget 작업이 대상 도구의 벡터 임베딩 생성을 자동으로 시작합니다. 임베딩이 생성되는 동안 CreateTarget 응답의 STATUS 필드는 "UPDATING"으로 표시됩니다.

![도구 검색](images/gateway_tool_search.png)

### 실습 세부 정보


| 정보                 | 세부 정보                                                 |
|:---------------------|:----------------------------------------------------------|
| 실습 유형            | 대화형                                                    |
| AgentCore 구성 요소  | AgentCore Gateway, AgentCore Identity                     |
| 에이전트 프레임워크  | Strands Agents                                            |
| LLM 모델             | Anthropic Claude Haiku 4.5, Amazon Nova Pro              |
| 실습 구성 요소       | AgentCore Gateway 생성 및 AgentCore Gateway 호출          |
| 실습 분야            | 산업 공통                                                  |
| 예제 난이도          | 쉬움                                                       |
| 사용 SDK             | boto3                                                     |

## 실습 아키텍처

### 실습의 주요 기능

#### 안전한 도구 액세스

Amazon Bedrock AgentCore Gateway는 수신 MCP 도구 호출의 권한 부여에 관한 [MCP 권한 부여 사양](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)을 준수합니다.
또한 Amazon Bedrock AgentCore Gateway는 Gateway에서 나가는 호출의 권한 부여를 지원하기 위해 다음 두 가지 옵션을 제공합니다.
* API key 사용
* OAuth 액세스 토큰 사용
Amazon Bedrock AgentCore Identity의 Credentials provider API로 권한 부여를 구성하고 AgentCore Gateway Target에 연결할 수 있습니다.
각 Target(AWS Lambda, Smithy, OpenAPI)을 자격 증명 공급자에 연결할 수 있습니다.

#### 통합

Bedrock AgentCore Gateway는 다음 서비스와 통합됩니다.
* Bedrock AgentCore Identity
* Bedrock AgentCore Runtime

### 사용 사례

* MCP 도구를 호출하는 실시간 대화형 에이전트
* 서로 다른 IdP를 사용하는 인바운드 및 아웃바운드 권한 부여
* AWS Lambda 함수, OpenAPI 및 Smithy 모델을 MCP 도구로 전환
* MCP 도구 탐색

### 이점

* 인프라 관리가 필요하지 않아 AI 에이전트 개발과 배포가 간소화됩니다.
* 호스팅을 신경 쓸 필요가 없는 완전관리형 서비스입니다. Amazon Bedrock AgentCore가 모든 인프라를 자동으로 처리합니다.
* 통합 인터페이스: 모든 도구에 단일 MCP 프로토콜을 사용하므로 에이전트 코드에서 여러 API 형식과 인증 메커니즘을 관리해야 하는 복잡성이 사라집니다.
* 내장 인증: 추가 개발 작업 없이 OAuth 및 자격 증명 관리가 토큰 수명 주기, 갱신, 안전한 저장을 처리합니다.
* 자동 확장: 수요에 따라 자동으로 확장되므로 수동 개입이나 용량 계획 없이 변화하는 워크로드를 처리합니다.
* 엔터프라이즈 보안: 암호화, 액세스 제어, 감사 로깅을 포함한 엔터프라이즈급 보안 기능으로 안전한 도구 액세스를 보장합니다.

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [AWS Lambda 함수를 MCP 도구로 전환](01-transform-lambda-into-mcp-tools)
- [API를 MCP 도구로 전환](02-transform-apis-into-mcp-tools)
- [MCP 도구 탐색](03-discover-mcp-tools)
- [Okta를 사용한 Inbound Auth Code Flow](17-inbound-auth-code-flow-okta)
