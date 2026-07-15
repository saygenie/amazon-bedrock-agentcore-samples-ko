# 프로그래밍 방식(코드 기반) evaluator

## 소개

이 튜토리얼에서는 Amazon Bedrock AgentCore Evaluations로 **사용자 지정 코드 기반 evaluator**를 구축하고 실행하는 방법을 보여줍니다. 코드 기반 evaluator는 LLM을 판정자로 사용하지 않고 사용자가 작성한 AWS Lambda 함수에 채점을 위임합니다. 따라서 LLM이 느슨하게 해석할 수 있는 정확한 비즈니스 규칙, 형식 제약 조건 또는 데이터 검증 요구 사항을 결정론적이고 저렴하며 완전하게 사용자 지정할 수 있는 평가 로직으로 구현할 수 있습니다.

이 튜토리얼에서는 **온디맨드 평가와 온라인 평가** 모두에서 코드 기반 evaluator를 사용하는 방법을 보여줍니다. 또한 기본 제공 LLM evaluator와 함께 사용하여 두 유형이 하나의 혼합 평가 실행에서 어떻게 함께 작동하는지 설명합니다.

---

## AgentCore CLI로 설정

에이전트를 가장 빠르게 bootstrap하고 배포하는 방법은 [AgentCore CLI](https://github.com/aws/agentcore-cli)(`0.11.0`)를 사용하는 것입니다.

### 사전 요구 사항

- **Node.js** 20.x 이상
- **uv** 0.4+(Python 패키지 관리자)
- 자격 증명이 구성된 **AWS CLI** 2.x
- 로컬에서 실행 중인 **Docker**(agent container 빌드용)
- **Git** 2.x

### CLI 설치

```bash
npm install -g @aws/agentcore@0.11.0
agentcore --version   # 0.11.0이 출력되어야 함
```

### AWS 자격 증명 구성

```bash
aws configure
aws sts get-caller-identity   # 자격 증명 확인
```

IAM 사용자/role에는 AgentCore Runtime, AgentCore Evaluations, Lambda,
CloudWatch Logs, ECR, IAM 및 Bedrock에 대한 권한이 필요합니다.

### 에이전트 생성 및 배포

```bash
# 새 AgentCore 프로젝트 scaffold 생성
agentcore create --name HRAssistant --framework Strands --model-provider Bedrock --defaults

# HR Assistant 구현 복사
cp hr_assistant_agent.py app/HRAssistant/main.py

# 로컬 테스트
agentcore dev

# AWS에 배포(container 빌드, ECR push, AgentCore Runtime 생성)
agentcore deploy
```

`agentcore deploy`가 완료되면 출력에 표시된 **Runtime ID**와 **ARN**을 기록해 둡니다.

### CLI로 코드 기반 evaluator 등록

`agentcore add evaluator`는 프로젝트의 `agentcore.json`에 evaluator를 등록합니다.
`agentcore deploy`를 실행하면 AWS에 evaluator가 생성됩니다.

```bash
# TRACE 수준 코드 기반 evaluator 등록
agentcore add evaluator \
  --name HRResponseLength \
  --level TRACE \
  --type code-based \
  --lambda-arn arn:aws:lambda:<region>:<account-id>:function:hr-response-length \
  --timeout 30

# SESSION 수준 코드 기반 evaluator 등록
agentcore add evaluator \
  --name HRFactChecker \
  --level SESSION \
  --type code-based \
  --lambda-arn arn:aws:lambda:<region>:<account-id>:function:hr-fact-checker \
  --timeout 60
```

### CLI로 온디맨드 평가 실행

**Standalone mode**(프로젝트 불필요)에서는 이미 배포된 리소스의 전체 ARN과 함께
`--runtime-arn` 및 `--evaluator-arn`을 사용합니다. 어느 디렉터리에서나 실행할 수 있습니다.

```bash
agentcore run eval \
  --runtime-arn <agent-runtime-arn> \
  --evaluator-arn <hr-response-length-evaluator-arn> \
  --evaluator-arn <hr-fact-checker-evaluator-arn> \
  --session-id <session-id> \
  --region <aws-region>
```

하나의 명령에서 코드 기반(`--evaluator-arn`) evaluator와 기본 제공(`--evaluator`) evaluator를 함께 사용합니다.

```bash
agentcore run eval \
  --runtime-arn <agent-runtime-arn> \
  --evaluator-arn <hr-response-length-evaluator-arn> \
  --evaluator-arn <hr-fact-checker-evaluator-arn> \
  --evaluator Builtin.Correctness \
  --evaluator Builtin.Helpfulness \
  --session-id <session-id> \
  --region <aws-region>
```

**Project mode**(배포된 프로젝트 디렉터리 내부)에서는 `agentcore.json`의 evaluator 이름을 사용합니다.
먼저 `agentcore deploy`를 실행해야 합니다.

```bash
agentcore run eval \
  --runtime HRAssistant \
  --evaluator HRResponseLength \
  --evaluator HRFactChecker \
  --session-id <session-id>
```

### CLI로 온라인 평가 추가

`agentcore add online-eval`은 `agentcore.json`에 config를 추가하며, `agentcore deploy`를 실행하면
AWS에 생성됩니다. 프로젝트 디렉터리 내부에서 실행하세요.

```bash
# sampling-rate는 백분율(0.01~100)
agentcore add online-eval \
  --name hr_online_eval \
  --runtime HRAssistant \
  --evaluator HRResponseLength \
  --evaluator HRFactChecker \
  --sampling-rate 100 \
  --enable-on-create
```

> 프로젝트 디렉터리 없이 노트북(10단계)과 boto3 SDK를 사용하여 프로그래밍 방식으로
> 온라인 평가 config를 생성할 수도 있습니다.

---

## 핵심 개념

### 코드 기반 evaluator와 기본 제공 evaluator 비교

| | 기본 제공(LLM-as-judge) | 코드 기반(Lambda) |
|---|---|---|
| **판정자** | 고정된 평가 prompt를 사용하는 LLM | 사용자 지정 Lambda 함수 |
| **출력** | 설명이 포함된 확률적 점수 | 결정론적 점수 |
| **비용** | 평가마다 LLM inference | Lambda 호출 |
| **적합한 용도** | 미묘한 차이를 반영하는 정성 평가 | 정확한 데이터 검증, 비즈니스 규칙 |
| **사용자 지정 가능 여부** | 제한적(고정된 prompt template) | 완전하게 사용자 지정 가능 |

### Evaluator 수준

| 수준 | 호출 시점 | 사용 시점 |
|---|---|---|
| **TRACE** | 에이전트 응답(turn)마다 한 번 | 길이, 형식 등 응답별 검사 |
| **SESSION** | 대화 세션마다 한 번 | 모든 turn에 걸친 end-to-end 사실 정확성 검사 |

### SDK v1.6 Lambda 계약

SDK v1.6에 새로 추가된 `@custom_code_based_evaluator()` decorator는 raw Lambda event를 typed `EvaluatorInput` 및 `EvaluatorOutput` 객체로 변환하여 이전 버전의 raw dict 기반 패턴을 대체합니다.

```python
from bedrock_agentcore.evaluation import (
    EvaluatorInput, EvaluatorOutput, custom_code_based_evaluator,
)

@custom_code_based_evaluator()
def lambda_handler(input: EvaluatorInput, context) -> EvaluatorOutput:
    # input.session_spans      — 세션의 OTel span 목록
    # input.evaluation_level   — "TRACE" 또는 "SESSION"
    # input.target_trace_id    — TRACE level에서 service가 설정
    return EvaluatorOutput(value=1.0, label="PASS", explanation="...")
```

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Notebook                                                                    │
│                                                                              │
│  1. Deploy Lambda functions (hr-response-length, hr-fact-checker)            │
│  2. Register evaluators via bedrock-agentcore-control                        │
│  3a. On-demand: EvaluationClient.run(session_id, evaluator_ids)             │
│  3b. Dataset: OnDemandEvaluationDatasetRunner.run(dataset, agent_invoker)   │
│  3c. Online: create_online_evaluation_config (auto-evaluates all sessions)  │
└────────────────┬────────────────────────────────────────────────────────────┘
                 │
     ┌───────────▼────────────┐        ┌──────────────────────────────┐
     │  AgentCore Runtime      │        │  AgentCore Evaluations DP   │
     │  HR Assistant agent     │──OTel─▶│  bedrock-agentcore          │
     │  (Strands Agents)       │        │                             │
     └─────────────────────────┘        │   ┌──────────────────────┐  │
                                        │   │  Builtin LLM evals   │  │
     ┌─────────────────────────┐        │   │  Correctness         │  │
     │  CloudWatch Logs        │        │   │  Helpfulness         │  │
     │  /aws/bedrock-agentcore/│        │   │  ResponseRelevance   │  │
     │  runtimes/<agent-id>    │        │   └──────────────────────┘  │
     └─────────────────────────┘        │   ┌──────────────────────┐  │
                                        │   │  Code-based Lambda   │  │
     ┌─────────────────────────┐        │   │  HRResponseLength    │  │
     │  AWS Lambda             │◀───────│   │  HRFactChecker       │  │
     │  hr-response-length     │        │   └──────────────────────┘  │
     │  hr-fact-checker        │        └─────────────────────────────┘
     └─────────────────────────┘
```

**평가 흐름:**
1. 에이전트가 호출되면 OTel span이 CloudWatch에 기록됨
2. `EvaluationClient` 또는 `OnDemandEvaluationDatasetRunner`가 CloudWatch에서 span 수집
3. 서비스가 각 evaluator 호출. 기본 제공 evaluator는 LLM inference를 실행하고, 코드 기반 evaluator는 span payload와 함께 Lambda 호출
4. **온라인 평가**에서는 AgentCore가 log group을 지속적으로 감시하고 명시적인 trigger 없이 새 세션을 자동 평가
5. 모든 결과를 집계하여 반환하거나(온디맨드) 온라인 평가 결과 log group에 기록

---

## 사전 요구 사항

- `agentcore-evals` Jupyter kernel이 구성된 **Python 3.10+**(상위 README 참조)
- 로컬에서 실행 중인 **Docker**(agent container image 빌드용)
- 다음 권한이 있는 **AWS 자격 증명**:
  - `bedrock-agentcore:*`: runtime 및 평가
  - `bedrock-agentcore-control:*`: evaluator 등록 및 온라인 평가 config 관리
  - `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:AddPermission`, `lambda:GetFunction`
  - `logs:FilterLogEvents`, `logs:DescribeLogGroups`: CloudWatch span 수집
  - `ecr:*`: 에이전트의 container image
  - `iam:*`: 에이전트 및 온라인 평가용 실행 role 생성
- **IAM role** 이름은 `AgentCoreLambdaExecutionRole`이며 `AWSLambdaBasicExecutionRole`이 연결되어 있어야 함
- 노트북 kernel에 설치된 **bedrock-agentcore >= 1.6.0**

> **팁:** 이미 `groundtruth_evaluations.ipynb`를 실행했다면 에이전트가 배포되어 있고 해당 정보가 `%store`를 통해 저장되어 있습니다. 이 노트북은 에이전트를 자동으로 다시 로드하고 재배포를 건너뜁니다.

---

## 파일

| 파일 | 설명 |
|---|---|
| `programmatic_evaluators.ipynb` | 기본 튜토리얼 노트북(standalone, end-to-end) |
| `hr_assistant_agent.py` | HR Assistant Strands 에이전트(groundtruth 튜토리얼과 동일) |
| `Dockerfile` | 에이전트의 container 정의(3단계 신규 배포 및 `agentcore deploy`에서 사용) |
| `requirements.txt` | Python 종속성(`bedrock-agentcore>=1.6.0`) |
| `lambdas/hr_response_length/lambda_function.py` | 응답 길이 evaluator Lambda |
| `lambdas/hr_fact_checker/lambda_function.py` | HR 사실 확인 evaluator Lambda |

---

## 이 튜토리얼에서 구축하는 evaluator

### HRResponseLength(TRACE 수준)

각 에이전트 응답이 50~600자인지 검사합니다. 50자보다 짧은 응답은 불완전할 가능성이 높고, 600자보다 길면 설명이 지나치게 많을 수 있습니다. 측정하기 전에 thinking block(`<thinking>...</thinking>`)을 제거합니다.

- **수준:** TRACE. 에이전트 응답마다 한 번 평가
- **Lambda:** `hr-response-length`
- **반환값:** 범위 내이면 `1.0`(PASS), 그렇지 않으면 `0.0`(FAIL)
- **사용 위치:** 온디맨드 평가(7, 8단계) 및 온라인 평가(10단계)

### HRFactChecker(SESSION 수준)

HR Assistant의 응답에 mock data store의 정확한 사실이 포함되어 있는지 결정론적으로 검증합니다. LLM inference 없이 정확한 pattern matching을 사용합니다.

- **수준:** SESSION. 대화마다 한 번 평가
- **Lambda:** `hr-fact-checker`
- **검사하는 사실:**
  - PTO 잔여 일수: EMP-001(10일), EMP-002(3일), EMP-042(13일)
  - 급여 명세서: 직원/기간별 총 급여와 실수령액
  - PTO 요청 ID 형식 `PTO-2026-NNN`
  - 정책 정보: PTO 15일 적립, 2일 전 사전 통보, 401k 4% match, 건강 보험료 90% 지원
- **반환값:** 적용 가능한 검사 중 통과한 비율(0.0~1.0), `PASS`, `PARTIAL`, `FAIL` 또는 `SKIP` label
- **사용 위치:** 온디맨드 평가(7, 8단계) 및 온라인 평가(10단계)

---

## 혼합 evaluator 집합

노트북은 5개의 evaluator와 함께 `OnDemandEvaluationDatasetRunner`를 동시에 실행합니다.

| Evaluator | 유형 | 수준 |
|---|---|---|
| `Builtin.Correctness` | 기본 제공 LLM | TRACE |
| `Builtin.Helpfulness` | 기본 제공 LLM | TRACE |
| `Builtin.ResponseRelevance` | 기본 제공 LLM | TRACE |
| `HRResponseLength` | 코드 기반 Lambda | TRACE |
| `HRFactChecker` | 코드 기반 Lambda | SESSION |

5개 evaluator의 결과를 시나리오별로 수집하여 정성적 LLM 점수와 결정론적 코드 점수를 나란히 비교할 수 있습니다.

---

## 코드 기반 evaluator를 사용한 온라인 평가

노트북의 10단계에서는 세션마다 명시적으로 API를 호출하지 않아도 AgentCore가 모든 실시간 에이전트 세션을
자동 평가하는 지속적 평가 모드인 **온라인 평가**를 보여줍니다.

### 작동 방식

1. 코드 기반 evaluator 등록(4~6단계, 온디맨드 평가와 동일)
2. `create_online_evaluation_config`를 통해 온라인 평가 config 생성:
   - 에이전트의 CloudWatch log group 지정
   - 표본 추출 비율 설정(0~100%)
   - evaluator ID 나열(코드 기반 및/또는 기본 제공)
   - 서비스가 수임할 수 있는 IAM 실행 role 제공
3. config 활성화. AgentCore가 log group 감시 시작
4. 새로운 모든 에이전트 세션 자동 평가
5. 온라인 평가 결과가 CloudWatch log group에 표시됨

### Evaluator 잠금

**활성화된** 온라인 평가 config에서 코드 기반 evaluator를 참조하면 AgentCore가 해당 evaluator를
자동으로 **잠급니다**. 잠긴 evaluator는 수정하거나 삭제할 수 없습니다. 업데이트하려면 다음 순서를 따르세요.

```
disable/delete online eval config
         ↓
update evaluator Lambda or re-register
         ↓
re-create online eval config
```

### 온디맨드 평가와 온라인 평가 비교

| 항목 | 온디맨드 | 온라인 |
|---|---|---|
| Trigger | 세션마다 명시적으로 실행 | 호출할 때마다 자동 실행 |
| 설정 | `EvaluationClient.run()` 또는 `OnDemandEvaluationDatasetRunner` | `create_online_evaluation_config` 한 번 실행 |
| 코드 기반 evaluator | 지원 | 지원 |
| Evaluator 잠금 | 아니요 | 예, config가 활성화된 동안 잠김 |
| 적합한 용도 | CI/CD, ad-hoc 디버깅 | 지속적인 프로덕션 모니터링 |

### AgentCore CLI 단축 명령

```bash
# sampling-rate는 백분율(0.01~100), 50 = 세션의 50% 평가
agentcore add online-eval \
  --name my_online_eval \
  --runtime MyAgent \
  --evaluator MyCodeEvaluator \
  --sampling-rate 50 \
  --enable-on-create
```

---

## 샘플 prompt

Dataset에는 `HRFactChecker`가 검증하는 사실을 테스트하는 5가지 시나리오가 포함되어 있습니다.

| 시나리오 | Prompt | 기대 동작 |
|---|---|---|
| `pto-balance-check` | "What is the current PTO balance for employee EMP-001?" | 에이전트가 `get_pto_balance`를 호출하고 잔여 일수 10일을 보고 |
| `submit-pto-request` | "Please submit a PTO request for EMP-001 from 2026-04-14 to 2026-04-16 for a family vacation." | 에이전트가 `submit_pto_request`를 호출하고 `PTO-2026-NNN` ID를 반환 |
| `pay-stub-lookup` | "Can you pull up the January 2026 pay stub for employee EMP-001?" | 에이전트가 `get_pay_stub`을 호출하고 총 급여 $8,333.33와 실수령액 $5,362.50을 보고 |
| `pto-policy-lookup` | "What is the company PTO policy?" | 에이전트가 `lookup_hr_policy`를 호출하고 15일 적립 및 2일 전 사전 통보를 언급 |
| `health-benefits` | "Can you tell me about the company health insurance options?" | 에이전트가 `get_benefits_summary`를 호출하고 보험료 90% 지원을 언급 |

원격 근무 정책, 육아 휴직, 401k 등 더 많은 HR 주제를 테스트하도록 dataset에 시나리오를 추가할 수 있습니다.

---

## 노트북 단계별 안내

| 단계 | 설명 |
|---|---|
| 1 | 종속성 설치(`bedrock-agentcore>=1.6.0`) |
| 2 | AWS 세션, 리전 및 Lambda role ARN 구성 |
| 3 | 에이전트 설정. `%store`(groundtruth 노트북)에서 다시 로드하거나 boto3로 새로 배포 |
| 4 | `@custom_code_based_evaluator()` decorator를 사용하여 Lambda evaluator 함수 정의 |
| 5 | Lambda 함수 배포(bedrock-agentcore SDK + pydantic 포함) |
| 6 | `bedrock-agentcore-control` boto3 서비스를 통해 evaluator 등록 |
| 7 | `EvaluationClient`를 사용한 온디맨드 평가(코드 기반 + 기본 제공 evaluator) |
| 8 | `OnDemandEvaluationDatasetRunner`를 사용한 dataset 평가(혼합 evaluator 집합) |
| 9 | 결과 검사 및 비교(시나리오별 표 + 집계 점수 비교) |
| **10** | **`create_online_evaluation_config`를 사용한 온라인 평가(코드 기반 evaluator, 자동 trigger)** |
| 11 | 리소스 정리. Lambda 함수, evaluator record, 온라인 평가 config 및 agent runtime 삭제 |

---

## Span 구조(Strands/AgentCore OTel)

Lambda 함수는 평가 서비스로부터 OTel span을 수신합니다. 주요 field는 다음과 같습니다.

```
span.name                                  e.g. "invoke_agent", "llm_call"
span.attributes.gen_ai.operation.name      "execute_tool" for tool-call spans
span.attributes.gen_ai.tool.name           tool name (e.g. "get_pto_balance")
span.span_events[*]
  .body.output.messages[*]
  .content.message                         final agent response text
```

`EvaluatorInput.session_spans`는 전체 목록을 제공합니다. TRACE 수준에서는 `EvaluatorInput.target_trace_id`가 평가 범위를 적용할 trace를 식별합니다.

---

## 코드 기반 evaluator를 사용해야 하는 경우

- **정확한 데이터 검증**: 응답에 특정 숫자, ID 또는 코드가 표시되는지 검사
- **형식 준수**: 응답 길이, 구조 또는 형식 제약 조건 검증
- **비즈니스 규칙 적용**: LLM이 느슨하게 해석할 수 있는 도메인별 규칙 구현
- **대규모 평가**: 모든 프로덕션 세션에서 실행되는 평가 비용 절감
- **규제 요구 사항**: 필수 공개 정보 또는 disclaimer가 항상 표시되는지 확인
- **지속적 모니터링**: 온라인 평가와 결합하여 자동화된 프로덕션 품질 gate 구성

코드 기반 evaluator는 **온디맨드**(`EvaluationClient`,
`OnDemandEvaluationDatasetRunner`) 및 **온라인**(`create_online_evaluation_config`) 평가를 모두 지원합니다.

---

## 리소스 정리

생성된 AWS 리소스를 제거하려면 다음을 실행합니다.

```python
# 1. 먼저 온라인 평가 config 비활성화(evaluator 잠금 해제)
cp_client.update_online_evaluation_config(
    onlineEvaluationConfigId=ONLINE_EVAL_CONFIG_ID,
    enableOnCreate=False,
)
cp_client.delete_online_evaluation_config(onlineEvaluationConfigId=ONLINE_EVAL_CONFIG_ID)

# 2. Lambda 함수 삭제
for fn in ["hr-response-length", "hr-fact-checker"]:
    lambda_client.delete_function(FunctionName=fn)

# 3. Evaluator 등록 삭제(현재 잠금 해제됨)
for name, eid in CODE_EVAL_IDS.items():
    cp_client.delete_evaluator(evaluatorId=eid)

# 4. Agent Runtime 삭제(이 노트북에서 배포한 경우에만)
if not _agent_loaded:
    agentcore_control.delete_agent_runtime(agentRuntimeId=AGENT_ID)
```

또는 노트북에서 cleanup cell(11단계)을 실행합니다. 실수로 삭제하는 것을 방지하기 위해 기본적으로 주석 처리되어 있습니다.

---

## 다음 단계

- 에이전트와 데이터 모델의 발전에 맞춰 추가 비즈니스 규칙으로 `HRFactChecker` 확장
- 코드 기반 evaluator를 `EvaluationClient`와 결합하여 특정 프로덕션 세션 검증
- 모든 배포에서 추가 비용 없이 regression 테스트를 수행하도록 CI/CD pipeline에 코드 기반 evaluator 추가
- 낮은 표본 추출 비율(예: 10%)로 온라인 평가를 사용하여 트래픽이 많은 에이전트를 비용 효율적으로 모니터링
- `EvaluationClient`와 기본 제공 evaluator를 사용하는 ground truth 기반 평가는 [groundtruth 튜토리얼](../05-groundtruth-based-evalautions/) 참조
