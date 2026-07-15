# 사전 요구 사항: 샘플 에이전트 생성

## 개요

에이전트를 평가하려면 먼저 평가할 에이전트가 필요합니다. 이 튜토리얼에서는 이후 평가 튜토리얼 전반에서 사용할 샘플 에이전트 두 개를 설정합니다. 하나는 [Strands Agents SDK](https://strandsagents.com/)를 사용하고, 다른 하나는 [LangGraph](https://www.langchain.com/langgraph)를 사용합니다.

## 에이전트
생성하는 두 에이전트는 기본적으로 동일하지만, AgentCore가 어떤 프레임워크와도 함께 작동한다는 점을 보여주기 위해 서로 다른 두 프레임워크를 사용합니다.

생성하는 에이전트에는 두 가지 핵심 기능이 있습니다.

**코드 실행**
- AgentCore Code Interpreter를 사용하여 Python 코드 실행
- 수학 계산 및 데이터 분석 처리

**메모리**
- 사용자 정보 및 선호도 저장
- 개인화된 응답에 필요한 관련 컨텍스트 검색

두 에이전트 모두 Amazon Bedrock의 Anthropic Claude Haiku 4.5를 LLM으로 사용하지만, AgentCore에서는 원하는 모델을 사용할 수 있습니다.

아키텍처는 다음과 같습니다.

![에이전트 아키텍처](../images/agent_architecture.png)

## 사전 요구 사항
에이전트를 배포하기 전에 다음 항목이 필요합니다.
* Python 3.10+
* AWS 액세스 권한


## 다음 단계
필요한 사전 요구 사항을 모두 갖췄으므로 개별 평가 튜토리얼을 살펴보겠습니다.

- **[튜토리얼 01](../01-creating-custom-evaluators)**: 사용자 지정 evaluator 생성
- **[튜토리얼 02](../02-running-evaluations)**: 온디맨드 및 온라인 평가 실행
- **[튜토리얼 03](../03-advanced)**: 고급 기법 및 대시보드
