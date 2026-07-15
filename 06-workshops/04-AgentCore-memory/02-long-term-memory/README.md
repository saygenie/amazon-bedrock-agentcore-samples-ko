# AgentCore Memory: 장기 메모리 전략

## 개요

Amazon Bedrock AgentCore의 장기 메모리를 사용하면 AI Agent가 여러 대화와 세션에 걸쳐 지속적인 정보를 유지할 수 있습니다. 즉각적인 맥락에 중점을 두는 단기 메모리와 달리, 장기 메모리는 향후 상호 작용에서 검색하고 적용할 수 있는 의미 있는 정보를 추출하고 처리하며 저장합니다. 이를 통해 진정으로 개인화되고 지능적인 Agent 경험을 만들 수 있습니다.

## 장기 메모리란?

장기 메모리는 다음 기능을 제공합니다.

- **세션 간 지속성**: 개별 대화가 끝난 뒤에도 유지되는 정보
- **지능형 추출**: 중요한 사실, 선호도, 패턴을 자동으로 식별하고 저장
- **시맨틱 이해**: 자연어 검색을 지원하는 벡터 기반 저장
- **개인화**: 맞춤형 경험을 제공하는 사용자별 정보
- **지식 축적**: 시간에 따른 지속적인 학습과 정보 구축

## 장기 메모리 전략의 작동 방식

장기 메모리는 어떤 정보를 추출하고 어떻게 처리할지 정의하는 **Memory Strategy**를 통해 작동합니다. 시스템은 백그라운드에서 자동으로 작동합니다.

### 처리 파이프라인

1. **대화 분석**: 구성된 전략에 따라 저장된 대화를 분석합니다.
2. **정보 추출**: AI 모델을 사용해 중요한 데이터(사실, 선호도, 요약)를 추출합니다.
3. **구조화된 저장**: 효율적으로 검색할 수 있도록 추출한 정보를 namespace로 구성합니다.
4. **시맨틱 인덱싱**: 자연어 검색 기능을 위해 정보를 벡터화합니다.
5. **통합**: 시간이 지남에 따라 유사한 정보를 병합하고 개선합니다.

**처리 시간**: 일반적으로 대화를 저장한 후 약 1분이 소요되며 추가 코드는 필요하지 않습니다.

### 내부 처리 과정

- **AI 기반 추출**: foundation model을 사용해 관련 정보를 이해하고 추출합니다.
- **벡터 임베딩**: 유사도 기반 검색을 위한 시맨틱 표현을 생성합니다.
- **Namespace 구성**: 구성 가능한 경로 형태의 계층 구조를 사용해 정보를 구조화합니다.
- **자동 통합**: 중복을 방지하도록 유사한 정보를 병합하고 개선합니다.
- **점진적 학습**: 대화 패턴을 기반으로 추출 품질을 지속적으로 개선합니다.

## 장기 메모리 전략 유형

AgentCore Memory는 장기 정보 저장을 위해 서로 다른 네 가지 전략 유형을 지원합니다.

### 1. Semantic Memory 전략

대화에서 추출한 사실 정보를 벡터 임베딩을 사용해 저장하여 유사도 검색에 활용합니다.

```python
{
    "semanticMemoryStrategy": {
        "name": "FactExtractor",
        "description": "Extracts and stores factual information",
        "namespaceTemplates": ["support/user/{actorId}/facts/"]
    }
}
```

**적합한 용도**: 제품 정보, 기술 세부 정보 또는 자연어 쿼리로 검색해야 하는 모든 사실 데이터 저장

### 2. Summary Memory 전략

긴 상호 작용의 맥락을 보존하기 위해 대화 요약을 생성하고 유지합니다.

```python
{
    "summaryMemoryStrategy": {
        "name": "ConversationSummary",
        "description": "Maintains conversation summaries",
        "namespaceTemplates": ["support/summaries/{sessionId}/"]
    }
}
```

**적합한 용도**: 후속 대화에 맥락을 제공하고 긴 상호 작용 전반에서 연속성 유지

### 3. User Preference Memory 전략

상호 작용을 개인화하기 위해 사용자별 선호도와 설정을 추적합니다.

