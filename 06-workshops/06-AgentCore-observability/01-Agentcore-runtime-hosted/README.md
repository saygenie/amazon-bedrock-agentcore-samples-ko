# Bedrock AgentCore Runtime 에이전트를 위한 Amazon CloudWatch의 AgentCore Observability

이 저장소에는 Amazon OpenTelemetry Python Instrumentation과 Amazon CloudWatch를 사용하여 Amazon Bedrock AgentCore Runtime에서 호스팅되는 Strands Agents, CrewAI 및 LlamaIndex 에이전트에 AgentCore Observability를 적용하는 예제가 포함되어 있습니다. 관측성을 활용하면 통합 운영 대시보드에서 프로덕션 환경의 에이전트 성능을 추적, 디버깅 및 모니터링할 수 있습니다. Amazon CloudWatch GenAI Observability는 OpenTelemetry 호환 텔레메트리와 에이전트 워크플로 각 단계의 상세한 시각화를 지원하므로, 개발자가 에이전트 동작을 쉽게 파악하고 대규모 환경에서도 품질 기준을 유지할 수 있습니다.

## 프레임워크 예제

### Strands Agents
[Strands](https://strandsagents.com/latest/)는 모델 중심의 에이전트 개발에 중점을 두고 복잡한 워크플로를 갖춘 LLM 애플리케이션을 구축할 수 있는 프레임워크를 제공합니다.

**위치**: `Strands Agents/`
- 자습서: `runtime_with_strands_and_bedrock_models.ipynb`
- 기능: Amazon Bedrock 모델을 사용하는 날씨 및 계산기 도구

### CrewAI
[CrewAI](https://www.crewai.com/)를 사용하면 역할 기반 에이전트 오케스트레이션으로 여러 에이전트가 협업할 수 있습니다.

**위치**: `CrewAI/`
- 자습서: `runtime-with-crewai-and-bedrock-models.ipynb`
- 기능: 협업 에이전트 패턴

### LlamaIndex
[LlamaIndex](https://www.llamaindex.ai/)는 고급 검색 및 추론 기능을 갖춘 LLM 애플리케이션용 데이터 프레임워크를 제공합니다.

**위치**: `LlamaIndex/`
- 자습서: `runtime_with_llamaindex_and_bedrock_models.ipynb`
- 기능: 산술 도구와 포괄적인 관측성을 갖춘 FunctionAgent

## 시작하기

각 프레임워크 폴더에는 다음 항목이 있습니다.
- AgentCore Runtime 배포와 CloudWatch 관측성을 보여 주는 Jupyter 노트북
- 필요한 종속성이 나열된 requirements.txt 파일
- 프레임워크별 지침이 포함된 README.md

## 사용 방법

1. 살펴볼 프레임워크의 디렉터리로 이동합니다.
2. 필수 패키지를 설치합니다: `pip install -r requirements.txt`
3. AWS 자격 증명을 구성합니다.
4. Jupyter notebook을 열어 실행합니다.

## 주요 기능

- **자동 관측성**: 에이전트가 AgentCore Runtime에서 실행될 때 기본 제공되는 텔레메트리 수집
- **CloudWatch 통합**: GenAI Observability 대시보드에서 트레이스와 지표 확인
- **유연한 프레임워크**: 여러 에이전트 프레임워크 지원

## 정리

예제를 완료한 후 다음을 수행합니다.

1. AgentCore Runtime 배포를 제거합니다.
2. 생성한 ECR 저장소를 정리합니다.
3. 더 이상 필요하지 않은 CloudWatch 로그 그룹을 삭제합니다.
