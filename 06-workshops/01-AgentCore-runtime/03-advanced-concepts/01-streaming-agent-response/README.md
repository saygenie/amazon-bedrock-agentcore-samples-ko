# Amazon Bedrock AgentCore Runtime에서 Strands Agents 및 Amazon Bedrock 모델로 응답 스트리밍

## 개요

이 자습서에서는 기존 에이전트와 Amazon Bedrock AgentCore Runtime을 사용하여 스트리밍 응답을 구현하는 방법을 학습합니다.

실시간 스트리밍 기능을 보여 주는 Amazon Bedrock 모델 기반 Strands Agents 예제에 중점을 둡니다.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                        |
|:--------------------|:---------------------------------------------------------------------------------|
| 자습서 유형         | 스트리밍을 사용하는 대화형                                                      |
| 에이전트 유형       | 단일                                                                             |
| 에이전틱 프레임워크 | Strands Agents                                                                   |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                       |
| 자습서 구성 요소    | AgentCore Runtime을 사용한 응답 스트리밍, Strands Agent 및 Amazon Bedrock 모델   |
| 자습서 분야         | 여러 산업 분야                                                                   |
| 예제 난이도         | 쉬움                                                                             |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                     |

### 자습서 아키텍처

이 자습서에서는 스트리밍 에이전트를 AgentCore Runtime에 배포하는 방법을 설명합니다.

데모를 위해 스트리밍 기능이 있는 Amazon Bedrock 모델을 사용하는 Strands Agent를 사용합니다.

이 예제에서는 `get_weather`, `get_time`, `calculator`라는 세 가지 도구와 실시간 스트리밍 응답 기능을 갖춘 간단한 에이전트를 사용합니다.

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

### 자습서 주요 기능

* Amazon Bedrock AgentCore Runtime에서 스트리밍 응답 구현
* Server-Sent Events(SSE)를 사용한 실시간 부분 결과 전송
* 스트리밍 기능이 있는 Amazon Bedrock 모델 사용
* 비동기 스트리밍을 지원하는 Strands Agents 사용
* 응답을 점진적으로 표시하여 사용자 경험 개선
