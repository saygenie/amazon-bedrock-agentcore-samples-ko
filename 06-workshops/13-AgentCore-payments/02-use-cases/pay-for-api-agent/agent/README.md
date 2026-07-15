# Pay-For-API - 구매자 에이전트

Amazon Bedrock Claude Sonnet 4.5에 연결된 최소 구성의 Strands Agent입니다.
`AgentCorePaymentsPlugin`을 통해 x402 결제를
**Amazon Bedrock AgentCore Payments**에 위임하여 판매자 API에서
정보를 구매합니다.

동일한 에이전트를 실행하는 방법은 두 가지입니다.

| 모드 | 위치 | 용도 |
|------|-------|------|
| **로컬** | `pay-for-api.ipynb`의 Notebook 셀(§8) | 교육 / 빠른 반복 |
| **Runtime** | CDK를 통해 배포한 AgentCore Runtime 컨테이너(§9) | 프로덕션 형태의 배포 |

두 모드에서 에이전트 코드는 동일합니다. 컨테이너 폴더에서는 동일한
`Agent()` 구성을 FastAPI `/invocations` 엔드포인트로 래핑하여
AgentCore Runtime 계약을 충족합니다.

## 사전 요구 사항

에이전트 Runtime을 배포하기 전에 상위 사용 사례의
[`../README.md`](../README.md)에 있는 사전 요구 사항을 완료하세요.
구체적으로 다음 항목이 필요합니다.

- 대상 리전에서 Amazon Bedrock AgentCore Payments가 활성화된 AWS 계정
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0`에 대한 Amazon Bedrock 모델 액세스
- AWS CDK v2(`npm install -g aws-cdk`) 및 Node.js 18+
- 사용 사례의 venv가 활성화된 Python 3.10+ 환경
- 상위 Notebook의 §1-§6 완료(Runtime에서 호출할 `PaymentManager`,
  `PaymentInstrument` 및 하나 이상의 `PaymentSession`이 있어야 함)

## 폴더 구조

```
agent/
├── cdk/
│   ├── app.py              CDK app entry point
│   ├── agent_stack.py      ECR + IAM + Runtime
│   ├── cdk.json
│   └── requirements.txt
├── container/
│   ├── Dockerfile
│   ├── agent.py            FastAPI server + Strands Agent
│   └── requirements.txt
└── README.md
```

## 결제 흐름의 작동 방식

1. 에이전트가 `http_request.GET <seller-url>/facts?topic=<x>`를 시도합니다.
2. 판매자가 x402 `accepts` 배열과 함께 **HTTP 402**를 반환합니다.
3. `AgentCorePaymentsPlugin`이 402를 가로채고 구성된 Payment Manager,
   Session 및 Instrument에 대해 **`ProcessPayment`**를 호출합니다. 그런 다음
   서명된 `CRYPTO_X402` proof를 받아 x402 protocol 사양에 따라 base64로
   인코딩한 `X-PAYMENT` header에 넣고 요청을 투명하게 다시 시도합니다.
4. 판매자가 x402 facilitator를 통해 proof를 검증하고 온체인에서 결제를
   정산한 뒤 구매한 정보를 **HTTP 200**으로 반환합니다.

에이전트는 private key를 확인하거나 `X-PAYMENT` header를 조립하지 않으며
boto3 client를 직접 다루지도 않습니다. 에이전트가 호출하는 유일한 도구는
`http_request`입니다. 플러그인은 읽기 전용 관리 도구 3개
(`get_payment_instrument`, `list_payment_instruments`,
`get_payment_session`)도 등록하지만, Notebook §7의 system prompt에서
모델이 이를 사용하지 않도록 지시합니다. 이 도구들은 운영자 디버그 흐름을
위해 예약되어 있습니다.

## 자격 증명 모델

- 모든 결제 작업은 `paymentInstrument.userId`의 **vendor-level user ID**로
  실행됩니다. 이는 서비스가 `CreatePaymentInstrument`에서 반환하는 값입니다.
  Notebook은 이 ID를 캡처하고 호출 시 `paymentUserId`로 에이전트에 전달합니다.
- Privy 기반 instrument에서는 Privy DID를 사용합니다.
- Coinbase 기반 instrument에서는 CDP end-user UUID(hub flow)를 사용합니다.
- 전송 과정에는 **tenant/Cognito sub가 없으며**, 자격 증명은 end-to-end로
  공급자를 기준으로 합니다.

## 배포

> ⚠️ **비용 안내:** 이 과정에서는 AgentCore Runtime, Amazon ECR
> repository, AWS CodeBuild project, AgentCore Memory 리소스 및 지원용
> CloudWatch log group을 배포합니다. CodeBuild(빌드 시간 기준)와
> Runtime(호출 기준)의 비용이 가장 높습니다. 실습을 마치면
> [정리](#정리) 단계를 실행하세요.

```bash
cd agent/cdk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk bootstrap         # 계정/리전별로 한 번만 실행
cdk deploy
```

출력: `AgentRuntimeArn`, `AgentRuntimeEndpoint`,
`AgentExecutionRoleArn`, `AgentEcrRepoUri`,
`AgentBuildProjectName`, `AgentMemoryId`.

Notebook의 §9에서 CDK를 대신 호출합니다.
`pay-for-api.ipynb`를 참조하세요.

## 정리

Runtime이 더 이상 필요하지 않으면 제거하세요. Notebook §11에서는 동일한 제거
작업과 함께 AgentCore Payments 리소스 정리를 실행합니다.

```bash
bash test/integration/destroy-agent.sh
```

또는 CDK를 통해 직접 제거합니다.

```bash
cd agent/cdk
source .venv/bin/activate
cdk destroy
```

이 명령은 AgentCore Runtime, AgentCore Memory 리소스, 이미지가 포함된
ECR repository 및 CodeBuild project를 제거합니다. CloudFormation stack을
나열해 제거 여부를 확인하세요.

```bash
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query "StackSummaries[?starts_with(StackName, 'AgentCorePaymentsBuyerAgent')].StackName"
```

출력이 비어 있어야 합니다.

## 마무리

이 폴더는 Pay-For-API 사용 사례의 구매자 측을 배포 가능한 AgentCore
Runtime으로 패키징합니다. 동일한 Strands Agent 패턴이 상위 Notebook의
§7에서는 로컬로 실행되고 여기서는 CDK stack을 통해 프로덕션 형태로
실행됩니다. 이를 통해 코드 변경 없이 로컬 에이전트 프로토타입을 관리형
Runtime으로 전환하는 방법을 보여줍니다. `AgentCorePaymentsPlugin`은 x402
결제 흐름을 에이전트에 투명하게 처리하므로, 운영자가 어떤 지갑 공급자를
구성했든 동일한 `http_request` 도구 호출로 콘텐츠 비용을 결제합니다.

더 자세히 살펴보려면 `pay-for-api.ipynb`를 처음부터 끝까지 실행하세요.
서비스 측 참고 자료는
[AgentCore Payments 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)를
참조하세요.
