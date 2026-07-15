# Amazon Bedrock AgentCore를 사용하는 비동기 데이터 분석 에이전트

## 개요

이 자습서에서는 사용자와 원활한 대화를 유지하면서 백그라운드에서 장시간 분석 작업을 수행하는 비동기 데이터 분석 에이전트를 구축하는 방법을 학습합니다. Amazon Bedrock AgentCore의 비동기 기능과 Strands를 활용하여 시간이 오래 걸리는 작업을 원활하게 처리하는 에이전트를 만드는 방법을 보여 줍니다.

이 예제에서는 다음 구성 요소를 생성합니다.

1. 사용자 상호 작용을 오케스트레이션하고 분석 작업을 위임하는 기본 에이전트
2. 데이터 분석 작업을 위한 Python 코드를 생성하는 coding agent
3. 에이전트 응답성을 유지하면서 Code Interpreter에서 코드를 실행하는 비동기 작업 시스템

이러한 구성 요소를 결합하면 사용자와 원활한 대화를 유지하면서 계산 집약적인 데이터 분석 작업을 처리하는 비동기 에이전트 구성이 완성됩니다.

이 자습서에서는 비동기 작업을 기본 지원하며 에이전트를 호스팅하고 관리하는 [**Amazon Bedrock AgentCore Runtime**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)과 격리된 환경에서 동적으로 생성된 Python 코드를 안전하게 실행하는 [**Amazon Bedrock Code Interpreter**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html)를 활용합니다. AgentCore Runtime은 대화형 AI 에이전트 배포를 위한 확장 가능한 인프라를 제공하고, Code Interpreter는 에이전트가 데이터 분석 작업용 코드를 안전하게 작성하고 실행할 수 있도록 합니다. [Amazon Bedrock AgentCore 자세히 알아보기](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore.html)

## 자습서 세부 정보

| 정보                | 세부 정보                                                             |
| :------------------ | :-------------------------------------------------------------------- |
| 자습서 유형         | 대화형                                                                  |
| 에이전트 유형       | 멀티 에이전트(Code Generation Agent를 도구로 사용하는 Orchestrator Agent) |
| 에이전틱 프레임워크 | Strands Agents                                                          |
| LLM 모델            | Anthropic Claude Sonnet 4(기본 에이전트) 및 Haiku 4.5(coding agent)     |
| 자습서 구성 요소    | AgentCore Runtime, 비동기 작업, Code Interpreter, S3 통합               |
| 자습서 분야         | 데이터 분석                                                              |
| 예제 난이도         | 중급                                                                     |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                             |

## 자습서 아키텍처

<div style="text-align:left">
    <img src="architecture.png" width="100%"/>
</div>

## 시작하기

[async_data_analysis_tutorial.ipynb](async_data_analysis_tutorial.ipynb) Notebook의 지침을 따르세요.
