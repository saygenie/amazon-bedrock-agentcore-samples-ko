# Amazon Bedrock AgentCore Code Interpreter를 사용한 에이전트 기반 코드 실행 튜토리얼

## 개요

이 튜토리얼에서는 Python 코드 실행을 통해 답변을 검증하는 AI 에이전트를 만드는 방법을 살펴봅니다. LLM이 생성한 코드는 Amazon Bedrock AgentCore Code Interpreter에서 실행합니다.

이 튜토리얼에서는 Amazon Bedrock AgentCore Code Interpreter를 사용하여 다음 작업을 수행하는 방법을 알아봅니다.

1. 샌드박스 환경 설정
2. 사용자 쿼리를 바탕으로 코드를 생성하는 Strands Agents 및 LangChain 기반 에이전트 구성
3. Code Interpreter를 사용하여 샌드박스 환경에서 코드 실행
4. 사용자에게 결과 표시


### 튜토리얼 세부 정보

| 정보                | 세부 정보                                                                        |
|:--------------------|:---------------------------------------------------------------------------------|
| 튜토리얼 유형       | 대화형                                                                            |
| 에이전트 유형       | 단일                                                                              |
| 에이전트 프레임워크 | LangChain 및 Strands Agents                                                      |
| LLM 모델            | Anthropic Claude Sonnet 3.5 및 3.7                                               |
| 튜토리얼 구성 요소  | Amazon Bedrock AgentCore Code Interpreter                                        |
| 튜토리얼 적용 분야  | 산업 전반                                                                         |
| 예제 난이도         | 쉬움                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                      |


### 튜토리얼 아키텍처

코드 실행 샌드박스는 Code Interpreter, 셸, 파일 시스템을 갖춘 격리 환경을 생성하여 에이전트가 사용자 쿼리를 안전하게 처리하도록 지원합니다. 대규모 언어 모델이 도구 선택을 지원한 후 이 세션 안에서 코드가 실행되며, 그 결과는 종합을 위해 사용자 또는 에이전트에게 반환됩니다.

<div style="text-align:left">
    <img src="images/code_interpreter.png" width="100%"/>
</div>
