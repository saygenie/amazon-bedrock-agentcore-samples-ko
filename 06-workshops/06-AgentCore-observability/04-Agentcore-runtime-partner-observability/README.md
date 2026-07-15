# 서드 파티 관측성 통합

이 섹션에서는 Amazon Bedrock AgentCore Runtime에서 호스팅되는 에이전트를 서드 파티 관측성 플랫폼과 통합하는 방법을 살펴봅니다. AgentCore Runtime의 이점을 유지하면서 전문 모니터링 도구를 활용하는 방법을 학습합니다.

## 제공되는 통합

이 폴더에는 다음 항목이 있습니다.
- 다양한 관측성 솔루션과 함께 AgentCore Runtime을 사용하는 방법을 보여 주는 Jupyter 노트북
- 필요한 종속성이 나열된 requirements.txt 파일

### 지원 플랫폼

- **Arize**: AI 및 에이전트 엔지니어링 플랫폼
- **Braintrust**: AI 평가 및 모니터링 플랫폼
- **Datadog**: 모니터링, APM, 로그 및 트레이스를 위한 통합 관측성 플랫폼
- **Honeycomb**: 높은 카디널리티의 데이터를 탐색하도록 구축된 관측성 플랫폼
- **Instana**: 실시간 APM 및 관측성 플랫폼
- **Langfuse**: LLM 관측성 및 분석
- **OpenLIT**: LLM 애플리케이션용 오픈 소스 관측성 플랫폼

## 시작하기

1. 관측성 플랫폼을 선택합니다.
2. 해당 플랫폼에서 계정을 생성합니다.
3. API 키와 구성 정보를 받습니다.
4. 필수 패키지를 설치합니다: `pip install -r requirements.txt`
5. notebook에서 환경 변수를 구성합니다.
6. 에이전트를 AgentCore Runtime에 배포합니다.
7. notebook을 실행하여 통합된 관측성을 확인합니다.


## 프레임워크 지원

Amazon Bedrock AgentCore에서는 원하는 에이전트 프레임워크와 모델을 사용할 수 있습니다.
- CrewAI
- LangGraph
- LlamaIndex
- Strands Agents

### Strands Agents
[Strands](https://strandsagents.com/latest/)는 텔레메트리를 기본으로 지원하므로 서드 파티 통합을 보여 주기에 적합합니다.

## 구성 요구 사항

플랫폼마다 특정 구성이 필요합니다.

### Arize
- Arize 대시보드의 API 키 및 Space ID
- 프로젝트 구성

### Braintrust
- Braintrust 대시보드의 API 키
- 프로젝트 구성

### Datadog
- Datadog 대시보드의 API 키(Organization Settings → API Keys)
- Datadog 사이트/리전(US1, US3, US5, EU1, AP1): OTLP 엔드포인트를 결정함
- Strands 기본 제공 텔레메트리를 사용하여 OTLP를 Datadog으로 직접 내보냄(Datadog Agent 불필요)

### Instana
- Instana 키
- 프로젝트 구성

### Langfuse
- 공개 키 및 보안 키
- 프로젝트 구성

### OpenLIT
- OpenLIT 배포(자체 호스팅 또는 클라우드)
- OTLP 엔드포인트 구성

## 정리

예제를 완료한 후 다음을 수행합니다.
1. AgentCore Runtime 배포를 삭제합니다.
2. ECR 저장소를 제거합니다.
3. 플랫폼별 리소스를 정리합니다.
4. 더 이상 필요하지 않은 API 키를 취소합니다.

## 추가 자료

- [Arize 문서](https://arize.com/docs/ax)
- [Braintrust 문서](https://www.braintrust.dev/docs)
- [Datadog 문서](https://docs.datadoghq.com/)
- [Datadog LLM Observability](https://docs.datadoghq.com/llm_observability/)
- [Datadog OpenTelemetry](https://docs.datadoghq.com/opentelemetry/)
- [Instana 문서](https://www.ibm.com/docs/en/instana-observability/1.0.308?topic=overview)
- [Langfuse 문서](https://langfuse.com/docs)
- [OpenLIT 문서](https://docs.openlit.io/)
- [AgentCore Runtime 가이드](https://docs.aws.amazon.com/bedrock-agentcore/latest/userguide/runtime.html)
