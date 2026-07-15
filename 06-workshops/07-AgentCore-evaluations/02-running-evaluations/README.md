# 평가 실행

## 개요

이 튜토리얼에서는 AgentCore Evaluations의 온디맨드 및 온라인 평가 방식을 사용하여 에이전트의 성능을 평가하는 방법을 알아봅니다. 기본 제공 및 사용자 지정 evaluator를 적용해 에이전트 상호 작용을 분석하고 대규모로 품질을 모니터링합니다.

## 학습 내용

- 특정 상호 작용을 집중적으로 평가하기 위한 온디맨드 평가 실행
- 지속적인 프로덕션 모니터링을 위한 온라인 평가 설정
- 에이전트 품질 개선을 위한 평가 결과 분석
- AgentCore Observability trace를 평가 입력으로 사용

## 사전 요구 사항

이 튜토리얼을 시작하기 전에 다음 항목을 준비해야 합니다.
- [튜토리얼 00: 사전 요구 사항](../00-prereqs) 완료 - 샘플 에이전트(Strands 및/또는 LangGraph) 생성
- [튜토리얼 01: 사용자 지정 evaluator 생성](../01-creating-custom-evaluators) 완료 - 사용자 지정 evaluator 생성
- observability가 활성화된 AgentCore Runtime에 에이전트 배포
- AgentCore Observability에서 trace가 포함된 세션을 하나 이상 생성

## 평가 유형

### 온디맨드 평가

온디맨드 평가는 선택한 span, trace 또는 세션 집합을 직접 분석하여 특정 에이전트 상호 작용을 유연하게 평가하는 방법을 제공합니다.

**주요 특징:**
- **집중 평가**: span, trace 또는 세션 ID를 제공하여 특정 상호 작용 평가
- **동기식 실행**: 평가 요청 결과를 즉시 확인
- **유연한 범위**: 개별 span, 전체 trace 또는 전체 세션 평가
- **조사 도구**: 특정 고객 상호 작용을 분석하거나 수정 사항을 검증하는 데 적합

**온디맨드 평가를 사용해야 하는 경우:**
- 특정 고객 상호 작용 또는 보고된 문제 조사
- 식별된 문제의 수정 사항 검증
- 품질 개선을 위한 과거 데이터 분석
- 프로덕션에 배포하기 전 evaluator 테스트
- edge case 심층 분석

**작동 방식:**

![온디맨드 평가 흐름](../images/on_demand_evaluations.png)

1. 에이전트가 AgentCore Observability에서 trace 생성
2. trace가 세션에 매핑되어 CloudWatch log group에 저장
3. 평가할 특정 세션 또는 trace 선택
4. 적용할 evaluator(기본 제공 또는 사용자 지정) 지정
5. AgentCore Evaluations가 선택한 trace를 처리하고 상세 결과 반환

### 온라인 평가

온라인 평가는 실시간 트래픽을 기반으로 프로덕션 환경에 배포된 에이전트의 품질을 지속적으로 모니터링합니다.

**주요 특징:**
- **지속적 모니터링**: 상호 작용이 발생할 때 에이전트 성능을 자동으로 평가
- **표본 기반**: 백분율 기반 표본 추출 또는 조건부 필터 구성
- **실시간 인사이트**: 품질 추세를 추적하고 regression을 조기에 감지
- **프로덕션 지원**: 성능에 미치는 영향을 최소화하면서 확장할 수 있도록 설계

**온라인 평가를 사용해야 하는 경우:**
- 프로덕션 에이전트 성능을 지속적으로 모니터링
- 사용자에게 영향을 주기 전에 품질 regression 감지
- 대규모 사용자 상호 작용의 패턴 식별
- 시간 경과에 따른 일관된 에이전트 성능 유지
- 서로 다른 에이전트 구성 A/B 테스트

**작동 방식:**

![온라인 평가 흐름](../images/online_evaluations.png)

1. 에이전트가 AgentCore Observability에서 trace 생성
2. 다음 항목을 지정하여 온라인 평가 구성 생성
   - 데이터 소스(CloudWatch log group 또는 AgentCore Runtime endpoint)
   - 표본 추출 비율(예: 전체 세션의 10% 평가)
   - 적용할 evaluator(기본 제공 및/또는 사용자 지정)
3. AgentCore Evaluations가 규칙에 따라 수신 trace를 지속적으로 처리
4. 대시보드 시각화 및 분석을 위해 결과를 CloudWatch로 출력
5. 집계 점수를 모니터링하고 추세를 추적하며 점수가 낮은 세션 조사

## AgentCore Observability 통합

두 평가 유형 모두 OpenTelemetry(OTEL) trace를 통해 에이전트 동작을 캡처하는 **AgentCore Observability**를 사용합니다.

**Observability 작동 방식:**

![AgentCore Observability trace 흐름](../images/observability_traces.png)

AgentCore는 **AWS Distro for OpenTelemetry(ADOT)**를 사용하여 다양한 에이전트 프레임워크에서 여러 유형의 OTEL trace를 계측합니다.

**AgentCore Runtime에서 호스팅되는 에이전트**(이 튜토리얼의 에이전트 등):
- 최소한의 구성으로 계측이 자동 적용됨
- `aws-opentelemetry-distro`를 `requirements.txt`에 포함
- AgentCore Runtime에서 OTEL 구성을 자동으로 처리
- CloudWatch GenAI Observability Dashboard에 trace 표시

**Runtime 외부의 에이전트:**
- telemetry가 CloudWatch로 전송되도록 환경 변수 구성
- OpenTelemetry 계측을 적용하여 에이전트 실행
- 자세한 내용은 [AgentCore Observability 문서](../../06-AgentCore-observability) 참조

## 튜토리얼 구성

이 튜토리얼은 AgentCore의 프레임워크 독립적 기능을 보여주기 위해 **Strands Agents**와 **LangGraph** 프레임워크 예제를 모두 제공합니다.

### [01-strands](01-strands/)
Strands Agents SDK를 사용하는 예제:
- **01-on-demand-eval.ipynb**: 특정 trace에 대한 집중 평가 실행
- **02-online-eval.ipynb**: 지속적인 프로덕션 모니터링 설정

### [02-langgraph](02-langgraph/)
LangGraph 프레임워크를 사용하는 예제:
- **01-on-demand-eval.ipynb**: 특정 trace에 대한 집중 평가 실행
- **02-online-eval.ipynb**: 지속적인 프로덕션 모니터링 설정

두 구현은 동일한 평가 개념을 설명하고 동등한 결과를 생성하여 AgentCore Evaluations가 서로 다른 에이전트 프레임워크에서도 일관되게 작동함을 보여줍니다.

## 다음 단계

이 튜토리얼을 완료한 후:
- [튜토리얼 03: 고급](../03-advanced)으로 이동하여 다음을 포함한 고급 기능을 살펴보세요.
  - boto3 SDK를 사용하여 온디맨드 평가용 CloudWatch 로그 쿼리
  - 서로 다른 에이전트 구성의 실험을 시각화하는 로컬 대시보드 생성
  - 온라인 평가를 위한 고급 필터링 및 표본 추출 전략
