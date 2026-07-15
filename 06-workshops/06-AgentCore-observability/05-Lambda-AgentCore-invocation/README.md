# CloudWatch Observability를 활용한 Lambda의 AgentCore 호출

이 자습서에서는 완전한 CloudWatch Gen AI Observability가 활성화된 AWS Lambda 함수에서 Amazon Bedrock AgentCore Runtime에 호스팅된 Strands Agents를 호출하는 방법을 살펴봅니다.

## 개요

Lambda 함수가 AgentCore Runtime에서 실행되는 MCP 지원 에이전트를 호출하고 CloudWatch를 통해 Lambda 실행과 에이전트 동작을 모두 완전하게 파악할 수 있는 서버리스 아키텍처를 구축하는 방법을 학습합니다.

## 프로젝트 구조
```
05-Lambda-AgentCore-invocation/
├── agentcore_observability_lambda.ipynb  # 기본 실습 Notebook
├── lambda_agentcore_invoker.py           # Lambda 함수 코드
├── mcp_agent_multi_server.py             # 여러 MCP server를 사용하는 Agent
├── requirements.txt                      # Python 의존성
├── .gitignore                            # Git ignore 패턴
└── README.md                             # 이 파일

참고: Dockerfile은 노트북에서 동적으로 생성되며 git에서 추적하지 않습니다.
```

## 자습서 세부 정보

| 정보                | 세부 정보                                                                         |
|:-------------------|:----------------------------------------------------------------------------------|
| 자습서 유형        | 대화형                                                                            |
| 에이전트 유형      | 단일 에이전트                                                                     |
| 에이전트 프레임워크| Strands Agents                                                                    |
| LLM 모델           | Anthropic Claude Haiku 4.5                                                       |
| 자습서 구성 요소   | Lambda 호출, AgentCore Runtime, MCP 서버, CloudWatch Observability               |
| 예제 난이도        | 고급                                                                              |
| 사용 SDK           | Amazon BedrockAgentCore Python SDK, boto3, AWS Lambda                            |

## 아키텍처
```
┌─────────┐      ┌────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   API   │─────>│  AWS Lambda    │─────>│  AgentCore       │─────>│  Strands Agent  │
│  /User  │      │  (Invoker)     │      │  Runtime         │      │  + MCP Servers  │
└─────────┘      └────────────────┘      └──────────────────┘      └─────────────────┘
                        │                         │                          │
                        ▼                         ▼                          ▼
                 ┌─────────────────────────────────────────────────────────────┐
                 │            CloudWatch Observability                         │
                 │       • Gen AI Traces     • Metrics     • Logs              │
                 └─────────────────────────────────────────────────────────────┘
```

## 주요 기능

* 여러 MCP 서버(AWS Documentation + AWS CDK)를 Strands Agents와 통합
* Amazon Bedrock AgentCore Runtime에서 에이전트 호스팅
* AWS Lambda 함수에서 호스팅된 에이전트 호출
* 포괄적인 에이전트 모니터링을 위한 CloudWatch Gen AI Observability 구성
* CloudWatch 콘솔에서 트레이스, 스팬 및 지표 확인

## 학습 내용

1. MCP 지원 에이전트를 AgentCore Runtime에 배포하는 방법
2. Runtime 에이전트를 호출하는 Lambda 함수를 생성하는 방법
3. 에이전트에 CloudWatch Gen AI Observability를 활성화하는 방법
4. 에이전트 실행 흐름을 보여 주는 트레이스를 확인하고 분석하는 방법

## 사전 요구 사항

* Python 3.10+
* 적절한 권한으로 구성된 AWS 자격 증명
* Amazon Bedrock AgentCore SDK
* Lambda 함수와 IAM 역할을 생성할 수 있는 권한
* CloudWatch Transaction Search 활성화(설정 지침은 자습서 참조)

## 시작하기

1. 필요한 패키지를 설치합니다.
```bash
   pip install -r requirements.txt
```

2. CloudWatch Transaction Search를 활성화합니다(AWS 계정별로 콘솔에서 한 번만 설정).

3. Jupyter notebook을 열어 실행합니다.
```bash
   jupyter notebook agentcore_observability_lambda.ipynb
```

4. notebook의 단계별 지침에 따라 다음을 수행합니다.
   - MCP 에이전트 생성 및 배포
   - Lambda 함수 빌드 및 배포
   - 통합 테스트
   - CloudWatch에서 트레이스 확인

## 구성 요소

### Lambda 함수 (`lambda_agentcore_invoker.py`)
사용자 prompt를 받아 AgentCore Runtime 에이전트를 호출하는 서버리스 함수입니다. 오류 처리와 포괄적인 로깅을 포함합니다.

### MCP 에이전트 (`mcp_agent_multi_server.py`)
여러 MCP 서버(AWS Documentation 및 AWS CDK)와 관측성을 위한 OpenTelemetry 계측이 구성된 Strands Agents입니다.

## 사용 방법

Lambda 함수에는 다음 이벤트 형식이 필요합니다.
```json
{
  "prompt": "Your question here",
  "sessionId": "optional-session-id"
}
```

응답 형식:
```json
{
  "statusCode": 200,
  "body": {
    "response": "Agent's response",
    "sessionId": "session-id"
  }
}
```

## 관측성 기능

* **Gen AI 트레이스**: 스팬 타임라인으로 전체 에이전트 워크플로 시각화
* **CloudWatch Logs**: Lambda 및 에이전트 실행의 상세 로깅
* **성능 지표**: 토큰 사용량, 소요 시간 및 오류율 추적
* **Transaction Search**: 애플리케이션 전반의 트레이스 쿼리 및 분석

## 정리

불필요한 비용이 발생하지 않도록 자습서를 완료한 후 다음 리소스를 삭제하세요.

1. Lambda 함수 및 연결된 IAM 역할
2. AgentCore Runtime 에이전트 및 엔드포인트
3. CloudWatch 로그 그룹
4. ECR의 컨테이너 이미지(해당하는 경우)

## 추가 자료

- [Amazon Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [CloudWatch Gen AI Observability 가이드](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/GenAI-observability.html)

## 라이선스

이 프로젝트에는 저장소에 명시된 라이선스 조건이 적용됩니다.
