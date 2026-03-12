# LlamaIndex와 AWS Bedrock AgentCore 메모리 통합

이 프로젝트는 지속적 메모리 기능을 갖춘 엔터프라이즈급 AI 에이전트를 보여주며, LlamaIndex의 ReAct 프레임워크가 AWS Bedrock AgentCore 메모리와 어떻게 원활하게 통합되어 시간이 지남에 따라 학습하고, 적응하며, 진화하는 지능형 시스템을 만드는지 시연합니다. 기존의 상태 비저장(stateless) 에이전트와 달리, 이러한 구현은 세션 간 컨텍스트 인식을 유지하여 정교한 종합적 분석, 교차 참조 기능, 누적 지식 구축을 가능하게 하며 AI 에이전트가 전문 환경에서 작동하는 방식을 혁신합니다.

## 주요 기능

- **네이티브 LlamaIndex 통합**: `agent.run(message, memory=agentcore_memory)`로 직접 메모리 전달
- **도메인별 예제**: 학술 연구, 법률 문서 분석, 의료 지식, 투자 포트폴리오 관리
- **포괄적 테스트**: 예제당 8-10개의 체계적 테스트 케이스 및 예상 결과 검증
- **단기 및 장기 메모리**: 두 메모리 유형의 완전한 커버리지
- **엔터프라이즈 지원**: 프로덕션 환경에 적합한 간단하고 명시적인 API

## 프로젝트 구조

```
├── 01-short-term-memory/
│   ├── academic-research-assistant-short-term-memory-tutorial.ipynb
│   ├── legal-document-analyzer-short-term-memory-tutorial.ipynb
│   ├── medical-knowledge-assistant-short-term-memory-tutorial.ipynb
│   └── investment-portfolio-advisor-short-term-memory-tutorial.ipynb
├── 02-long-term-memory/
│   ├── academic-research-assistant-long-term-memory-tutorial.ipynb
│   ├── legal-document-analyzer-long-term-memory-tutorial.ipynb
│   ├── medical-knowledge-assistant-long-term-memory-tutorial.ipynb
│   └── investment-portfolio-advisor-long-term-memory-tutorial.ipynb
└── requirements.txt
```

## 사용 사례

### 학술 연구 어시스턴트
- **단기 메모리**: 단일 세션 내 논문 분석, 연구 종합
- **장기 메모리**: 크로스 세션 연구 진화, 수개월에 걸친 연구비 제안서 지원
- **메모리 인텔리전스**: 연구 주제, 인용 네트워크, 방법론 진화 추적
- **테스트**: 컨텍스트 추론 및 교차 참조 검증을 포함한 8개 포괄적 테스트

### 법률 문서 분석기
- **단기 메모리**: 계약 분석, 리스크 평가, 컴플라이언스 검토
- **장기 메모리**: 다중 사건 판례 추적, 법률 지식 축적 (12개월 보존)
- **메모리 인텔리전스**: 판례법 데이터베이스 구축, 규제 변경 추적, 고객 이력 유지
- **테스트**: 판례 적용 및 규제 컴플라이언스를 포함한 9개 체계적 테스트

### 의료 지식 어시스턴트
- **단기 메모리**: 환자 상담, 약물 상호작용, 임상 가이드라인
- **장기 메모리**: 장기 환자 케어, 치료 결과, 인구 건강 추세
- **메모리 인텔리전스**: 환자 이력 유지, 치료 효과 추적, 결과로부터 학습
- **테스트**: 임상 추론 및 치료 계획을 포함한 10개 포괄적 테스트

### 투자 포트폴리오 어드바이저
- **단기 메모리**: 고객 프로파일링, 포트폴리오 분석, 투자 추천
- **장기 메모리**: 다분기 성과 추적 (Q1->Q2->Q3->Q4), 시장 인텔리전스, 자산 관리
- **메모리 인텔리전스**: $3.2M->$3.45M 포트폴리오 진화 추적, 시장 타이밍 결정, 논제 적응
- **테스트**: 분기별 성과 기여도 및 다년 투자 여정 분석을 포함한 10개 체계적 테스트

## 시스템 아키텍처

*아키텍처 다이어그램이 여기에 추가될 예정입니다*

## 사전 요구사항

- Python 3.10+
- Bedrock AgentCore 메모리 권한이 있는 AWS 계정
- 적절한 자격 증명으로 구성된 AWS CLI
- Claude 3.7 Sonnet 추론 프로필 접근 권한 (`us.anthropic.claude-3-7-sonnet-20250219-v1:0`)

## 설치

```bash
# Jupyter를 포함한 모든 종속성 설치
pip install -r requirements.txt

# 대안: Jupyter를 별도로 설치
pip install jupyter ipykernel
```

## 빠른 시작

1. **AWS 자격 증명 구성:**
   ```bash
   aws configure
   ```

