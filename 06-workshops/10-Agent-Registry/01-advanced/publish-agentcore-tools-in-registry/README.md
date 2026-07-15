# AWS Agent Registry에 AgentCore 도구 게시

## 개요

조직에서 수십 또는 수백 개의 AI 에이전트, MCP 서버 및 도구를 운영하면 어떤 리소스가 있는지, 누가 소유하는지, 사용 승인을 받았는지 추적하는 일이 큰 과제가 됩니다. 팀에서 다른 곳에 이미 있는 기능을 다시 구축하거나 적절한 감독 없이 리소스를 배포하는 상황이 발생합니다. Amazon Bedrock AgentCore의 일부인 AWS Agent Registry는 플랫폼 팀이 조직 전반의 AI 에이전트, MCP 서버, Agent Skills 및 사용자 지정 리소스를 구성하고 관리하며 공유할 수 있는 중앙 집중식 카탈로그를 제공합니다.

레지스트리의 각 항목은 에이전트나 도구의 기능, 사용하는 프로토콜, 호출 방법 및 게시자를 담은 구조화된 레코드입니다. 레지스트리는 **MCP**(Model Context Protocol) 및 **A2A**(Agent-to-Agent)를 기본적으로 지원하며, 표준 프로토콜에 해당하지 않는 리소스를 위한 Agent Skills 및 사용자 지정 리소스 유형도 지원합니다.

## 아키텍처 흐름

![아키텍처 흐름](images/agentregistry_flow.png)


이 튜토리얼에서는 주문 관리 사용 사례를 통해 두 가지 페르소나의 엔드 투 엔드 워크플로를 다룹니다.

- **게시자**: 주문 관리용 A2A 에이전트와 MCP 서버를 구축하여 AgentCore Runtime에 배포하고 작동 여부를 확인한 다음, 올바른 설명자 구조로 Agent Registry에 등록하고 승인을 요청합니다.
- **소비자**: 레코드가 승인되면 자연어 쿼리로 Agent Registry에서 시맨틱 검색을 수행하여 등록된 에이전트와 도구를 찾습니다.

### 검색 작동 방식

레지스트리는 키워드 일치와 시맨틱 일치를 결합한 하이브리드 검색을 제공합니다. 모든 쿼리에 키워드 일치가 사용되며, 긴 자연어 쿼리에는 시맨틱 이해도 적용되어 개념적으로 관련된 결과를 표시합니다. 따라서 "cancel an order"를 검색하면 도구 이름이 다르더라도 주문 관리와 관련된 도구를 찾을 수 있습니다. 팀은 먼저 레지스트리를 검색하고 검증된 기능이 있으면 이를 사용하므로 검색이 가장 간편한 선택지가 됩니다.

### 거버넌스 작동 방식

모든 레코드는 승인 워크플로를 따릅니다. 레코드는 **DRAFT**로 시작하여 **PENDING_APPROVAL**로 이동하고, **APPROVED** 상태가 되면 조직의 더 많은 사용자가 검색할 수 있습니다. 관리자는 IAM 정책을 사용하여 에이전트를 등록할 수 있는 사용자와 검색할 수 있는 사용자를 정의합니다. 시간에 따른 변경 사항을 추적할 수 있도록 레코드에 버전을 지정하며, 조직에서는 더 이상 사용하지 않는 레코드를 사용 중단 처리할 수 있습니다.

### 레지스트리 레코드 설명자 유형

| 설명자 유형 | 프로토콜 | 포함 내용 |
|:----------------|:---------|:-----------------|
| `MCP` | Model Context Protocol | `serverSchema`(서버 메타데이터, 패키지, 전송 방식) + `toolSchema`(JSON Schema를 사용하는 개별 함수 정의) |
| `A2A` | Agent-to-Agent | `agentCard`(에이전트 자격 증명, 기능 및 자연어 스킬 설명) |
| `AGENT_SKILLS` | Agent Skills | `skillMd`(SKILL.md 지침) + `skillDefinition`(리포지토리, 패키지) |
| `CUSTOM` | 사용자 지정 | `inlineContent`(모든 리소스 유형을 위한 자유 형식 JSON) |

### 튜토리얼 세부 정보

| 정보                  | 세부 정보                                                                                 |
|:---------------------|:-----------------------------------------------------------------------------------------|
| 튜토리얼 유형         | 대화형                                                                                    |
| AgentCore 구성 요소   | AgentCore Runtime, AWS Agent Registry                                                    |
| 에이전트 프레임워크   | Strands Agents (A2A), FastMCP (MCP)                                                      |
| 다루는 프로토콜       | MCP(Model Context Protocol), A2A(Agent-to-Agent)                                         |
| 인바운드 인증         | IAM SigV4                                                                                |
| LLM 모델              | 기본 Bedrock 모델(A2A 에이전트만 해당)                                                   |
| 튜토리얼 구성 요소    | 에이전트 구축, Runtime 배포, 레지스트리 생성, 레코드 등록, 승인 워크플로, 시맨틱 검색 |
| 튜토리얼 분야         | 주문 관리                                                                                |
| 예제 난이도           | 중급                                                                                     |
| 사용 SDK              | boto3, bedrock-agentcore-starter-toolkit                                                 |

### 이 튜토리얼에서 다루는 내용

1. **구축**: 주문 생성, 업데이트, 취소 및 추적 도구를 포함하는 주문 관리용 MCP 서버와 A2A 에이전트를 생성합니다.
2. **배포**: 두 리소스를 AgentCore Runtime에 배포합니다(MCP는 포트 8000, A2A는 포트 9000).
3. **검증**: MCP `tools/list` + `tools/call` 및 A2A 에이전트 카드 + `message/send`를 통해 에이전트가 작동하는지 확인합니다.
4. **등록**: Agent Registry를 생성하고 올바른 설명자 구조(MCP는 `serverSchema` + `toolSchema`, A2A는 `agentCard`)로 두 에이전트를 등록합니다.
5. **승인**: 승인 워크플로(DRAFT → PENDING_APPROVAL → APPROVED)를 진행합니다.
6. **검색**: 소비자 역할로 자연어 쿼리를 사용하여 등록된 에이전트와 도구를 찾는 시맨틱 검색을 수행합니다.

## 튜토리얼

- [AWS Agent Registry에 A2A 에이전트 및 MCP 서버 게시](publish-agentcore-a2a-mcp-in-registry.ipynb)
