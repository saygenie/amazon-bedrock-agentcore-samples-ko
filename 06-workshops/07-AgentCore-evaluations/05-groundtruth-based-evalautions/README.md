# 사용자 지정 evaluator를 활용한 ground truth 평가

## 소개

이 튜토리얼에서는 ground truth 참조 입력과
[**Amazon Bedrock AgentCore Evaluations**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)를 사용하여 에이전트 애플리케이션을 평가하는 방법을 보여줍니다.
세 가지 평가 인터페이스를 다루고, ground truth placeholder를 사용해 애플리케이션 도메인의 채점 기준을 정의하는
**사용자 지정 LLM-as-a-judge evaluator**를 생성하는 방법을 설명합니다.

이 튜토리얼에서는 Acme Corp의 **HR Assistant 에이전트**를 배포합니다. 이
[Strands Agents](https://strandsagents.com/) 애플리케이션은 직원의 PTO 관리,
HR 정책 조회, 복리후생 정보 확인, 급여 명세서 검색을 지원합니다. 도구가 결정론적 mock 데이터를
반환하므로 평가 결과를 완전히 재현할 수 있습니다.

### 다루는 핵심 개념

| 개념 | 설명 |
|---|---|
| `EvaluationClient` | 기존의 특정 CloudWatch 세션을 ground truth 참조와 비교하여 평가 |
| `OnDemandEvaluationDatasetRunner` | 테스트 dataset을 정의하고 시나리오별로 에이전트를 자동 호출한 후 결과 평가 |
| `BatchEvaluationRunner` | 단일 서비스 측 job에서 여러 세션을 평가하고 evaluator별 집계 점수 제공 |
| `ReferenceInputs` | `expected_response`, `expected_trajectory`, `assertions`를 ground truth로 제공 |
| 사용자 지정 evaluator | 도메인별 지침과 ground truth placeholder를 사용하는 LLM-as-a-judge evaluator 생성 |

| | OnDemandEvaluationDatasetRunner | BatchEvaluationRunner |
|---|---|---|
| **평가 실행 위치** | Client 측: 호출, 대기, span 수집, Evaluate API 호출 | 서비스 측: 호출, 대기, `StartBatchEvaluation`, `GetBatchEvaluation` polling |
| **결과** | 응답 객체에서 시나리오별, evaluator별 세부 정보를 즉시 제공 | evaluator별 집계 `averageScore`, 세션별 세부 정보는 CloudWatch에 제공 |
| **적합한 용도** | 개발 단계 반복, CI/CD pipeline, 소규모 dataset, 개별 시나리오 디버깅 | baseline 측정, 대규모 dataset, 여러 세션의 변경 전후 비교 |
| **Evaluator 지원** | 모든 기본 제공 evaluator 및 사용자 지정 evaluator, session/trace/tool-call 수준 자동 처리 | 모든 기본 제공 evaluator, job당 최대 500개 세션 지원 |

> **추가 자료**
> - [Ground truth 평가](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html)
> - [Dataset 기반 평가](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations.html)
> - [Batch 평가](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations.html)

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Tutorial Notebook (groundtruth_evaluations.ipynb)                      │
│                                                                         │
│  Step 1  ──► Install dependencies (bedrock-agentcore, strands-agents)  │
│                                                                         │
│  Step 2  ──► Configure boto3 session and REGION                        │
│                                                                         │
│  Step 3  ──► Deploy HR Assistant via agentcore CLI                     │
│               │  deploy_hr_assistant_agent.py                           │
│               └──► AgentCore Runtime  (HR Assistant Agent)              │
│                         │  invoke_agent_runtime()                       │
│                                                                         │
│  Step 4  ──► Invoke agent to generate sessions                         │
│               │  OTel spans ──► CloudWatch Logs                         │
│                                                                         │
│  Step 5  ──► EvaluationClient.run()                                    │
│               │  CloudWatchAgentSpanCollector reads spans               │
│               └──► Evaluate API  ──► Built-in + Custom Evaluators       │
│                                       └──► Scores & Explanations        │
│                                                                         │
│  Step 6  ──► OnDemandEvaluationDatasetRunner.run()                     │
│               │  Invokes agent per scenario                             │
│               │  Waits for CloudWatch ingestion                         │
│               └──► Evaluate API  ──► Built-in + Custom Evaluators       │
│                                       └──► Per-scenario Results         │
│                                                                         │
│  Step 7  ──► BatchEvaluationRunner.run_dataset_evaluation()            │
│               │  Invokes agent, submits StartBatchEvaluation            │
│               │  Polls GetBatchEvaluation until complete                │
│               └──► Aggregate scores per evaluator                       │
└─────────────────────────────────────────────────────────────────────────┘
```

**구성 요소 역할**

| 구성 요소 | 역할 |
|---|---|
| AgentCore Runtime | HR Assistant 에이전트를 호스팅하고 OTel span을 CloudWatch로 전송 |
| CloudWatch Logs | 세션 span 저장, span collector 및 batch 평가에서 쿼리 |
| `bedrock-agentcore-control` | Control plane: 사용자 지정 evaluator 및 agent runtime 생성 |
| Evaluate API (`bedrock-agentcore`) | Data plane: evaluator 정의에 따라 세션 채점 |
| `agentcore` CLI | CodeBuild를 통해 container image를 빌드하고 runtime 배포 |

---

## 사전 요구 사항

- `requirements.txt`의 패키지가 설치된 **Python 3.10+**
- 다음 권한이 구성된 **AWS 자격 증명**(예: `aws configure` 또는 환경 변수 사용):
  - `bedrock-agentcore:*`: agent runtime 호출 및 Evaluate API 호출
  - `bedrock-agentcore-control:CreateAgentRuntime`, `UpdateAgentRuntime`,
    `GetAgentRuntime`, `CreateEvaluator`: 에이전트 배포 및 evaluator 등록
  - `logs:FilterLogEvents`, `logs:DescribeLogGroups`, `logs:StartQuery`,
    `logs:GetQueryResults`: CloudWatch span 읽기
  - `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`,
    `ecr:InitiateLayerUpload`, `ecr:PutImage`: container image push
  - `codebuild:StartBuild`, `codebuild:BatchGetBuilds`: CodeBuild를 통한 image 빌드
  - `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole`: 실행 role 자동 생성
  - `s3:PutObject`, `s3:GetObject`: CodeBuild source 업로드

종속성을 설치합니다.

```bash
pip install -r requirements.txt
```

---

## 사용법

### 노트북 실행

[`groundtruth_evaluations.ipynb`](groundtruth_evaluations.ipynb)를 열고 위에서 아래로 실행합니다.
각 cell은 idempotent합니다. 노트북을 다시 실행하면 기존 agent runtime을 업데이트하고
이름 충돌을 방지하기 위해 고유한 suffix가 붙은 새 사용자 지정 evaluator를 생성합니다.

```bash
jupyter notebook groundtruth_evaluations.ipynb
```

또는 다음과 같이 비대화형으로 실행합니다.

```bash
jupyter nbconvert --to notebook --execute --inplace groundtruth_evaluations.ipynb
```

### 노트북 단계별 안내

| 단계 | 수행 작업 |
|---|---|
| **1: 설치** | `bedrock-agentcore`, `strands-agents` 및 기타 종속성 설치 |
| **2: 구성** | boto3 세션을 생성하고 `REGION` 설정 |
| **3: 에이전트 배포** | `deploy_hr_assistant_agent.py`를 `%run -i`로 실행하고 `agentcore` CLI를 사용하여 runtime 빌드, push 및 생성 |
| **4: 에이전트 호출** | 5개 세션(single-turn 및 multi-turn)을 실행하고 CloudWatch 수집을 위해 60초 대기 |
| **사용자 지정 evaluator** | `HRResponseSimilarity`(TRACE) 및 `HRAssertionChecker`(SESSION) 사용자 지정 evaluator 생성 |
| **5: EvaluationClient** | 기본 제공 및 사용자 지정 evaluator를 사용해 세션 ID별로 각 세션 평가 |
| **6: OnDemandEvaluationDatasetRunner** | 5개 시나리오 dataset을 정의하고 시나리오별로 에이전트를 호출한 후 180초 대기하여 모든 시나리오 평가 |
| **7: BatchEvaluationRunner** | 동일한 dataset을 `BatchEvaluationRunner`로 실행하여 evaluator별 집계 점수 산출 |
| **정리** | (주석 처리됨) agent runtime 삭제 |

### `EvaluationClient` 직접 사용

```python
from bedrock_agentcore.evaluation import EvaluationClient, ReferenceInputs
from datetime import timedelta

ec = EvaluationClient(region_name="us-east-1")

results = ec.run(
    evaluator_ids=["Builtin.Correctness", "Builtin.GoalSuccessRate", MY_CUSTOM_EVAL_ID],
    session_id="<session-id>",
    agent_id="<agent-id>",
    look_back_time=timedelta(hours=2),
    reference_inputs=ReferenceInputs(
        expected_response="Employee EMP-001 has 10 remaining PTO days.",
        assertions=["Agent called get_pto_balance", "Agent reported 10 remaining days"],
        expected_trajectory=["get_pto_balance"],
    ),
)
```

### `OnDemandEvaluationDatasetRunner` 직접 사용

```python
from bedrock_agentcore.evaluation import (
    Dataset, PredefinedScenario, Turn,
    EvaluationRunConfig, EvaluatorConfig,
    OnDemandEvaluationDatasetRunner,
    CloudWatchAgentSpanCollector,
)

dataset = Dataset(scenarios=[
    PredefinedScenario(
        scenario_id="pto-check",
        turns=[Turn(
            input="What is the PTO balance for EMP-001?",
            expected_response="EMP-001 has 10 remaining PTO days.",
        )],
        expected_trajectory=["get_pto_balance"],
        assertions=["Agent reported 10 remaining PTO days"],
    ),
])

runner = OnDemandEvaluationDatasetRunner(region="us-east-1")
result = runner.run(
    config=EvaluationRunConfig(
        evaluator_config=EvaluatorConfig(evaluator_ids=["Builtin.Correctness"]),
        evaluation_delay_seconds=180,
    ),
    dataset=dataset,
    agent_invoker=my_invoker_fn,
    span_collector=CloudWatchAgentSpanCollector(log_group_name=CW_LOG_GROUP, region="us-east-1"),
)
```

### `BatchEvaluationRunner` 직접 사용

```python
from bedrock_agentcore.evaluation import (
    BatchEvaluationRunner,
    BatchEvaluationRunConfig,
    BatchEvaluatorConfig,
    CloudWatchDataSourceConfig,
)

config = BatchEvaluationRunConfig(
    batch_evaluation_name="my_batch_eval",
    evaluator_config=BatchEvaluatorConfig(
        evaluator_ids=["Builtin.Correctness", "Builtin.GoalSuccessRate"],
    ),
    data_source=CloudWatchDataSourceConfig(
        service_names=[SERVICE_NAME],
        log_group_names=[LOG_GROUP],
        ingestion_delay_seconds=180,
    ),
    polling_timeout_seconds=1800,
    polling_interval_seconds=30,
)

runner = BatchEvaluationRunner(region="us-east-1")
result = runner.run_dataset_evaluation(
    config=config,
    dataset=dataset,
    agent_invoker=my_invoker_fn,
)

print(f"Status: {result.status}")
for summary in result.evaluation_results.evaluator_summaries:
    print(f"  {summary.evaluator_id}: avg={summary.statistics.average_score}")
```

---

## 시뮬레이션 기반 multi-turn 평가

위의 평가 기법은 미리 정의된 시나리오와 script로 작성된 사용자 입력을 사용합니다.
수동 작업을 줄이면서 dataset을 구성하는 또 다른 방법은 사용자를 시뮬레이션하여
시뮬레이션 dataset을 만드는 것입니다. 사용자 시뮬레이션에서는 LLM 기반 actor가
에이전트와 상호 작용하는 최종 사용자 역할을 수행합니다. actor의 profile과 목표를
정의하면 목표를 달성하거나 turn 제한에 도달할 때까지 actor가 에이전트와의
multi-turn 대화를 진행합니다. 자세한 내용과 테스트 방법은 다음 companion 노트북을 참조하세요.

**[`Strands-AgentCore-ShoppingConcierge.ipynb`](../03-advanced/02-simulating-agent-interactions/Strands-AgentCore-ShoppingConcierge.ipynb)**

이 노트북은 Shopping Concierge 에이전트를 배포하고 5가지 고객 시뮬레이션
시나리오(헤드폰 구매, 주문 추적, 반품, 여러 품목의 장바구니, 예산 적합성)를 실행합니다.
또한 단일 `StartBatchEvaluation` 호출로 모든 세션을 채점하며, actor에는
`boto3` 및 Bedrock Converse API를 사용합니다.

---

## 파일

| 파일 | 설명 |
|---|---|
| `groundtruth_evaluations.ipynb` | 기본 튜토리얼 노트북 |
| `hr_assistant_agent.py` | HR Assistant 에이전트 source(5개 도구를 사용하는 Strands 에이전트) |
| `deploy_hr_assistant_agent.py` | `agentcore` CLI를 사용하는 배포 script |
| `requirements.txt` | Python 종속성 |
| `.gitignore` | 생성된 `.bedrock_agentcore.yaml` 무시 |

---

## Ground truth를 사용하는 사용자 지정 evaluator

사용자 지정 evaluator를 사용하면 자연어로 평가 기준을 정의할 수 있습니다. 서비스는
채점 전에 `ReferenceInputs`의 **ground truth placeholder**를 대입합니다.

### Placeholder 참조

| 수준 | Placeholder | 입력 출처 |
|---|---|---|
| TRACE | `{assistant_turn}` | 해당 turn에 대한 에이전트의 실제 응답 |
| TRACE | `{expected_response}` | `ReferenceInputs.expected_response` |
| TRACE | `{context}` | 해당 turn 이전의 대화 컨텍스트 |
| SESSION | `{actual_tool_trajectory}` | 세션 중 에이전트가 호출한 도구 |
| SESSION | `{expected_tool_trajectory}` | `ReferenceInputs.expected_trajectory` |
| SESSION | `{assertions}` | `ReferenceInputs.assertions` |
| SESSION | `{available_tools}` | 에이전트에서 사용할 수 있는 도구 |

### 이 튜토리얼의 사용자 지정 evaluator

| Evaluator | 수준 | 사용하는 placeholder | 사용 위치 |
|---|---|---|---|
| `HRResponseSimilarity` | TRACE | `{assistant_turn}`, `{expected_response}` | EvaluationClient(5단계), DatasetRunner(6단계) |
| `HRAssertionChecker` | SESSION | `{actual_tool_trajectory}`, `{expected_tool_trajectory}`, `{assertions}` | EvaluationClient(5단계, multi-turn), DatasetRunner(6단계) |

---

## 기본 제공 evaluator

| Evaluator | 수준 | 필요한 ground truth |
|---|---|---|
| `Builtin.Correctness` | TRACE | `expected_response` |
| `Builtin.Helpfulness` | TRACE | 없음 |
| `Builtin.ResponseRelevance` | TRACE | 없음 |
| `Builtin.GoalSuccessRate` | SESSION | `assertions` |
| `Builtin.TrajectoryExactOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.TrajectoryInOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.TrajectoryAnyOrderMatch` | SESSION | `expected_trajectory` |

**평가 수준:**
- **TRACE**: 대화 turn(에이전트 응답)당 하나의 결과
- **SESSION**: 전체 대화당 하나의 결과

---

## 리소스 정리

노트북의 cleanup cell에서 주석을 제거하고 실행하거나 AWS CLI를 사용합니다.

```bash
# Agent Runtime 삭제
aws bedrock-agentcore-control delete-agent-runtime \
    --agent-runtime-id <AGENT_ID> \
    --region <REGION>
```

---

## 추가 리소스

- [Ground truth 평가](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html)
- [Dataset 기반 평가](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations.html)
- [Batch 평가](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations.html)
- [사용자 시뮬레이션](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/user-simulation.html)
- [Amazon Bedrock AgentCore 개발자 가이드](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Strands Agents SDK](https://strandsagents.com/)
