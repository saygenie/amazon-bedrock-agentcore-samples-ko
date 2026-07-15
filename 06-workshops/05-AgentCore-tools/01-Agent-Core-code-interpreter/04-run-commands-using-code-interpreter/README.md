# Amazon Bedrock AgentCore Code Interpreter에서 명령 실행하기 튜토리얼

## 개요

이 튜토리얼에서는 Amazon Bedrock AgentCore Code Interpreter를 사용하여 셸 및 AWS CLI 명령을 실행하는 방법을 살펴봅니다. 특히 Amazon S3 작업을 중심으로 AWS 서비스와 상호 작용하며 다음 단계를 진행합니다.

1. Python 기반 Code Interpreter 생성
2. Code Interpreter 세션 시작
3. 셸 및 AWS CLI 명령 실행
4. Amazon S3 작업 수행(버킷 생성, 객체 복사, 버킷 객체 나열)
5. 리소스 정리(세션 중지 및 Code Interpreter 삭제)


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