```python
{
    "userPreferenceMemoryStrategy": {
        "name": "UserPreferences",
        "description": "Captures user preferences and settings",
        "namespaceTemplates": ["support/user/{actorId}/preferences/"]
    }
}
```

**적합한 용도**: 커뮤니케이션 선호도, 제품 선호도 또는 모든 사용자별 설정 저장

### 4. Custom Memory 전략

추출 및 통합 prompt를 사용자 지정할 수 있어 특화된 사용 사례에 유연하게 대응합니다.

```python
{
    "customMemoryStrategy": {
        "name": "CustomExtractor",
        "description": "Custom memory extraction logic",
        "namespaceTemplates": ["user/custom/{actorId}/"],
        "configuration": {
            "semanticOverride": { # Summary 또는 User Preferences도 override할 수 있음
                "extraction": {
                    "appendToPrompt": "Extract specific information based on custom criteria",
                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                },
                "consolidation": {
                    "appendToPrompt": "Consolidate extracted information in a specific format",
                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                }
            }
        }
    }
}
```

**적합한 용도**: 표준 전략에 맞지 않는 특수한 추출 요구 사항

## Namespace 이해

Namespace는 경로 형태의 구조를 사용하여 전략 내 메모리 레코드를 구성합니다. 동적으로 치환되는 변수를 포함할 수 있습니다.

- `support/facts/{sessionId}`: 세션별로 사실 구성
- `user/{actorId}/preferences`: actor ID별로 사용자 선호도 저장
- `meetings/{memoryId}/summaries/{sessionId}`: 메모리별로 요약 그룹화

메모리를 저장하고 검색할 때 `{actorId}`, `{sessionId}`, `{memoryId}` 변수는 실제 값으로 자동 치환됩니다.

## 실제 작동 방식 예제

사용자가 고객 지원 Agent에게 다음과 같이 말했다고 가정해 보겠습니다: _"I'm vegetarian and I really enjoy Italian cuisine. Please don't call me after 6 PM."_

이 대화를 저장하면 구성된 전략이 다음 정보를 자동으로 처리합니다.

**Semantic Strategy**가 추출하는 정보:

- "User is vegetarian"
- "User enjoys Italian cuisine"

**User Preference Strategy**가 캡처하는 정보:

- "Dietary preference: vegetarian"
- "Cuisine preference: Italian"
- "Contact preference: no calls after 6 PM"

**Summary Strategy**가 생성하는 정보:

- "User discussed dietary restrictions and contact preferences"

이 모든 과정은 백그라운드에서 자동으로 이루어집니다. 대화만 저장하면 나머지는 전략이 처리합니다.

## 제공되는 샘플 노트북

다음 실습 예제를 통해 장기 메모리 전략 구현 방법을 알아보세요.

