# 오프라인 다중 세션 평가

AgentCore Observability의 과거 trace를 사용하여 배포된 AI 에이전트 세션을 평가합니다. 이 도구는 에이전트의 observability 로그에서 trace를 가져와 Strands Evals 형식으로 변환하고 평가를 실행합니다. 그런 다음 대시보드에서 연관 관계를 확인할 수 있도록 원본 trace ID와 함께 결과를 AgentCore Observability에 다시 기록합니다.

## 사용 사례

AgentCore Observability 계측을 적용한 AI 에이전트가 배포되어 있으면 이 도구를 사용하여 다음을 수행할 수 있습니다.

- 과거 에이전트 상호 작용에 대한 오프라인 평가 실행
- 점수가 낮았던 세션을 업데이트된 rubric으로 재평가
- 기존 trace에 새 evaluator 구성 테스트
- 에이전트 출력을 ground truth(SME가 작성한 기대 응답)와 비교
- 에이전트 변경으로 검증된 동작이 손상되지 않는지 확인하는 regression 테스트 수행
- AgentCore Observability 대시보드에서 평가 결과를 원본 trace와 연결

## 작동 방식

1. **세션 검색**: AgentCore Observability를 쿼리하여 시간 범위 또는 기존 평가 점수에 따라 에이전트 세션 검색
2. **trace 가져오기**: CloudWatch Logs Insights를 사용하여 각 세션의 span 검색
3. **형식 변환**: AgentCore Observability span을 Strands Evals Session 형식(tool call, 에이전트 응답, trajectory)으로 매핑
4. **평가**: 다음 두 가지 접근 방식 중 하나로 evaluator 실행
   - **Rubric 기반**: 사용자가 정의한 기준에 따라 채점(유연한 정성 평가)
   - **Ground truth**: 기대 출력과 비교(참조 기반 regression 테스트)
5. **결과 기록**: 대시보드에서 연관 관계를 확인할 수 있도록 원본 trace ID와 함께 평가 결과를 EMF 형식으로 전송

## 노트북 workflow

![노트북 workflow](images/notebook_workflow.svg)

## 에이전트 평가 이해

에이전트 평가는 기존 소프트웨어 테스트의 범위를 넘어섭니다. unit test는 결정론적 출력을 검증하지만, 에이전트는 정성적 평가가 필요한 가변적인 응답을 생성합니다. 체계적으로 평가하면 실패 패턴을 식별하고 시간 경과에 따른 개선 정도를 측정하며, prompt와 도구를 반복적으로 개선하는 동안 일관된 품질을 유지할 수 있습니다.

### 상호 보완적인 두 가지 접근 방식

**AgentCore Evaluations**와 **Strands Evals**는 원활하게 함께 작동하여 포괄적인 에이전트 품질 관리 기능을 제공합니다.

| | AgentCore Evaluations | Strands Evals |
|---|---|---|
| **목적** | 지속적인 실시간 품질 모니터링 | 오프라인 batch 평가 및 실험 |
| **사용 사례** | 프로덕션 모니터링, 품질 저하 알림 | 테스트, regression 분석, rubric 개발 |
| **실행** | 완전 관리형으로 실시간 상호 작용 표본 추출 | 온디맨드 방식으로 과거 trace에서 실행 |
| **기본 제공 evaluator** | Correctness, helpfulness, tool selection accuracy, safety, goal success rate, context relevance | Output, trajectory, helpfulness, faithfulness, goal success rate, tool accuracy |
| **사용자 지정 evaluator** | 사용자 지정 prompt를 사용한 모델 기반 채점 | 코드 기반 또는 LLM 기반 evaluator |

**AgentCore Evaluations**는 실제 동작을 바탕으로 에이전트 성능을 지속적으로 모니터링하는 완전 관리형 서비스입니다. 실시간 상호 작용에서 표본을 추출하여 기본 제공 또는 사용자 지정 evaluator로 채점하고, observability 인사이트와 함께 결과를 CloudWatch에 시각화합니다. 만족도나 정중함 점수가 하락하는 경우와 같이 품질 metric이 임계값 아래로 떨어질 때 알림을 설정하면 문제를 더 빠르게 감지하고 해결할 수 있습니다.

