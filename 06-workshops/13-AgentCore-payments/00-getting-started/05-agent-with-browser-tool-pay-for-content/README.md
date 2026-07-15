# Browser Tool을 사용하는 에이전트 - 제한된 콘텐츠 결제

> **패턴 참고.** 이 Notebook은 Browser + payment 아키텍처를 보여 줍니다. End-to-end로 실행하려면 x402를 지원하는 콘텐츠 엔드포인트가 필요합니다.

> **Testnet 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC와 함께 Base Sepolia(Ethereum)를 사용합니다. Testnet USDC는 실제 가치가 없습니다. AgentCore Browser session은 사용 시간에 따라 AWS 비용이 발생할 수 있습니다.

> 전체 단계별 자습서는 `browser_paywall_payments.ipynb`를 참조하세요.

## 개요

AgentCore Browser와 payments를 함께 사용하면 에이전트가 x402를 지원하고 paywall이 적용된 웹사이트에 자율적이고 안전하게 액세스할 수 있습니다. 이 자습서는 AgentCore Browser(관리형 cloud Chromium) + Playwright를 사용하는 사용자 지정 Strands `@tool`을 구축합니다. 동일한 browser session 내에서 x402 엔드포인트를 탐색하고, 402 응답을 감지하고, `PaymentManager.generate_payment_header()`를 통해 결제에 서명한 뒤 proof header와 함께 재시도합니다.

### 학습 내용

| AgentCore payments 기능 | 자습서 주요 내용 |
|---------------------------|-------------------------------|
| 결제 처리 | 사용자 지정 도구를 위한 수동 서명 패턴인 `PaymentManager.generate_payment_header()` |
| 결제 한도 | 브라우저 기반 결제에 session 예산 적용 |
| Wallet 통합 | 동일한 코드가 Coinbase CDP 또는 Stripe(Privy)에서 작동하는 wallet 독립적 방식 |

### 두 결제 패턴 비교

| 패턴 | 도구 | 결제 처리 | 적합한 용도 |
|---------|------|-----------------|----------|
| Plugin(자습서 01) | `http_request` 또는 MCP 도구 | `AgentCorePaymentsPlugin`이 402를 가로채고 외부에서 재시도 | API 엔드포인트, MCP 도구 |
| Browser(이 자습서) | 사용자 지정 `browse_with_payment` | 도구가 Playwright를 통해 내부에서 402를 처리하고 동일한 session에서 재시도 | 브라우저 rendering 콘텐츠, paywall |

API 호출에는 plugin 패턴을 사용하세요. 결제 재시도 중 session 상태(cookie, auth token, DOM context)를 유지해야 할 때는 browser 패턴을 사용하세요.

### 아키텍처

```
┌─────────────────────────────────┐
│  Strands Agent                  │
│  + browse_with_payment (@tool)  │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│  AgentCore Browser              │
│  BrowserClient → Chromium       │
│  Playwright CDP + interception  │
└──────────┬──────────────────────┘
           │ page.goto → 402 → pay → retry
┌──────────▼──────────────────────┐   ┌──────────────────┐
│  AgentCore payments             │──▶│ Wallet Provider   │
│  generate_payment_header()      │   │ Coinbase CDP      │
│  Session budget enforcement     │   │   — or —          │
│                                 │   │ Stripe Privy      │
└─────────────────────────────────┘   └──────────────────┘
```

### 자습서 세부 정보

| 정보                | 세부 정보                                                               |
|:--------------------|:------------------------------------------------------------------------|
| 자습서 유형         | 패턴 참고                                                               |
| 에이전트 유형       | 단일                                                                    |
| 에이전틱 프레임워크 | Strands Agents                                                          |
| LLM 모델            | Anthropic Claude Sonnet                                                 |
| 자습서 구성 요소    | AgentCore Browser, Playwright, AgentCore payments, x402                 |
| 예제 난이도         | 중급                                                                    |
| 사용 SDK            | bedrock-agentcore SDK(BrowserClient + PaymentManager), Strands Agents   |

## 사전 요구 사항

* 자습서 00 완료(`.env`에 payment manager 및 instrument가 있음)
* https://faucet.circle.com/ 에서 받은 testnet USDC로 wallet 자금 충전
* `pip install -r requirements.txt`
* `python -m playwright install chromium`
* 탐색할 x402 지원 엔드포인트

이 자습서는 자습서 00에서 구성한 두 wallet 제공업체(Coinbase CDP 또는 Stripe/Privy) 중 어느 쪽에서도 작동합니다. 무엇을 선택하든 에이전트 코드는 같습니다.

> **Testnet 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC와 함께 Base Sepolia(Ethereum)를 사용합니다. Testnet USDC는 실제 가치가 없습니다.

## 정리

> **비용 알림:** AgentCore Browser session에는 브라우저 Runtime 시간(분)당 요금이 발생합니다. Payment session은 무료지만 기반 Payment Manager와 Instrument에는 자습서 00을 통해 삭제할 때까지 표준 AWS 요금이 발생합니다.

AgentCore Browser session(BrowserClient)은 구성된 timeout이 지나면 자동으로 만료됩니다. Payment session은 구성된 `expiryTimeInMinutes`가 지나면 만료됩니다. 이 자습서에서 생성한 session은 수동으로 정리할 필요가 없습니다.

## 결론

이 자습서는 paywall이 적용된 x402 콘텐츠에 액세스하기 위한 Browser + payment 아키텍처 패턴을 보여 줍니다. 결제 재시도 중 browser session 상태(cookie, auth token, DOM context)를 유지해야 할 때 이 패턴을 사용하세요. API 전용 엔드포인트에는 자습서 01의 plugin 패턴을 사용하세요.
