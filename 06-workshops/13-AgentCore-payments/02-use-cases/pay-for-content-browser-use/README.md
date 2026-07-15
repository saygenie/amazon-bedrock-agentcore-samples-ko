# 콘텐츠 결제 - 브라우저 사용 사례(AgentCore Runtime)

## 개요

"Amazon Bedrock AgentCore Payments를 사용하면 AI 에이전트가 프라이빗 키를 보유하거나
거래마다 사람의 승인을 받지 않고도 디지털 서비스 비용을 자율적으로 결제할 수
있습니다."

AgentCore Payments가 없다면 콘텐츠 비용을 결제해야 하는 에이전트는 프라이빗 키를
보유하여 자격 증명을 모델에 노출하거나, 사용자를 중단시키고 결제를 수동으로
완료하도록 해야 합니다. 이 사용 사례에서는 세 번째 방법을 보여 줍니다. 에이전트가
**결제 처리에 AgentCore Payments를 활용**하고 사람이 설정한 결제 한도 내에서
관리형 Runtime 컨테이너의 탐색-결제-추출 흐름 전체를 자율적으로 완료합니다.

에이전트는 `ProcessPaymentRole`로 **AgentCore Runtime에 배포**되고,
**AgentCore Browser Tool**을 사용하여 유료 웹 사이트를 탐색합니다. 페이지 DOM에
포함된 x402 결제 요구 사항을 읽고 `ProcessPayment`를 호출하여 결제 증명을 생성한
후, 유료 UI와 상호 작용하고 잠금 해제된 콘텐츠를 반환합니다. 이 과정에서 프라이빗
키가 노출되거나 사람이 개입하지 않습니다.

### 사용 사례 세부 정보

| 항목                | 세부 정보                                                      |
|:--------------------|:--------------------------------------------------------------|
| 사용 사례 유형      | 자율 소액 결제를 사용하는 에이전트 기반 브라우저 자동화       |
| 에이전트 유형       | 단일                                                          |
| 호스팅              | AgentCore Runtime(관리형 microVM, 역할 분리)                   |
| 결제 프로토콜       | x402(HTTP 402 Payment Required)                                |
| 에이전트 프레임워크 | Strands Agents                                                 |
| LLM 모델            | Anthropic Claude Sonnet 4.6                                    |
| 난이도              | 중급                                                           |
| 사용 SDK            | boto3 + AgentCore SDK + AgentCorePaymentsPlugin(Strands) + AgentCore CLI |
| 지갑 유형           | 내장형 암호화폐 지갑(AgentCore 프로비저닝, Coinbase CDP)       |
| 네트워크            | Base Sepolia 테스트넷(`eip155:84532`), Solana Devnet 사용 가능 |

---

## 아키텍처

네 단계로 구분됩니다. **리소스 프로비저닝**(한 번 실행), **세션 설정**(각 에이전트
호출 전 실행), **배포**(에이전트 코드 변경 시 실행), **호출**(실시간 결제 흐름)입니다.
콘텐츠 공급자는 이 저장소의 `content-provider/` CDK 스택에서 별도로 배포하는
인프라이며 Notebook에서 생성하지 않습니다.

> **SDK 선택 참고:** AgentCore Python SDK가 아직 `CreatePaymentManager` /
> `CreatePaymentSession` / `CreatePaymentInstrument`를 노출하지 않으므로 Notebook은
> Payments 리소스 관리에 boto3 클라이언트(`bedrock-agentcore-control` 및
> `bedrock-agentcore`)를 사용합니다. Runtime에서 실행되는 에이전트 자체는
> 결제 처리에 `bedrock-agentcore[strands-agents]` SDK와
> `AgentCorePaymentsPlugin`을 사용하며, 이 부분은 SDK로 완전히 구동됩니다.

