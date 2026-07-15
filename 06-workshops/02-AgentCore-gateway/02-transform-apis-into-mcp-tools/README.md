# Amazon Bedrock AgentCore Gateway를 사용해 API를 MCP 도구로 구현

## 개요
Bedrock AgentCore Gateway를 사용하면 인프라나 호스팅을 관리하지 않고도 기존 API(OpenAPI 및 Smithy)를 완전관리형 MCP 서버로 전환할 수 있습니다. 기존 OpenAPI 및 Smithy 사양을 가져와 도구로 변환할 수 있습니다. Gateway는 이러한 모든 도구에 일관된 Model Context Protocol(MCP) 인터페이스를 제공합니다. Gateway는 수신 요청과 대상 리소스로 나가는 연결 모두에 안전한 액세스 제어를 보장하기 위해 이중 인증 모델을 사용합니다. 이 프레임워크는 Gateway 대상에 액세스하려는 사용자를 검증하고 권한을 부여하는 Inbound Auth와, API key, OAuth token 및 AWS IAM role을 사용해 인증된 사용자를 대신하여 Gateway가 백엔드 API에 안전하게 연결하도록 지원하는 Outbound Auth라는 두 가지 핵심 구성 요소로 이루어집니다.

![작동 방식](images/apis-into-mcp-gateway.png)


## 주요 개념

시작하기 전에 Amazon Bedrock AgentCore Gateway를 사용하는 데 필요한 몇 가지 주요 개념을 살펴보겠습니다.
OpenAPI 또는 Smithy API를 그룹화하여 Bedrock AgentCore Gateway Target을 생성할 수 있습니다. 대상은 API를 논리적으로 그룹화하고 Amazon Bedrock AgentCore Gateway에 연결할 때 사용하는 리소스입니다.

## API를 Gateway 대상으로 그룹화

API를 Gateway 대상으로 그룹화할 때는 다음 모범 사례를 따르세요.
* 마이크로서비스 패러다임에 적용되는 Domain Driven Design 원칙과 유사하게 에이전트 애플리케이션의 비즈니스 도메인을 기준으로 MCP 도구를 그룹화합니다.
* Gateway 대상에는 아웃바운드 권한 부여용 리소스 자격 증명 공급자를 하나만 연결할 수 있습니다. 아웃바운드 권한 부여자를 기준으로 도구를 그룹화합니다.
* OpenAPI, Smithy 또는 다른 엔터프라이즈 API와 연결하는 AWS Lambda 등 API 유형을 기준으로 API를 그룹화합니다.

![API 도구를 대상으로 그룹화](images/api-groups-targets.png)

## 모범 사례

1. 문서 품질 지침
- 각 API 엔드포인트와 리소스에 명확하고 구체적인 요약을 작성합니다.
- 목적과 기능을 설명하는 자연어 설명을 사용합니다.
- 설명에 실제 사용 사례를 포함합니다.
- 필요한 경우가 아니라면 기술 전문 용어를 피합니다.
- 문서 전체에서 일관된 용어를 사용합니다.

2. 스키마 문서
- 모든 필드에 상세한 설명을 제공합니다.
- 필드 제약 조건과 검증 규칙을 포함합니다.
- 데이터 형식을 정확하게 문서화합니다.
- 복잡한 데이터 구조에는 예시를 추가합니다.
- 서로 다른 스키마 간 관계를 설명합니다.

3. OpenAPI Specification 모범 사례
- OpenAPI linter로 사양을 검증합니다.
- 올바른 semantic versioning을 적용합니다.
- 완전한 요청/응답 예시를 포함합니다.
- 오류 응답과 코드를 문서화합니다.
- security scheme 정의를 추가합니다.

4. 도구 검색 최적화
- 설명에 관련 키워드를 자연스럽게 포함합니다.
- 각 API를 언제 사용해야 하는지 컨텍스트를 제공합니다.
- 대체 접근 방식이나 관련 엔드포인트를 문서화합니다.
- 비즈니스 도메인 용어를 포함합니다.

5. API 추출 지침
- 에이전트 작업에 필요한 핵심 기능을 식별합니다.
- 사용 사례를 기준으로 범위가 명확한 API 하위 집합을 만듭니다.
- 추출된 API 간의 의미 관계를 유지합니다.
- 보안 정의와 공통 스키마를 보존합니다.
- 추출된 구성 요소 간 종속성을 문서화합니다.

6. 모놀리식 API 추출 절차
- 전체 OpenAPI 사양을 검토합니다.
- 에이전트 사용 사례를 특정 엔드포인트 및 Auth 요구 사항과 연결합니다.
- 관련 경로와 스키마를 추출합니다.
- 구성 요소 종속성을 유지합니다.
- 추출한 사양을 검증합니다.
- semantic search 효과를 테스트합니다.

API가 발전함에 따라 문서를 정기적으로 검토하고 업데이트하여 에이전트의 품질과 정확성을 유지하세요.

## 인바운드 및 아웃바운드 권한 부여
Bedrock AgentCore Gateway는 인바운드 및 아웃바운드 인증을 통해 안전한 연결을 제공합니다. 인바운드 인증에서는 호출 시 전달된 OAuth 토큰을 AgentCore Gateway가 분석하여 Gateway의 도구에 대한 액세스 허용 여부를 결정합니다. 도구가 외부 리소스에 액세스해야 하는 경우, AgentCore Gateway는 API Key, IAM 또는 OAuth Token을 통한 아웃바운드 인증으로 외부 리소스에 대한 액세스 허용 여부를 결정할 수 있습니다.

인바운드 권한 부여 흐름에서 에이전트 또는 MCP 클라이언트는 사용자의 IdP에서 생성한 OAuth 액세스 토큰을 추가하여 AgentCore Gateway의 MCP 도구를 호출합니다. 그러면 AgentCore Gateway가 OAuth 액세스 토큰을 검증하고 인바운드 권한 부여를 수행합니다.

AgentCore Gateway에서 실행되는 도구가 외부 리소스에 액세스해야 하면 OAuth는 Gateway 대상의 리소스 자격 증명 공급자를 사용해 다운스트림 리소스의 자격 증명을 가져옵니다. AgentCore Gateway는 다운스트림 API에 액세스할 수 있도록 호출자에게 권한 부여 자격 증명을 전달합니다.

![안전한 액세스](../images/gateway_secure_access.png)

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

* OpenAPI API를 MCP 도구로 변환
* Smithy 모델을 MCP 도구로 변환

### 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [OpenAPI를 MCP 도구로 전환](01-transform-openapi-into-mcp-tools)
- [Smithy 모델을 MCP 도구로 전환](02-transform-smithyapis-into-mcp-tools)
