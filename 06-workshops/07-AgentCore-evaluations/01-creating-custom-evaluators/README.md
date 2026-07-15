# Evaluator 생성

## 개요
이 튜토리얼에서는 AgentCore Evaluations의 기본 제공 및 사용자 지정 metric을 알아봅니다.
각 유형을 언제 사용해야 하는지 살펴보고, 구체적인 요구 사항에 맞는 사용자 지정 evaluator를 생성하는 방법을 학습합니다.

## 학습 내용
- 기본 제공 evaluator와 사용 사례 이해
- 특수 요구 사항을 위한 사용자 지정 evaluator 생성
- 에이전트에 적합한 평가 접근 방식 선택

## Evaluator 유형

### 기본 제공 evaluator
기본 제공 evaluator는 Large Language Model(LLM)을 판정자로 사용하여 에이전트 성능을 평가하도록 미리 구성된 evaluator입니다.

**주요 특징:**
- **사전 구성**: 세심하게 설계된 prompt template, 선정된 evaluator model, 표준화된 채점 기준 제공
- **즉시 사용 가능**: 추가 구성 없이 바로 평가 시작
- **일관성**: 고정된 구성으로 평가 전반의 신뢰성과 일관성 보장
- **포괄성**: 정확성, 유용성, 안전성을 포함한 13가지 핵심 평가 요소 지원

**기본 제공 evaluator를 사용해야 하는 경우:**
- 품질 평가를 빠르게 구현해야 하는 경우
- 팀 또는 프로젝트 전반에 표준화된 평가 metric이 필요한 경우
- 평가 요구 사항이 일반적인 품질 요소와 일치하는 경우
- 사용자 지정 기능보다 일관성과 신뢰성을 우선하는 경우


사용 사례에 따라 다음과 같은 기본 제공 evaluator를 사용할 수 있습니다.
* 응답 품질 metric:
  * **Builtin.Correctness**: 에이전트 응답의 정보가 사실에 부합하는지 평가
  * **Builtin.Faithfulness**: 응답의 정보가 제공된 컨텍스트 또는 출처로 뒷받침되는지 평가
  * **Builtin.Helpfulness**: 에이전트 응답이 사용자 관점에서 얼마나 유용하고 가치 있는지 평가
  * **Builtin.ResponseRelevance**: 응답이 사용자의 쿼리를 적절히 다루는지 평가
  * **Builtin.Conciseness**: 핵심 정보를 누락하지 않으면서 응답이 적절히 간결한지 평가
  * **Builtin.Coherence**: 응답이 논리적으로 구성되고 일관성이 있는지 평가
  * **Builtin.InstructionFollowing**: 에이전트가 제공된 system instruction을 얼마나 잘 따르는지 측정
  * **Builtin.Refusal**: 에이전트가 질문을 회피하거나 답변을 직접 거부하는지 감지
* 작업 완료 metric:
  * **Builtin.GoalSuccessRate**: 대화가 사용자의 목표를 성공적으로 달성하는지 평가
* 도구 수준 metric:
  * **Builtin.ToolSelectionAccuracy**: 에이전트가 작업에 적합한 도구를 선택했는지 평가
  * **Builtin.ToolParameterAccuracy**: 에이전트가 사용자 쿼리에서 파라미터를 얼마나 정확히 추출하는지 평가
* 안전성 metric:
  * **Builtin.Harmfulness**: 응답에 유해한 콘텐츠가 포함되어 있는지 평가
  * **Builtin.Stereotyping**: 개인 또는 집단을 일반화하는 콘텐츠 감지

**참고:** 모든 사용자에게 일관되고 신뢰할 수 있는 평가를 제공하기 위해 기본 제공 evaluator 구성은 수정할 수 없습니다. 단, 기본 제공 evaluator를 기반으로 자체 evaluator를 생성할 수 있습니다.

### 사용자 지정 evaluator
사용자 지정 evaluator는 LLM을 기반 판정자로 활용하면서 평가 프로세스의 모든 요소를 정의할 수 있어 높은 유연성을 제공합니다.

**사용자 지정 옵션:**
- **Evaluator model**: 평가 요구 사항에 가장 적합한 LLM 선택
- **평가 prompt**: 사용 사례에 맞는 평가 지침 작성
- **채점 schema**: 조직의 metric에 부합하는 채점 시스템 설계

**사용자 지정 evaluator를 사용해야 하는 경우:**
- 도메인별 에이전트(예: 의료, 금융, 법률)를 평가하는 경우
- 고유한 품질 표준 또는 규정 준수 요구 사항이 있는 경우
- 조직의 KPI에 부합하는 특화된 채점 시스템이 필요한 경우
- 기본 제공 evaluator가 구체적인 평가 요소를 포착하지 못하는 경우

**사용 사례 예시:**
- HIPAA 규정 준수 평가가 필요한 의료 에이전트
- 규제 준수 점수 산정이 필요한 금융 에이전트
- 브랜드별 품질 표준에 따라 평가하는 고객 서비스 에이전트
- 문제 해결 방법론을 기준으로 평가하는 기술 지원 에이전트

## 다음 단계
이 튜토리얼을 완료한 후 [온디맨드 평가 사용](../02-running-evaluations)으로 이동하여 이러한 evaluator를 에이전트 trace에 적용하는 방법을 알아보세요.