```
RESOURCE PROVISIONING  (notebook Step 3, ControlPlaneRole)
─────────────────────────────────────────────────────────────────────────────

  cp_client   ──► bedrock-agentcore-control ──► CreatePaymentCredentialProvider,
                                                CreatePaymentManager,
                                                CreatePaymentConnector
  mgmt_client ──► bedrock-agentcore         ──► CreatePaymentInstrument

  Result: CREDENTIAL_PROVIDER_ARN, MANAGER_ARN, PAYMENT_CONNECTOR_ID, PAYMENT_INSTRUMENT_ID


SESSION SETUP  (notebook Step 4, ManagementRole)
─────────────────────────────────────────────────────────────────────────────

  Notebook (ManagementRole)              AgentCore payments
  ─────────────────────────              ──────────────────────────────
  CreatePaymentSession ─────────────────► budget=$1.00 USD, expiry=60 min
                                          paymentSessionId


DEPLOY AGENT TO RUNTIME  (notebook Step 5, AgentCore CLI)
─────────────────────────────────────────────────────────────────────────────

  agent/payment_agent.py            agentcore CLI                 AWS
  agent/requirements.txt          + agentcore deploy            (CodeBuild builds
  agent/Dockerfile                                               from Dockerfile)
  (BedrockAgentCoreApp +    ──►    create / deploy     ──►   AgentRuntime
   AgentCoreBrowser +                                          (execution role:
   process_x402_payment)                                       ProcessPaymentRole)
                                                               + ECR image
                                                               + CodeBuild project
                                                               + CloudWatch logs


INVOKE  (notebook Step 6, ManagementRole → AgentCore Runtime)
─────────────────────────────────────────────────────────────────────────────

  Notebook (ManagementRole)
   │
   │ InvokeAgentRuntime(arn,
   │     paywall_url, session_id,
   │     instrument_id, manager_arn)
   ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  AgentCore Runtime microVM  (ProcessPaymentRole)             │
  │                                                              │
  │  Strands Agent  (Claude Sonnet 4.6)                          │
  │   Tool 1: AgentCoreBrowser ──► managed cloud Chromium        │
  │   Tool 2: process_x402_payment ──► PaymentManager            │
  │   Plugin: AgentCorePaymentsPlugin (payment query tools)      │
  └───────────┬──────────────────────────────┬───────────────────┘
              │ HTTPS                        │ AWS API (ambient creds)
              ▼                              ▼
  ┌───────────────────────┐      ┌───────────────────────────────┐
  │  Content Provider     │      │  AgentCore payments           │
  │  (team-hosted demo or │      │  ProcessPayment API           │
  │   your own deploy)    │      │                               │
  │                       │      │  ┌────────────────────────┐   │
  │  HTTP 200             │      │  │  Embedded Wallet        │   │
  │  x402 requirement     │      │  │  (Coinbase CDP)         │   │
  │  in DOM script tag    │      │  │  Base Sepolia testnet   │   │
  │                       │      │  └────────────────────────┘   │
  │  proof submitted via  │ ◄────┤  status: PROOF_GENERATED      │
  │  paywall UI → unlock  │      └───────────────────────────────┘
  └───────────────────────┘
   │ article text
   ▼
  Agent returns content + amount paid to caller


OBSERVABILITY  (Step 7, automatic)
─────────────────────────────────────────────────────────────────────────────

  Each invocation emits a CloudWatch GenAI Observability trace covering
  the agent loop, tool calls, payment SDK calls, and ProcessPayment API
  latency. Metrics in the bedrock-agentcore namespace.


CLEANUP
─────────────────────────────────────────────────────────────────────────────

  agentcore remove all -y       — tears down Runtime, ECR, log groups
  Session expiry                — agent can no longer spend after expiry
```

**주요 설계 사항:**

- **AgentCore Runtime에 호스팅.** 에이전트는 `ProcessPaymentRole`로 관리형 microVM
  내부에서 실행됩니다. 인프라에서 역할 분리를 적용합니다. 컨테이너가
  `ProcessPaymentRole`을 직접 수임하고, 이 역할에는 세션 및 결제 수단 관리에
  대한 명시적인 Deny가 있습니다. 에이전트 코드는 `sts:AssumeRole`을 호출하지
  않습니다.
- **Notebook = 앱 백엔드.** `ManagementRole`로 실행되는 Notebook이 예산이 있는
  세션을 생성한 다음, 페이로드에 세션/결제 수단/Manager 컨텍스트를 넣어
  `InvokeAgentRuntime`을 호출합니다. 에이전트는 상태 비저장이고 지갑에
  독립적이므로 동일한 배포에서 백엔드가 권한을 부여한 모든 사용자를 지원합니다.
