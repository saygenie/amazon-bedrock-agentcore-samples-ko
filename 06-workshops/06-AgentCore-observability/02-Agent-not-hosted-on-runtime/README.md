# AgentCore를 사용하는 자체 호스팅 에이전트 관측성

이 섹션에서는 Amazon Bedrock AgentCore Runtime에서 호스팅되지 **않는** 널리 사용되는 오픈 소스 에이전트 프레임워크의 AgentCore Observability를 살펴봅니다. OpenTelemetry와 Amazon CloudWatch를 사용하여 기존 에이전트에 포괄적인 관측성을 추가하는 방법을 학습합니다.

## 지원 프레임워크

### CrewAI
- **노트북**: `CrewAI_Observability.ipynb`
- **설명**: 팀으로 작업하는 자율 AI 에이전트
- **기능**: 사용자 지정 계측을 사용하는 다중 에이전트 협업

### LangGraph
- **노트북**: `Langgraph_Observability.ipynb`
- **설명**: 상태 기반 다중 행위자 LLM 애플리케이션
- **기능**: 트레이스 시각화를 갖춘 복잡한 추론 시스템

### LlamaIndex
- **노트북**: `LlamaIndex_Observability.ipynb`
- **설명**: 데이터 기반의 LLM 에이전트
- **기능**: 세션 추적 기능을 갖춘 함수 에이전트
- **추가 자료**: 아키텍처 다이어그램이 포함된 상세 README

### Strands Agents
- **노트북**: `Strands_Observability.ipynb`
- **설명**: 모델 중심의 에이전트 개발
- **기능**: 사용자 지정 span을 갖춘 복잡한 워크플로 에이전트

## 시작하기

1. 사용할 프레임워크 디렉터리를 선택합니다.
2. 필수 패키지를 설치합니다: `pip install -r requirements.txt`
3. AWS 자격 증명을 구성합니다.
4. `.env.example`을 `.env`로 복사하고 변수를 업데이트합니다.
5. CloudWatch Transaction Search를 활성화합니다.
6. Jupyter notebook을 실행합니다.


## 사전 요구 사항

- 적절한 Bedrock 및 CloudWatch 액세스 권한이 있는 AWS 계정
- Python 3.10+
- AWS CloudWatch Transaction Search 활성화
- 프레임워크별 종속성

## 정리

예제를 완료한 후 다음을 수행합니다.
1. CloudWatch 로그 그룹을 삭제합니다.
2. 생성한 AWS 리소스를 제거합니다.
3. 로컬 환경 파일을 정리합니다.
