# Amazon Bedrock AgentCore Observability: 데이터 보호

## 개요

이 자습서에서는 Amazon Bedrock Guardrails와 Amazon CloudWatch Logs Data Protection 정책을 사용하여 에이전틱 AI 애플리케이션에 포괄적인 데이터 보호를 구현하는 방법을 학습합니다. 입력 처리부터 출력 생성 및 로깅에 이르기까지 에이전트의 전체 수명 주기에서 민감한 데이터를 보호하는 방법을 살펴봅니다.

개인 식별 정보(PII), 금융 데이터, 건강 기록 및 기타 기밀 정보를 보호하기 위해 함께 작동하는 여러 보호 계층을 결합하여 AI 애플리케이션을 보호하는 심층 방어 전략을 구축하는 데 중점을 둡니다.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                         |
|:--------------------|:---------------------------------------------------------------------------------|
| 자습서 유형         | 관측성 및 보안                                                                    |
| 에이전트 유형       | 단일 에이전트                                                                     |
| 에이전트 프레임워크 | Strands Agents                                                                   |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                       |
| 자습서 구성 요소    | 데이터 보호, Bedrock Guardrails, CloudWatch Logs Data Protection                |
| 자습서 산업군       | 산업 전반                                                                         |
| 예제 난이도         | 고급                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                      |

### 자습서 아키텍처

이 자습서에서는 AgentCore Runtime에 배포된 에이전트에 데이터 보호 메커니즘을 구현하는 방법을 살펴봅니다. 민감한 정보를 처리하는 고객 지원 에이전트를 사용하여 여러 보안 계층으로 데이터를 보호하는 방법을 보여 줍니다.

예제에는 다음 항목이 포함됩니다.
- 고객 지원 기능을 갖춘 Strands Agents
- 콘텐츠 필터링을 위한 Amazon Bedrock Guardrails
- 로그 마스킹을 위한 CloudWatch Logs Data Protection
- 민감한 정보 탐지 및 처리

### 자습서 주요 기능

* **다계층 데이터 보호**: Bedrock Guardrails 및 CloudWatch Logs Data Protection 구현
* **민감한 정보 탐지**: PII, 금융 데이터 및 기타 기밀 정보 자동 탐지
* **에이전트 보안**: 에이전트 상호 작용과 트레이스의 민감한 데이터 보호
* **규정 준수 지원**: 개인 정보 보호 규정(GDPR, HIPAA, CCPA) 요구 사항 충족
* **심층 방어 전략**: 에이전틱 AI 애플리케이션을 위한 포괄적인 보안 구축

## 학습 내용

이 실습 자습서에서는 다음 내용을 살펴봅니다.

- 에이전트 상호 작용과 CloudWatch 로그 및 트레이스에서 민감한 정보를 탐지하는 방법
- Amazon Bedrock Guardrails: AI 에이전트가 민감한 콘텐츠를 처리하거나 생성하지 못하도록 민감한 정보 필터를 구성하는 방법
- CloudWatch Logs Data Protection: 애플리케이션 로그에서 민감한 데이터를 자동으로 탐지하고 마스킹하는 방법
- AgentCore 통합: 에이전트 워크플로에 이러한 보호 조치를 구현하는 방법

## 중요한 이유

적절한 보호 조치가 없으면 에이전틱 AI 시스템에서 다음 문제가 발생할 수 있습니다.

- 응답이나 로그에서 민감한 고객 데이터가 의도치 않게 노출됨
- 개인 정보 보호 규정을 위반하는 정보를 처리하거나 보관함
- 공유해서는 안 되는 PII가 포함된 출력을 생성함
- 애플리케이션 인프라에 규정 준수 및 보안 취약점을 만듦

## 자습서 파일

- `data_protection.ipynb` - 단계별 지침이 포함된 기본 자습서 노트북
- `requirements.txt` - 자습서에 필요한 Python 종속성
- `data/` - 고객 지원 대화 예제를 포함한 샘플 데이터 파일
- `images/` - 자습서용 아키텍처 다이어그램 및 시각 자료
