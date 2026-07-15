# AgentCore Optimization 튜토리얼 — HR Assistant

## 개요

이 튜토리얼에서는 에이전트의 기준 성능을 측정하고, AI 기반 권장 사항을 생성하고, 이를 Configuration Bundle로 패키징한 다음, 실시간 A/B 테스트로 개선 효과를 검증하는 전체 **Amazon Bedrock AgentCore Optimization** 워크플로를 살펴봅니다.

데모 에이전트는 Acme Corp 직원의 PTO 요청, 정책 조회, 복리후생 문의 및 급여 명세서 검색을 처리하는 **HR Assistant**입니다.

### 학습 내용

| 단계 | 주요 개념 |
|-------|-----------------|
| **기준 성능 평가** | 에이전트 세션에 대한 배치 평가 |
| **권장 사항** | 프로덕션 추적 데이터를 활용한 시스템 프롬프트 최적화 및 도구 설명 최적화 |
| **Configuration Bundle** | 버전이 지정된 구성 컨테이너, Runtime 구성 훅, baggage 기반 주입 |
| **A/B 테스트: Config-Bundle 라우팅** | 재배포 없는 프롬프트 수준 A/B 테스트, 온라인 평가, 통계 분석 |
| **A/B 테스트: Target-Based 라우팅** | 코드 수준 A/B 테스트, 단계적 롤아웃(90/10 카나리), 여러 Runtime 비교 |

---

## 아키텍처

```
                        ┌─────────────────────────────────────────────────────────────┐
                        │                  AgentCore Optimization Loop                 │
                        │                                                               │
                        │  1. Invoke Agent ──────────► CloudWatch Logs (OTel spans)   │
                        │                                         │                     │
                        │  2. Batch Evaluate ◄────────────────────┘                   │
                        │     GoalSuccessRate / Helpfulness / Correctness              │
                        │                │                                              │
                        │  3. Recommend ─┘  ──► Improved System Prompt                │
                        │                        Improved Tool Descriptions            │
                        │                                │                              │
                        │  4. Bundle ───────────────────►│  Configuration Bundle (C)   │
                        │                                 │  Configuration Bundle (T1)  │
                        │                                 │                             │
                        │  5a. A/B Test ─────────────────┘                             │
                        │      Config-Bundle Routing: same runtime, different prompts  │
                        │                                                               │
                        │  5b. A/B Test (target-based)                                 │
                        │      Target Routing: different runtimes (v1 vs v2)           │
                        └─────────────────────────────────────────────────────────────┘

Config-Bundle A/B Architecture:

  User ──► [Gateway] ──50%──► [Config Bundle C  → HR Runtime v1] ──► CloudWatch
                  │                                                         │
                  └──50%──► [Config Bundle T1 → HR Runtime v1] ──► CloudWatch
                                                                            │
                                                              [Online Eval] ┘ ──► A/B Results

Target-Based A/B Architecture (Phased Rollout):

  User ──► [Gateway] ──90%──► [Target HRAgentV1 → HR Runtime v1 (stable)] ──► CloudWatch
                  │                                                                    │
                  └──10%──► [Target HRAgentV2 → HR Runtime v2 (canary)]  ──► CloudWatch
                                                                                       │
                                                                 [Online Eval v1+v2] ──┘ ──► A/B Results
```

### 주요 구성 요소

| 구성 요소 | 서비스 | 용도 |
|-----------|---------|---------|
| AgentCore Runtime | `bedrock-agentcore-control` | HR Assistant 컨테이너 호스팅 |
| Configuration Bundle | `bedrock-agentcore-control` | 버전이 지정된 시스템 프롬프트 저장 |
| Batch Evaluation | `bedrock-agentcore` (DP) | 이전 세션의 오프라인 점수 산정 |
| Recommendation | `bedrock-agentcore` (DP) | AI가 생성한 프롬프트 및 도구 개선 사항 |
| Gateway + Targets | `bedrock-agentcore-control` | A/B 테스트를 위한 트래픽 라우팅 |
| Online Eval Config | `bedrock-agentcore-control` | 지속적인 자동 세션 점수 산정 |
| A/B Test | `bedrock-agentcore` (DP) | 트래픽 분할 및 통계 비교 |

---

## 시작하기

