# Amazon Bedrock AgentCore Gateway - 시맨틱 검색

## 실습 아키텍처

Amazon Bedrock AgentCore Gateway는 에이전트와 에이전트가 상호 작용해야 하는 도구 및 리소스 사이에 통합 연결을 제공합니다. Gateway는 이 연결 계층에서 여러 역할을 수행합니다.

1. **보안 관리자**: Gateway는 OAuth 권한 부여를 관리하여 유효한 사용자와 에이전트만 도구 및 리소스에 액세스하도록 보장합니다.
2. **변환기**: Gateway는 Model Context Protocol(MCP)과 같은 널리 사용되는 프로토콜을 이용한 에이전트 요청을 API 요청과 Lambda 호출로 변환합니다. 따라서 개발자가 서버 호스팅, 프로토콜 통합, 버전 지원, 버전 패치 등을 관리할 필요가 없습니다.
3. **구성기**: Gateway를 사용하면 개발자가 여러 API, 함수, 도구를 에이전트가 사용할 수 있는 단일 MCP 엔드포인트로 원활하게 결합할 수 있습니다.
4. **자격 증명 관리자**: Gateway는 각 도구에 적합한 자격 증명 주입을 처리하므로, 에이전트가 서로 다른 자격 증명 집합이 필요한 도구를 원활하게 활용할 수 있습니다.
5. **검색기**: Gateway를 사용하면 에이전트가 모든 도구를 검색하여 주어진 컨텍스트나 질문에 가장 적합한 도구만 찾을 수 있습니다. 따라서 에이전트는 몇 개의 도구에 그치지 않고 수천 개의 도구를 활용할 수 있습니다. 또한 에이전트의 LLM prompt에 제공해야 하는 도구 집합을 최소화하여 지연 시간과 비용을 줄입니다.
6. **인프라 관리자**: Gateway는 완전한 serverless 서비스이며 observability 및 감사 기능이 내장되어 있어, 개발자가 에이전트와 도구를 통합하기 위한 추가 인프라를 관리할 필요가 없습니다.

![작동 방식](images/gw-arch-overview.png)

## AgentCore Gateway를 사용해 도구가 많은 MCP 서버의 문제 해결

일반적인 엔터프라이즈 환경에서 에이전트 개발자는 수백 개 또는 수천 개의 MCP 도구가 있는 MCP 서버를 접하게 됩니다. 이렇게 많은 도구는 과도한 도구 메타데이터에 따른 토큰 사용량 증가로 인해 도구 선택 정확도 저하, 비용 증가, 지연 시간 증가와 같은 문제를 AI 에이전트에 일으킵니다.
이 문제는 에이전트를 서드 파티 서비스(예: Zendesk, Salesforce, Slack, JIRA 등)나 기존 엔터프라이즈 REST 서비스에 연결할 때 발생할 수 있습니다. AgentCore Gateway는 도구 전반에 걸친 내장 semantic search를 제공하므로, 에이전트에 필요한 도구를 제공하면서도 지연 시간, 비용, 정확도를 개선합니다. 사용 사례, LLM 모델 및 에이전트 프레임워크에 따라 일반적인 MCP Server의 수백 개 도구 전체를 제공하는 대신 관련 도구에 에이전트를 집중시키면 지연 시간을 최대 3배까지 개선할 수 있습니다.

![작동 방식](images/gateway_tool_search.png)

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- AWS Lambda 기반 대상으로 Amazon Bedrock AgentCore Gateway 생성
- AgentCore Gateway semantic search 사용
- Strands Agents를 사용하여 AgentCore Gateway 검색이 지연 시간을 개선하는 방식 확인

- [Amazon Bedrock AgentCore Gateway - 시맨틱 검색](./01-gateway-search.ipynb)
