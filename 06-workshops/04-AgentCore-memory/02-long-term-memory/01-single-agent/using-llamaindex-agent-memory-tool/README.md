# LlamaIndex와 AWS Bedrock AgentCore Memory 통합

이 프로젝트는 지속적인 메모리 기능을 갖춘 엔터프라이즈급 AI Agent를 소개합니다. LlamaIndex의 ReAct 프레임워크를 AWS Bedrock AgentCore Memory와 원활하게 통합하여 시간이 지남에 따라 학습하고 적응하며 발전하는 지능형 시스템을 만드는 방법을 보여 줍니다. 기존의 상태 비저장 Agent와 달리, 이러한 구현은 세션 전반에서 맥락 인식을 유지합니다. 이를 통해 정교한 종단 분석, 상호 참조 기능, 누적 지식 구축이 가능하며 전문 업무 환경에서 AI Agent가 작동하는 방식을 개선할 수 있습니다.

## 🚀 주요 기능

- **LlamaIndex 기본 통합**: `agent.run(message, memory=agentcore_memory)`으로 메모리를 직접 전달
- **도메인별 예제**: 학술 연구, 법률 문서 분석, 의학 지식, 투자 포트폴리오 관리
- **포괄적인 테스트**: 예제마다 예상 검증 결과가 포함된 8~10개의 체계적인 테스트 사례 제공
- **단기 및 장기 메모리**: 두 메모리 유형을 모두 다룸
- **엔터프라이즈 지원**: 프로덕션 환경에 적합한 단순하고 명시적인 API

## 📁 프로젝트 구조

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

## 🎯 사용 사례

### 학술 연구 도우미
- **단기**: 단일 세션 내 논문 분석 및 연구 종합
- **장기**: 세션 간 연구 발전 추적 및 수개월에 걸친 연구비 지원 제안서 작성 지원
- **메모리 인텔리전스**: 연구 주제, 인용 네트워크, 방법론의 발전 과정 추적
- **테스트**: 맥락 추론과 상호 참조 검증을 포함한 8개의 포괄적인 테스트

### 법률 문서 분석기
- **단기**: 계약 분석, 위험 평가, 규정 준수 확인
- **장기**: 여러 사건의 판례 추적 및 법률 지식 축적(12개월 보존)
- **메모리 인텔리전스**: 판례 데이터베이스 구축, 규제 변경 추적, 고객 기록 유지
- **테스트**: 판례 적용 및 규정 준수를 포함한 9개의 체계적인 테스트

### 의학 지식 도우미
- **단기**: 환자 상담, 약물 상호 작용, 임상 지침
- **장기**: 종단 환자 진료, 치료 결과, 인구 집단 건강 추세
- **메모리 인텔리전스**: 환자 기록 유지, 치료 효과 추적, 결과를 통한 학습
- **테스트**: 임상 추론 및 치료 계획을 포함한 10개의 포괄적인 테스트

### 투자 포트폴리오 자문
- **단기**: 고객 프로파일링, 포트폴리오 분석, 투자 추천
- **장기**: 여러 분기의 성과 추적(Q1→Q2→Q3→Q4), 시장 인텔리전스, 자산 관리
- **메모리 인텔리전스**: $3.2M→$3.45M의 포트폴리오 변화, 시장 진입 시점 결정, 투자 논리 조정 과정 추적
- **테스트**: 분기별 성과 기여도와 다년간의 투자 여정 분석을 포함한 10개의 체계적인 테스트

## 🏗️ 시스템 아키텍처

*아키텍처 다이어그램이 여기에 추가될 예정입니다.*

## 🛠️ 사전 요구 사항

- Python 3.10+
- Bedrock AgentCore Memory 권한이 있는 AWS 계정
- 적절한 자격 증명으로 구성된 AWS CLI
- Claude 3.7 Sonnet inference profile(`us.anthropic.claude-3-7-sonnet-20250219-v1:0`) 액세스 권한

## 📦 설치

```bash
# Jupyter를 포함한 모든 종속성 설치
pip install -r requirements.txt

# 대안: Jupyter를 별도로 설치
pip install jupyter ipykernel
```

## 🚀 빠른 시작

1. **AWS 자격 증명을 구성합니다.**
   ```bash
   aws configure
   ```

2. **튜토리얼을 선택하고 노트북을 엽니다.**
   ```bash
   jupyter notebook 01-short-term-memory/academic-research-assistant-short-term-memory-tutorial.ipynb
   ```

3. 포괄적인 테스트가 포함된 **단계별 튜토리얼을 따라 진행합니다.**

## 🏗️ 주요 이점

