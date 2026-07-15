# 03 — 실행 제한

**실행 제한**을 설정하여 AgentCore Harness 에이전트가 호출 한 번에 수행할 수 있는 작업량을 제한합니다. 예측 가능한 지연 시간과 비용 상한을 설정하고 에이전트의 무한 실행을 방지하는 데 유용합니다.

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`03_execution_limits.ipynb`](03_execution_limits.ipynb) | 노트북 | 세 가지 제한 파라미터를 각각 적용하거나 함께 적용하고, 에이전트가 제한에 도달했을 때 어떤 일이 발생하는지 보여 줍니다. |

## 세 가지 제한

`invoke_harness` API는 다음 선택적 파라미터를 지원합니다.

| 파라미터 | 제어 대상 | 사용 사례 예시 |
|---|---|---|
| `maxIterations` | 에이전트 루프의 최대 반복 횟수(사고 → 행동 → 관찰 주기) | 빠르고 제한된 답변을 강제하고 여러 단계의 탐색 방지 |
| `timeoutSeconds` | 전체 호출의 실제 경과 시간 제한 | 프로덕션 환경에서 p99 지연 시간을 예측 가능하게 유지 |
| `maxTokens` | 모델이 호출 한 번에 생성할 수 있는 최대 토큰 수 | 비용을 제어하거나 응답을 간결하게 유지 |

에이전트는 **어느 하나의** 제한에 도달하는 즉시 중지됩니다. 어떤 제한에 도달했는지는 `messageStop.stopReason`에서 확인할 수 있습니다.

## 노트북에서 확인할 내용

```python
# 제한됨 - 에이전트가 응답하기 전에 도구를 한 번만 호출할 수 있음
invoke("Create 3 files with content.", maxIterations=1)

# 제한 없음 - 에이전트가 원하는 만큼 단계를 수행할 수 있음
invoke("Create 3 files with content.", maxIterations=10)

# 짧은 timeout - 작업 도중 에이전트가 중단됨
invoke("Write and run a Python script for 50 primes.", timeoutSeconds=5)

# 적은 token budget - 응답이 잘림
invoke("Explain Python history in detail.", maxTokens=10)

# 세 가지 모두 적용 - 먼저 도달한 제한이 적용됨
invoke("...", maxIterations=3, timeoutSeconds=30, maxTokens=1024)
```

## 핵심 요점

- **`maxIterations=1`**은 *동작*에 가장 큰 영향을 주는 제한입니다. 에이전트가 도구를 한 번 호출한 후 반드시 답해야 하므로 단일 실행 방식에 가까워집니다.
- **`timeoutSeconds`**는 프로덕션 **지연 시간 SLO**를 제어하는 데 적합합니다.
- **`maxTokens`**는 **비용**과 **응답 간결성**을 위한 설정이며, 에이전트 루프 자체를 단축하지는 않습니다.
- 세 가지를 모두 조합하여 강력한 가드레일을 설정하세요. 예를 들어 에이전트의 실행 시간을 30초, 반복 횟수를 5회, 출력 토큰을 2K로 엄격하게 제한할 수 있습니다.

## 실행 방법

```bash
cd 03-execution-limits
jupyter notebook 03_execution_limits.ipynb
# 또는 VSCode에서 열기
```

각 섹션은 독립적이므로 원하는 순서로 실행할 수 있습니다.

## 프로덕션 패턴

사용자 대상 에이전트에서 흔히 사용하는 패턴은 다음과 같습니다.

```python
response = client.invoke_harness(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    messages=[...],
    maxIterations=10,       # 무한 루프 제한
    timeoutSeconds=60,      # 60s SLO
    maxTokens=4096,         # 비용 제한
)
```

배치 또는 연구용 에이전트에는 제한을 생략하거나 넉넉하게 설정하세요.
