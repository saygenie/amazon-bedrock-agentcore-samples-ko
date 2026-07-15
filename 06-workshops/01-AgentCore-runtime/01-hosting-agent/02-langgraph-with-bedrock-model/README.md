# Amazon Bedrock AgentCore Runtime에서 Amazon Bedrock 모델을 사용하는 LangGraph 에이전트 호스팅

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime을 사용하여 기존 에이전트를 호스팅하는 방법을 학습합니다.

Amazon Bedrock 모델을 사용하는 LangGraph 예제에 중점을 둡니다. Amazon Bedrock 모델을 사용하는 Strands Agents는 [여기](../01-strands-with-bedrock-model)를,
OpenAI 모델을 사용하는 Strands Agents는 [여기](../03-strands-with-openai-model)를 참조하세요.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                    |
|:--------------------|:-----------------------------------------------------------------------------|
| 자습서 유형         | 대화형                                                                        |
| 에이전트 유형       | 단일                                                                          |
| 에이전틱 프레임워크 | LangGraph                                                                     |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                    |
| 자습서 구성 요소    | AgentCore Runtime에서 에이전트 호스팅, LangGraph 및 Amazon Bedrock 모델 사용 |
| 자습서 분야         | 여러 산업 분야                                                                |
| 예제 난이도         | 쉬움                                                                          |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                  |

### 자습서 아키텍처

이 자습서에서는 기존 에이전트를 AgentCore Runtime에 배포하는 방법을 설명합니다.

데모를 위해 Amazon Bedrock 모델을 사용하는 LangGraph 에이전트를 사용합니다.

이 예제에서는 `get_weather`와 `get_time`이라는 두 도구가 포함된 간단한 에이전트를 사용합니다.

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

### 자습서 주요 기능

* Amazon Bedrock AgentCore Runtime에서 에이전트 호스팅
* Amazon Bedrock 모델 사용
* LangGraph 사용
