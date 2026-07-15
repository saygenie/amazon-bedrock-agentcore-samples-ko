# Amazon Bedrock AgentCore payments - 자습서

**Amazon Bedrock AgentCore payments**로 결제 기능을 갖춘 AI 에이전트를 구축하는 단계별 Jupyter Notebook 자습서입니다.

AgentCore payments는 AI 에이전트가 유료 API, MCP 서버, 콘텐츠에 액세스할 때 안전한 실시간 소액 결제를 제공하는 Amazon Bedrock AgentCore 기능입니다. x402 프로토콜의 결제 오케스트레이션, 구성 가능한 결제 한도, Coinbase CDP 및 Stripe(Privy) stablecoin wallet과의 서드 파티 wallet 통합을 처리합니다.

**대상 독자**: 이 자습서는 에이전트가 유료 서비스에 액세스할 때 x402 결제를 자율적으로 수행하도록 만들려는 AI 에이전트 개발자를 대상으로 합니다.

> **Testnet 전용.** 모든 자습서는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC와 함께 Base Sepolia(Ethereum) 또는 Solana Devnet을 사용합니다. Testnet USDC는 실제 가치가 없습니다.

## 사전 요구 사항

- Python 3.10+
- 최소 필수 권한으로 구성된 AWS CLI(`aws sts get-caller-identity`로 확인)
- AgentCore payments에 액세스할 수 있는 AWS 계정
- Jupyter (`pip install jupyter`)

## 경로 선택

하나의 wallet 제공업체를 사용하는지, 두 제공업체를 모두 사용하는지에 따라 두 가지 경로가 있습니다.

### 경로 A: 단일 제공업체(자습서 00~06)

하나의 wallet 제공업체로 AgentCore payments를 학습하려면 이 경로를 사용하세요. 대부분의 개발자는 여기에서 시작합니다.

```
1. Pick ONE provider and run its setup guide:
      providers/coinbase_cdp_account_setup.ipynb   ← writes Coinbase keys to .env
   OR providers/stripe_privy_account_setup.ipynb    ← writes Privy keys to .env

2. Run Tutorial 00 (setup_agentcore_payments.ipynb)
      Reads your provider keys from .env
      Creates IAM roles, PaymentManager, Connector, Instrument, Session
      Writes resource IDs back to .env

3. Run Tutorials 01–06 in any order
      Each loads .env and uses the resources Tutorial 00 created
```

`.env` 파일은 공유 구성입니다. 제공업체 Notebook은 자격 증명을 기록하고, 자습서 00은 리소스 ID를 기록하며, 이후 자습서는 두 정보를 모두 읽습니다. 두 제공업체 Notebook을 모두 실행하지 마세요. 두 번째 Notebook이 `CREDENTIAL_PROVIDER_TYPE`을 덮어쓰며 자습서 00은 마지막으로 설정된 값을 사용합니다.

### 경로 B: 멀티 제공업체(자습서 07)

자습서 07(멀티 에이전트 오케스트레이터)은 Coinbase와 Privy wallet을 하나씩 사용하고 에이전트별로 별도의 예산을 설정합니다. 따라서 다른 설정이 필요합니다.

```
1. Run BOTH provider setup guides:
      providers/coinbase_cdp_account_setup.ipynb   ← writes COINBASE_* keys to .env
      providers/stripe_privy_account_setup.ipynb    ← writes PRIVY_* keys to .env

2. Run Tutorial 00b (00b_multi_provider_setup.ipynb) instead of Tutorial 00
      Creates one PaymentManager with two Connectors (Coinbase + Privy)
      Creates two Instruments (one per provider)
      Writes prefixed resource IDs to .env (COINBASE_INSTRUMENT_ID, PRIVY_INSTRUMENT_ID, etc.)

3. Run Tutorial 07
      Reads the prefixed keys and assigns each agent its own wallet + budget
```

경로 B를 완료한 후 자습서 01~06도 실행할 수 있습니다. 멀티 제공업체 `.env`를 감지하고 사용 가능한 첫 번째 제공업체를 자동으로 선택합니다.

## 시작하기

### 1. SDK 설치

```bash
pip install 'bedrock-agentcore[strands-agents]'
```

### 2. Wallet 제공업체 설정

