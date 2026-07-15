# AgentCore Observability

이 저장소에서는 Amazon CloudWatch 및 기타 제공업체를 사용하여 에이전트에 AgentCore Observability를 구현하는 방법을 살펴봅니다. Amazon Bedrock AgentCore Runtime에서 호스팅되는 에이전트와 널리 사용되는 오픈 소스 에이전트 프레임워크를 사용하여 Runtime 외부에서 호스팅되는 에이전트의 예제를 모두 제공합니다.



AgentCore Observability에 대한 자세한 내용은 [이 블로그 게시물](https://aws.amazon.com/blogs/machine-learning/build-trustworthy-ai-agents-with-amazon-bedrock-agentcore-observability/)을 참조하세요.
## 프로젝트 구조

```
06-AgentCore-observability/
├── 01-Agentcore-runtime-hosted/
│   ├── CrewAI/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   └── runtime-with-crewai-and-bedrock-models.ipynb
│   ├── LlamaIndex/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   ├── runtime_with_llamaindex_and_bedrock_models.ipynb
│   │   └── README.md
│   ├── Strands Agents/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_bedrock_models.ipynb
│   └── README.md
├── 02-Agent-not-hosted-on-runtime/
│   ├── CrewAI/
│   │   ├── .env.example
│   │   ├── CrewAI_Observability.ipynb
│   │   └── requirements.txt
│   ├── Langgraph/
│   │   ├── .env.example
│   │   ├── Langgraph_Observability.ipynb
│   │   └── requirements.txt
│   ├── LlamaIndex/
│   │   ├── images/
│   │   ├── .env.example
│   │   ├── LlamaIndex_Observability.ipynb
│   │   ├── README.md
│   │   └── requirements.txt
│   ├── Strands/
│   │   ├── images/
│   │   ├── .env.example
│   │   ├── requirements.txt
│   │   └── Strands_Observability.ipynb
│   └── README.md
├── 03-advanced-concepts/
│   ├── 01-custom-span-creation/
│   │   ├── .env.example
│   │   ├── Custom_Span_Creation.ipynb
│   │   └── requirements.txt
│   └── README.md
├── 04-Agentcore-runtime-partner-observability/
│   ├── Arize/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_arize.ipynb
│   ├── Braintrust/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_braintrust.ipynb
│   ├── Datadog/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_datadog.ipynb
│   ├── Instana/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_instana.ipynb
│   ├── Langfuse/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_langfuse.ipynb
│   ├── images/
│   └── README.md
├── 05-Lambda-AgentCore-invocation/
│   ├── .gitignore
│   ├── agentcore_observability_lambda.ipynb
│   ├── lambda_agentcore_invoker.py
│   ├── mcp_agent_multi_server.py
│   ├── README.md
│   └── requirements.txt
└── README.md
```

## 개요

이 저장소는 개발자가 생성형 AI 애플리케이션에 관측성을 구현하는 데 도움이 되는 예제와 도구를 제공합니다. AgentCore Observability를 사용하면 통합 운영 대시보드에서 프로덕션 환경의 에이전트 성능을 추적, 디버깅 및 모니터링할 수 있습니다. Amazon CloudWatch GenAI Observability는 OpenTelemetry 호환 텔레메트리와 에이전트 워크플로 각 단계의 상세한 시각화를 지원하므로, 개발자가 에이전트 동작을 쉽게 파악하고 대규모 환경에서도 품질 기준을 유지할 수 있습니다.

## 구성

널리 사용되는 다음 에이전트 개발 프레임워크의 예제를 살펴봅니다.

- **Strands Agents**: 모델 중심의 에이전트 개발 방식으로 복잡한 워크플로를 갖춘 LLM 애플리케이션 구축
- **CrewAI**: 역할에 따라 협업하며 작업을 수행하는 자율 AI 에이전트 생성
- **LangGraph**: 복잡한 추론 시스템을 위한 상태 기반 다중 행위자 애플리케이션으로 LangChain 확장
- **LlamaIndex**: 워크플로를 활용하여 데이터 기반의 LLM 에이전트 구축


### 1. Bedrock AgentCore Runtime 호스팅 (01-Agentcore-runtime-hosted)

Amazon OpenTelemetry Python Instrumentation과 Amazon CloudWatch를 사용하여 Amazon Bedrock AgentCore Runtime에서 호스팅되는 에이전트의 관측성을 구현하는 예제입니다.

### 2. Runtime 외부에서 호스팅되는 에이전트 (02-Agent-not-hosted-on-runtime)

Amazon Bedrock AgentCore Runtime에서 호스팅되지 않는 널리 사용되는 오픈 소스 에이전트 프레임워크의 관측성 예제입니다.

### 3. 고급 개념 (03-advanced-concepts)

고급 관측성 패턴과 기법을 다룹니다.

- **사용자 지정 스팬 생성**: 에이전트 워크플로의 특정 작업을 상세히 추적하고 모니터링하기 위한 사용자 지정 스팬 생성 방법 학습

### 4. 파트너 관측성 (04-Agentcore-runtime-partner-observability)

Amazon Bedrock AgentCore Runtime에서 호스팅되는 에이전트를 서드 파티 관측성 도구와 함께 사용하는 예제입니다.

- **Arize**: AI 및 에이전트 엔지니어링 플랫폼
- **Braintrust**: AI 평가 및 모니터링 플랫폼
- **Datadog**: 모니터링, APM, 로그 및 트레이스를 위한 통합 관측성 플랫폼
- **Instana**: 실시간 APM 및 관측성 플랫폼
- **Langfuse**: LLM 관측성 및 분석

### 5. Lambda에서 AgentCore 호출 (05-Lambda-AgentCore-invocation)

완전한 CloudWatch 관측성을 갖춘 AWS Lambda 함수에서 AgentCore Runtime 에이전트를 호출하는 방법을 학습합니다.

- **Lambda 통합**: 호스팅된 에이전트를 호출하는 서버리스 함수 배포
- **MCP 다중 서버**: 단일 에이전트에서 여러 MCP 서버(AWS Docs + CDK) 사용
- **CloudWatch GenAI Observability**: 프로덕션 환경의 에이전트 동작과 성능 모니터링

## 시작하기

1. 살펴볼 프레임워크의 디렉터리로 이동합니다.
2. 필수 패키지를 설치합니다.
3. AWS 자격 증명을 구성합니다.
4. `.env.example` 파일을 `.env`로 복사하고 변수를 업데이트합니다.
5. Jupyter notebook을 열어 실행합니다.

## 사전 요구 사항

- 적절한 권한이 있는 AWS 계정
- Python 3.10+
- Jupyter 노트북 환경
- 자격 증명이 구성된 AWS CLI
- Transaction Search 활성화

## 정리

불필요한 비용이 발생하지 않도록 예제를 완료한 후 Amazon CloudWatch에서 생성한 로그 그룹과 관련 리소스를 삭제하세요.

## 라이선스

이 프로젝트에는 저장소에 명시된 라이선스 조건이 적용됩니다.
