# API Gateway를 AgentCore Gateway Target으로 통합

## 개요

조직에서 에이전트 애플리케이션의 가능성을 모색하면서, 엔터프라이즈 정책에 부합하는 안전한 방식으로 엔터프라이즈 데이터를 large language model(LLM) 호출 요청의 컨텍스트로 사용하는 문제가 계속 발생하고 있습니다. 이러한 상호 작용을 표준화하고 보호하기 위해 많은 조직에서 에이전트 애플리케이션이 데이터 소스 및 도구에 안전하게 연결하는 방법을 정의하는 Model Context Protocol(MCP) 사양을 사용하고 있습니다.

MCP는 새로운 사용 사례에 유용하지만 조직은 기존 API 환경을 에이전트 시대에 도입하는 데에도 어려움을 겪습니다. MCP로 기존 API를 래핑할 수 있지만 MCP 요청을 RESTful API로 변환하고, 전체 요청 흐름에서 보안을 유지하며, 프로덕션 배포에 필요한 표준 observability를 적용하는 추가 작업이 필요합니다.

[Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)는 이제 [Amazon API Gateway](https://aws.amazon.com/api-gateway/)를 대상으로 지원하여 AgentCore Gateway(ACGW)에 대한 MCP 요청을 API Gateway(APIGW)에 대한 RESTful 요청으로 변환합니다. 이제 내장된 보안 및 observability와 함께 APIGW의 신규 및 기존 API 엔드포인트를 MCP를 통해 에이전트 애플리케이션에 노출할 수 있습니다. 이 노트북에서는 이 새로운 기능과 구현 방법을 다룹니다.

## 새로운 기능

AgentCore Gateway는 이미 Lambda 함수, OpenAPI 스키마, Smithy 모델, MCP 서버 등 여러 대상 유형을 지원하며 이제 API Gateway도 지원합니다.


![](Images/agent-core-gateway-targets.png)


**고객은 API Gateway를 사용해 여러 애플리케이션의 백엔드를 연결하는 광범위한 API 생태계를 성공적으로 구축해 왔습니다.** 엔터프라이즈가 차세대 에이전트 애플리케이션으로 발전함에 따라 기존 API와 백엔드 도구를 AI 기반 시스템에 노출하여 기존 인프라와 최신 지능형 에이전트를 원활하게 통합하는 것은 자연스러운 변화입니다.

현재 고객은 APIGW API를 OpenAPI 3 사양으로 내보낸 다음 ACGW에 OpenAPI 대상으로 추가하는 수동 워크플로를 사용합니다. 이 통합은 APIGW와 ACGW 간 연결을 자동화하여 이 프로세스를 간소화하는 것을 목표로 합니다.


이 통합을 사용하면 고객이 내보내기/가져오기 프로세스를 직접 관리할 필요가 없습니다. ACGW에 새로운 API_GATEWAY 대상 유형이 추가됩니다. REST API 소유자는 콘솔에서 몇 번 클릭하거나 단일 CLI 명령을 사용해 API를 ACGW 대상으로 추가하여 기존 REST API method를 ACGW를 통해 MCP 도구로 노출할 수 있습니다. 그러면 API 사용자는 Model Context Protocol(MCP)을 통해 AI 에이전트를 이러한 REST API에 연결하고 AI 통합으로 워크플로를 강화할 수 있습니다. 이제 에이전트 애플리케이션을 신규 또는 기존 APIGW API에 연결할 수 있습니다. 현재 ACGW와 APIGW 간 통합은 IAM authorization 및 API key authorization을 지원합니다.

![](Images/agent-core-apigw-target.png)

### 실습 세부 정보


| 정보                 | 세부 정보                                                 |
|:---------------------|:----------------------------------------------------------|
| 실습 유형            | 대화형                                                    |
| AgentCore 구성 요소  | AgentCore Gateway, AgentCore Identity                     |
| 에이전트 프레임워크  | Strands Agents                                            |
| Gateway Target 유형  | API Gateway                                               |
| Agent                | Strands                                                   |
| Inbound Auth IdP     | Amazon Cognito, 다른 IdP도 사용 가능                      |
| Outbound Auth        | IAM Authorization and API Key                             |
| LLM 모델             | Anthropic Claude Sonnet 4                                 |
| 실습 구성 요소       | AgentCore Gateway 대상을 통해 API Gateway 호출            |
| 실습 분야            | 산업 공통                                                  |
| 예제 난이도          | 쉬움                                                       |
| 사용 SDK             | boto3                                                     |

## 실습 아키텍처

이 실습은 더 광범위한 엔터프라이즈 과제인 **차세대 에이전트 애플리케이션을 위해 API Gateway API를 중앙 집중식 Gateway 아키텍처에 통합하는 방법**을 보여주는 실용적인 예제입니다.
[여기에서 실습을 시작하세요](01-api-gateway-target.ipynb).
