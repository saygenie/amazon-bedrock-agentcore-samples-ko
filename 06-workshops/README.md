# 📚 Amazon Bedrock AgentCore 튜토리얼

이 폴더에는 Amazon Bedrock AgentCore로 AI 에이전트를 구축, 배포 및 관리하는 실습형 튜토리얼이 포함되어 있습니다.

AgentCore 서비스는 모든 에이전트 프레임워크(Strands Agents, LangChain, LangGraph, CrewAI 등) 및 모델과 함께 개별적으로 또는 조합하여 사용할 수 있습니다.

![Amazon Bedrock AgentCore 개요](images/agentcore_overview.png)

## 사전 요구 사항

- Amazon Bedrock에 액세스할 수 있는 AWS 계정
- Python 3.10 이상 및 Jupyter Notebook(또는 JupyterLab)
- 적절한 자격 증명으로 구성된 AWS CLI
- AI 에이전트와 AWS 서비스에 대한 기본 지식

## 튜토리얼

### 01 - [Runtime](01-AgentCore-runtime/)

프레임워크, 프로토콜 또는 모델에 관계없이 안전한 서버리스 Runtime에서 AI 에이전트를 배포하고 확장합니다. 에이전트 및 MCP 서버 호스팅, A2A, 양방향 스트리밍을 다룹니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html) · [심층 해설 동영상](https://www.youtube.com/live/wizEw5a4gvM?si=7owv5C-kgU8UTzPl))

### 02 - [Gateway](02-AgentCore-gateway/)

통합을 직접 관리하지 않고도 API, AWS Lambda 함수 및 기존 서비스를 MCP 호환 도구로 전환합니다. 인증, 액세스 제어, 민감한 데이터 마스킹 등의 예제를 제공합니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) · [심층 해설 동영상](https://www.youtube.com/live/atWXM5lziY8?si=qKEzTbU1-15B8pQ0))

### 03 - [Identity](03-AgentCore-identity/)

표준 자격 증명 공급자(Okta, Entra, Cognito)를 사용하여 AWS 서비스와 서드 파티 앱(Slack, Zoom) 전반에서 에이전트 자격 증명과 액세스를 관리합니다. 인바운드 인증, 아웃바운드 인증 및 3LO 흐름을 다룹니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html) · [심층 해설 동영상](https://www.youtube.com/live/wv2doVDF7KQ?si=sxt2lOufwt7cOeUY))

### 04 - [Memory](04-AgentCore-memory/)

에이전트에 완전관리형 메모리를 추가하여 개인화된 경험을 제공합니다. 단기 메모리, 장기 메모리, 분기 및 보안 패턴을 살펴봅니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) · [심층 해설 동영상](https://www.youtube.com/live/-N4v6-kJgwA))

### 05 - [Tools](05-AgentCore-tools/)

AgentCore의 내장 도구를 사용합니다. **Code Interpreter**는 코드를 안전하게 실행하고, **Browser Tool**은 웹 탐색과 양식 작성을 수행합니다. ([Code Interpreter 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html) · [Browser Tool 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html) · [심층 해설 동영상](https://www.youtube.com/live/z3lAJ-Nf_lk?si=Tf45AR3mZVo9rweL))

### 06 - [Observability](06-AgentCore-observability/)

OpenTelemetry 호환 텔레메트리를 사용하여 에이전트 성능을 추적, 디버깅 및 모니터링합니다. Runtime에서 호스팅되는 에이전트, 자체 호스팅 에이전트, AWS Lambda 기반 에이전트 및 EKS 호스팅 에이전트에 사용할 수 있습니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) · [심층 해설 동영상](https://www.youtube.com/watch?v=wWQgawUPr1k))

### 07 - [Evaluations](07-AgentCore-evaluations/)

내장 평가기와 사용자 지정 평가기를 사용하여 정확성, 유용성, 안전성 등의 관점에서 에이전트 품질을 평가합니다. 평가기 생성, 평가 실행 및 결과 활용 방법을 다룹니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html) · [심층 해설 동영상](https://www.youtube.com/live/i0h7xA8cqYs?si=ZSR_-iQRjju-2H04))

### 08 - [Policy](08-AgentCore-policy/)

Cedar 언어 정책을 사용하여 보안 제어를 정의하고 적용함으로써 데이터 유출과 권한 남용을 방지합니다. 자연어를 사용한 정책 작성과 세분화된 액세스 제어를 다룹니다. ([문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) · [심층 해설 동영상](https://www.youtube.com/watch?v=q_9htaugcgI))

### 09 - [엔드 투 엔드 워크숍](09-AgentCore-E2E/)

Runtime, Gateway, Identity, Memory 등을 결합하여 프로덕션 환경에 적용할 수 있는 완전한 에이전트를 단계별로 구축합니다. ([심층 해설 동영상](https://youtu.be/gI_qvheaSoA?si=Pa6VzGXzopuX_koW&t=490))

## 시작 가이드

- **AgentCore를 처음 사용하시나요?** [01 - Runtime](01-AgentCore-runtime/)부터 시작하여 튜토리얼을 순서대로 진행하세요.
- **특정 기능을 찾고 있나요?** 각 튜토리얼은 독립적으로 구성되어 있으므로 원하는 튜토리얼로 바로 이동하세요.
- **전체 흐름을 파악하고 싶으신가요?** [엔드 투 엔드 워크숍](09-AgentCore-E2E/)에서 모든 구성 요소를 함께 살펴볼 수 있습니다.

## 리소스

- [Amazon Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/) -- 공식 개발자 가이드 및 API 레퍼런스
- [AgentCore 심층 해설 재생목록](https://www.youtube.com/live/wzIQDPFQx30?si=K4EgotJ6DDj7Ri41) -- 각 구성 요소를 자세히 다루는 동영상 재생목록
