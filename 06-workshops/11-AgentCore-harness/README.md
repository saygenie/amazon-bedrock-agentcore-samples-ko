# AgentCore Harness 샘플

AgentCore Harness 샘플에 오신 것을 환영합니다.

이 폴더에는 Amazon Bedrock AgentCore Harness를 위한 Jupyter 노트북, CLI 스크립트, 애플리케이션 샘플이 있습니다.

자세한 내용은 [AWS 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)를 참조하세요.

## 사전 요구 사항

- Amazon Bedrock AgentCore에 액세스할 수 있는 AWS 계정
- 자격 증명이 구성된 AWS CLI v2
- Python 3.10+

종속성을 설치합니다.

```bash
pip install -r requirements.txt

# 또는
uv pip install -r requirements.txt
```

## 00 — 시작하기

[00-getting-started](00-getting-started) 폴더를 여세요. [README](00-getting-started/README.md) 파일에는 AgentCore CLI를 시작하는 단계별 안내가 있으며, [01_getting_started_bedrock](00-getting-started/01_getting_started_bedrock.ipynb) 노트북에서는 AWS SDK for Python (Boto3)을 사용합니다.

## 01 — 고급 예제

VPC, 파라미터, 통합 등 구체적인 구성을 보여 주는 고급 예제입니다. 각 예제는 별도의 하위 폴더에 있습니다.

## 02 — 사용 사례

AgentCore Harness로 해결할 수 있는 사용 사례입니다.

## IAM 권한

각 예제에는 다음 권한이 있는 IAM 실행 역할(`HarnessExecutionRole`)이 필요합니다.

| 권한 | 용도 |
|---|---|
| `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` | 모델 호출(Claude, Llama 등) |
| `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`, `ecr:GetAuthorizationToken` | ECR에서 사용자 지정 컨테이너 이미지 가져오기 |
| `ecr-public:GetAuthorizationToken`, `sts:GetServiceBearerToken` | Public ECR에서 이미지 가져오기 |
| `xray:PutTraceSegments`, `xray:PutTelemetryRecords` | AgentCore Observability 추적 |
| `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | CloudWatch 로그 |
| `bedrock-agentcore:*Memory*`, `bedrock-agentcore:*Browser*` 등 | AgentCore 기능(Memory, Browser, Gateway, CodeInterpreter) |

이 역할은 `bedrock-agentcore.amazonaws.com`이 역할을 수임할 수 있도록 허용하는 신뢰 정책을 사용합니다. 전체 정책 문서는 [`helper/iam.py`](helper/iam.py)를 참조하세요.

## 정리

**중요: 비용이 발생하지 않도록 테스트를 마친 후 리소스를 삭제하세요.**

각 노트북 하단에는 정리 셀이 있습니다. `--skip-cleanup`을 전달하지 않으면 CLI 스크립트가 자동으로 리소스를 정리합니다.

```bash
# 모든 Harness 나열
aws bedrock-agentcore-control list-harnesses --region <your-region>

# 특정 Harness 삭제
aws bedrock-agentcore-control delete-harness --region <your-region> \
    --harness-id <HARNESS_ID>

```