**Strands Evals**는 여러 평가 유형, multi-turn 대화를 위한 동적 simulator, OpenTelemetry를 통한 trace 기반 평가, 자동화된 실험 생성 및 모든 라이브러리의 사용자 지정 evaluator를 지원하는 확장 가능한 아키텍처를 제공하는 포괄적인 평가 프레임워크입니다. 전체 기능은 [Strands Evals 문서](https://strandsagents.com/latest/documentation/docs/user-guide/evals-sdk/quickstart/)를 참조하세요.

### 이 프로젝트

이 프로젝트는 **AgentCore Observability**에서 수집한 trace를 **Strands Evals로 오프라인 평가**하며, 다음 두 가지 일반적인 패턴을 보여줍니다.

- **출력 품질**: 에이전트의 응답이 사용자 요청을 정확하고 완전하게 처리하는가? 생성 방식과 관계없이 최종 답변을 평가합니다.

- **Trajectory 품질**: 에이전트가 도구를 효과적으로 사용했는가? 적절한 도구를 선택하고 효율적으로 사용했으며 논리적인 순서를 따랐는지 평가합니다.

결과는 원본 trace ID와 함께 AgentCore Observability에 다시 기록되므로 대시보드에서 AgentCore Evaluations 결과와 함께 연관 관계를 확인할 수 있습니다.

## Strands Evals 개념

이 도구는 AI 에이전트용 범용 평가 프레임워크인 [Strands Evals](https://github.com/strands-agents/strands-evals)를 사용합니다. Strands Evals는 LLM을 판정자로 사용하여 사람이 정의한 기준에 따라 에이전트 동작을 채점합니다. 이 프레임워크는 품질을 설명과 함께 0.0~1.0 척도로 정량화하여 에이전트 응답에 내재된 변동성을 처리합니다.

**핵심 인사이트**: 에이전트는 단순히 "정답" 또는 "오답"을 내놓는 것이 아니라 더 나은 응답이나 더 나쁜 응답을 생성합니다. Strands Evals는 주관적인 품질 평가를 측정 가능하고 일관된 metric으로 바꿉니다.

핵심 개념을 이해하면 평가를 효과적으로 사용자 지정할 수 있습니다.

**Session**: 여러 차례 주고받은 상호 작용이 포함될 수 있는 전체 사용자 대화를 나타냅니다. AgentCore Observability에서 session은 관련 상호 작용을 `session.id`로 그룹화합니다.

**Trace**: 하나의 사용자 요청과 해당 요청을 처리하기 위해 수행된 모든 tool call을 포함한 에이전트의 전체 응답입니다. 각 trace에는 AgentCore Observability와 연결되는 고유한 `trace_id`가 있습니다.

**Case**: 입력(user prompt), 실제 출력(에이전트 응답), 메타데이터(trace_id, tool trajectory)를 포함한 평가용 test case입니다. Evaluator는 case를 채점합니다.

**Experiment**: 하나 이상의 evaluator와 연결된 case 모음입니다. Experiment를 실행하면 각 case의 점수와 설명이 생성됩니다.

## 평가 접근 방식

Strands Evals는 여러 평가 접근 방식을 지원하는 확장 가능한 LLM 기반 평가 프레임워크입니다. 정확한 문자열 일치 대신 LLM을 판정자로 사용하여 에이전트 출력을 채점합니다. 유연성을 고려하여 설계되었으므로 사실상 모든 평가 유형을 구현할 수 있습니다.

**두 가지 기본 평가 접근 방식:**

| 접근 방식 | 설명 | 사용 시점 |
|----------|-------------|----------|
| **Rubric 기반** | 사용자가 정의한 기준에 따라 LLM이 판정 | 유연한 정성 평가가 필요한 경우 |
| **Ground truth** | 검증된 정답과 비교 | 측정 기준이 되는 기대 출력이 있는 경우 |

이 프로젝트는 별도의 노트북에서 두 접근 방식을 모두 보여줍니다.

### Rubric 기반 평가(노트북 02)

Rubric에 평가 기준을 정의하면 LLM이 해당 기준에 따라 각 응답을 판정합니다. 응답이 다양하더라도 서로 다른 방식으로 "우수"할 수 있는 경우에 적합한 접근 방식입니다.

**OutputEvaluator**: 에이전트 응답의 품질을 평가합니다. 우수한 응답의 조건(관련성, 정확성, 완전성)을 설명하는 rubric을 제공하면 evaluator가 LLM을 사용하여 출력에 0.0~1.0의 점수와 설명을 부여합니다.

**TrajectoryEvaluator**: 에이전트가 도구를 사용한 방식을 평가합니다. 올바른 도구 사용 패턴(적절한 선택, 효율성, 논리적 순서)을 설명하는 rubric을 제공하면 evaluator가 tool trajectory에 0.0~1.0의 점수를 부여합니다.

### Ground truth 평가(노트북 03)

실제 에이전트 출력을 미리 정의된 기대 응답과 비교합니다. 검증된 정답이 있는 regression 테스트, benchmarking 및 기타 사례에 적합한 접근 방식입니다.

Evaluator는 실제 출력과 기대 출력을 비교하고 에이전트 출력이 Subject Matter Expert(SME)가 정의한 정답과 얼마나 일치하는지 채점합니다. 자세한 내용은 [Ground truth 평가](#ground-truth-evaluation) 섹션을 참조하세요.

### 확장성

Strands Evals 프레임워크는 이 프로젝트에서 보여주는 범위를 넘어 사용자 지정 evaluator를 지원합니다. 사실 정확성, 안전성, 도메인별 품질 검사, 규정 준수 요구 사항처럼 채점 기준으로 표현할 수 있는 모든 평가는 LLM-as-a-judge 방식으로 구현할 수 있습니다.

**Rubric 작동 방식**: 에이전트 출력과 함께 rubric이 LLM으로 전송됩니다. LLM은 판정자 역할을 하며 기준을 적용하여 점수와 설명을 생성합니다. 명확한 채점 지침이 포함된 잘 작성된 rubric은 더 일관된 평가 결과를 제공합니다.

<a id="ground-truth-evaluation"></a>

## Ground truth 평가

Ground truth 평가는 에이전트 출력을 미리 정의된 기대 응답과 비교합니다. 특정 쿼리에 대해 검증된 정답이 있고 에이전트가 그 답과 얼마나 일치하는지 측정하려는 경우에 유용합니다.

![Ground truth 평가 흐름](images/ground_truth_flow.svg)

**핵심 개념:**
- **session_id**: 하나의 사용자 세션에 속한 모든 trace를 그룹화
- **trace_id**: 세션 내의 각 개별 상호 작용(user prompt + 에이전트 응답)을 식별

**두 파일 방식**: Ground truth 노트북은 동일한 `session_id`를 공유하는 두 파일을 사용합니다.

1. **Trace 파일**(`demo_traces.json`): CloudWatch의 실제 에이전트 출력 포함
   ```json
   {
     "session_id": "5B467129-E54A-4F70-908D-CB31818004B5",
     "traces": [
       {
         "trace_id": "693cb6c4e931",
         "user_prompt": "What is the best route for a NZ road trip?",
         "actual_output": "Based on the search results...",
         "actual_trajectory": ["web_search"]
       },
       {
         "trace_id": "693cb6fa87aa",
         "user_prompt": "Should I visit North or South Island?",
         "actual_output": "Here's how the islands compare...",
         "actual_trajectory": ["web_search"]
       }
     ]
   }
   ```

2. **Ground truth 파일**(`demo_ground_truth.json`): SME가 작성한 기대 출력
   ```json
   {
     "session_id": "5B467129-E54A-4F70-908D-CB31818004B5",
     "ground_truth": [
       {
         "trace_id": "693cb6c4e931",
         "expected_output": "Response should mention Milford Road, Southern Scenic Route...",
         "expected_trajectory": ["web_search"]
       },
       {
         "trace_id": "693cb6fa87aa",
         "expected_output": "Response should compare both islands...",
         "expected_trajectory": ["web_search"]
       }
     ]
   }
   ```

**작동 방식:**
1. 노트북이 CloudWatch에서 trace를 가져오거나 demo 파일 로드
2. SME가 각 `trace_id`의 기대 출력이 포함된 ground truth 파일 생성
3. 노트북이 `trace_id`를 기준으로 병합하여 실제 출력과 기대 출력을 연결
4. Evaluator가 각 pair 채점

**Demo mode**: 자체 CloudWatch 데이터에 연결하기 전에 제공된 예제 파일로 테스트하려면 `USE_DEMO_MODE = True`로 실행합니다.

## 데이터 흐름

평가 pipeline은 AgentCore Observability trace를 채점된 결과로 변환합니다.

![평가 pipeline](images/evaluation_pipeline.svg)

## 프로젝트 구조

```
01_session_discovery.ipynb        - Notebook 1: Discover sessions
02_multi_session_analysis.ipynb   - Notebook 2: Evaluate with custom rubrics
03_ground_truth_evaluation.ipynb  - Notebook 3: Evaluate against ground truth
demo_traces.json                  - Example trace data (for demo mode)
demo_ground_truth.json            - Example ground truth expectations (for demo mode)
config.py                         - Centralized configuration
requirements.txt                  - Python dependencies
utils/
  __init__.py                     - Module exports
  cloudwatch_client.py            - CloudWatch Logs Insights query client
  constants.py                    - Constants and evaluator configurations
  evaluation_cloudwatch_logger.py - EMF logger preserving original trace IDs
  models.py                       - Data models (Span, TraceData, SessionInfo)
  session_mapper.py               - AgentCore Observability span to Strands Evals Session mapper
```

## 빠른 시작

### 1. 구성

AWS 설정에 맞게 `config.py`를 편집합니다.

```python
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "123456789012"
SOURCE_LOG_GROUP = "your-agent-log-group"
EVAL_RESULTS_LOG_GROUP = "your-eval-log-group"
EVALUATION_CONFIG_ID = "your-evaluation-config-id"
SERVICE_NAME = "your-service-name"
```

### 2. 세션 검색

`01_session_discovery.ipynb`를 실행합니다.
- 시간 기반 검색(시간 범위 내 모든 세션) 또는 점수 기반 검색(평가 점수별 세션) 선택
- 검색된 세션 미리 보기
- 평가 노트북에서 사용할 JSON으로 저장

### 3. 세션 평가(한 가지 경로 선택)

**옵션 A: 사용자 지정 rubric** - `02_multi_session_analysis.ipynb` 실행:
- 검색된 세션을 로드하거나 사용자 지정 세션 ID 제공
- 사용 사례에 맞게 evaluator rubric 사용자 지정
- 평가를 실행하고 결과 확인
- 원본 trace ID와 함께 결과를 AgentCore Observability에 기록

**옵션 B: Ground truth** - `03_ground_truth_evaluation.ipynb` 실행:
- 에이전트 출력을 미리 정의된 기대 응답과 비교
- 평가 기준으로 사용할 검증된 정답이 있을 때 유용
- 예제 파일(`demo_traces.json`, `demo_ground_truth.json`)을 사용하는 demo mode 지원
- `trace_id`를 기준으로 trace와 ground truth 병합

## 구성 참조

모든 설정은 `config.py`에 있습니다. 값을 직접 편집하세요.

| 변수 | 설명 |
|----------|-------------|
| `AWS_REGION` | AWS 리전(예: us-east-1) |
| `AWS_ACCOUNT_ID` | AWS 계정 ID |
| `SOURCE_LOG_GROUP` | AgentCore Observability log group 이름 |
| `EVAL_RESULTS_LOG_GROUP` | 평가 결과 log group 이름 |
| `EVALUATION_CONFIG_ID` | AgentCore Observability 평가 config ID |
| `SERVICE_NAME` | CloudWatch logging용 서비스 이름 |
| `EVALUATOR_NAME` | 점수 기반 검색에 사용할 evaluator 이름 |
| `LOOKBACK_HOURS` | 세션을 조회할 과거 시간 범위(기본값: 72) |
| `MAX_SESSIONS` | 검색할 최대 세션 수(기본값: 100) |
| `MIN_SCORE` / `MAX_SCORE` | 점수 기반 검색용 점수 필터 |
| `MAX_CASES_PER_SESSION` | 세션당 평가할 최대 trace 수(기본값: 10) |

## 사용자 지정

### Evaluator 평가 기준

분석 노트북에서 평가 기준에 맞게 rubric을 사용자 지정합니다.

```python
output_rubric = """
Evaluate the agent's response based on:
1. Relevance: Does it address the user's question?
2. Accuracy: Is the information correct?
...
"""
```

### Evaluator 이름

CloudWatch metric에 사용할 사용자 지정 evaluator 이름을 설정합니다.

```python
OUTPUT_EVALUATOR_NAME = "Custom.YourOutputEvaluator"
TRAJECTORY_EVALUATOR_NAME = "Custom.YourTrajectoryEvaluator"
```

### 평가 config ID

AgentCore Observability 평가 구성에 맞게 `config.py`에서 평가 config ID를 설정합니다.

```python
EVALUATION_CONFIG_ID = "your-evaluation-config-id"
```

## 요구 사항

- Python 3.9+
- CloudWatch Logs 액세스 권한이 있는 AWS 자격 증명
- `strands-evals` 패키지
- `boto3`
