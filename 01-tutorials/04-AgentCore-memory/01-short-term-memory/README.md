# AgentCore Memory: 단기 메모리(Short-Term Memory)

## 개요

Amazon Bedrock AgentCore의 단기 메모리는 즉각적인 대화 컨텍스트와 세션 기반 정보 관리를 제공합니다. AI 에이전트가 단일 상호작용 또는 밀접하게 관련된 세션 내에서 연속성을 유지하여 대화 전반에 걸쳐 일관되고 컨텍스트를 인식하는 응답을 보장합니다.

## 단기 메모리란?

단기 메모리는 다음에 중점을 둡니다:

- **세션 연속성**: 단일 대화 세션 내에서 컨텍스트 유지
- **즉각적인 컨텍스트**: 일관된 응답을 위한 최근 대화 이력 보존
- **임시 상태**: 현재 상호작용과 관련된 일시적인 정보 관리
- **대화 흐름**: 세션 내 주제 간 원활한 전환 보장

## AgentCore에서 단기 메모리 작동 방식

### 이벤트 저장소

AgentCore Memory는 완전한 대화 이벤트를 원시 형태로 저장하여 다음에 대한 즉각적인 접근을 제공합니다:

- 최근 `k`개의 사용자 메시지 및 에이전트 응답
- 대화 메타데이터 (타임스탬프, 세션 ID, 액터 ID)
- 복잡한 상호작용을 위한 브랜칭 대화 경로

### 세션 관리

단기 메모리는 세션 수준에서 작동합니다:

- 각 대화 세션은 자체 컨텍스트를 유지합니다
- 관련 세션은 세션 그룹화를 통해 컨텍스트를 공유할 수 있습니다
- 만료된 세션 데이터의 자동 정리 (구성된 TTL 기반)

### 실시간 접근

백그라운드에서 처리되는 장기 메모리 전략과 달리, 단기 메모리는 다음을 제공합니다:

- 최근 대화 이력의 즉각적인 검색
- 세션이 중단되거나 에이전트가 실패한 경우의 대화 재개
- 대화 진행에 따른 실시간 컨텍스트 업데이트
- 세션별 정보에 대한 저지연 접근

## 모범 사례

1. **컨텍스트 윈도우 관리**: 오버플로우를 방지하기 위해 컨텍스트 사용량 모니터링
2. **세션 경계**: 세션의 시작과 종료를 명확하게 정의
3. **메모리 정리**: 만료된 세션에 대한 적절한 정리 정책 구현
4. **오류 처리**: 메모리 검색 실패를 우아하게 처리
5. **성능 최적화**: 대규모 대화 이력에 대해 효율적인 쿼리 패턴 사용 (예: 장기 메모리의 요약 전략 활용)

## 프레임워크 통합

단기 메모리는 인기 있는 에이전트 프레임워크와 원활하게 통합됩니다:

- **Strands Agent**: 대화 훅과의 네이티브 통합
- **LangGraph**: 상태 관리 통합
- **커스텀 프레임워크**: 유연한 구현을 위한 직접 API 접근

## 사용 가능한 샘플 노트북

다음 실습 예제를 통해 단기 메모리 구현을 학습하세요:

| 프레임워크    | 사용 사례        | 설명                                                                                                   | 노트북                                                                                                                    | 아키텍처                                                                |
| ------------- | --------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Strands Agent | 개인 에이전트    | 세션 내에서 대화 컨텍스트를 유지하고 사용자 상호작용을 기억하는 AI 어시스턴트                           | [personal-agent.ipynb](./01-single-agent/with-strands-agent/personal-agent.ipynb)                                          | [보기](./01-single-agent/with-strands-agent/architecture.png)          |
| LangGraph     | 피트니스 코치   | 운동 진행 상황을 추적하고 트레이닝 세션 전반에 걸쳐 컨텍스트를 유지하는 개인 피트니스 코치              | [personal-fitness-coach.ipynb](./01-single-agent/with-langgraph-agent/personal-fitness-coach.ipynb)                        | [보기](./01-single-agent/with-langgraph-agent/images/architecture.png) |
| LangGraph     | 지원 에이전트   | 복잡한 문제 해결을 위한 Human-in-the-Loop 기능을 갖춘 고객 지원 에이전트                               | [support-agent-human-in-the-loop.ipynb](./01-single-agent/with-langgraph-agent/support-agent-human-in-the-loop.ipynb)      | [보기](./01-single-agent/with-langgraph-agent/images/architecture.png) |
| LangGraph     | 수학 에이전트   | 복잡한 계산을 위한 다단계 영속성을 갖춘 수학 문제 해결 에이전트                                        | [math-agent-with-multi-step-persistence.ipynb](./01-single-agent/with-langgraph-agent/math-agent-with-checkpointing.ipynb) | [보기](./01-single-agent/with-langgraph-agent/images/architecture.png) |
| Strands Agent | 여행 계획       | 복잡한 여행 일정을 계획하면서 컨텍스트를 공유하는 협업 에이전트                                         | [travel-planning-agent.ipynb](./02-multi-agent/with-strands-agent/travel-planning-agent.ipynb)                             | [보기](./02-multi-agent/with-strands-agent/architecture.png)           |

## 시작하기

1. 사용 사례에 맞는 샘플을 선택하세요
2. 샘플 폴더로 이동하세요
3. 요구사항 설치: `pip install -r requirements.txt`
4. Jupyter 노트북을 열고 단계별 구현을 따라하세요

## 다음 단계

단기 메모리에 익숙해지면, [장기 메모리](../02-long-term-memory/)를 탐색하여 여러 대화와 세션에 걸쳐 작동하는 영속적인 메모리 전략에 대해 알아보세요.