- **내장형 지갑.** AgentCore가 온체인 지갑을 프로비저닝하므로 기존 CDP 지갑이나
  자금이 있는 계정이 필요하지 않습니다. `linkedAccounts` 이메일 필드는 지갑을
  사용자 ID와 연결합니다. Coinbase 내장형 지갑은 OTP 단계 없이 동기식으로
  프로비저닝됩니다.
- **브라우저 도구.** `AgentCoreBrowser`는 Runtime 컨테이너 내부에서 WebSocket으로
  연결하는 관리형 클라우드 Chromium 세션입니다. 브라우저는 `localhost`에 접근할
  수 없으므로 콘텐츠 공급자를 공개 HTTPS URL에 배포해야 합니다.
- **프라이빗 키 없음.** 서명은 AgentCore 관리형 내장 지갑에 위임됩니다. 현재는
  Coinbase CDP를 사용하며 StripePrivy를 사용하려면 3단계의 자격 증명 공급자
  구성만 변경합니다.

---

## 사전 요구 사항

- Amazon Bedrock AgentCore 액세스 권한이 있는 AWS 계정
- Python 3.10+ 및 Jupyter Notebook(또는 JupyterLab)
- Node.js 20+(AgentCore CLI 및 콘텐츠 공급자 CDK용)
- 자격 증명이 구성된 AWS CLI v2(`aws configure`)
- 설치된 AWS CDK v2(AgentCore CLI가 내부적으로 사용)
- 설치된 AgentCore CLI: `npm install -g @aws/agentcore`
  > **로컬 Docker는 필요하지 않습니다.** 5단계에서는 CLI의 CDK 앱을 통해
  > AWS CodeBuild에서 에이전트 컨테이너 이미지를 빌드합니다. 로컬 핫 리로드
  > 개발에 `agentcore dev`를 사용하려는 경우에만 Docker가 필요합니다.
- 생성된 IAM 역할 - `bash setup_roles.sh`를 실행하고 ARN을 `.env`에 기록합니다.
  이 스크립트는 `ProcessPaymentRole`이 AgentCore Runtime 실행 역할(ECR 가져오기,
  CloudWatch 로그, X-Ray, Bedrock 모델 호출, 브라우저 도구)도 수행하도록 구성하고
  세션/결제 수단 관리에는 명시적인 Deny를 적용합니다. 또한 Notebook이 배포된
  에이전트를 호출할 수 있도록 `ManagementRole`에 `InvokeAgentRuntime`을 추가합니다.