- ✅ **명시적 제어**: 숨겨진 자동화 대신 메모리 파라미터를 직접 사용
- ✅ **간편한 디버깅**: 백그라운드 hook 대신 메모리 작업을 직접 확인
- ✅ **단순한 API**: 복잡한 구성 대신 `agent.run(message, memory=memory)` 사용
- ✅ **포괄적인 테스트**: 예상 결과를 포함한 체계적인 검증
- ✅ **도메인 전문성**: 일반적인 예제 대신 특화된 사용 사례 제공

## 📊 테스트 방법론

각 노트북에는 명확한 검증 기준을 갖춘 **8~10개의 체계적인 테스트**가 포함되어 있습니다.

### 테스트 범주
- **테스트 1~2: 메모리 저장** - 정보 지속성과 도구 통합 확인
- **테스트 3~4: 맥락 회상** - ID, 지표, 세부 정보 검색 검증
- **테스트 5~6: 추론 및 종합** - 상호 참조 기능과 지식 종합 테스트
- **테스트 7~8: 실무 적용** - 실제 시나리오 검증(연구비 지원 제안서, 사건 분석)
- **테스트 9~10: 세션 경계** - 메모리 격리 및 세션 간 동작 확인

### 검증 방식
- **✅ 예상 결과**: 각 테스트에 비교할 예상 출력 표시
- **🎯 성공 기준**: 구체적인 지표를 사용한 명확한 통과/실패 기준
- **📊 점진적 복잡도**: 기본 회상부터 고급 추론까지 단계적으로 구성된 테스트
- **🔍 엣지 케이스 테스트**: 세션 경계, 메모리 제한, 오류 처리

### 테스트 패턴 예제
```python
# 테스트 4: 상세 지표 회상
response = await agent.run("What were the exact accuracy percentages?", memory=memory)
print("📊 Result:", response)
print("✅ Expected: Zhang et al - CNNs 95.2%, Johnson et al - BERT 89.1%")
# 사용자는 응답에 두 정확도 수치가 모두 포함되는지 확인할 수 있음
```

## 🔧 기술 개요

**주요 장기 메모리 구성 요소:**
1. **Semantic Strategy 구성**: SemanticStrategy를 사용하여 365일 동안 보존되는 인사이트를 자동으로 추출합니다.
2. **세션 간 지속성**: 동일한 actor_id와 memory_id를 사용하고 기간마다 다른 session_id를 사용하여 지식의 연속성을 유지합니다.
3. **사용자 지정 메모리 검색 도구**: AgentCore의 기본 search_long_term_memories()를 LlamaIndex FunctionTool로 래핑합니다.
4. **Semantic 처리 파이프라인**: 대화 이벤트를 90~120초 동안 처리한 후 semantic memory로 변환합니다.
5. **동적 세션 관리**: memory.context.session_id를 사용하여 세션을 유연하게 처리합니다.

## 🔧 메모리 구성

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

### 장기 메모리(12개월 보존)
```python
# Semantic strategy를 사용한 세션 간 지속성
memory = memory_manager.get_or_create_memory(
    name='DomainSpecificLongTerm',
    strategies=[SemanticStrategy(name="domainLongTermMemory")],
    event_expiry_days=365  # 12개월 보존
)

# 지속성을 위해 세션 간 동일한 context 사용
context = AgentCoreMemoryContext(
    actor_id="advisor-id",      # 세션 간 동일한 actor
    memory_id=memory_id,        # 동일한 memory store
    session_id="q1-session",    # 상호 작용마다 다름
    namespace="/domain-specific/"
)
```

### 메모리 인텔리전스 예제
- **투자 자문**: 분기별 성과 추적(Q1: +8.2% → Q2: -2.1% → Q3: 회복)
- **법률 분석기**: 여러 사건과 규제 변경에 걸친 판례 데이터베이스 유지
- **의학 도우미**: 종단 환자 진료 기록과 치료 결과 구축
- **연구 도우미**: 수개월에 걸쳐 연구 주제와 방법론 인사이트 발전

## 🤝 기여

이 프로젝트는 LlamaIndex + AgentCore Memory 통합의 모범 사례를 보여 줍니다. 다음과 같은 기여를 환영합니다.

- 추가 도메인 예제
- 향상된 테스트 방법론
- 성능 최적화
- 문서 개선

## 📄 라이선스

이 프로젝트는 MIT License에 따라 사용이 허가됩니다.

## 🙋‍♂️ 지원

다음 항목에 관한 질문은 아래 자료를 참조하세요.
- **LlamaIndex 통합**: 도메인별 노트북 참조
- **AgentCore Memory**: AWS Bedrock 문서 확인
- **테스트 패턴**: 포괄적인 테스트 예제 검토
