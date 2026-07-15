# AgentCore Memory: 메모리 분기

## 개요

메모리 분기를 사용하면 Agent가 이전의 어떤 이벤트에서든 대화를 대체 경로로 분기하고, 계속할 경로를 선택하기 전에 각 분기를 독립적으로 탐색할 수 있습니다. 분기 지점까지 동일한 상위 기록을 공유하므로, Agent는 정식 대화 기록을 훼손하지 않고 시나리오별 결과를 비교할 수 있습니다.

## 분기를 사용해야 하는 경우

- **병렬 탐색**: 여러 전문 Agent를 동일한 기본 맥락의 개별 분기에서 실행하고 결과 비교
- **가정 분석**: 공유된 대화 루트에서 나온 대체 추천 평가
- **A/B 비교**: 두 가지 후보 응답을 캡처하고 나중에 모두 검색하여 채택할 응답 선택
- **예측 실행**: Agent가 다단계 계획을 분기에서 시도하고 실패하면 해당 분기 폐기

## AgentCore Memory에서 분기가 작동하는 방식

- 분기는 분기가 갈라지는 이벤트인 `rootEventId`에 고정됩니다.
- 각 분기는 세션 내에서 고유한 `name`을 가집니다.
- `fork_conversation(root_event_id, branch_name, messages)`는 분기를 시작하고, `add_turns(..., branch={"name": ...})`는 분기를 계속합니다.
- `list_branches()`는 세션의 모든 분기를 반환하고, `list_events(branch_name=...)`는 검색 범위를 하나의 분기로 한정합니다.
- 장기 메모리 추출은 구성된 전략에 따라 분기 내 이벤트 전체에서 실행됩니다.

## 제공되는 샘플 노트북

| 사용 사례                                                 | 설명                                                                                                                | 노트북                                                                                                                                                   |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 대체 일정을 활용한 여행 계획(단일 Agent)                  | 세션을 여러 일정 분기로 나누고 나란히 비교하는 여행 계획 Agent                                                     | [travel-planning-agent-with-memory-branching.ipynb](./travel-planning-agent-with-memory-branching.ipynb)                                                 |
| Multi-Agent 병렬 실행(Multi-Agent)                        | 전문 Agent가 공유 루트에서 갈라진 분기에서 병렬로 실행된 후 조정 Agent를 통해 결과 병합                             | [multi-agent-parallel-execution-with-memory-branching.ipynb](./multi-agent-parallel-execution-with-memory-branching.ipynb)                               |

분기 흐름을 시각적으로 살펴보려면 이 폴더의 `architecture.png`를 참조하세요.

## 사전 요구 사항

- AgentCore Memory 리소스(한 번 생성한 후 실행 간에 재사용)
- `bedrock-agentcore` 및 `bedrock-agentcore-control` 권한이 있는 AWS 자격 증명
- Python 3.10+ 및 `requirements.txt`의 종속성

## 시작하기

1. 위 노트북 중 하나를 엽니다.
2. 종속성을 설치합니다: `pip install -r requirements.txt`
3. 셀을 순서대로 실행합니다. 노트북은 메모리 리소스를 생성하고 기본 대화를 실행한 다음, 하나 이상의 분기를 만들고 각 분기를 검사합니다.

## 관련 튜토리얼

- [단기 메모리](../01-short-term-memory/) - 이벤트 저장 기본 사항
- [장기 메모리](../02-long-term-memory/) - 분기 전반에서 실행되는 메모리 전략