선택한 제공업체의 가이드를 따르세요. 각 Notebook은 계정 생성, 자격 증명 발급, `.env` 저장 과정을 안내합니다.

- **Coinbase CDP** - `.env.coinbase.sample`을 `.env`로 복사한 다음 [`providers/coinbase_cdp_account_setup.ipynb`](00-setup-agentcore-payments/providers/coinbase_cdp_account_setup.ipynb)를 따릅니다.
- **Stripe (Privy)** - `.env.privy.sample`을 `.env`로 복사한 다음 [`providers/stripe_privy_account_setup.ipynb`](00-setup-agentcore-payments/providers/stripe_privy_account_setup.ipynb)를 따릅니다. 일회성 Privy reference frontend에 Node.js가 필요합니다.

경로 B(멀티 제공업체)에서는 두 제공업체 Notebook을 모두 실행하세요. 접두사가 붙은 키(`COINBASE_*`, `PRIVY_*`)를 충돌 없이 동일한 `.env`에 기록합니다.

자습서 00을 실행하기 전에 `.env`의 `LINKED_EMAIL`을 실제 이메일 주소로 설정하세요. 이 이메일은 embedded wallet을 생성하고 자금 충전 및 위임을 위해 wallet hub에 로그인할 때 사용됩니다.

### 3. 설정 Notebook 실행

```bash
cd 00-setup-agentcore-payments

# 경로 A(단일 제공업체):
jupyter notebook setup_agentcore_payments.ipynb

# 경로 B(멀티 제공업체):
jupyter notebook 00b_multi_provider_setup.ipynb
```

IAM 역할과 결제 스택을 생성하고 리소스 ID를 `.env`에 기록합니다. 이후의 모든 자습서는 이 파일을 불러옵니다.

### 4. 추가 도구(특정 자습서에만 필요)

| 도구 | 자습서 | 설치 |
|------|-----------|---------|
| AgentCore CLI | 02, 04, 07 | `npm install -g @aws/agentcore`(Node.js 20+ 필요) |
| Docker | 02, 07 | `agentcore deploy` 컨테이너 빌드에 필요 |
| Playwright | 05 | `pip install playwright && python -m playwright install chromium` |

## 자습서 흐름

```
경로 A(단일 제공업체):
  Provider setup ──► T00 Setup ──► T01 Local Agent ──► T02 Deploy to Runtime
                                   │
                                   ├──► T03 Wallet Operations
                                   ├──► T04 Gateway + Bazaar
                                   ├──► T05 Browser + Payments (pattern reference)
                                   └──► T06 Memory + Payments

경로 B(멀티 제공업체):
  Both provider setups ──► T00b Multi-Provider Setup ──► T07 Multi-Agent Orchestrator
                                                         │
                                                         └──► T01–T06 also work
```

## 보안 알림