### 사전 요구 사항

- Amazon Bedrock AgentCore 액세스가 활성화된 AWS 계정
- 구성된 AWS CLI: `aws configure`(또는 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` 설정)
- IAM 호출자 권한([Optimization 사전 요구 사항](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization-prereqs.html) 참조):
  - `bedrock-agentcore:GetConfigurationBundle*`, `ListConfigurationBundleVersions`, `CreateConfigurationBundle`, `UpdateConfigurationBundle`, `DeleteConfigurationBundle` (ConfigurationBundles)
  - `bedrock-agentcore:StartRecommendation`, `GetRecommendation` (Recommendations)
  - `bedrock-agentcore:StartABTest`, `StopABTest`, `GetABTest`, `DeleteABTest`, `ListABTests` (ABTesting)
  - `logs:GetLogEvents`, `FilterLogEvents`, `StartQuery`, `GetQueryResults` 권한: `runtimes/*` 로그 그룹(CloudWatchLogs)
  - A/B 테스트 실행 역할을 생성하기 위한 `iam:CreateRole`, `AttachRolePolicy`, `PassRole`
- Python 3.10 이상

### 옵션 1: Jupyter Notebook

전체 튜토리얼을 대화형으로 실행합니다.

```bash
# 필요한 경우 Jupyter 설치
pip install jupyter

# 종속성 설치(노트북의 첫 번째 셀에서도 수행)
pip install "bedrock-agentcore>=1.7.0" "boto3>=1.43.0" requests

# 노트북 실행
jupyter notebook optimization_tutorial.ipynb
```

그런 다음 모든 셀을 위에서 아래로 실행합니다. 노트북은 실행 중에 배포 및 평가 출력을 실시간으로 표시합니다.

### 옵션 2: AgentCore CLI

동일한 워크플로를 명령줄에서 모두 실행할 수도 있습니다. 다음과 같이 CLI를 설치합니다.

```bash
npm install -g @aws/agentcore
agentcore --version   # 0.13.0 이상이 출력되어야 함
```

전체 명령 순서는 아래의 [CLI 예제](#agentcore-cli-examples) 섹션을 참조하세요.

---

<a id="agentcore-cli-examples"></a>

## AgentCore CLI 예제

다음 명령을 사용하면 노트북 워크플로를 명령줄에서 동일하게 실행할 수 있습니다.

### 1단계: HR Assistant 배포

```bash
# 새 AgentCore 프로젝트 scaffold 생성
agentcore create --name HRAssistant --framework Strands --model-provider Bedrock --defaults

# HR Assistant 구현 복사
cp hr_assistant_agent.py app/HRAssistant/main.py

# 배포 전 로컬 테스트
agentcore dev

# AWS에 배포(container 빌드, ECR push, AgentCore Runtime 생성)
agentcore deploy
# 출력의 Runtime ID 및 ARN 기록
```

### 2단계: 기준 성능 평가 실행

```bash
# 트래픽을 생성하도록 에이전트 호출
agentcore invoke \
  --runtime HRAssistant \
  --prompt "Employee ID: EMP-001. What is my PTO balance?" \
  --session-id $(python3 -c "import uuid; print(uuid.uuid4())")

# 모든 세션에서 batch evaluation 실행
agentcore run batch-evaluation \
  --runtime HRAssistant \
  --evaluator Builtin.GoalSuccessRate Builtin.Helpfulness Builtin.Correctness
```

### 3단계: 권장 사항 가져오기

```bash
# System prompt 권장 사항(GoalSuccessRate 최적화)
# 현재 prompt에는 --inline을 사용하거나 --prompt-file ./system-prompt.txt 사용
agentcore run recommendation \
  --runtime HRAssistant \
  --type system-prompt \
  --evaluator Builtin.GoalSuccessRate \
  --inline "You are an HR assistant for Acme Corp. Help employees with PTO, policies, benefits, and pay stubs."

# Tool description 권장 사항
agentcore run recommendation \
  --runtime HRAssistant \
  --type tool-description \
  --tools "get_pto_balance:Get the PTO balance for an employee" \
  --tools "get_policy:Look up an HR policy by name"
```

### 4단계: Configuration Bundle 생성

```bash
# {{runtime:<name>}} placeholder를 사용하여 control bundle 생성(원본 prompt)
agentcore add config-bundle \
  --name HRControl \
  --components '{"{{runtime:HRAssistant}}": {"configuration": {"systemPrompt": "'"$(cat original_prompt.txt)"'"}}}'
agentcore deploy

# Treatment bundle 생성(권장 prompt)
agentcore add config-bundle \
  --name HRTreatment \
  --components '{"{{runtime:HRAssistant}}": {"configuration": {"systemPrompt": "'"$(cat recommended_prompt.txt)"'"}}}'
agentcore deploy

# Version ID 보기(아래 A/B 테스트에 필요)
agentcore cb versions --bundle HRControl --json
agentcore cb versions --bundle HRTreatment --json
```

### 5a단계: A/B 테스트 — Config-Bundle 라우팅

```bash
# Gateway 생성
agentcore add gateway --name HRGateway --authorizer-type AWS_IAM

# Gateway target 생성
agentcore add gateway-target \
  --gateway HRGateway \
  --name HRAgentV1 \
  --type mcp-server \
  --runtime HRAssistant

# 온라인 평가 config 생성
agentcore add online-eval \
  --name HROnlineEval \
  --runtime HRAssistant \
  --evaluator Builtin.GoalSuccessRate Builtin.Helpfulness \
  --sampling-rate 100 \
  --enable-on-create
agentcore deploy

# Config-bundle 라우팅으로 A/B 테스트 생성(50/50 분할)
# <control-version-id> 및 <treatment-version-id>를 다음 명령에서 확인한 ID로 교체: agentcore cb versions --bundle HRControl --json
agentcore add ab-test \
  --name HRBundleABTest \
  --runtime HRAssistant \
  --control-bundle HRControl \
  --control-version <control-version-id> \
  --treatment-bundle HRTreatment \
  --treatment-version <treatment-version-id> \
  --control-weight 50 \
  --treatment-weight 50 \
  --online-eval HROnlineEval \
  --enable
agentcore deploy

# 결과 모니터링
agentcore ab-test HRBundleABTest
```

### 5b단계: A/B 테스트 — Target-Based 라우팅(단계적 롤아웃)

```bash
# 에이전트 v2 배포(새 코드 변경 사항 포함)
agentcore create --name HRAssistantV2 --framework Strands --model-provider Bedrock --defaults
cp hr_assistant_agent.py app/HRAssistantV2/main.py
# (main.py에 v2 코드 변경 사항 적용)
cd HRAssistantV2 && agentcore deploy

# v2 Gateway target 추가
agentcore add gateway-target \
  --gateway HRGateway \
  --name HRAgentV2 \
  --type mcp-server \
  --runtime HRAssistantV2

# v2용 온라인 평가 config 생성
agentcore add online-eval \
  --name HROnlineEvalV2 \
  --runtime HRAssistantV2 \
  --evaluator Builtin.GoalSuccessRate Builtin.Helpfulness \
  --sampling-rate 100 \
  --enable-on-create
agentcore deploy

# 각 Runtime 버전에 명명된 endpoint 등록(target-based 모드에 필요)
agentcore add runtime-endpoint --runtime HRAssistant   --name v1
agentcore add runtime-endpoint --runtime HRAssistantV2 --name v2
agentcore deploy

# Target-based 라우팅으로 A/B 테스트 생성(90/10 canary)
agentcore add ab-test \
  --name HRTargetABTest \
  --mode target-based \
  --control-endpoint v1 \
  --treatment-endpoint v2 \
  --control-weight 90 \
  --treatment-weight 10 \
  --control-online-eval HROnlineEval \
  --treatment-online-eval HROnlineEvalV2 \
  --enable
agentcore deploy

# Canary 결과 모니터링
agentcore ab-test HRTargetABTest

# v2가 우수하면 테스트 중지
agentcore stop ab-test HRTargetABTest
```

### 6단계: 리소스 정리

```bash
agentcore stop ab-test HRBundleABTest
agentcore stop ab-test HRTargetABTest
agentcore remove ab-test --name HRBundleABTest
agentcore remove ab-test --name HRTargetABTest
agentcore remove online-eval --name HROnlineEval
agentcore remove online-eval --name HROnlineEvalV2
agentcore remove config-bundle --name HRControl
agentcore remove config-bundle --name HRTreatment
agentcore remove gateway --name HRGateway
agentcore remove agent --name HRAssistant
agentcore remove agent --name HRAssistantV2
agentcore deploy -y
```

---

## 파일 안내

| 파일 | 설명 |
|------|-------------|
| `hr_assistant_agent.py` | Configuration Bundle 훅을 사용하는 Strands Agents 기반 HR Assistant입니다. PTO, 정책, 복리후생 및 급여 명세서를 처리합니다. |
| `deploy_agent.py` | IAM 역할을 생성하고, 종속성을 패키징하고, S3에 업로드한 후 AgentCore Runtime을 생성하는 독립 실행형 배포 스크립트입니다. `--version v1`과 `--version v2`를 지원합니다. |
| `optimization_tutorial.ipynb` | AgentCore Optimization의 모든 기능을 다루는 엔드 투 엔드 튜토리얼 노트북입니다. |

---

## 주요 개념

### Config-Bundle 라우팅과 Target-Based A/B 테스트 비교

| | Config-Bundle 라우팅 | Target-Based 라우팅 |
|---|---|---|
| **변경 대상** | 시스템 프롬프트, 구성(코드 변경 없음) | 에이전트 바이너리, 도구, 모델 |
| **재배포 필요 여부** | 필요 없음 — 요청 시 구성이 적용됨 | 필요함 — 새 Runtime이 필요함 |
| **적합한 용도** | 프롬프트 튜닝, 구성 실험 | 코드 릴리스, 버전 업그레이드 |
| **트래픽 분할** | 일반적으로 50/50 | 일반적으로 90/10 카나리 |
| **롤백** | 즉시 가능 — Bundle 버전 업데이트 | Runtime은 계속 실행되며 가중치를 이전 값으로 조정 |

### 단계적 롤아웃 워크플로(Target-Based)

```
10% canary  →  validate no regressions (errors, latency, quality drop)
      ↓
50% ramp    →  gather statistical significance
      ↓
100% promote →  complete cutover; decommission old runtime
```

### Configuration Bundle 훅

HR 에이전트는 모델을 호출할 때마다 Configuration Bundle에서 시스템 프롬프트를 읽습니다.

```python
from bedrock_agentcore.runtime import BedrockAgentCoreContext
from strands.hooks.events import BeforeModelCallEvent

def _config_bundle_hook(event: BeforeModelCallEvent) -> None:
    bundle = BedrockAgentCoreContext.get_config_bundle()
    if bundle:
        event.agent.system_prompt = bundle.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

agent.hooks.add_callback(BeforeModelCallEvent, _config_bundle_hook)
```

이 패턴을 사용하면 재배포 없이 실시간으로 프롬프트를 업데이트하고 A/B 테스트를 수행할 수 있습니다.

---

## 다음 단계

- **사용자 지정 평가기 추가**: HR 정책 준수 여부를 일관되게 검사할 수 있도록 AWS Lambda 기반 코드 평가기를 구현합니다(튜토리얼 `06-workshops/07-AgentCore-evaluations/06-programmatic_evaluators` 참조).
- **루프 자동화**: 배포 전에 회귀를 발견할 수 있도록 CI/CD에서 배치 평가를 실행합니다(튜토리얼 `06-workshops/07-AgentCore-evaluations/05-groundtruth-based-evalautions` 참조).
- **권장 사항을 반복적으로 활용**: 트래픽 배치가 완료될 때마다 권장 사항을 다시 실행하여 개선 효과를 누적합니다.
- **다중 지표 최적화**: 서로 다른 평가기를 대상으로 별도의 권장 사항 작업을 실행한 다음, 중요하게 보는 지표 간 균형이 가장 좋은 프롬프트를 선택합니다.
- **카나리 노출 확대**: Target-Based 테스트에서 개선이 확인되면 `update_ab_test`를 사용하여 처리군 가중치를 단계적으로 높입니다(10% → 25% → 50% → 100%).
- **온라인 평가 활용**: 세션마다 명시적인 API 호출을 추가하지 않고도 품질을 지속적으로 모니터링할 수 있도록 프로덕션 환경에서 온라인 평가 구성을 활성화해 둡니다.
