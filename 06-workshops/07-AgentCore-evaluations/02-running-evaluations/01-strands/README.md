# Strands Agents로 평가 실행

## 개요

이 튜토리얼에서는 [Strands Agents SDK](https://strandsagents.com/)로 구축한 에이전트에 AgentCore Evaluations를 사용하는 방법을 보여줍니다. 기본 제공 및 사용자 지정 evaluator를 사용하여 온디맨드 평가와 온라인 평가를 모두 실행하고 Strands 에이전트의 성능을 평가하고 모니터링하는 방법을 알아봅니다.

## 학습 내용

- 특정 Strands 에이전트 trace에 대한 온디맨드 평가 실행
- Strands 에이전트의 지속적인 모니터링을 위한 온라인 평가 설정
- AgentCore Starter Toolkit을 사용하여 평가 관리
- 에이전트 품질 개선을 위한 평가 결과 분석

## 사전 요구 사항

이 튜토리얼을 시작하기 전에 다음 항목을 준비했는지 확인하세요.
- [튜토리얼 00: 사전 요구 사항](../../00-prereqs)을 완료하고 Strands 에이전트(`eval_agent_strands.py`) 생성
- [튜토리얼 01: 사용자 지정 evaluator 생성](../../01-creating-custom-evaluators)을 완료하고 사용자 지정 evaluator 생성
- AgentCore Runtime에 Strands 에이전트 배포
- 에이전트를 호출하여 trace가 포함된 세션을 하나 이상 생성
- Python 3.10+ 설치
- 적절한 권한으로 AWS 자격 증명 구성

## 튜토리얼 구성

### [01-on-demand-eval.ipynb](01-on-demand-eval.ipynb)

**튜토리얼 유형:** 온디맨드 evaluator(기본 제공 및 사용자 지정)를 사용한 Strands 에이전트 평가

**학습 내용:**
- 배포된 Strands 에이전트에서 세션 및 trace 정보 검색
- Starter Toolkit을 사용하여 AgentCore Evaluations client 초기화
- 특정 trace 또는 세션에 대한 온디맨드 평가 실행
- 기본 제공 evaluator(예: `Builtin.Correctness`, `Builtin.Helpfulness`)와 사용자 지정 evaluator 함께 사용
- 점수, 설명, 토큰 사용량을 포함한 평가 결과 해석

**핵심 개념:**
- **집중 평가**: 세션 또는 trace ID를 제공하여 특정 상호 작용 평가
- **동기식 실행**: 평가 요청 결과를 즉시 확인
- **유연한 evaluator 선택**: 동일한 trace에 여러 evaluator 적용
- **조사 도구**: 특정 상호 작용을 분석하거나 수정 사항을 검증하는 데 적합

### [02-online-eval.ipynb](02-online-eval.ipynb)

**튜토리얼 유형:** 온라인 evaluator(기본 제공 및 사용자 지정)를 사용한 Strands 에이전트 평가

**학습 내용:**
- Strands 에이전트용 온라인 평가 구성 생성
- 표본 추출 비율 및 필터링 규칙 구성
- 기본 제공 및 사용자 지정 evaluator를 사용한 지속적 평가 설정
- CloudWatch 대시보드에서 평가 결과 모니터링
- 온라인 평가 구성 관리(활성화, 비활성화, 업데이트, 삭제)

**핵심 개념:**
- **지속적 모니터링**: 상호 작용이 발생할 때 에이전트 성능을 자동으로 평가
- **표본 기반**: 백분율 기반 표본 추출 구성(예: 세션의 10% 평가)
- **실시간 인사이트**: 품질 추세를 추적하고 regression을 조기에 감지
- **프로덕션 지원**: 성능에 미치는 영향을 최소화하면서 확장할 수 있도록 설계

## Strands 에이전트 아키텍처

이 튜토리얼에서 사용하는 Strands 에이전트는 다음 기능으로 구성됩니다.

**코드 실행 기능:**
- AgentCore Code Interpreter를 사용하여 Python 코드 실행
- 수학 계산 및 데이터 분석 처리

**메모리 통합:**
- 사용자 정보 및 선호도 저장
- 개인화된 응답에 필요한 관련 컨텍스트 검색

**모델:**
- Amazon Bedrock의 Anthropic Claude Haiku 4.5

**관찰성:**
- AgentCore Runtime을 통한 자동 OTEL 계측
- CloudWatch GenAI Observability Dashboard에서 trace 확인 가능

## Strands Agents의 평가 작동 방식

1. **에이전트 호출**: Strands 에이전트가 사용자 요청 처리
2. **trace 생성**: AgentCore Observability가 OTEL trace를 자동으로 캡처
3. **trace 저장**: trace가 CloudWatch log group에 저장됨
4. **평가**:
   - **온디맨드**: 평가할 특정 세션/trace 선택
   - **온라인**: AgentCore가 구성에 따라 자동으로 표본을 추출하고 평가
5. **결과 분석**: CloudWatch에서 점수, 설명 및 추세 확인

## AgentCore Starter Toolkit 사용

두 노트북 모두 **AgentCore Starter Toolkit**을 사용하여 평가 workflow를 간소화합니다.

```python
from bedrock_agentcore_starter_toolkit import Evaluations

# Evaluations client 초기화
evaluations = Evaluations()

# 온디맨드 평가
result = evaluations.evaluate_session(
    session_id="your-session-id",
    evaluator_ids=["Builtin.Correctness", "your-custom-evaluator-id"]
)

# 온라인 평가
config = evaluations.create_online_evaluation(
    config_name="your-config-name",
    sampling_percentage=100,
    evaluator_ids=["Builtin.Helpfulness", "your-custom-evaluator-id"]
)
```

## 예상 결과

이 튜토리얼을 완료하면 다음을 수행할 수 있습니다.
- 온디맨드 평가를 사용하여 특정 Strands 에이전트 상호 작용 평가
- 프로덕션 Strands 에이전트의 지속적인 품질 모니터링 설정
- 개선 영역을 식별하기 위한 평가 결과 분석
- 기본 제공 및 사용자 지정 evaluator를 효과적으로 사용
- 시간 경과에 따른 에이전트 품질 추세 모니터링

## 다음 단계

Strands 관련 튜토리얼을 완료한 후:
- [LangGraph 예제](../02-langgraph/)를 살펴보며 다른 프레임워크에서 평가가 작동하는 방식 확인
- 고급 평가 기법은 [튜토리얼 03: 고급](../../03-advanced)으로 이동
- CloudWatch GenAI Observability Dashboard에서 평가 결과 검토