2. **튜토리얼을 선택하고 노트북 열기:**
   ```bash
   jupyter notebook 01-short-term-memory/academic-research-assistant-short-term-memory-tutorial.ipynb
   ```

3. **포괄적 테스트와 함께 단계별 튜토리얼을 따라가세요**

## 주요 이점

- **명시적 제어**: 숨겨진 자동화 대비 직접 메모리 매개변수
- **쉬운 디버깅**: 백그라운드 훅 대비 가시적 메모리 작업
- **간단한 API**: 복잡한 설정 대비 `agent.run(message, memory=memory)`
- **포괄적 테스트**: 예상 결과와 함께 체계적 검증
- **도메인 전문성**: 일반 예제 대비 특화된 사용 사례

## 테스트 방법론

각 노트북에는 명확한 검증과 함께 **8-10개의 체계적 테스트**가 포함되어 있습니다:

### 테스트 카테고리
- **테스트 1-2: 메모리 저장** - 정보 지속성 및 도구 통합 확인
- **테스트 3-4: 컨텍스트 회상** - 신원, 지표, 상세 정보 검색 검증
- **테스트 5-6: 추론 및 종합** - 교차 참조 기능 및 지식 종합 테스트
- **테스트 7-8: 실제 적용** - 실제 시나리오 검증 (연구비 제안서, 사건 분석)
- **테스트 9-10: 세션 경계** - 메모리 격리 및 크로스 세션 동작 확인

### 검증 접근 방식
- **예상 결과**: 각 테스트에서 비교를 위한 예상 출력 표시
- **성공 기준**: 특정 지표와 함께 명확한 통과/실패 지표
- **점진적 복잡도**: 기본 회상에서 고급 추론까지 테스트 구축
- **에지 케이스 테스트**: 세션 경계, 메모리 제한, 오류 처리

### 테스트 패턴 예시
```python
# 테스트 4: 상세 지표 회상
response = await agent.run("What were the exact accuracy percentages?", memory=memory)
print("결과:", response)
print("예상 결과: Zhang et al - CNNs 95.2%, Johnson et al - BERT 89.1%")
# 사용자가 확인 가능: 응답에 두 정확도 수치가 포함되어 있는지?
```

## 기술 개요

**주요 장기 메모리 구성 요소:**
1. **시맨틱 전략 구성**: 365일 보존의 자동 인사이트 추출을 위한 SemanticStrategy 사용
2. **크로스 세션 지속성**: 동일 actor_id + memory_id, 기간별 다른 session_id로 지식 연속성 확보
3. **커스텀 메모리 검색 도구**: AgentCore의 네이티브 search_long_term_memories()를 LlamaIndex FunctionTool로 래핑
4. **시맨틱 처리 파이프라인**: 대화 이벤트 -> 시맨틱 메모리 변환을 위한 90-120초 대기
5. **동적 세션 관리**: 유연한 세션 처리를 위한 memory.context.session_id 사용

## 메모리 구성

### 단기 메모리
```python
context = AgentCoreMemoryContext(
    actor_id="user-id",
    memory_id=memory_id,
    session_id="session-id",
    namespace="/domain-specific/"
)
agentcore_memory = AgentCoreMemory(context=context)
```

### 장기 메모리 (12개월 보존)
```python
# 시맨틱 전략을 사용한 크로스 세션 지속성
memory = memory_manager.get_or_create_memory(
    name='DomainSpecificLongTerm',
    strategies=[SemanticStrategy(name="domainLongTermMemory")],
    event_expiry_days=365  # 12개월 보존
)

# 지속성을 위한 세션 간 동일 컨텍스트
context = AgentCoreMemoryContext(
    actor_id="advisor-id",      # 세션 간 동일한 액터
    memory_id=memory_id,        # 동일한 메모리 저장소
    session_id="q1-session",    # 상호작용별 다른 세션
    namespace="/domain-specific/"
)
```

### 메모리 인텔리전스 예시
- **투자 어드바이저**: 분기별 성과 추적 (Q1: +8.2% -> Q2: -2.1% -> Q3: 회복)
- **법률 분석기**: 사건 및 규제 변경 전반에 걸친 판례 데이터베이스 유지
- **의료 어시스턴트**: 장기 환자 케어 기록 및 치료 결과 구축
- **연구 어시스턴트**: 수개월에 걸친 연구 주제 및 방법론 인사이트 진화

## 기여

이 프로젝트는 LlamaIndex + AgentCore 메모리 통합의 베스트 프랙티스를 시연합니다. 다음에 대한 기여를 환영합니다:

- 추가 도메인 예제
- 향상된 테스트 방법론
- 성능 최적화
- 문서 개선

## 라이선스

이 프로젝트는 MIT 라이선스에 따라 라이선스가 부여됩니다.

## 지원

질문 사항:
- **LlamaIndex 통합**: 도메인별 노트북 참조
- **AgentCore 메모리**: AWS Bedrock 문서 확인
- **테스트 패턴**: 포괄적 테스트 예제 검토
