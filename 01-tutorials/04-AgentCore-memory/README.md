# Amazon Bedrock AgentCore Memory

## 개요

메모리는 지능의 핵심 구성 요소입니다. 대규모 언어 모델(LLM)은 뛰어난 기능을 갖추고 있지만, 대화 간 영속적인 메모리가 부족합니다. Amazon Bedrock AgentCore Memory는 AI 에이전트가 시간이 지남에 따라 컨텍스트를 유지하고, 중요한 사실을 기억하며, 일관되고 개인화된 경험을 제공할 수 있도록 하는 관리형 서비스를 제공하여 이러한 한계를 해결합니다.

## 주요 기능

AgentCore Memory는 다음을 제공합니다:

- **핵심 인프라**: 내장된 암호화 및 관측성을 갖춘 서버리스 설정
- **이벤트 저장소**: 브랜칭을 지원하는 원시 이벤트 저장소 (대화 이력/체크포인팅)
- **전략 관리**: 구성 가능한 추출 전략 (SEMANTIC, SUMMARY, USER_PREFERENCES, CUSTOM)
- **메모리 레코드 추출**: 구성된 전략에 기반한 사실, 선호도, 요약의 자동 추출
- **시맨틱 검색**: 자연어 쿼리를 사용한 벡터 기반 관련 메모리 검색

## AgentCore Memory 작동 방식

![high_level_workflow](./images/high_level_memory.png)

AgentCore Memory는 두 가지 수준에서 작동합니다:

### 단기 메모리(Short-Term Memory)

단일 상호작용 또는 밀접하게 관련된 세션 내에서 연속성을 제공하는 즉각적인 대화 컨텍스트 및 세션 기반 정보입니다.

### 장기 메모리(Long-Term Memory)

사실, 선호도, 요약을 포함하여 여러 대화에 걸쳐 추출 및 저장되는 영속적인 정보로, 시간이 지남에 따라 개인화된 경험을 가능하게 합니다.

## 메모리 아키텍처

1. **대화 저장**: 완전한 대화가 원시 형태로 저장되어 즉각적인 접근이 가능합니다
2. **전략 처리**: 구성된 전략이 백그라운드에서 대화를 자동으로 분석합니다
3. **정보 추출**: 전략 유형에 따라 중요한 데이터가 추출됩니다 (일반적으로 약 1분 소요)
4. **구조화된 저장**: 추출된 정보가 효율적인 검색을 위해 구조화된 네임스페이스에 저장됩니다
5. **시맨틱 검색**: 자연어 쿼리가 벡터 유사도를 사용하여 관련 메모리를 검색할 수 있습니다

## 메모리 전략 유형

AgentCore Memory는 다섯 가지 전략 유형을 지원합니다:

- **시맨틱 메모리(Semantic Memory)**: 유사도 검색을 위해 벡터 임베딩을 사용하여 사실 정보를 저장
- **요약 메모리(Summary Memory)**: 컨텍스트 보존을 위한 대화 요약 생성 및 유지
- **사용자 선호도 메모리(User Preference Memory)**: 사용자별 선호도 및 설정 추적
- **에피소딕 메모리(Episodic Memory)**: 자동 에피소드 감지, 통합, 리플렉션 생성을 통한 의미 있는 상호작용 시퀀스 캡처
- **커스텀 메모리(Custom Memory)**: 추출 및 통합 로직의 커스터마이징 허용

## 시작하기

체계적인 튜토리얼을 통해 메모리 기능을 탐색하세요:

- **[단기 메모리](./01-short-term-memory/)**: 세션 기반 메모리와 즉각적인 컨텍스트 관리 학습
- **[장기 메모리](./02-long-term-memory/)**: 영속적인 메모리 전략과 대화 간 연속성 이해

## 샘플 노트북 개요

| 메모리 유형 | 프레임워크          | 사용 사례          | 노트북                                                                                                                            |
| ----------- | ------------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| 단기        | Strands Agent       | 개인 에이전트      | [personal-agent.ipynb](./01-short-term-memory/01-single-agent/with-strands-agent/personal-agent.ipynb)                             |
| 단기        | LangGraph           | 피트니스 코치      | [personal-fitness-coach.ipynb](./01-short-term-memory/01-single-agent/with-langgraph-agent/personal-fitness-coach.ipynb)           |
| 단기        | Strands Agent       | 여행 계획          | [travel-planning-agent.ipynb](./01-short-term-memory/02-multi-agent/with-strands-agent/travel-planning-agent.ipynb)                |
| 장기        | Strands Hooks       | 고객 지원          | [customer-support.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/customer-support/customer-support.ipynb)  |
| 장기        | Strands Hooks       | 수학 어시스턴트    | [math-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb) |
| 장기        | Strands Tool        | 요리 어시스턴트    | [culinary-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb)         |
| 장기        | Strands Multi-Agent | 여행 예약          | [travel-booking-assistant.ipynb](./02-long-term-memory/02-multi-agent/with-strands-agent/travel-booking-assistant.ipynb)           |
| 에피소딕    | Strands Hooks       | 회의 노트 어시스턴트 | [meeting-notes-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/meeting-notes-assistant-using-episodic/meeting-notes-assistant.ipynb)                                         |

## 사전 요구사항

- Python 3.10 이상
- Amazon Bedrock 접근 권한이 있는 AWS 계정
- Jupyter Notebook 환경
- 필요한 Python 패키지 (각 샘플의 requirements.txt 파일 참조)
