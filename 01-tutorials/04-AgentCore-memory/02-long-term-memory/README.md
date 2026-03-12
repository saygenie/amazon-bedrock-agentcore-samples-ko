# AgentCore Memory: 장기 메모리 전략(Long-Term Memory Strategies)

## 개요

Amazon Bedrock AgentCore의 장기 메모리는 AI 에이전트가 여러 대화와 세션에 걸쳐 영속적인 정보를 유지할 수 있게 합니다. 즉각적인 컨텍스트에 초점을 맞추는 단기 메모리와 달리, 장기 메모리는 의미 있는 정보를 추출, 처리, 저장하여 향후 상호작용에서 검색하고 적용할 수 있도록 하며, 진정으로 개인화되고 지능적인 에이전트 경험을 만듭니다.

## 장기 메모리란?

장기 메모리는 다음을 제공합니다:

- **세션 간 영속성**: 개별 대화를 넘어 유지되는 정보
- **지능적 추출**: 중요한 사실, 선호도, 패턴의 자동 식별 및 저장
- **시맨틱 이해**: 자연어 검색을 가능하게 하는 벡터 기반 저장
- **개인화**: 맞춤형 경험을 가능하게 하는 사용자별 정보
- **지식 축적**: 시간이 지남에 따른 지속적인 학습 및 정보 구축

## 장기 메모리 전략 작동 방식

장기 메모리는 어떤 정보를 추출하고 어떻게 처리할지를 정의하는 **메모리 전략**을 통해 작동합니다. 시스템은 백그라운드에서 자동으로 작동합니다:

### 처리 파이프라인

1. **대화 분석**: 저장된 대화가 구성된 전략에 따라 분석됩니다
2. **정보 추출**: AI 모델을 사용하여 중요한 데이터(사실, 선호도, 요약)가 추출됩니다
3. **구조화된 저장**: 추출된 정보가 효율적인 검색을 위해 네임스페이스로 구성됩니다
4. **시맨틱 인덱싱**: 자연어 검색 기능을 위해 정보가 벡터화됩니다
5. **통합**: 유사한 정보가 시간이 지남에 따라 병합되고 정제됩니다

**처리 시간**: 대화가 저장된 후 일반적으로 약 1분이 소요되며, 추가 코드가 필요하지 않습니다.

### 내부 동작

- **AI 기반 추출**: 파운데이션 모델을 사용하여 관련 정보를 이해하고 추출합니다
- **벡터 임베딩**: 유사도 기반 검색을 위한 시맨틱 표현을 생성합니다
- **네임스페이스 구성**: 구성 가능한 경로형 계층 구조를 사용하여 정보를 구조화합니다
- **자동 통합**: 중복을 방지하기 위해 유사한 정보를 병합하고 정제합니다
- **점진적 학습**: 대화 패턴을 기반으로 추출 품질을 지속적으로 개선합니다

## 장기 메모리 전략 유형

AgentCore Memory는 장기 정보 저장을 위한 네 가지 고유한 전략 유형을 지원합니다:

### 1. 시맨틱 메모리 전략(Semantic Memory Strategy)

유사도 검색을 위해 벡터 임베딩을 사용하여 대화에서 추출된 사실 정보를 저장합니다.

```python
{
    "semanticMemoryStrategy": {
        "name": "FactExtractor",
        "description": "Extracts and stores factual information",
        "namespaces": ["support/user/{actorId}/facts/"]
    }
}
```

**적합한 용도**: 자연어 쿼리를 통해 검색해야 하는 제품 정보, 기술 세부사항 또는 기타 사실 데이터를 저장하는 데 적합합니다.

### 2. 요약 메모리 전략(Summary Memory Strategy)

긴 상호작용의 컨텍스트를 보존하기 위해 대화 요약을 생성하고 유지합니다.

```python
{
    "summaryMemoryStrategy": {
        "name": "ConversationSummary",
        "description": "Maintains conversation summaries",
        "namespaces": ["support/summaries/{sessionId}/"]
    }
}
```

**적합한 용도**: 후속 대화에서 컨텍스트를 제공하고 긴 상호작용 간의 연속성을 유지하는 데 적합합니다.

### 3. 사용자 선호도 메모리 전략(User Preference Memory Strategy)

상호작용을 개인화하기 위해 사용자별 선호도 및 설정을 추적합니다.

```python
{
    "userPreferenceMemoryStrategy": {
        "name": "UserPreferences",
        "description": "Captures user preferences and settings",
        "namespaces": ["support/user/{actorId}/preferences"/]
    }
}
```

**적합한 용도**: 커뮤니케이션 선호도, 제품 선호도 또는 기타 사용자별 설정을 저장하는 데 적합합니다.

### 4. 커스텀 메모리 전략(Custom Memory Strategy)

추출 및 통합을 위한 프롬프트 커스터마이징을 허용하여 특수한 사용 사례에 대한 유연성을 제공합니다.

