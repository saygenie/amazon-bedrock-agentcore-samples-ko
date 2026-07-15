# Amazon Bedrock AgentCore Memory

## 개요

메모리는 Agent 지능의 핵심 구성 요소입니다. Large Language Model(LLM)은 대화 간에 지속되는 메모리가 없습니다. Amazon Bedrock AgentCore Memory는 AI Agent가 세션 전반에서 관련 맥락을 유지하고, 개인화된 경험을 제공하며, 시간이 지남에 따라 학습할 수 있도록 지원하는 관리형 서비스로 이 문제를 해결합니다.

## 주요 기능

- **핵심 인프라**: 암호화와 관찰성이 기본 제공되는 serverless 구성
- **이벤트 저장**: 분기 기능을 지원하는 원시 이벤트 저장(대화 기록/체크포인트)
- **전략 관리**: 구성 가능한 추출 전략(SEMANTIC, SUMMARY, USER_PREFERENCES, EPISODIC, SELF_MANAGED)
- **메모리 레코드 추출**: 구성된 전략에 따라 사실, 선호도, 요약을 자동으로 추출
- **시맨틱 검색**: 자연어 쿼리를 사용해 관련 메모리를 벡터 기반으로 검색

## AgentCore Memory 작동 방식

![상위 수준 워크플로](./images/high_level_memory.png)

AgentCore Memory는 두 가지 수준으로 작동합니다.

### 단기 메모리

단일 상호 작용이나 밀접하게 관련된 세션 내에서 연속성을 제공하는 즉각적인 대화 맥락과 세션 기반 정보입니다.

### 장기 메모리

여러 대화에서 추출하고 저장하는 지속적인 정보입니다. 시간이 지남에 따라 개인화된 경험을 제공할 수 있도록 사실, 선호도, 요약 등을 포함합니다.

## 메모리 아키텍처

1. **대화 저장**: 즉시 액세스할 수 있도록 전체 대화를 원시 형태로 저장합니다.
2. **전략 처리**: 구성된 전략이 백그라운드에서 대화를 자동으로 분석합니다.
3. **정보 추출**: 전략 유형에 따라 중요한 데이터를 추출합니다(일반적으로 약 1분 소요).
4. **체계적인 저장**: 효율적으로 검색할 수 있도록 추출한 정보를 구조화된 namespace에 저장합니다.
5. **시맨틱 검색**: 자연어 쿼리와 벡터 유사도를 사용해 관련 메모리를 검색합니다.

## Memory 전략 유형

AgentCore Memory는 다섯 가지 전략 유형을 지원합니다.

- **Semantic Memory**: 유사도 검색을 위해 벡터 임베딩을 사용하여 사실 정보를 저장합니다.
- **Summary Memory**: 맥락을 보존하기 위해 대화 요약을 생성하고 유지합니다.
- **User Preference Memory**: 사용자별 선호도와 설정을 추적합니다.
- **Episodic Memory**: 에피소드 자동 감지, 통합, reflection 생성을 통해 의미 있는 상호 작용 시퀀스를 캡처합니다.
- **Self-managed Memory**: 추출 및 통합 로직을 사용자 지정할 수 있습니다.

## 폴더 구조

```
04-AgentCore-memory/
├── 01-short-term-memory/          # 세션 기반 메모리 및 컨텍스트 관리
│   ├── 01-single-agent/
│   │   ├── with-strands-agent/    # Strands SDK 예제 + checkpointing
│   │   ├── with-langgraph-agent/  # LangGraph 예제 + checkpointing + human-in-the-loop
│   │   └── with-llamaindex-agent/ # 여러 도메인의 LlamaIndex 예제
│   └── 02-multi-agent/
│       └── with-strands-agent/    # Multi-agent 여행 계획
├── 02-long-term-memory/           # 대화 간 영구 메모리
│   ├── 01-single-agent/
│   │   ├── using-strands-agent-hooks/         # Strands lifecycle hook 통합
│   │   ├── using-strands-agent-memory-tool/   # Strands memory tool 통합
│   │   ├── using-langgraph-agent-hooks/       # LangGraph hook 통합
│   │   └── using-llamaindex-agent-memory-tool/ # LlamaIndex memory tool 통합
│   └── 02-multi-agent/
│       └── with-strands-agent/    # Multi-agent 여행 예약 + 의료
├── 03-advanced-patterns/          # 고급 통합 및 도구
│   ├── 01-guardrails-integration/ # Amazon Bedrock Guardrails를 사용하는 Memory
│   ├── 02-memory-runtime-integration/          # Memory + AgentCore Runtime
│   ├── 03-memory-identity-runtime-integration/ # Memory + Identity + Runtime
│   ├── 04-memory-browser/         # Memory store 탐색용 Web UI
│   └── 05-memory-streaming/       # Streaming memory record 추출
├── 04-memory-branching/           # 대화 분기 및 병렬 실행
└── 05-memory-security-patterns/   # IAM policy 및 Cognito Identity 통합
    ├── 01-memory-iam-policies/
    └── 02-memory-iam-cognito-identities/
```

