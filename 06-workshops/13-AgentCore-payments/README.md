# Amazon Bedrock AgentCore payments - 샘플

Amazon Bedrock AgentCore payments는 AI 에이전트가 유료 API, MCP 서버, 콘텐츠에 액세스할 때 소액 결제를 지원하는 완전관리형 서비스입니다. AI 에이전트는 API 호출, MCP 서버 액세스, 다른 에이전트와의 상호 작용을 통해 점점 더 복잡한 작업을 처리하고 있습니다. 사용량 기반 결제 모델을 도입하는 서비스가 늘어나면서 개발자는 에이전틱 워크플로에 결제를 통합하는 데 어려움을 겪습니다. 이러한 거래는 일반적으로 1달러 미만이거나 1센트보다도 작은 소액 결제이므로, 최소 거래 수수료가 높은 기존 결제 방식은 비용 효율성이 떨어집니다. 한편 콘텐츠 제공업체와 게시자는 AI 에이전트의 콘텐츠 액세스에 paywall을 도입하고 있습니다. AgentCore payments는 stablecoin, 비용 효율적인 소액 결제를 위한 x402 같은 개방형 프로토콜, 에이전트 지출을 제어하는 구성 가능한 guardrail을 사용하여 유료 서비스에 안전하게 즉시 결제하는 솔루션을 개발할 수 있도록 개발자 친화적인 기능을 제공합니다. 이를 통해 수개월이 걸리던 개발 작업을 며칠로 줄일 수 있습니다.

![AgentCore payments](00-getting-started/00-setup-agentcore-payments/images/main-image.png)

> **Preview** - AgentCore payments는 현재 preview로 제공됩니다. 정식 출시 전에 기능과 API가 변경될 수 있습니다.

## 자습서

설정부터 고급 멀티 에이전트 오케스트레이션까지 단계별로 다루는 Notebook입니다.

| # | 자습서 | 학습 내용 |
|---|----------|-------------------|
| 00 | [설정](00-getting-started/00-setup-agentcore-payments/) | IAM 역할, PaymentManager, PaymentConnector, embedded wallet, 예산이 설정된 PaymentSession 생성 |
| 01 | [에이전트 결제 한도](00-getting-started/01-agents-payments-and-limits/) | 예산을 적용하면서 x402 엔드포인트에 자동으로 결제하는 Strands 및 LangGraph 에이전트 |
| 02 | [AgentCore Runtime에 배포](00-getting-started/02-deploy-to-agentcore-runtime/) | 역할 분리와 observability를 적용한 결제 에이전트 패키징 및 배포 |
| 03 | [Wallet 작업](00-getting-started/03-user-onboarding-wallet-funding/) | 사용자 온보딩, wallet 자금 충전, 위임, 잔액 확인, 멀티 네트워크 결제 수단 |
| 04 | [Gateway + Coinbase Bazaar](00-getting-started/04-agent-with-coinbase-bazaar-via-gateway/) | AgentCore Gateway를 통해 10,000개 이상의 유료 MCP 도구를 검색하고 호출 시 결제 |
| 05 | [Browser + payments](00-getting-started/05-agent-with-browser-tool-pay-for-content/) | 브라우저 세션에서 402 paywall을 가로채고 웹 콘텐츠에 결제 |
| 06 | [결제 Memory를 사용하는 리서치 에이전트](00-getting-started/06-research-agent-with-payment-memory/) | AgentCore payments와 AgentCore Memory를 결합해 이전 데이터를 기억하고 세션 간 중복 유료 호출 방지 |
| 07 | [멀티 에이전트 오케스트레이터](00-getting-started/07-multi-agent-payment-orchestrator/) | 에이전트별 wallet과 예산을 사용하는 여러 에이전트 및 Runtime 배포 |

## 사용 사례

AgentCore payments를 end-to-end로 보여 주는 실제 사용 사례입니다. 전체 목록은 [02-use-cases/](02-use-cases/)에서 확인하세요.

| 사용 사례 | 주요 내용 |
|---|---|
| [콘텐츠 결제(Browser Use)](02-use-cases/pay-for-content-browser-use/) | Strands 에이전트가 AgentCore Browser Tool로 paywall이 적용된 웹사이트를 탐색하고, 페이지 DOM에 포함된 x402 요구 사항을 읽고, `ProcessPayment`를 호출해 USDC 증명을 생성한 다음 잠금 해제된 콘텐츠를 반환합니다. 결제 단계에 사람의 개입이 필요하지 않습니다. 배포 가능한 CDK 콘텐츠 제공업체 스택을 포함합니다. |
| [데이터 결제(Heurist)](02-use-cases/pay-for-data/) | 금융 리서치 에이전트가 실시간 가격과 거시경제 데이터를 제공하는 유료 Heurist x402 엔드포인트를 호출하고, Code Interpreter로 결과를 분석한 뒤 차트와 보고서를 S3로 내보냅니다. `AgentCorePaymentsPlugin`을 통해 Base mainnet에서 USDC로 결제합니다. 전체 AgentCore observability를 적용하여 AgentCore Runtime에 배포합니다. **Mainnet - 실제 USDC가 필요하므로 실행 전에 wallet에 자금을 충전하세요.** |

## 사전 요구 사항

- Python 3.10+
- AWS CLI 구성(`aws sts get-caller-identity`로 확인)
- AgentCore payments preview에 액세스할 수 있는 AWS 계정
- Jupyter (`pip install jupyter`)
- Wallet 제공업체 자격 증명(Coinbase CDP 또는 Stripe/Privy) - 자습서 00 참조

## 보안

- 모든 자습서는 **testnet만** 사용합니다(Base Sepolia / Solana Devnet). 실제 자금은 사용하지 않습니다.
- `.env` 파일이나 private key를 절대 commit하지 마세요. 프로덕션 자격 증명에는 AWS Secrets Manager를 사용하세요.
- IAM 최소 권한 원칙에 따라 ControlPlaneRole, ManagementRole, ProcessPaymentRole을 분리하세요.

## 리소스

- [AgentCore payments 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
- [출시 블로그 게시물](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/)
- [Coinbase 발표](https://www.coinbase.com/en-ca/blog/introducing-amazon-bedrock-agentcore-payments-powered-by-x402-and-coinbase)
- [Stripe 발표](https://stripe.com/newsroom/news/aws-stripe-agentcore-privy)