| 통합 방법                  | 사용 사례                        | 설명                                                                                                           | 노트북                                                                                                                                                                                              |
| ------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strands Agents Hooks      | 고객 지원(기본 제공)             | 기본 제공 semantic 및 user-preference 전략을 사용하는 지원 Agent                                               | [customer-support-inbuilt-strategy.ipynb](./01-single-agent/using-strands-agent-hooks/customer-support/customer-support-inbuilt-strategy.ipynb)                                                     |
| Strands Agents Hooks      | 고객 지원(재정의)                | 추출/통합 prompt를 재정의한 사용자 지정 전략을 사용하는 지원 Agent                                              | [customer-support-override-strategy.ipynb](./01-single-agent/using-strands-agent-hooks/customer-support/customer-support-override-strategy.ipynb)                                                   |
| Strands Agents Hooks      | 수학 도우미                       | 학습 선호도를 기억하고 STM 이벤트 메타데이터 필터링을 보여 주는 수학 튜터                                      | [math-assistant.ipynb](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb)                                                                                      |
| Strands Agents Hooks      | 회의록(Episodic)                 | 에피소드 감지와 reflection을 위해 Episodic Memory 전략을 사용하는 회의 도우미                                  | [meeting-notes-assistant.ipynb](./01-single-agent/using-strands-agent-hooks/meeting-notes-assistant-using-episodic/meeting-notes-assistant.ipynb)                                                    |
| Strands Agents Hooks      | 요리 도우미(Self-managed, 인용 포함) | 사용자 지정 추출/통합 prompt와 메모리 인용을 사용하는 Self-managed 전략                                    | [agentcore_self_managed_memory_demo.ipynb](./01-single-agent/using-strands-agent-hooks/culinary-assistant-self-managed-strategy-with-citations/agentcore_self_managed_memory_demo.ipynb)            |
| Strands Agents Memory Tool | 요리 도우미                      | Agent가 호출할 수 있는 도구로 메모리 읽기/쓰기를 제공하는 음식 추천 Agent                                      | [culinary-assistant.ipynb](./01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb)                                                                                              |
| Strands Agents Memory Tool | 디버깅 Agent(Episodic)           | 이전 문제 해결 세션의 Episodic Memory를 구축하는 코드 디버깅 도우미                                            | [debugging_assistant_episodic_memory.ipynb](./01-single-agent/using-strands-agent-memory-tool/debugging-agent/debugging_assistant_episodic_memory.ipynb)                                             |
| LangGraph Agent Hooks     | 영양 도우미(선호도)              | user-preference 전략을 통해 식단 선호도를 저장하는 영양 자문                                                   | [nutrition-assistant-with-user-preference-saving.ipynb](./01-single-agent/using-langgraph-agent-hooks/custom-user-preferences/nutrition-assistant-with-user-preference-saving.ipynb)                 |
| LangGraph Agent Hooks     | 영양 도우미(Episodic)            | 식사 세션 회상을 위해 Episodic Memory 전략을 기반으로 구축한 영양 자문                                         | [nutrition-assistant-with-episodic-memory.ipynb](./01-single-agent/using-langgraph-agent-hooks/episodic-memory/nutrition-assistant-with-episodic-memory.ipynb)                                       |
| LlamaIndex Memory Tool    | 장기 메모리 레시피(4종)          | LlamaIndex + 장기 메모리를 보여 주는 학술, 투자, 법률, 의료의 네 가지 도메인 변형                               | [폴더](./01-single-agent/using-llamaindex-agent-memory-tool/)                                                                                                                                       |
| Multi-Agent(Strands Agents) | 의료 분류(Episodic)            | 공유 Episodic Memory를 사용해 여러 Agent가 환자 분류에 협업                                                    | [healthcare-data-assistant.ipynb](./02-multi-agent/with-strands-agent/healthcare-assistant-using-episodic/healthcare-data-assistant.ipynb)                                                           |
| Multi-Agent(Strands Agents) | 여행 예약                       | 여러 Agent가 장기 메모리를 공유하는 여행 도우미                                                                | [travel-booking-assistant.ipynb](./02-multi-agent/with-strands-agent/travel-booking-agent/travel-booking-assistant.ipynb)                                                                            |

## 시작하기

1. 사용 사례에 맞는 샘플을 선택합니다.
2. 샘플 폴더로 이동합니다.
3. 필수 패키지를 설치합니다: `pip install -r requirements.txt`
4. Jupyter Notebook을 열고 단계별 구현을 따라 진행합니다.

## 모범 사례

1. **전략 선택**: 사용 사례 요구 사항에 따라 적절한 전략을 선택합니다.
2. **Namespace 설계**: 정보를 효율적으로 구성하도록 namespace 계층 구조를 계획합니다.
3. **추출 튜닝**: 도메인별 정보에 맞게 추출 prompt를 사용자 지정합니다.
4. **성능 모니터링**: 메모리 추출 품질과 검색 성능을 추적합니다.
5. **개인정보 보호 고려 사항**: 적절한 데이터 보존 및 개인정보 보호 정책을 구현합니다.

## 다음 단계

장기 메모리 전략을 익힌 후 다음 내용을 살펴보세요.

- 포괄적인 Agent 경험을 위한 단기 및 장기 메모리 결합
- 고급 사용자 지정 전략 구성
- Multi-Agent 메모리 공유 패턴
- 프로덕션 배포 고려 사항
