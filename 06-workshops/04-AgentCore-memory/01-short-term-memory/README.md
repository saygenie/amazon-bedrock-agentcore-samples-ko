# AgentCore Memory: 단기 메모리

## 개요

Amazon Bedrock AgentCore의 단기 메모리는 즉각적인 대화 맥락과 세션 기반 정보 관리를 제공합니다. AI Agent가 단일 상호 작용이나 밀접하게 관련된 세션 내에서 연속성을 유지하도록 하여 대화 전반에서 일관되고 맥락을 인식하는 응답을 제공할 수 있습니다.

## 단기 메모리란?

단기 메모리는 다음 항목에 중점을 둡니다.

- **세션 연속성**: 단일 대화 세션 내에서 맥락 유지
- **즉각적인 맥락**: 일관된 응답을 위해 최근 대화 기록 보존
- **임시 상태**: 현재 상호 작용과 관련된 일시적 정보 관리
- **대화 흐름**: 세션 내 주제 간 자연스러운 전환 보장

## AgentCore에서 단기 메모리가 작동하는 방식

### 이벤트 저장

AgentCore Memory는 전체 대화 이벤트를 원시 형태로 저장하여 다음 정보에 즉시 액세스할 수 있게 합니다.

- 최근 `k`개의 사용자 메시지와 Agent 응답
- 대화 메타데이터(timestamp, session ID, actor ID)
- 복잡한 상호 작용을 위한 분기 대화 경로

### 세션 관리

단기 메모리는 세션 수준에서 작동합니다.

- 각 대화 세션은 자체 맥락을 유지합니다.
- 관련 세션은 세션 그룹화를 통해 맥락을 공유할 수 있습니다.
- 만료된 세션 데이터를 구성된 TTL에 따라 자동으로 정리합니다.

### 실시간 액세스

백그라운드에서 처리되는 장기 메모리 전략과 달리, 단기 메모리는 다음 기능을 제공합니다.

- 최근 대화 기록 즉시 검색
- 세션이 중단되거나 Agent에 장애가 발생했을 때 대화 재개
- 대화 진행에 따른 실시간 맥락 업데이트
- 세션별 정보에 대한 짧은 지연 시간의 액세스

## 모범 사례

1. **Context Window 관리**: 오버플로를 방지하도록 맥락 사용량을 모니터링합니다.
2. **세션 경계**: 세션의 시작과 종료 시점을 명확히 정의합니다.
3. **메모리 정리**: 만료된 세션에 적절한 정리 정책을 구현합니다.
4. **오류 처리**: 메모리 검색 실패를 적절히 처리합니다.
5. **성능 최적화**: 대규모 대화 기록에는 효율적인 쿼리 패턴을 사용합니다(예: 장기 메모리의 Summary Strategy 활용).

## 프레임워크 통합

단기 메모리는 널리 사용되는 Agent 프레임워크와 원활하게 통합됩니다.

- **Strands Agents**: 대화 hook과 기본 통합
- **LangGraph**: 상태 관리 통합
- **사용자 지정 프레임워크**: 유연한 구현을 위한 직접 API 액세스

## 제공되는 샘플 노트북

다음 실습 예제를 통해 단기 메모리 구현 방법을 알아보세요.

| 프레임워크    | 사용 사례       | 설명                                                                                                   | 노트북                                                                                                                     | 아키텍처                                                               |
| ------------- | --------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Strands Agents | 개인 Agent     | 대화 맥락을 유지하고 세션 내 사용자 상호 작용을 기억하는 AI 도우미                                    | [personal-agent.ipynb](./01-single-agent/with-strands-agent/personal-agent.ipynb)                                          | [보기](./01-single-agent/with-strands-agent/architecture.png)          |
| LangGraph     | 피트니스 코치   | 운동 진행 상황을 추적하고 훈련 세션 전반에서 맥락을 유지하는 개인 피트니스 코치                        | [personal-fitness-coach.ipynb](./01-single-agent/with-langgraph-agent/personal-fitness-coach.ipynb)                        | [보기](./01-single-agent/with-langgraph-agent/images/architecture.png) |
| LangGraph     | 지원 Agent      | 복잡한 문제 해결을 위해 Human-in-the-Loop 기능을 갖춘 고객 지원 Agent                                  | [support-agent-human-in-the-loop.ipynb](./01-single-agent/with-langgraph-agent/support-agent-human-in-the-loop.ipynb)      | [보기](./01-single-agent/with-langgraph-agent/images/architecture.png) |
| LangGraph     | 수학 Agent      | AgentCore Memory 기반의 LangGraph 체크포인트를 사용하는 수학 문제 해결 Agent                            | [math-agent-with-checkpointing.ipynb](./01-single-agent/with-langgraph-agent/math-agent-with-checkpointing.ipynb)          | [보기](./01-single-agent/with-langgraph-agent/images/architecture.png) |
| Strands Agents | 여행 계획      | 복잡한 여행 일정을 계획하면서 맥락을 공유하는 협업 Agent                                               | [travel-planning-agent.ipynb](./02-multi-agent/with-strands-agent/travel-planning-agent.ipynb)                             | [보기](./02-multi-agent/with-strands-agent/architecture.png)           |

## 시작하기

1. 사용 사례에 맞는 샘플을 선택합니다.
2. 샘플 폴더로 이동합니다.
3. 필수 패키지를 설치합니다: `pip install -r requirements.txt`
4. Jupyter Notebook을 열고 단계별 구현을 따라 진행합니다.

## 다음 단계

단기 메모리에 익숙해졌다면 [장기 메모리](../02-long-term-memory/)에서 여러 대화와 세션에 걸쳐 작동하는 지속적인 메모리 전략을 알아보세요.
