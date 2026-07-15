# Amazon Bedrock AgentCore Code Interpreter 시작하기 튜토리얼

## 개요

이 튜토리얼에서는 Amazon Bedrock AgentCore Code Interpreter를 사용하여 다음 작업을 수행하는 방법을 알아봅니다.

1. 샌드박스 환경 설정
2. 데이터 로드 및 분석
3. 샌드박스 환경에서 코드 실행
4. 결과 처리 및 검색


### 튜토리얼 세부 정보

| 정보                | 세부 정보                                                                        |
|:--------------------|:---------------------------------------------------------------------------------|
| 튜토리얼 유형       | 대화형                                                                            |
| 튜토리얼 구성 요소  | Amazon Bedrock AgentCore Code Interpreter                                        |
| 튜토리얼 적용 분야  | 산업 전반                                                                         |
| 예제 난이도         | 쉬움                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                      |


### 튜토리얼 아키텍처

코드 실행 샌드박스는 Code Interpreter, 셸, 파일 시스템을 갖춘 격리 환경을 생성하여 에이전트가 사용자 쿼리를 안전하게 처리하도록 지원합니다. 대규모 언어 모델이 도구 선택을 지원한 후 이 세션 안에서 코드가 실행되며, 그 결과는 종합을 위해 사용자 또는 에이전트에게 반환됩니다.

<div style="text-align:left">
    <img src="images/code_interpreter.png" width="100%"/>
</div>
