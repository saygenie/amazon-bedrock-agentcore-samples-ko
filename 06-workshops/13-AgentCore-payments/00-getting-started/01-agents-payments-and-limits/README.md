# 에이전트에 결제 한도 적용

## 개요

이 자습서는 Coinbase Bazaar의 유료 x402 엔드포인트에 액세스하는 결제 지원 에이전트를 구축합니다. 두 Notebook은 서로 다른 프레임워크로 동일한 결제 흐름을 보여 주어 AgentCore payments가 프레임워크에 독립적임을 확인합니다.

| Notebook | 프레임워크 | 결제 처리 |
|----------|-----------|-----------------|
| `strands_payment_agent.ipynb` | Strands Agents | `AgentCorePaymentsPlugin`(자동 처리, 결제 코드 없음) |
| `langgraph_payment_agent.ipynb` | LangGraph | `PaymentManager.generate_payment_header()`를 사용하는 `wrap_with_auto_402()` |

Payment 인프라(PaymentManager, session, instrument, 결제 한도)는 두 예제에서 동일합니다. 에이전트 프레임워크 통합 방식만 다릅니다.

### 학습 내용

| 기능 | 자습서 주요 내용 |
|---------|-------------------------------|
| 결제 처리 | 에이전트가 Coinbase Bazaar x402 엔드포인트를 호출하고 plugin/wrapper가 402를 자동 처리 |
| 결제 한도 | 예산이 $1.00, $0.50, $0.01인 session을 생성하고 지출을 추적하며 초과 지출 거부 확인 |
| Built-in tools(Strands) | 에이전트가 자체 예산 조회, wallet 목록 표시, Runtime에서 instrument 세부 정보 검사 |
| Wallet 독립적 설계 | 동일한 에이전트 코드가 Coinbase CDP 또는 Stripe(Privy)에서 작동 |

### 자습서 세부 정보

| 정보                | 세부 정보                                                       |
|:--------------------|:----------------------------------------------------------------|
| 자습서 유형         | 대화형                                                          |
| 에이전트 유형       | 단일                                                            |
| 에이전틱 프레임워크 | Strands Agents + LangGraph                                      |
| LLM 모델            | Anthropic Claude Sonnet                                         |
| 자습서 구성 요소    | PaymentManager, AgentCorePaymentsPlugin, x402 엔드포인트         |
| 예제 난이도         | 쉬움                                                            |
| 사용 SDK            | bedrock-agentcore SDK, Strands Agents SDK, LangGraph            |

## 사전 요구 사항

* 자습서 00 완료(`.env`에 manager ARN, connector ID, instrument ID가 있음)
* https://faucet.circle.com/ 에서 받은 testnet USDC로 wallet 자금 충전
* Strands: `pip install 'bedrock-agentcore[strands-agents]'`
* LangGraph: `pip install langchain-aws langgraph bedrock-agentcore pydantic requests python-dotenv`

각 Notebook에서 session을 새로 생성하므로 `.env`의 이전 session은 필요하지 않습니다.

이 자습서는 두 wallet 제공업체(Coinbase CDP 또는 Stripe/Privy) 중 어느 쪽에서도 작동합니다. 에이전트 코드는 같고 자습서 00의 `.env` 값만 다릅니다.

> **Testnet 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC와 함께 Base Sepolia(Ethereum)를 사용합니다. Testnet USDC는 실제 가치가 없습니다.

## 검증

Notebook을 실행한 후 다음 방법으로 결제 한도가 적용되는지 확인합니다.

1. Session 지출 출력에서 각 x402 호출 후 금액이 차감되는지 확인합니다.
2. Session 예산이 소진되면 초과 지출 거부 message가 표시되는지 확인합니다.

## 정리

Payment session은 구성된 `expiryTimeInMinutes`가 지나면 자동으로 만료됩니다. 모든 Notebook 실험을 마친 후 자습서 00의 정리 셀을 실행하여 모든 결제 리소스(Manager, Connector, Instrument)를 삭제하세요.

## 결론

이 자습서는 두 프레임워크를 사용하는 결제 지원 에이전트를 보여 줍니다. Strands 에이전트는 402 자동 처리에 plugin을 사용하고 LangGraph 에이전트는 wrapper 패턴을 사용합니다. 결제 한도는 프레임워크와 관계없이 인프라 수준에서 적용됩니다.