이 자습서는 편의를 위해 `.env` 파일에 자격 증명을 저장합니다. 배포된 워크로드에서는 모든 자격 증명을 [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html) 또는 Systems Manager Parameter Store에 저장하세요. `.env` 파일을 버전 관리에 commit하지 마세요. 자세한 지침은 [보안](#security) 섹션을 참조하세요.

## 자습서

각 자습서는 하나 이상의 AgentCore payments 기능과 연결됩니다. 자습서 00으로 시작한 다음 원하는 경로를 선택하세요.

| # | 자습서 | 다루는 기능 | 학습 내용 |
|---|----------|-----------------|-------------------|
| 00 | [설정](00-setup-agentcore-payments/) | Wallet 통합, 결제 한도 | IAM 역할, PaymentManager, Connector, embedded wallet, 예산이 설정된 세션을 처음부터 생성 |
| 01 | [에이전트 결제 한도 활성화](01-agents-payments-and-limits/) | 결제 처리, 결제 한도 | 유료 엔드포인트를 호출하고 자동으로 결제하는 Strands 에이전트와 LangGraph 에이전트 구축. 결제 한도 적용 및 초과 지출 거부 확인 |
| 02 | [Runtime에 배포](02-deploy-to-agentcore-runtime/) | 결제 처리, Observability | 역할을 분리하여 결제 에이전트를 AgentCore Runtime에 배포. AgentCore Observability에서 결제 trace 및 log 확인 |
| 03 | [Wallet 작업](03-user-onboarding-wallet-funding/) | Wallet 통합 | 추가 사용자 온보딩, 자금 충전 옵션(testnet faucet 및 onramp), 제공업체별 위임, 잔액 확인, 멀티 네트워크 wallet, 세션 예산 패턴을 포함한 전체 wallet 수명 주기 |
| 04 | [Gateway + Bazaar](04-agent-with-coinbase-bazaar-via-gateway/) | 엔드포인트 검색, 결제 처리 | AgentCore Gateway를 통해 Coinbase x402 Bazaar(Base Sepolia)의 유료 MCP 도구를 검색하고 자동 결제로 호출 |
| 05 | [Browser + Payments](05-agent-with-browser-tool-pay-for-content/) | 결제 처리 | 패턴 참고: Playwright 브라우저 세션에서 HTTP 402 응답을 가로채고 paywall이 적용된 웹 콘텐츠에 결제 |
| 06 | [결제 Memory를 사용하는 리서치 에이전트](06-research-agent-with-payment-memory/) | 결제 처리, 결제 한도, Memory | AgentCore payments와 AgentCore Memory를 결합해 세션 간 이전 데이터와 사용자 기본 설정을 기억하고 중복 유료 호출 방지 |
| 07 | [멀티 에이전트 오케스트레이터](07-multi-agent-payment-orchestrator/) | Wallet 통합, 결제 한도, Observability | 별도의 wallet(Coinbase + Privy)과 에이전트별 결제 한도를 사용하는 여러 에이전트를 오케스트레이션하고 Runtime 배포 및 온라인 평가 수행 |

### AgentCore payments 기능과 자습서 매핑

| 기능 | 설명 | 자습서 |
|---------|-------------|-----------|
| 결제 처리 | x402 프로토콜 오케스트레이션, transaction 서명, 증명 생성 | 01, 02, 04, 05, 06, 07 |
| 결제 한도 | 세션 예산(`maxSpendAmount`), 만료, 초과 지출 거부 | 00, 01, 03, 06, 07 |
| Wallet 통합 | Coinbase CDP 및 Stripe(Privy) embedded wallet, 위임, 자금 충전 | 00, 03, 07 |
| 엔드포인트 검색 | AgentCore Gateway를 통한 Coinbase x402 Bazaar 및 MCP 도구 검색 | 04 |
| Memory | 세션 간 기억 및 지출 최적화를 위한 AgentCore Memory | 06 |
| Observability | AgentCore Observability(CloudWatch를 통한 vended log 및 trace) | 00, 02, 07 |

### Coinbase x402 Bazaar 액세스 패턴

Bazaar는 세 가지 인터페이스를 제공합니다.

| 인터페이스 | 엔드포인트 | 적합한 용도 |
|-----------|----------|----------|
| Semantic search(HTTP) | `GET /v2/x402/discovery/search` | 직접 HTTP 호출. 검색은 무료이며 유료 도구 호출은 402 반환 |
| MCP Server | `GET /v2/x402/discovery/mcp` | AgentCore Gateway를 통한 AI 에이전트. `search_resources` + `proxy_tool_call` |
| 페이지가 매겨진 catalog(HTTP) | `GET /v2/x402/discovery/resources` | 사용자 지정 UI 및 backend 통합 |

## 저장소 구조

```
├── utils.py                              ← shared helpers (all tutorials import this)
├── .env                                  ← created by Tutorial 00 (git-ignored)
├── 00-setup-agentcore-payments/          ← start here
│   ├── .env.coinbase.sample              ← copy to .env for Coinbase CDP
│   ├── .env.privy.sample                 ← copy to .env for Stripe (Privy)
│   └── providers/                        ← Coinbase + Privy account setup guides
├── 01-agents-payments-and-limits/        ← Strands + LangGraph notebooks
├── 02-deploy-to-agentcore-runtime/
├── 03-user-onboarding-wallet-funding/
├── 04-agent-with-coinbase-bazaar-via-gateway/
├── 05-agent-with-browser-tool-pay-for-content/
├── 06-research-agent-with-payment-memory/
└── 07-multi-agent-payment-orchestrator/
```

## 공유 파일

| 파일 | 용도 |
|------|---------|
| `utils.py` | IAM 역할 생성(`setup_payment_roles()`), 구성 유지, observability 설정, 표시 helper |
| `.env` | 자습서 00에서 생성하고 이후 모든 자습서가 불러오는 공유 구성(gitignore 대상) |
| `.gitignore` | `.env`, `private.pem`, Python artifact 제외 |

## Wallet 독립적 설계

이 자습서는 자습서 00에서 구성한 두 지원 wallet 제공업체 중 어느 쪽에서도 작동하도록 설계되었습니다. Coinbase CDP와 Stripe(Privy) 중 무엇을 선택하든 에이전트 코드는 같고 `.env` 값만 달라집니다.

## 정리

> **비용 알림:** AgentCore Runtime 배포, Gateway, 결제 세션, CloudWatch observability에는 AWS 비용이 발생합니다. 실험을 마친 후 정리를 실행하여 지속적인 비용을 방지하세요.

> **경고:** 정리는 되돌릴 수 없으며 모든 결제 리소스, transaction 기록, 감사 log를 영구 삭제합니다. 계속하기 전에 필요한 데이터를 내보냈는지 확인하세요.

자습서를 마치면 불필요한 비용이 발생하지 않도록 리소스를 정리하세요.

1. **Runtime 배포** - 배포된 에이전트와 Gateway를 제거합니다.
   ```bash
   agentcore remove all -y
   agentcore deploy -y
   ```
2. **결제 리소스**(Manager, Connector, Instrument) - 자습서 00 하단의 정리 셀을 실행합니다. Payment Manager와 모든 하위 리소스(connector, instrument)가 삭제됩니다.
3. **IAM 역할** - `setup_payment_roles()`가 생성한 4개 역할이 더 이상 필요하지 않으면 IAM 콘솔에서 삭제할 수 있습니다.
4. **CloudWatch log group** - observability를 활성화했다면 CloudWatch 콘솔에서 `/aws/vendedlogs/bedrock-agentcore/<manager-id>`를 삭제합니다.

*참고*: 1. **결제 세션** - 구성된 `expiryTimeInMinutes`가 지나면 자동으로 만료됩니다. 별도의 작업은 필요하지 않습니다.

<a id="security"></a>

## 보안

이 자습서는 실제 가치가 없는 testnet 리소스를 사용합니다. 실제 환경에 배포할 때는 다음 사항을 고려하세요.

- **자격 증명 관리** - secret은 `.env` 파일이 아닌 [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html) 또는 Systems Manager Parameter Store에 저장하세요. 자격 증명을 정기적으로 교체하세요.
- **IAM 최소 권한** - `"Resource": "*"` 대신 특정 리소스로 IAM 정책 범위를 제한하세요. control plane(ManagementRole)과 data plane(ProcessPaymentRole) 작업에 별도의 역할을 사용하세요.
- **네트워크 보안** - AgentCore Runtime을 private subnet에 배포하세요. AWS 서비스 액세스에는 VPC endpoint를 사용하세요.
- **모니터링** - 결제 trace에 CloudWatch Logs를 활성화하세요. 비정상적인 지출 패턴이나 결제 실패에 대한 alarm을 설정하세요.

[AWS 공동 책임 모델](https://aws.amazon.com/compliance/shared-responsibility-model/)을 따르세요. 자격 증명, IAM 정책, wallet 액세스, 세션 예산을 보호할 책임은 사용자에게 있습니다.

## 결론

이 자습서는 Amazon Bedrock AgentCore payments를 사용하는 결제 지원 AI 에이전트의 전체 수명 주기를 다룹니다. Wallet 설정, 로컬 에이전트 개발, Runtime 배포, wallet 작업, Gateway 통합, 브라우저 기반 결제, 중복 유료 호출을 건너뛰는 Memory 인식 에이전트, 멀티 에이전트 오케스트레이션을 학습합니다. 자습서 00과 선택한 wallet의 제공업체 설정 가이드로 시작한 다음 사용 사례에 맞는 경로를 따르세요. 프로덕션 지침은 [AgentCore payments 문서](https://docs.aws.amazon.com/bedrock-agentcore/)를 확인하고 위의 보안 섹션을 검토하세요.
