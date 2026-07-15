# AgentCore Gateway를 통해 에이전트를 Coinbase Bazaar와 통합

## 개요

Coinbase x402 Bazaar는 10,000개 이상의 사용량 기반 x402 엔드포인트를 제공하는 MCP marketplace입니다. 에이전트는 semantic search로 도구를 검색하고 x402를 사용하여 호출당 비용을 결제합니다. 이 자습서는 Strands 에이전트를 AgentCore Gateway를 통해 Bazaar에 연결하여 엔드포인트 검색과 자동 결제 처리를 결합합니다.

### 학습 내용

| AgentCore payments 기능 | 자습서 주요 내용 |
|---------------------------|-------------------------------|
| 엔드포인트 검색 | AgentCore Gateway를 통해 Coinbase x402 Bazaar의 유료 MCP 도구 검색 |
| 결제 처리 | 에이전트가 검색된 도구를 호출하고 `AgentCorePaymentsPlugin`이 402를 자동 처리 |
| 결제 한도 | Session 예산에서 여러 Bazaar 도구 호출의 누적 지출 추적 |
| Wallet 통합 | 동일한 코드가 Coinbase CDP 또는 Stripe(Privy)에서 작동하며 `.env` 값만 다름 |

### 아키텍처

```
┌─────────────────────────────────┐
│  🧑‍💻 Developer Code              │
│  Strands Agent                  │
│  + AgentCorePaymentsPlugin      │
│  + MCPClient (streamable HTTP)  │
└──────────┬──────────────────────┘
           │ MCP protocol
┌──────────▼──────────────────────┐
│  🔀 AgentCore Gateway            │
│  Target: Coinbase x402 Bazaar   │
│  (No outbound auth)             │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│  🌐 Coinbase x402 Bazaar        │
│  search_resources → discover    │
│  proxy_tool_call  → call + pay  │
└──────────┬──────────────────────┘
           │ HTTP 402 → pay → retry
┌──────────▼──────────────────────┐   ┌──────────────────┐
│  ☁️ AgentCore payments           │──▶│ 🏦 Wallet Provider│
│  Payment Manager + Session      │   │ Coinbase CDP     │
│  Payment Instrument             │   │   — or —         │
│  ProcessPayment (sign + proof)  │   │ Stripe Privy     │
└─────────────────────────────────┘   │ (routed by       │
                                      │  PaymentConnector)│
                                      └──────────────────┘
```

### 자습서 세부 정보

| 정보                | 세부 정보                                                       |
|:--------------------|:----------------------------------------------------------------|
| 자습서 유형         | 작업 기반                                                       |
| 에이전트 유형       | 단일                                                            |
| 에이전틱 프레임워크 | Strands Agents                                                  |
| LLM 모델            | Anthropic Claude Sonnet                                         |
| 자습서 구성 요소    | AgentCore Gateway, Coinbase Bazaar MCP, AgentCorePaymentsPlugin |
| 예제 난이도         | 중급                                                            |
| 사용 SDK            | AgentCore CLI(`@aws/agentcore`), bedrock-agentcore SDK, Strands Agents SDK |

## 사전 요구 사항

* 자습서 00 완료(`.env`가 있음)
* https://faucet.circle.com/ 에서 받은 testnet USDC로 wallet 자금 충전
* AgentCore CLI: `npm install -g @aws/agentcore`(Node.js 20+ 필요)
* AWS CLI 구성(`aws configure`)

이 자습서는 자습서 00에서 구성한 두 wallet 제공업체(Coinbase CDP 또는 Stripe/Privy) 중 어느 쪽에서도 작동합니다. 무엇을 선택하든 에이전트 코드는 같습니다.

> **Testnet 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC와 함께 Base Sepolia(Ethereum)를 사용합니다. Testnet USDC는 실제 가치가 없습니다.

## Gateway 설정

### 옵션 A: AgentCore Console(권장)

1. [Amazon Bedrock AgentCore console](https://console.aws.amazon.com/bedrock-agentcore/) 열기
2. Gateway → Create Gateway → Add Target으로 이동
3. Target type: **Integrations**
4. **Coinbase x402 Bazaar** 선택
5. Outbound 인증은 필요하지 않음(No Authorization이 기본값)

### 옵션 B: AgentCore CLI

```bash
agentcore create --name BazaarAgent --defaults
agentcore add gateway --name BazaarGateway
agentcore add gateway-target \
  --name CoinbaseBazaar \
  --type mcp-server \
  --endpoint https://api.cdp.coinbase.com/platform/v2/x402/discovery/mcp \
  --gateway BazaarGateway
agentcore deploy -y
agentcore fetch access --name BazaarGateway --type gateway
```

출력의 `GATEWAY_URL`을 `.env` 파일에 추가합니다.

## 정리

> **비용 알림:** AgentCore Gateway의 요청 및 데이터 전송에는 AWS 비용이 발생합니다. 작업을 마친 후 정리를 실행하여 지속적인 비용을 방지하세요.

작업을 마치면 Gateway를 제거합니다.

```bash
agentcore remove gateway --name BazaarGateway -y
```

Payment session은 자동으로 만료됩니다. Payment 리소스는 자습서 00의 정리 작업을 통해 관리합니다.

## 결론

이 자습서는 AgentCore Gateway를 통해 에이전트를 Coinbase Bazaar와 통합하여 MCP 기반 도구 검색과 자동 x402 결제 처리를 결합합니다. Gateway 패턴은 유료 MCP 도구를 중앙에서 관리하고 AgentCorePaymentsPlugin은 결제 로직을 자동으로 처리합니다.