- AWS에 배포된 콘텐츠 공급자 - `cd content-provider && PAY_TO=0x<your-wallet> bash deploy.sh`를 실행하고 `.env`에 `CONTENT_DISTRIBUTION_URL`을 설정합니다([content-provider/README.md](content-provider/README.md) 참조).
- API 키가 있는 Coinbase Developer Platform(CDP) 계정
  - API key name, private key, wallet secret이 필요합니다(`.env.sample` 참조).
  - 에이전트를 실행하기 전에 CDP 프로젝트에서 **Delegated Signing을 활성화**합니다.
    [portal.cdp.coinbase.com](https://portal.cdp.coinbase.com) → 프로젝트 → **Wallet** → **Embedded Wallets** → **Policies**로 이동하여 **Delegated signing**을 활성화합니다.
  - 기존 지갑은 필요하지 않습니다. AgentCore가 내장형 지갑을 프로비저닝합니다.
  - 프로비저닝 후 Circle faucet(https://faucet.circle.com)을 통해 지갑에 자금을 공급합니다.

> **참고:** 이 사용 사례에서는 AgentCore를 통해 **내장형 암호화폐 지갑**을
> 프로비저닝합니다. 기존 Coinbase 지갑은 필요하지 않습니다. 자격 증명
> 공급자(CDP API 키)가 사용자를 대신하여 지갑을 생성하고 관리하도록 AgentCore에
> 권한을 부여합니다. 프로비저닝 후 3단계에서 **WalletHub URL**을 출력합니다.
> 이 URL을 열어 지갑에 자금을 공급하고 서명 권한을 부여하세요.

> **중요:** `AgentCoreBrowser`는 클라우드 관리형 브라우저이므로 `localhost`에
> 접근할 수 없습니다. 콘텐츠 공급자 `CONTENT_DISTRIBUTION_URL`은 공개 HTTPS
> URL이어야 합니다. 먼저 포함된 CDK 스택을 배포한 다음
> [content-provider/README.md](content-provider/README.md)를 참조하여 `.env`의
> `CONTENT_DISTRIBUTION_URL`을 출력된 CloudFront URL로 설정하세요.

---

## 사용 사례 실행

### 0단계 - IAM 역할 생성

`setup_roles.sh`를 실행하여 필요한 IAM 역할을 생성합니다(계정당 한 번만 필요).

```bash
bash setup_roles.sh
```

### 1단계 - 환경 구성

```bash
cp .env.sample .env
# .env를 편집하고 값 입력
```

설정할 주요 변수:
- `CDP_API_KEY_NAME` / `CDP_API_KEY_PRIVATE_KEY` / `CDP_WALLET_SECRET` - Coinbase CDP API 키
- `WALLET_EMAIL` - 내장형 지갑에 연결할 이메일 주소
- `CONTROL_PLANE_ROLE_ARN` / `MANAGEMENT_ROLE_ARN` / `PROCESS_PAYMENT_ROLE_ARN` - `setup_roles.sh`에서 생성
- `CONTENT_DISTRIBUTION_URL` - 콘텐츠 공급자 CDK 스택을 배포한 후 출력된 CloudFront URL로 설정

첫 실행 후 3단계 출력의 `MANAGER_ARN`, `PAYMENT_CONNECTOR_ID`,
`PAYMENT_INSTRUMENT_ID`를 `.env`에 복사하면 이후 실행에서 프로비저닝을 건너뛸
수 있습니다.

### 2단계 - 종속 항목 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3단계 - Notebook 실행

```bash
jupyter notebook pay_for_content_browser.ipynb
```

모든 셀을 순서대로 실행합니다. Notebook은 다음 작업을 수행합니다.
1. 구성을 로드하고 환경 변수 확인
2. 앱 백엔드 boto3 클라이언트 두 개(`ControlPlaneRole`, `ManagementRole`) 초기화
3. 사용자별로 한 번 내장형 지갑 리소스 스택 프로비저닝:
   CredentialProvider → PaymentManager → PaymentConnector → EmbeddedCryptoWallet Instrument
   이후 WalletHub와 Circle faucet을 통해 지갑에 자금을 공급할 수 있도록 일시 중지
3e. `GetPaymentInstrumentBalance`로 지갑 USDC 잔액 확인(잔액 확인 시에만 로컬에서
    잠시 `ProcessPaymentRole` 수임)
4. 예산과 만료 시간이 있는 결제 세션 생성(`ManagementRole`)
4b. **Payment Manager 관찰성 활성화** - 4단계 vended log 전달 설정
    (`PutDeliverySource` × 2 → `PutDeliveryDestination` × 2 →
    `CreateDelivery` × 2)을 실행합니다. 그러면 Payment Manager가 세션, 거래 및
    `Agents using Payments` 귀속 정보와 함께 AgentCore Observability → Payments
    대시보드에 표시됩니다.
5. AgentCore CLI를 통해 `agent/payment_agent.py`를 AgentCore Runtime에 배포:
   `agentcore create` + `agentcore add agent --build Container` 실행,
   [`agent/Dockerfile`](agent/Dockerfile) 복사 후 `agentcore deploy` 실행(CodeBuild가
   이미지를 빌드하여 ECR로 푸시하고 AgentRuntime 생성). Python 3.13,
   `ProcessPaymentRole` 실행 역할, 유휴 시간 10분/최대 수명 30분으로 고정됩니다.
6. 페이로드에 세션/결제 수단 컨텍스트를 넣어 `InvokeAgentRuntime`으로 배포된
   에이전트를 호출한 후 `GetPaymentSession`으로 지출 확인
7. CloudWatch GenAI Observability에서 세션 추적 확인. Runtime, Agent,
   Browser tool, Payment Manager 원격 측정이 하나의 대시보드에 연결됩니다.
8. 정리 - `agentcore remove all`을 실행하여 Runtime 배포 해제

### 관찰성 범위

| 계층 | 활성화 방법 | 확인 위치 |
|---|---|---|
| Runtime | `agentcore deploy`를 통해 자동 활성화(`opentelemetry-instrument` CMD) | 모든 추적 대시보드 |
| Agent(Strands) | Runtime 배포판을 통한 OTEL span | 각 추적의 waterfall 내부 |
| Browser tool | Strands `AgentCoreBrowser`가 클라이언트 측 span 방출 | 각 추적의 waterfall 내부 |
| Payment Manager | Vended log 전달(4b단계) | AgentCore Observability 대시보드의 **Payments 탭** |

SDK가 `X-Amzn-Bedrock-AgentCore-Payments-Agent-Name` 헤더를 전송할 때만 대시보드의
*Agents using Payments* 카운터가 증가합니다. `PaymentManager`와
`AgentCorePaymentsPluginConfig`를 `agent_name=`으로 생성하면 SDK가 이 헤더를
자동으로 전송합니다. `agent/payment_agent.py`는 컨테이너 환경에서 `AGENT_NAME`을
읽어 두 구성 요소 모두에 전달합니다.

> **Browser 관찰성 주의 사항:** 현재 AgentCore Browser 서비스는 리소스별 vended
> log 전달을 지원하지 않습니다. `PutDeliverySource`는 다음 오류와 함께 브라우저
> ARN을 거부합니다: *valid resource types are runtime / gateway / memory /
> payment-manager / code-interpreter / workload-identity*. Browser tool 작업은
> OTEL 배포판을 통해 에이전트 추적 내부에 span으로 계속 표시됩니다
> (`browser session start`, `navigate`, `cleanup`). 따라서 *유용한* 가시성은
> 확보되지만 현재 별도의 Browser 서비스 대시보드는 없습니다.

---

## 주요 참고 사항 및 주의 사항

### 엔드포인트

Notebook은 `AWS_REGION`에 설정한 AWS 리전에서 두 엔드포인트를 구성합니다.
- `CP_ENDPOINT` = `https://bedrock-agentcore-control.{region}.amazonaws.com` - credential provider, manager, connector
- `DP_ENDPOINT` = `https://bedrock-agentcore.{region}.amazonaws.com` - instrument, session, process payment

`CreatePaymentCredentialProvider`는 표준 `bedrock-agentcore-control` 엔드포인트에
있습니다. 별도의 ACPS 엔드포인트는 필요하지 않습니다.

### 내장형 지갑 - Coinbase CDP(공급자 독립적 설계)

이 사용 사례에서는 Coinbase CDP를 통해 **내장형 암호화폐 지갑**을
프로비저닝합니다. AgentCore가 온체인 지갑을 생성하고 관리하므로 지갑 주소가
아닌 CDP API 자격 증명을 제공합니다. 이 설계는 공급자와 독립적입니다.
**StripePrivy**로 전환하려면 3a 및 3c단계의 자격 증명 공급자 구성만 변경하면
되며 모든 에이전트 로직과 결제 도구 코드는 그대로 유지됩니다.

CreatePaymentInstrument 후 3단계에서 **WalletHub URL**을 출력합니다. 이 URL을
열어 다음 작업을 수행합니다.
- `WALLET_EMAIL`로 로그인
- Circle faucet(https://faucet.circle.com)을 통해 테스트넷 USDC로 지갑에 자금 공급
- AgentCore Payments에 서명 권한 부여

> Coinbase 내장형 지갑은 동기식으로 프로비저닝되므로 OTP 단계가 필요하지
> 않습니다. StripePrivy 내장형 지갑은 프로비저닝 중 OTP 이메일 확인이 필요합니다.

### 지원 네트워크

| 네트워크 별칭  | Chain ID                                   | 상태           |
|:---------------|:-------------------------------------------|:---------------|
| `base-sepolia` | `eip155:84532`                             | 기본값, 테스트 완료 |
| `solana-devnet`| `solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` | 자리 표시자, 아직 테스트하지 않음 |

네트워크를 전환하려면 `.env`에서 `NETWORK`를 설정합니다. Solana Devnet의 결제
증명에는 추가 `feePayer` 필드가 필요하며 Notebook에 이에 관한 주석이 포함되어
있습니다.

### 테스트넷 전용

이 사용 사례는 테스트넷 네트워크를 대상으로 합니다. 어느 주체도 영구적인 판매자
주소를 보장하지 않습니다. 콘텐츠 공급자의 지갑 주소가 변경되면 콘텐츠 공급자
배포의 `PAY_TO`를 업데이트하세요.

### DOM 선택기는 샘플 전용

브라우저 에이전트가 사용하는 요소 ID(`pay-btn`, `proof-input`, `verify-btn`,
`content`)는 `content-provider/`의 **데모 콘텐츠 공급자** 전용입니다. 실제 x402
사이트에는 다른 선택기가 있습니다. 에이전트는 하드코딩된 ID 대신 의미론적
단서(버튼 텍스트, 입력 유형, aria-label)를 사용하여 결제 양식 요소를 동적으로
검색합니다.

---

## IAM 역할 설계

| 역할 | 허용 작업 | 거부 작업 | 사용 주체 |
|:-----|:-------------------|:-------|:--------|
| `ControlPlaneRole` | `CreatePaymentCredentialProvider`, `CreatePaymentManager`, `CreatePaymentConnector`, `CreatePaymentInstrument` | `ProcessPayment`, 세션 관리 | Notebook(3단계) |
| `ManagementRole` | `CreatePaymentSession`, `GetPaymentSession`, `InvokeAgentRuntime` | `ProcessPayment` | Notebook(4단계, 6단계) |
| `ProcessPaymentRole` | `ProcessPayment`, `GetPaymentInstrument`, `GetPaymentInstrumentBalance`, 브라우저 도구, ECR 가져오기, CloudWatch 로그/지표, X-Ray, Bedrock 모델 호출 | 모든 설정 및 세션 관리 작업(`CreatePaymentSession`, `CreatePaymentInstrument` 등) | 실행 역할로 사용하는 **AgentCore Runtime** |
| `ResourceRetrievalRole` | 서비스 측 결제 토큰 검색 | 해당 없음(AWS 서비스에서 수임) | AgentCore 서비스 |

---

## 정리

작업을 마치면 다음 순서로 해제합니다.

1. **Runtime 배포** - `cd PayForContentRuntime && agentcore remove all -y`
   (AgentRuntime, ECR 리포지토리, CodeBuild 프로젝트 및 CloudWatch 로그 제거).
2. **결제 세션** - `SESSION_EXPIRY_MINUTES` 후 자동 만료(기본값 60분). 종료를 위한
   API 호출은 필요하지 않습니다.
3. **Payment Manager/Connector/Instrument/Credential Provider** - 계정을 완전히
   정리하려면 AWS CLI 또는 boto3로 삭제합니다.
4. **콘텐츠 공급자** - `cd content-provider && cdk destroy`(CloudFront 배포와
   Lambda@Edge 함수 제거).
5. **IAM 역할** - 더 이상 필요하지 않으면 IAM 콘솔 또는 AWS CLI에서 네 개의
   `AgentCorePayments*` 역할을 삭제합니다.

---

## 공동 책임

| 고려 사항                     | AWS/AgentCore                                             | 고객                                                 |
|:------------------------------|:---------------------------------------------------------|:----------------------------------------------------|
| Runtime 컨테이너 격리         | 세션별 microVM, 자동 해제                                 | 워크로드에 맞게 `idleTimeout`, `maxLifetime` 설정    |
| 결제 서명 키                  | AgentCore Identity에 보관/Coinbase CDP에서 위임          | CDP 프로젝트에서 Delegated Signing 활성화           |
| 지출 한도                     | 서비스에서 세션별 `maxSpendAmount` 적용                  | 작업에 적합한 세션별 예산 설정                       |
| IAM 역할 분리                 | Runtime이 지정된 실행 역할 수임                          | 최소 권한 역할 정책 작성(`setup_roles.sh` 참조)      |
| 관찰성 수집                   | 추적 및 지표 자동 방출                                   | 필요한 지표에 대한 경보 구성                         |
| 지갑 자금 공급                | AgentCore가 내장형 지갑 프로비저닝                       | faucet(테스트넷) 또는 onramp(프로덕션)를 통해 자금 공급 |
| 브라우저 세션 보안            | 컨테이너화된 Chromium, 임시 세션, 선택적 기록            | 에이전트를 통한 프로덕션 계정 로그인 방지            |