## 샘플 노트북

### 단기 메모리

| 프레임워크 | Agent 유형 | 사용 사례                         | 노트북                                                                                                                                                           |
| ---------- | ---------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strands    | 단일       | 개인 Agent                        | [personal-agent.ipynb](./01-short-term-memory/01-single-agent/with-strands-agent/personal-agent.ipynb)                                                           |
| Strands    | 단일       | 개인 Agent(Memory Manager)        | [personal-agent-memory-manager.ipynb](./01-short-term-memory/01-single-agent/with-strands-agent/personal-agent-memory-manager.ipynb)                             |
| LangGraph  | 단일       | 개인 피트니스 코치                | [personal-fitness-coach.ipynb](./01-short-term-memory/01-single-agent/with-langgraph-agent/personal-fitness-coach.ipynb)                                         |
| LangGraph  | 단일       | 체크포인트를 사용하는 수학 Agent  | [math-agent-with-checkpointing.ipynb](./01-short-term-memory/01-single-agent/with-langgraph-agent/math-agent-with-checkpointing.ipynb)                           |
| LangGraph  | 단일       | 지원 Agent(Human-in-the-Loop)     | [support-agent-human-in-the-loop.ipynb](./01-short-term-memory/01-single-agent/with-langgraph-agent/support-agent-human-in-the-loop.ipynb)                       |
| LlamaIndex | 단일       | 학술 연구 도우미                  | [academic-research-assistant.ipynb](./01-short-term-memory/01-single-agent/with-llamaindex-agent/academic-research-assistant-short-term-memory-tutorial.ipynb)   |
| LlamaIndex | 단일       | 투자 포트폴리오 자문              | [investment-portfolio-advisor.ipynb](./01-short-term-memory/01-single-agent/with-llamaindex-agent/investment-portfolio-advisor-short-term-memory-tutorial.ipynb) |
| LlamaIndex | 단일       | 법률 문서 분석기                  | [legal-document-analyzer.ipynb](./01-short-term-memory/01-single-agent/with-llamaindex-agent/legal-document-analyzer-short-term-memory-tutorial.ipynb)           |
| LlamaIndex | 단일       | 의학 지식 도우미                  | [medical-knowledge-assistant.ipynb](./01-short-term-memory/01-single-agent/with-llamaindex-agent/medical-knowledge-assistant-short-term-memory-tutorial.ipynb)   |
| Strands    | 다중       | 여행 계획 Agent                   | [travel-planning-agent.ipynb](./01-short-term-memory/02-multi-agent/with-strands-agent/travel-planning-agent.ipynb)                                              |
| Strands    | 다중       | 여행 계획(Memory Manager)         | [travel-planning-agent-memory-manager.ipynb](./01-short-term-memory/02-multi-agent/with-strands-agent/travel-planning-agent-memory-manager.ipynb)                |

### 장기 메모리