```python
{
    "customMemoryStrategy": {
        "name": "CustomExtractor",
        "description": "Custom memory extraction logic",
        "namespaces": ["user/custom/{actorId}/"],
        "configuration": {
            "semanticOverride": { # Summary 또는 User Preferences도 오버라이드할 수 있습니다.
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

**적합한 용도**: 표준 전략에 맞지 않는 특수한 추출 요구사항에 적합합니다.

## 네임스페이스 이해하기

네임스페이스는 경로형 구조를 사용하여 전략 내에서 메모리 레코드를 구성합니다. 동적으로 대체되는 변수를 포함할 수 있습니다:

- `support/facts/{sessionId}`: 세션별로 사실을 구성
- `user/{actorId}/preferences`: 액터 ID별로 사용자 선호도를 저장
- `meetings/{memoryId}/summaries/{sessionId}`: 메모리별로 요약을 그룹화

`{actorId}`, `{sessionId}`, `{memoryId}` 변수는 메모리를 저장하고 검색할 때 실제 값으로 자동 대체됩니다.

## 예제: 실제 작동 방식

사용자가 고객 지원 에이전트에게 다음과 같이 말한다고 가정해보세요: _"저는 채식주의자이고 이탈리안 요리를 정말 좋아합니다. 오후 6시 이후에는 전화하지 말아 주세요."_

이 대화를 저장하면 구성된 전략이 자동으로 다음을 수행합니다:

**시맨틱 전략**이 추출하는 내용:

- "사용자는 채식주의자이다"
- "사용자는 이탈리안 요리를 좋아한다"

**사용자 선호도 전략**이 캡처하는 내용:

- "식이 선호도: 채식주의자"
- "요리 선호도: 이탈리안"
- "연락 선호도: 오후 6시 이후 전화 금지"

**요약 전략**이 생성하는 내용:

- "사용자가 식이 제한사항과 연락 선호도에 대해 논의했다"

이 모든 것이 백그라운드에서 자동으로 이루어집니다 - 대화를 저장하기만 하면 전략이 나머지를 처리합니다.

## 사용 가능한 샘플 노트북

다음 실습 예제를 통해 장기 메모리 전략 구현을 학습하세요:

| 통합 방법                 | 사용 사례           | 설명                                                                                    | 노트북                                                                                                         | 아키텍처                                                                                   |
| ------------------------- | ------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Strands Agent Hooks       | 고객 지원           | 시맨틱 및 선호도 메모리 전략을 갖춘 완전한 지원 시스템                                  | [customer-support.ipynb](./01-single-agent/using-strands-agent-hooks/customer-support/customer-support.ipynb)  | [보기](./01-single-agent/using-strands-agent-hooks/customer-support/architecture.png)      |
| Strands Agent Hooks       | 수학 어시스턴트     | 사용자 학습 선호도와 진행 상황을 기억하는 수학 튜터 어시스턴트                           | [math-assistant.ipynb](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb) | [보기](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/architecture.png) |
| LangGraph Agent Hooks     | 영양 어시스턴트     | 사용자 식이 선호도와 건강 목표를 저장하여 개인화된 추천을 제공하는 영양 어드바이저       | [nutrition-assistant-with-user-preference-saving.ipynb](./01-single-agent/using-langgraph-agent-hooks/nutrition-assistant-with-user-preference-saving.ipynb) | [보기](./01-single-agent/using-langgraph-agent-hooks/architecture.png) |
| Strands Agent Memory Tool | 요리 어시스턴트     | 식이 선호도와 요리 스타일을 학습하는 음식 추천 에이전트                                  | [culinary-assistant.ipynb](./01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb)         | [보기](./01-single-agent/using-strands-agent-memory-tool/architecture.png)                 |
| Multi-Agent               | 에이전트 협업       | 여러 에이전트가 장기 메모리 전략을 공유하고 활용하는 여행 어시스턴트                     | [travel-booking-assistant.ipynb](./02-multi-agent/with-strands-agent/travel-booking-assistant.ipynb)           | [보기](./02-multi-agent/with-strands-agent/architecture.png)                               |

## 시작하기

1. 사용 사례에 맞는 샘플을 선택하세요
2. 샘플 폴더로 이동하세요
3. 요구사항 설치: `pip install -r requirements.txt`
4. Jupyter 노트북을 열고 단계별 구현을 따라하세요

## 모범 사례

1. **전략 선택**: 사용 사례 요구사항에 따라 적절한 전략 선택
2. **네임스페이스 설계**: 효율적인 정보 구성을 위한 네임스페이스 계층 구조 계획
3. **추출 튜닝**: 도메인별 정보에 맞게 추출 프롬프트 커스터마이징
4. **성능 모니터링**: 메모리 추출 품질 및 검색 성능 추적
5. **개인정보 보호 고려**: 적절한 데이터 보존 및 개인정보 보호 정책 구현

## 다음 단계

장기 메모리 전략을 마스터한 후 다음을 탐색하세요:

- 포괄적인 에이전트 경험을 위한 단기 메모리와 장기 메모리의 결합
- 고급 커스텀 전략 구성
- 멀티 에이전트 메모리 공유 패턴
- 프로덕션 배포 고려사항
