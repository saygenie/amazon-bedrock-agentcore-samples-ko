# AgentCore Runtime에서 대용량 멀티모달 Payload 처리

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime이 Excel 파일 및 이미지 같은 멀티모달 콘텐츠를 포함하여 최대 100MB의 대용량 payload를 처리하는 방법을 보여 줍니다. AgentCore Runtime은 rich media 콘텐츠와 대규모 dataset을 원활하게 처리하도록 설계되었습니다.

### 자습서 세부 정보

| 정보                | 세부 정보                                                    |
|:--------------------|:-------------------------------------------------------------|
| 자습서 유형         | 대용량 Payload 및 멀티모달 처리                              |
| 에이전트 유형       | 단일                                                         |
| 에이전틱 프레임워크 | Strands Agents                                               |
| LLM 모델            | Anthropic Claude Haiku 4.5                                   |
| 자습서 구성 요소    | 대용량 파일 처리, 이미지 분석, Excel 데이터 처리            |
| 자습서 분야         | 데이터 분석 및 멀티모달 AI                                  |
| 예제 난이도         | 중급                                                         |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK                           |

### 주요 기능

* **대용량 Payload 지원**: 최대 100MB 크기의 파일 처리
* **멀티모달 처리**: Excel 파일, 이미지, 텍스트를 동시에 처리
* **데이터 분석**: 구조화된 데이터 및 시각적 콘텐츠에서 인사이트 추출
* **Base64 Encoding**: JSON payload를 통한 안전한 binary 데이터 전송