| 프레임워크 | Agent 유형 | 통합        | 사용 사례                                     | 노트북                                                                                                                                                                                                       |
| ---------- | ---------- | ----------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Strands    | 단일       | Hooks       | 고객 지원(기본 제공 전략)                    | [customer-support-inbuilt-strategy.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/customer-support/customer-support-inbuilt-strategy.ipynb)                                          |
| Strands    | 단일       | Hooks       | 고객 지원(재정의 전략)                       | [customer-support-override-strategy.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/customer-support/customer-support-override-strategy.ipynb)                                        |
| Strands    | 단일       | Hooks       | 수학 도우미                                  | [math-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb)                                                                           |
| Strands    | 단일       | Hooks       | 회의록(Episodic)                             | [meeting-notes-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/meeting-notes-assistant-using-episodic/meeting-notes-assistant.ipynb)                                        |
| Strands    | 단일       | Hooks       | 요리 도우미(Self-Managed)                    | [agentcore_self_managed_memory_demo.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/culinary-assistant-self-managed-strategy/agentcore_self_managed_memory_demo.ipynb)                |
| Strands    | 단일       | Hooks       | 요리 도우미(Self-Managed + 인용)             | [agentcore_self_managed_memory_demo.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/culinary-assistant-self-managed-strategy-with-citations/agentcore_self_managed_memory_demo.ipynb) |
| Strands    | 단일       | Memory Tool | 요리 도우미                                  | [culinary-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb)                                                                                   |
| Strands    | 단일       | Memory Tool | 디버깅 도우미(Episodic)                      | [debugging_assistant_episodic_memory.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-memory-tool/debugging-agent/debugging_assistant_episodic_memory.ipynb)                                 |
| LangGraph  | 단일       | Hooks       | 영양 도우미(User Preferences)                | [nutrition-assistant-with-user-preference-saving.ipynb](./02-long-term-memory/01-single-agent/using-langgraph-agent-hooks/custom-user-preferences/nutrition-assistant-with-user-preference-saving.ipynb)     |
| LangGraph  | 단일       | Hooks       | 영양 도우미(Episodic)                        | [nutrition-assistant-with-episodic-memory.ipynb](./02-long-term-memory/01-single-agent/using-langgraph-agent-hooks/episodic-memory/nutrition-assistant-with-episodic-memory.ipynb)                           |
| LlamaIndex | 단일       | Memory Tool | 학술 연구 도우미                             | [academic-research-assistant.ipynb](./02-long-term-memory/01-single-agent/using-llamaindex-agent-memory-tool/academic-research-assistant-long-term-memory-tutorial.ipynb)                                    |
| LlamaIndex | 단일       | Memory Tool | 투자 포트폴리오 자문                         | [investment-portfolio-advisor.ipynb](./02-long-term-memory/01-single-agent/using-llamaindex-agent-memory-tool/investment-portfolio-advisor-long-term-memory-tutorial.ipynb)                                  |
| LlamaIndex | 단일       | Memory Tool | 법률 문서 분석기                             | [legal-document-analyzer.ipynb](./02-long-term-memory/01-single-agent/using-llamaindex-agent-memory-tool/legal-document-analyzer-long-term-memory-tutorial.ipynb)                                            |
| LlamaIndex | 단일       | Memory Tool | 의학 지식 도우미                             | [medical-knowledge-assistant.ipynb](./02-long-term-memory/01-single-agent/using-llamaindex-agent-memory-tool/medical-knowledge-assistant-long-term-memory-tutorial.ipynb)                                    |
| Strands    | 다중       | Hooks       | 여행 예약 도우미                             | [travel-booking-assistant.ipynb](./02-long-term-memory/02-multi-agent/with-strands-agent/travel-booking-agent/travel-booking-assistant.ipynb)                                                                |
| Strands    | 다중       | Hooks       | 의료 데이터 도우미(Episodic)                | [healthcare-data-assistant.ipynb](./02-long-term-memory/02-multi-agent/with-strands-agent/healthcare-assistant-using-episodic/healthcare-data-assistant.ipynb)                                               |

### 고급 패턴

| 패턴                        | 설명                                               | 노트북                                                                                                                                               |
| --------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Guardrails 통합             | 메모리와 Amazon Bedrock Guardrails 결합            | [guardrails-memory.ipynb](./03-advanced-patterns/01-guardrails-integration/guardrails-memory.ipynb)                                                  |
| Memory + Runtime            | 메모리와 AgentCore Runtime 통합                    | [runtime_memory_integration.ipynb](./03-advanced-patterns/02-memory-runtime-integration/runtime_memory_integration.ipynb)                            |
| Memory + Identity + Runtime | 메모리, ID 확인, Runtime 통합                      | [runtime_memory_identity_integration.ipynb](./03-advanced-patterns/03-memory-identity-runtime-integration/runtime_memory_identity_integration.ipynb) |
| Memory Browser              | 메모리 저장소를 탐색하고 관리하는 Web UI           | [README](./03-advanced-patterns/04-memory-browser/README.md)                                                                                         |
| Memory Streaming            | 메모리 레코드 추출 결과 스트리밍                   | [memory_record_streaming.ipynb](./03-advanced-patterns/05-memory-streaming/memory_record_streaming.ipynb)                                            |

### Memory 분기

| 사용 사례                                     | 노트북                                                                                                                                         |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Memory 분기를 활용한 여행 계획                | [travel-planning-agent-with-memory-branching.ipynb](./04-memory-branching/travel-planning-agent-with-memory-branching.ipynb)                   |
| 분기를 활용한 Multi-Agent 병렬 실행           | [multi-agent-parallel-execution-with-memory-branching.ipynb](./04-memory-branching/multi-agent-parallel-execution-with-memory-branching.ipynb) |

### Memory 보안 패턴

| 패턴                                   | 노트북                                                                                                                                                                    |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Memory 액세스 제어를 위한 IAM 정책     | [runtime_memory_identity_integration.ipynb](./05-memory-security-patterns/01-memory-iam-policies/runtime_memory_identity_integration.ipynb)                               |
| IAM + Cognito 페더레이션 ID            | [runtime_memory_federated_identity_integration.ipynb](./05-memory-security-patterns/02-memory-iam-cognito-identities/runtime_memory_federated_identity_integration.ipynb) |

## 리소스

- [Amazon Bedrock AgentCore Memory 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)
- [심층 분석 동영상](https://www.youtube.com/live/-N4v6-kJgwA)

## 사전 요구 사항

- Python 3.10 이상
- Amazon Bedrock 액세스 권한이 있는 AWS 계정
- Jupyter Notebook 환경
- 필수 Python 패키지(각 샘플의 `requirements.txt` 파일 참조)
