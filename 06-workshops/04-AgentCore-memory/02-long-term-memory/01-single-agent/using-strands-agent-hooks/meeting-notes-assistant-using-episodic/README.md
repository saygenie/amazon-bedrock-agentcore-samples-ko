# AgentCore Memory: Episodic Memory 전략

| 정보                | 세부 정보                                                    |
|:--------------------|:-------------------------------------------------------------|
| 튜토리얼 유형       | 장기 Episodic                                                |
| Agent 유형          | 회의록 도우미                                                |
| Agent 프레임워크    | Strands Agents                                               |
| LLM 모델            | Anthropic Claude Haiku 4.5                                   |
| 튜토리얼 구성 요소  | Reflection 및 Hook을 사용하는 AgentCore Episodic Memory      |
| 예제 난이도         | 중급                                                         |

## 개요

Episodic Memory는 사용자와 시스템 간 상호 작용에서 의미 있는 부분을 캡처하여 애플리케이션이 관련성 높은 맥락에 집중해 회상할 수 있도록 합니다. 모든 원시 이벤트를 저장하는 대신 중요한 순간을 식별하고, 간결한 레코드로 요약하며, 불필요한 정보 없이 핵심 내용을 검색할 수 있도록 구성합니다.

**Reflection**은 과거 에피소드를 분석하여 인사이트, 패턴, 상위 수준의 결론을 도출함으로써 episodic 레코드를 확장합니다. 원시 경험을 애플리케이션에서 즉시 활용할 수 있는 지침으로 전환합니다.

## Episodic Memory란?

Episodic Memory는 다음 기능을 제공합니다.

- **에피소드 감지**: 의미 있는 상호 작용 시퀀스가 완료되는 시점을 자동 식별
- **구조화된 캡처**: 상황, 의도, 평가, 근거, 에피소드 수준의 reflection 기록
- **에피소드 간 학습**: 여러 에피소드의 패턴을 식별하는 reflection 생성
- **맥락 기반 검색**: Agent가 과거 경험에서 학습하고 동일한 실수를 반복하지 않도록 지원

## 다른 전략과 Episodic Memory의 차이점

| 전략 | 중점 사항 | 적합한 용도 |
|----------|-------|----------|
| **Semantic** | 사실과 지식 | 정적 정보 검색 |
| **User Preference** | 사용자 설정 및 선호도 | 개인화 |
| **Summary** | 대화 요약 | 긴 대화의 맥락 |
| **Episodic** | 상호 작용 시퀀스 + reflection | 경험을 통한 학습 |

Episodic Memory에는 다음과 같은 고유한 특징이 있습니다.
1. 단순한 사실뿐 아니라 작업의 **시퀀스**를 캡처합니다.
2. 에피소드 전반의 패턴을 식별하는 **reflection**을 생성합니다.
3. Agent가 특정 접근 방식이 성공하거나 실패한 **이유**를 이해하도록 돕습니다.

## Episodic Memory를 사용해야 하는 경우

다음과 같은 사용 사례에 적합합니다.

- **회의 도우미**: 여러 회의에 걸쳐 결정 사항, 작업 항목, 후속 조치 추적
- **고객 지원 대화**: 성공적인 해결 패턴에서 학습
- **Agent 기반 워크플로**: 가장 효과적인 도구 조합 기억
- **개인 생산성 도구**: 시간에 따른 사용자 작업 패턴에 적응
- **프로젝트 관리**: 반복되는 방해 요소와 성공적인 전략 식별

## 전략 단계

Episodic Memory 전략은 세 단계로 구성됩니다.

1. **추출**: 진행 중인 에피소드를 분석하고 완료 여부를 판단합니다.
2. **통합**: 완료되면 추출 결과를 하나의 에피소드로 결합합니다.
3. **Reflection**: 여러 에피소드에 걸친 인사이트를 생성합니다.

## Namespace 구성

에피소드와 reflection은 구성 가능한 namespace에 저장됩니다.

```python
# Actor 수준에 episode 저장(대부분의 사용 사례에 권장)
"namespaceTemplates": ["meetings/actor/{actorId}/episodes"]

# Reflection은 episodic namespace와 같거나 그 접두사여야 함
"reflectionConfiguration": {
    "namespaceTemplates": ["meetings/actor/{actorId}"]  # Episode namespace의 접두사
}
```

