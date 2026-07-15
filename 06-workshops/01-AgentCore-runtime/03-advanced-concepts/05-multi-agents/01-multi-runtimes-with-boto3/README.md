# Amazon Bedrock AgentCore를 사용하는 분산 멀티 에이전트 솔루션

## 개요

이 자습서에서는 서로 다른 에이전틱 프레임워크로 구축한 에이전트를 각각의 Amazon Bedrock AgentCore Runtime에 독립적으로 호스팅하는 방법을 학습합니다. 그런 다음 에이전트 간 통신을 활성화하여 분산 멀티 에이전트 솔루션을 구현합니다.

이 예제에서는 다음 에이전트를 생성합니다.
1. 프로그래밍 및 기술 문제 해결에 관한 질문에 특화된 기술 에이전트(tech_agent)
2. 회사 복리후생에 특화된 HR 에이전트(hr_agent)
3. 질문을 기술 또는 HR 에이전트로 전달하는 오케스트레이터 에이전트(orchestrator_agent)

이 세 에이전트를 결합하면 사용자 질문을 적절한 하위 에이전트로 전달할 수 있는 supervisor 기반 멀티 에이전트 구성이 완성됩니다. 이 시스템은 직원이 회사에서 가질 수 있는 다양한 질문에 답할 수 있습니다.

## 자습서 세부 정보

| 정보                | 세부 정보                                                                        |
|:--------------------|:---------------------------------------------------------------------------------|
| 자습서 유형         | 대화형                                                                            |
| 에이전트 유형       | 멀티 에이전트(Supervisor가 에이전트를 도구로 호출)                               |
| 에이전틱 프레임워크 | Strands Agents 및 LangGraph                                                      |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                       |
| 자습서 구성 요소    | AgentCore Runtime에서 에이전트 호스팅 및 멀티 에이전트 협업 활성화               |
| 자습서 분야         | 여러 산업 분야                                                                   |
| 예제 난이도         | 중간                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                     |

## 자습서 아키텍처

<div style="text-align:left">
    <img src="architecture.png" width="100%"/>
</div>

## 시작하기

[distributed_agents_with_agentcore.ipynb](distributed_agents_with_agentcore.ipynb) Notebook의 지침을 따르세요.
