# AgentCore Evaluations 유틸리티

CloudWatch trace 데이터를 추출하고 AgentCore Evaluation DataPlane API를 사용하여 에이전트 세션을 평가하는 Python 유틸리티입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 구성

CloudWatch Logs 및 AgentCore Evaluation API에 액세스할 수 있는 AWS 자격 증명을 구성합니다.

```bash
aws configure
```

또는 환경 변수를 설정합니다.

```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

## 사용법

```python
from utils import EvaluationClient

# Client 초기화
client = EvaluationClient(region="us-east-1")

# 세션 평가
results = client.evaluate_session(
    session_id="your-session-id",
    evaluator_ids=["Builtin.Helpfulness"],
    agent_id="your-agent-id",
    region="us-east-1"
)

# 결과 출력
for result in results.results:
    print(f"{result.evaluator_name}: {result.value} - {result.label}")
    print(f"Explanation: {result.explanation}")
```

## 여러 evaluator 지원

한 번의 호출로 여러 evaluator를 사용해 평가합니다.

```python
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.Helpfulness", "Builtin.Accuracy", "Builtin.Harmfulness"],
    agent_id="agent-id",
    region="us-east-1"
)
```

## 자동 저장 및 메타데이터

입출력 파일을 저장하고 실험을 추적합니다.

```python
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.Helpfulness"],
    agent_id="agent-id",
    region="us-east-1",
    auto_save_input=True,   # evaluation_input/에 저장
    auto_save_output=True,  # evaluation_output/에 저장
    auto_create_dashboard=True,  # 로컬에서 사용할 수 있는 HTML 대시보드용 데이터 생성
    metadata={. # 어떤 값이든 그대로 전달
        "experiment": "baseline",
        "description": "Initial evaluation run"
    }
)
```

입력 파일에는 정확한 재현을 위해 API로 전송한 span만 포함됩니다. 출력 파일에는 메타데이터를 포함한 전체 결과가 저장됩니다.

## 구현 세부 정보

이 유틸리티는 CloudWatch Logs에서 OpenTelemetry span과 runtime 로그를 쿼리하고, 관련 데이터(gen_ai 속성 및 대화 로그)를 필터링한 뒤 평가 API로 전송합니다. 기본 조회 기간은 7일이며, 평가당 최대 항목 수는 1,000개입니다.
