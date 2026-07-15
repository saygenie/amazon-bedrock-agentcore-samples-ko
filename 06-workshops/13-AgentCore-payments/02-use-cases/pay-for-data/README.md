# 데이터 결제 - Heurist Finance Agent

## 개요

**Amazon Bedrock AgentCore Payments**를 사용하여 실시간 시장 데이터 비용을 결제하는 금융 조사 에이전트입니다. 에이전트는 실시간 가격, SEC 공시 및 거시 지표를 제공하는 유료 [Heurist](https://heurist.xyz) 엔드포인트를 호출하고 AgentCore Code Interpreter로 데이터를 분석한 후, 차트와 보고서를 S3 presigned URL로 반환합니다. 이 모든 과정에서 도구에 수동 결제 코드를 작성할 필요가 없습니다.

에이전트는 HTTPS 호출, SigV4 인증 및 CloudWatch를 통한 자동 관찰성을 제공하는 관리형 컨테이너 엔드포인트인 **AgentCore Runtime**에 배포됩니다.

> **Mainnet 샘플.** 이 실습은 Base mainnet을 대상으로 하며 실제 [Heurist mesh x402 registry](https://mesh.heurist.xyz/x402/agents?details=true)를 호출합니다. 호출할 때마다 실제 USDC가 온체인에서 정산됩니다. 일반적인 호출당 가격은 $0.002~$0.005이므로 $1 USDC로 약 200회 호출할 수 있습니다. `/x402/base-sepolia/agents?details=true`에는 카탈로그의 Base Sepolia 변형이 있지만, AgentCore Coinbase 커넥터의 EIP-712 서명 경로는 커넥터의 네트워크 선택을 따르므로 이 샘플에서는 Base mainnet을 사용합니다.

Heurist 엔드포인트는 [x402 프로토콜](https://x402.org)을 사용하며 유효한 결제 증명이 첨부될 때까지 HTTP 402를 반환합니다. `AgentCorePaymentsPlugin`은 결제를 처음부터 끝까지 처리합니다. 402 응답을 가로채고 AgentCore Payment Manager를 통해 USDC 증명을 생성하여 첨부한 후 다시 시도합니다. 도구 코드는 일반 `http_request` 호출 형태를 유지합니다.

![CloudWatch GenAI Observability - Heurist Finance Agent](images/obs-dashboard.png)

## 아키텍처

```
App Backend (ManagementRole)              AgentCore Runtime
  |                                        +------------------------------+
  | create_session(budget=$X)              |  agent/main.py               |
  |                                        |  BedrockAgentCoreApp         |
  |-- invoke(manager_arn, session_id, -->  |  + AgentCorePaymentsPlugin   |
  |         instrument_id, prompt)         |                              |
  |                                        |  http_request -> 402         |
  |<-- {response, artifacts: [{url}]} ---  |  -> ProcessPayment -> retry  |
  |                                        |  -> Code Interpreter         |
  | get_session(check spend)               |  -> export to S3             |
                                           +------------------------------+
                                                      |
                                                      v
                                          CloudWatch GenAI Observability
                                          (automatic via OpenTelemetry)
```

## 작동 방식

`AgentCorePaymentsPlugin`은 전체 x402 결제 수명 주기를 처리합니다.

```python
from bedrock_agentcore.payments.integrations.strands import (
    AgentCorePaymentsPlugin,
    AgentCorePaymentsPluginConfig,
)

payment_plugin = AgentCorePaymentsPlugin(
    config=AgentCorePaymentsPluginConfig(
        payment_manager_arn=PAYMENT_MANAGER_ARN,
        user_id=USER_ID,
        payment_instrument_id=PAYMENT_INSTRUMENT_ID,
        payment_session_id=PAYMENT_SESSION_ID,
        region="us-west-2",
    )
)

agent = Agent(
    model=BedrockModel(model_id=MODEL_ID),
    tools=[http_request, code_interpreter, export_artifact_to_s3, ...],
    plugins=[payment_plugin],
)
```

전체 구현은 [`agent/main.py`](agent/main.py)을 참조하세요.

## 샘플 세부 정보

| | |
|---|---|
| AgentCore 구성 요소 | AgentCore Payments, AgentCore Code Interpreter, AgentCore Runtime |
| 에이전트 프레임워크 | [Strands Agents](https://strandsagents.com/) |
| 모델 | Amazon Bedrock의 Claude Sonnet 4.6(구성 가능) |
| 결제 프로토콜 | [x402](https://x402.org) |
| 결제 네트워크 | Base(USDC) |

## 데이터 소스

런타임에 [Heurist mesh registry](https://mesh.heurist.xyz/x402/agents?details=true)에서 가져옵니다. 기본적으로 샘플은 네 에이전트의 도구를 로드합니다.

| 에이전트 | 대표 도구 | 일반적인 가격 |
|-------|----------------------|---------------|
| `YahooFinanceAgent` | `price_history`, `quote_snapshot`, `futures_snapshot` | $0.002 |
| `FredMacroAgent` | `macro_series_snapshot`, `macro_regime_context` | $0.003 |
| `SecEdgarAgent` | `filing_timeline`, `filing_diff`, `xbrl_fact_trends` | $0.002 |
| `ExaSearchDigestAgent` | `exa_web_search`, `exa_scrape_url` | $0.005 |

`HEURIST_AGENT_IDS` 환경 변수로 재정의할 수 있습니다.

## 사전 요구 사항

- AWS 계정에 생성된 **AgentCore Payment Manager**
- 생성되고 자금이 공급된 **Payment Instrument** - **Base mainnet**의 USDC가 있는 내장형 암호화폐 지갑(기본값, Notebook의 4단계에서 안내)
- **Delegated signing**이 활성화된 Coinbase CDP 프로젝트 및 결제 수단 생성 시 반환된 WalletHub URL을 통해 승인된 지갑별 위임 권한
- Python 3.11+
- `us-west-2`에서 Bedrock 및 AgentCore 액세스 권한이 있는 AWS 자격 증명
- Node.js 20+(`@aws/agentcore` CLI용)
- 실행 중인 Docker(`agentcore deploy` 컨테이너 빌드용)
- 전역으로 설치된 [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)

## 디렉터리 구성

```
pay-for-data/
├── README.md
├── .env.example
├── pay-for-data.ipynb                    # Notebook: AgentCore Runtime을 통한 배포 및 호출
└── agent/                                # 아래 항목은 모두 Runtime container에 포함
    ├── main.py                           # AgentCore Runtime 진입점(BedrockAgentCoreApp)
    ├── catalog.py                        # Heurist registry 조회 후 system prompt용으로 형식 지정
    ├── catalog_live_cache.json           # 동기화된 catalog(Runtime image에 포함)
    ├── config.py                         # .env / payment context 로드
    ├── sync_registry.py                  # CLI: catalog cache 갱신(배포 전에 실행)
    ├── requirements.txt                  # Container Python 의존성
    └── Dockerfile                        # opentelemetry-instrument python -m main
```

## 빠른 시작

[`pay-for-data.ipynb`](pay-for-data.ipynb)을 열고 셀을 순서대로 실행합니다.

| 단계 | 수행 작업 |
|------|-------------|
| 1 | 자격 증명 구성 및 AWS ID 확인 |
| 2 | Heurist 도구 카탈로그 동기화(컨테이너 이미지에 포함) |
| 3 | S3 아티팩트 버킷 생성 |
| 4 | 내장형 지갑 리소스 프로비저닝(credential provider, manager, connector, instrument) |
| 5 | 지갑에 자금 공급 및 WalletHub를 통한 서명 위임 권한 부여 |
| 6 | Payment Manager 관찰성 활성화(CW Logs + X-Ray vended-log 전달) |
| 7 | `agentcore` CLI를 통해 AgentCore Runtime 스캐폴딩 및 배포 |
| 8 | 실행 역할 권한 부여(결제, Code Interpreter, S3, Bedrock + inference profile) |
| 9 | 배포된 에이전트 호출 및 결과 검사 |
| 10 | CloudWatch에서 관찰성 추적 확인 |
| 11 | 정리 |

## 결제 흐름

에이전트가 유료 Heurist 엔드포인트를 호출하면 다음 흐름이 진행됩니다.

1. `http_request`가 엔드포인트 URL로 POST를 전송합니다.
2. Heurist가 x402 결제 조건(network, asset, amount, recipient)과 함께 HTTP 402를 반환합니다.
3. `AgentCorePaymentsPlugin`이 응답을 가로챕니다.
4. 플러그인이 AgentCore Payment Manager에 결제 증명 생성을 요청합니다.
5. Payment Manager가 Payment Instrument를 사용하여 USDC 전송에 서명하고 증명을 반환합니다.
6. 플러그인이 증명을 `X-PAYMENT`로 첨부하여 다시 시도하면 Heurist가 이를 검증하고 데이터를 반환합니다.

플러그인은 도구 호출당 최대 3회 다시 시도합니다. 결제 한도는 세션 범위에서 적용되므로 에이전트가 `maxSpendAmount`를 초과할 수 없습니다.

## Runtime 에이전트 작동 방식

`agent/main.py`는 모든 기능을 동일하게 지원하는 AgentCore Runtime 서비스 계약을 구현합니다.

**상태 비저장, 페이로드 기반**
모든 결제 구성(manager ARN, session ID, instrument ID)은 호출 페이로드에서 전달됩니다. 컨테이너는 자격 증명을 보유하지 않습니다. 앱 백엔드(ManagementRole)는 각 호출 전에 지출 한도가 있는 결제 세션을 생성합니다. Runtime 실행 역할(ProcessPaymentRole)은 해당 한도 내에서만 지출할 수 있습니다.

**AgentCore Code Interpreter**
Code Interpreter는 원격 AWS API이므로 Runtime 컨테이너와 다른 환경에서 동일하게 작동합니다. 에이전트는 pandas/matplotlib 분석 및 차트 생성에 이를 사용합니다.

**S3 아티팩트 저장**
Code Interpreter에서 생성한 아티팩트는 S3에 업로드되고 presigned 다운로드 URL로 반환됩니다. 응답 형식은 다음과 같습니다.

```json
{
  "response": "<markdown research summary>",
  "artifacts": [
    {"name": "chart.png", "url": "https://...", "expires_in": 3600}
  ]
}
```

`CI_ARTIFACTS_BUCKET`이 구성되지 않으면 에이전트는 기능을 단계적으로 축소합니다. 차트는 Markdown 표가 되고 텍스트는 인라인으로 반환됩니다.

**관찰성**
`agentcore deploy` CLI는 컨테이너가 `opentelemetry-instrument`에서 실행되도록 구성합니다. 이를 `agent/requirements.txt`에 포함된 `aws-opentelemetry-distro`와 함께 사용하면 다음 항목이 제공됩니다.
- Strands 에이전트 span(LLM 호출, 도구 호출, 에이전트 턴) → CloudWatch GenAI Observability
- W3C `traceparent` botocore 계측을 통해 하위 span으로 연결된 Code Interpreter 호출
- boto3 하위 span으로 표시되는 결제 호출(`ProcessPayment`, `GetPaymentInstrument`)

`agent/main.py`에는 계측 코드가 필요하지 않습니다.

**실행 역할 권한**(Notebook의 8단계에서 연결):

| 권한 세트 | 작업 | 리소스 범위 |
|---|---|---|
| 결제 데이터 플레인 | `ProcessPayment`, `GetPaymentInstrument`, `GetPaymentInstrumentBalance`, `GetPaymentSession`, `GetResourcePaymentToken` | `payment-manager/*`, `payment-manager/*/instrument/*`, `payment-manager/*/session/*` |
| Code Interpreter | `StartCodeInterpreterSession`, `InvokeCodeInterpreter`, `StopCodeInterpreterSession` | `code-interpreter/*` |
| S3 아티팩트 | `PutObject`, `GetObject` | `<bucket>/heurist-finance-artifacts/*` |
| Bedrock 모델 | `InvokeModel`, `InvokeModelWithResponseStream` | `foundation-model/*`, `inference-profile/*`, `application-inference-profile/*`(뒤의 두 항목은 us-west-2의 Claude Sonnet 4.6처럼 CRIS를 사용하는 모델에 필요) |

## 환경 변수

호스트(Notebook)에 필요한 항목은 [`.env.example`](.env.example)을 참조하세요.

| 변수 | 설명 |
|----------|-------------|
| `PAYMENT_MANAGER_ARN` | AgentCore Payment Manager의 ARN |
| `PAYMENT_SESSION_ID` | 활성 결제 세션의 ID |
| `PAYMENT_INSTRUMENT_ID` | 자금이 공급된 Payment Instrument(내장형 암호화폐 지갑)의 ID |
| `USER_ID` | 결제 추적용 사용자 식별자 |
| `BEDROCK_MODEL_ID` | Bedrock 모델(기본값: Claude Sonnet 4.6) |
| `HEURIST_AGENT_IDS` | 로드할 Heurist 에이전트의 쉼표로 구분된 목록 |
| `HEURIST_CATALOG_URL` | 카탈로그 엔드포인트 - `https://mesh.heurist.xyz/x402/agents?details=true`(mainnet) 또는 테스트넷용 `/x402/base-sepolia/...` 변형 |

컨테이너 `.env`에 포함되는 항목(7단계에서 설정):

| 변수 | 설명 |
|----------|-------------|
| `CI_ARTIFACTS_BUCKET` | 아티팩트 업로드에 사용하는 S3 버킷 |
| `CI_ARTIFACTS_PREFIX` | S3 키 접두사(기본값: `heurist-finance-artifacts`) |
| `CI_ARTIFACTS_TTL` | Presigned URL TTL(초)(기본값: 3600) |
| `AWS_REGION` | boto3 클라이언트용 리전 |
| `AGENT_NAME` | 결제 관찰성에 보고되는 이름 |
| `BYPASS_TOOL_CONSENT` | `strands_tools.http_request`가 TTY 확인 프롬프트를 건너뛰도록 `true`로 설정. Runtime 컨테이너에는 TTY가 없으므로 필요 |
| `AGENT_MAX_TOKENS` | 에이전트 턴당 최대 Bedrock 출력 토큰 수(기본값: `32000`). 짧은 Q&A만 필요하다면 낮추세요. Bedrock은 출력 토큰당 요금을 부과하므로 32k 한도에서 Claude Sonnet 4.6의 턴당 최악의 비용은 약 $0.48입니다. 대부분의 턴에서는 이보다 훨씬 적게 사용합니다. SDK 기본값(4k)은 데이터를 가져오고 Code Interpreter를 실행하며 한 번의 턴에 Markdown 보고서를 작성하는 워크플로에는 너무 낮아 실행 중 `MaxTokensReachedException`이 발생합니다. |

결제 컨텍스트(`PAYMENT_MANAGER_ARN`, `PAYMENT_SESSION_ID`, `PAYMENT_INSTRUMENT_ID`, `USER_ID`)는 컨테이너의 환경 변수가 아니라 런타임의 **호출 페이로드**로 전달됩니다.

## 비용

에이전트를 한 번 호출하면 다음 범주에서 요금이 발생합니다. 기본 구성의 대략적인 최악의 비용은 다음과 같습니다.

| 범주 | 비용 요인 | 턴당 예상 비용 | 참고 |
|---|---|---|---|
| **Heurist x402(Base mainnet의 USDC)** | 각 유료 도구 호출 | 호출당 $0.002~$0.005 | 실제 USDC를 온체인에서 정산합니다. 일반적인 조사 실행에서는 3~10회의 유료 호출을 사용합니다. 지갑에 자금이 있어야 합니다. |
| **Bedrock 모델 출력** | `AGENT_MAX_TOKENS` × Claude Sonnet 4.6 출력 요율 | 32k 한도에서 턴당 최대 약 $0.90 | Bedrock은 us-west-2의 Claude Sonnet 4.6 출력 토큰 1,000개당 $0.015를 부과합니다(입력은 1,000개당 $0.003로 더 저렴). 대부분의 턴은 한도보다 훨씬 적게 사용합니다. 짧은 Q&A에는 `AGENT_MAX_TOKENS`를 낮추세요. |
| **Bedrock AgentCore Runtime** | 호출 중 컨테이너 vCPU × 초 + 메모리 × 초 | 활성 호출 시간 분당 수 센트 | 호출 사이의 유휴 시간에는 요금이 부과되지 않습니다(`idleRuntimeSessionTimeout=600s`). |
| **Bedrock AgentCore Code Interpreter** | 시작된 세션 수 + 활성 시간(분) | 턴당 수 센트 | 에이전트가 실제로 Code Interpreter 도구를 호출할 때만 요금이 부과됩니다. |
| **S3 + CloudWatch** | 아티팩트 스토리지 + 로그/추적 수집 | 매우 적음 | 작은 차트와 보고서는 1MB보다 훨씬 작습니다. CW Logs 및 X-Ray로의 vended log 전달에는 다른 CW 사용량과 동일한 방식으로 요금이 부과됩니다. |

실제로 실행하는 워크플로에 맞게 `.env`의 `AGENT_MAX_TOKENS`와 `SESSION_MAX_SPEND`를 조정하세요. Notebook은 기본적으로 세션당 $0.25의 지출 한도를 사용하며 여러 번 호출하는 조사 워크플로에 충분합니다.

## 참고 사항

- 결제 세션은 만료됩니다. 자동화된 워크플로에서는 호출할 때마다 새 세션을 생성하세요.
- 각 유료 호출은 Base에서 USDC로 정산됩니다. Payment Instrument에 자금이 있는지 확인하세요.
- 컨테이너 이미지를 빌드하기 전에 카탈로그 캐시를 동기화하세요(`python agent/sync_registry.py`). 캐시는 이미지에 포함되므로 컨테이너가 시작 시 Heurist registry를 호출하지 않습니다.
- Presigned 아티팩트 URL은 `CI_ARTIFACTS_TTL`초 후 만료됩니다(기본값: 1시간). URL을 즉시 다운로드하거나 최종 사용자에게 전달하세요.