**중요**: Reflection namespace는 episodic namespace와 동일하거나 그 접두사여야 합니다. 예를 들어 에피소드가 `meetings/actor/{actorId}/episodes`에 있으면 reflection은 접두사인 `meetings/actor/{actorId}`에 있어야 합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Meeting Notes Assistant                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │  Meeting     │     │              Strands Agent                        │  │
│  │ Participant  │────▶│  ┌─────────────────────────────────────────────┐  │  │
│  │              │     │  │           System Prompt                     │  │  │
│  │  "Let's      │     │  │  "You are a meeting assistant that tracks   │  │  │
│  │  discuss     │     │  │   decisions and action items..."            │  │  │
│  │  Q3 goals"   │     │  └─────────────────────────────────────────────┘  │  │
│  └──────────────┘     │                      │                            │  │
│                       │                      ▼                            │  │
│                       │  ┌─────────────────────────────────────────────┐  │  │
│                       │  │         EpisodicMemoryHooks                 │  │  │
│                       │  │  ┌───────────────┐  ┌───────────────────┐   │  │  │
│                       │  │  │ MessageAdded  │  │ AfterInvocation   │   │  │  │
│                       │  │  │    Hook       │  │      Hook         │   │  │  │
│                       │  │  │ (retrieve)    │  │ (save events)     │   │  │  │
│                       │  │  └───────┬───────┘  └─────────┬─────────┘   │  │  │
│                       │  └──────────┼────────────────────┼─────────────┘  │  │
│                       │             │                    │                │  │
│                       │  ┌──────────┴────────────────────┴─────────────┐  │  │
│                       │  │              Tools                          │  │  │
│                       │  │  capture_action | identify_decision |       │  │  │
│                       │  │  summarize_discussion | track_followup      │  │  │
│                       │  └─────────────────────────────────────────────┘  │  │
│                       └──────────────────────────────────────────────────┘  │
│                                          │                                   │
│                                          ▼                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentCore Memory Service                            │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                   Episodic Strategy                              │  │  │
│  │  │                                                                  │  │  │
│  │  │   ┌──────────────┐   ┌───────────────┐   ┌─────────────────┐   │  │  │
│  │  │   │  Extraction  │──▶│ Consolidation │──▶│   Reflection    │   │  │  │
│  │  │   │              │   │               │   │                 │   │  │  │
│  │  │   │ Detect when  │   │ Combine into  │   │ Generate cross- │   │  │  │
│  │  │   │ meeting ends │   │ single record │   │ meeting insights│   │  │  │
│  │  │   └──────────────┘   └───────────────┘   └─────────────────┘   │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────┐  ┌─────────────────────────────────┐ │  │
│  │  │        Episodes             │  │         Reflections             │ │  │
│  │  │ /meetings/actor/{id}/episodes│  │/meetings/actor/{id}/reflections │ │  │
│  │  │                             │  │                                 │ │  │
│  │  │  • Meeting purpose          │  │  • Effective meeting patterns   │ │  │
│  │  │  • Key decisions made       │  │  • Action item completion rate  │ │  │
│  │  │  • Action items assigned    │  │  • Participant preferences      │ │  │
│  │  │  • Follow-up status         │  │  • Common blockers              │ │  │
│  │  └─────────────────────────────┘  └─────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Data Flow:
1. Meeting participant discusses topics
2. MessageAdded hook retrieves relevant past meeting episodes & reflections
3. Agent processes discussion with historical context
4. Agent uses tools (capture_action, identify_decision, summarize_discussion, track_followup)
5. AfterInvocation hook saves interaction as event
6. AgentCore extracts episodes when meeting completes (~1 min)
7. Reflections generated across multiple meetings (background)
```

## 제공되는 샘플 노트북

| 프레임워크 | 사용 사례 | 설명 | 노트북 |
|-----------|----------|-------------|----------|
| Strands Agents | 회의록 | 결정 사항과 작업 항목을 추적하고 과거 회의에서 학습하는 회의 도우미 | [meeting-notes-assistant.ipynb](./meeting-notes-assistant.ipynb) |

## 시작하기

1. 이 폴더로 이동합니다.
2. 필수 패키지를 설치합니다: `pip install -r requirements.txt`
3. Jupyter Notebook을 열고 단계별 구현을 따라 진행합니다.

## 샘플 Prompt

다음 회의 시나리오를 사용하여 Episodic Memory 학습을 테스트해 보세요.

### 1. 이전 결정 사항 후속 조치
**Prompt**: "Let's revisit the Q3 marketing budget we discussed last week"

**예상 동작**: Agent가 예산 논의가 있었던 과거 에피소드를 회상하고 이전 결정 사항을 검색하여 해당 회의의 맥락을 참조합니다.

### 2. 작업 항목 확인
**Prompt**: "Did we assign someone to handle the website redesign?"

**예상 동작**: Agent가 웹사이트 재설계를 논의했던 과거 에피소드를 검색하고 배정된 작업 항목과 담당자를 식별합니다.

### 3. 반복되는 회의 패턴
**Prompt**: "We need to plan the weekly sprint review meeting"

**예상 동작**: Agent가 과거 스프린트 검토에서 학습한 패턴을 적용합니다(예: "Team prefers 30-min format" 또는 "Always include demo time").

### 4. 맥락이 있는 새 회의
**Prompt**: "Let's have a quick sync about the product launch timeline. We need to finalize dates."

**예상 동작**: 도구를 사용해 결정 사항을 캡처하고, 작업 항목을 식별하며, 후속 조치를 추적하는 다단계 회의 진행을 지원합니다.

### 5. 참가자 선호도 인식
**Prompt**: "Sarah wants to discuss the technical architecture for the new feature"

**예상 동작**: Agent가 과거 회의에서 Sarah의 선호도를 인식합니다(예: "Sarah prefers detailed diagrams" 또는 "Technical meetings with Sarah typically need 1 hour").

### 6. 새로운 주제
**Prompt**: "We need to discuss the company's sustainability initiative for the first time"

**예상 동작**: Agent가 과거 에피소드가 없는 새로운 주제임을 인식하고 일반적인 회의 구조를 제공하며, 나중에 참조할 수 있도록 결정 사항과 작업 항목을 캡처합니다.

## 주요 개념

### 에피소드와 Reflection 비교

**에피소드**는 개별 상호 작용 시퀀스를 캡처합니다.
- 결정이 이루어진 프로젝트 계획 회의
- 작업 항목이 배정된 스프린트 회고
- 구체적인 결과가 나온 예산 검토 논의

**Reflection**은 에피소드 전반의 패턴을 분석합니다.
- 팀별로 가장 효과적인 회의 형식
- 반복적으로 나타나는 공통 방해 요소
- 팀원별 작업 항목 완료율
- 참가자의 커뮤니케이션 선호도

### 검색 모범 사례

1. **의도별 쿼리**: 에피소드는 "intent"로, reflection은 "use case"로 인덱싱됩니다.
2. **도구 결과 포함**: 최적의 추출을 위해 이벤트를 생성할 때 `TOOL` 결과를 포함합니다.
3. **Reflection을 선제적으로 사용**: 알려진 문제를 피하도록 작업 시작 시 reflection을 쿼리합니다.
4. **성공한 에피소드 선형화**: 성공한 에피소드의 turn을 제공하여 Agent가 집중하도록 합니다.

## 다음 단계

Episodic Memory를 익힌 후 다음 내용을 살펴보세요.
- 포괄적인 Agent 경험을 위해 Semantic Memory와 결합
- 팀 학습을 위한 Agent 간 reflection 공유 구현
- 에피소드 감지를 개선하는 피드백 루프 구축

## 문제 해결

### 에피소드가 나타나지 않음
**문제**: 테스트를 실행한 후 에피소드를 찾을 수 없음

**해결 방법**: 대화가 완료된 후 에피소드 추출에 약 1분이 걸립니다. 기다린 후 검색을 다시 시도하세요. 에피소드는 백그라운드에서 비동기식으로 추출됩니다.

### 권한 오류
**문제**: 메모리를 생성하거나 이벤트를 저장할 때 `AccessDeniedException` 발생

**해결 방법**: AWS 자격 증명에 필요한 권한이 있는지 확인하세요.
- 정책: `BedrockAgentCoreFullAccess`(관리형 정책)
- 또는 `bedrock-agentcore:*` 권한이 있는 사용자 지정 정책

### 모델 액세스 오류
**문제**: Claude Haiku 4.5 모델에 액세스할 수 없음

**해결 방법**: AWS Bedrock 콘솔에서 모델 액세스를 활성화하세요.
1. AWS Console → Bedrock → Model access로 이동합니다.
2. "Anthropic Claude Haiku 4.5" 액세스를 요청합니다.
3. 승인을 기다립니다(표준 모델은 일반적으로 즉시 승인됨).

### Reflection 결과가 비어 있음
**문제**: Reflection namespace에서 결과가 반환되지 않음

**해결 방법**: 여러 에피소드가 수집된 후 reflection이 생성됩니다. 다양한 시나리오로 회의 세션을 추가 실행하여 에피소드를 축적하세요. Reflection은 백그라운드에서 생성되며 몇 분 정도 걸릴 수 있습니다.

### "Already Exists" 오류로 메모리 생성 실패
**문제**: 같은 이름의 Memory 리소스가 이미 존재함

**해결 방법**: 코드는 기존 메모리를 재사용하여 이 상황을 자동으로 처리합니다. 처음부터 다시 시작하려면 `client.delete_memory_and_wait(memory_id=memory_id)`를 사용해 기존 메모리를 먼저 삭제하세요.

## 정리

튜토리얼을 완료한 후 지속적인 요금이 발생하지 않도록 Memory 리소스를 삭제하세요.

```python
try:
    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"✅ Deleted memory resource: {memory_id}")
except Exception as e:
    print(f"❌ Error deleting memory: {e}")
```

**참고**: 이 작업은 해당 Memory 리소스에 저장된 모든 에피소드와 reflection을 영구적으로 삭제합니다. 보관할 데이터가 있다면 삭제 전에 내보내세요.

**비용 고려 사항**: AgentCore Memory 요금은 저장 및 검색을 기준으로 부과됩니다. 개발/테스트 Memory 리소스를 정기적으로 정리하면 비용을 관리하는 데 도움이 됩니다.
