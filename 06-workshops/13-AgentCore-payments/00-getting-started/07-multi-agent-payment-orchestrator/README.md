# 멀티 에이전트 결제 오케스트레이터

## 개요

이 튜토리얼에서는 에이전트별 예산, 다중 지갑 지원, 전체 지출 귀속 기능을 갖춘 멀티 에이전트 시스템을 구축합니다. 그런 다음 역할 분리, 관찰 가능성, 온라인 평가를 적용해 AgentCore Runtime에 배포합니다.

> 전체 단계별 튜토리얼은 `multi_agent_payments.ipynb`를 참조하세요.

### 학습 내용

| AgentCore payments 기능 | 이 튜토리얼에서 다루는 내용 |
|---------------------------|-------------------------------|
| 결제 처리 | 두 전문 에이전트가 각각 `AgentCorePaymentsPlugin`을 사용해 x402 엔드포인트를 독립적으로 호출 |
| 결제 한도 | 에이전트별 세션 예산($0.50 및 $0.20), 독립적인 지출 추적, 예산 소진 처리 |
| 지갑 통합 | 하나의 PaymentManager, 두 개의 connector(Coinbase CDP + Stripe Privy), 두 개의 instrument로 다중 지갑 구성 |
| 관찰 가능성 | CloudWatch GenAI Observability Dashboard에서 에이전트별 결제 trace와 예산 진행 상황 확인 |

### 아키텍처

```
┌─────────────────────────────────────┐
│  App Backend (ManagementRole)       │
│  Creates Session A ($0.50, Coinbase)│
│  Creates Session B ($0.20, Privy)   │
│  Invokes Orchestrator               │
└──────────┬──────────────────────────┘
           │ payload: sessions + instruments
┌──────────▼──────────────────────────┐
│  AgentCore Runtime                  │
│  (ProcessPaymentRole)               │
│                                     │
│  Orchestrator (NO plugin)           │
│    ├── Research Agent               │
│    │   Coinbase wallet, Session A   │
│    ├── Discovery Agent              │
│    │   Privy wallet, Session B      │
│    └── check_budgets tool           │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  AgentCore payments                 │
│  Session A ←→ Coinbase CDP          │
│  Session B ←→ Stripe Privy          │
│  Independent budget enforcement     │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  CloudWatch + Evaluations           │
│  Per-agent payment traces           │
│  Online eval scores                 │
└─────────────────────────────────────┘
```

### 튜토리얼 세부 정보

| 정보                 | 세부 정보                                                                        |
|:--------------------|:---------------------------------------------------------------------------------|
| 튜토리얼 유형        | 작업 기반                                                                        |
| 에이전트 유형        | 멀티 에이전트(orchestrator + 전문 에이전트 2개)                                  |
| 에이전트 프레임워크  | Strands Agents(agents-as-tools pattern)                                          |
| LLM 모델             | Anthropic Claude Sonnet                                                          |
| 튜토리얼 구성 요소   | AgentCore payments, AgentCore Runtime, AgentCore CLI, AgentCore Evaluations      |
| 예제 난이도          | 고급                                                                             |
| 사용 SDK             | bedrock-agentcore SDK, Strands Agents SDK, AgentCore CLI (`@aws/agentcore`)      |

## 사전 요구 사항

* Tutorial 00b 완료(Coinbase와 Privy가 모두 설정된 다중 공급자 `.env`)
* https://faucet.circle.com/ 에서 테스트넷 USDC를 받아 두 지갑 모두 충전
* AgentCore CLI: `npm install -g @aws/agentcore`(Node.js 20+ 필요)
* Docker 설치(배포 중 컨테이너 빌드에 사용)
* `pip install -r requirements.txt`

AWS 자격 증명에는 Tutorial 00의 `setup_payment_roles()`에서 생성한 IAM 권한이 필요합니다. Tutorial 00b를 성공적으로 완료했다면 필요한 권한이 이미 있습니다.

> **테스트넷 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC를 사용해 Base Sepolia (Ethereum)에서 실행됩니다. 테스트넷 USDC는 실제 가치가 없습니다.

## 파일

| 파일 | 설명 |
|------|-------------|
| `multi_agent_payments.ipynb` | 튜토리얼 Notebook(로컬 + 배포 + 평가) |
| `payment_orchestrator.py` | AgentCore Runtime용 에이전트 코드(페이로드 기반, 상태 비저장) |
| `requirements.txt` | Python 종속성 |

## 정리

> **비용 안내:** AgentCore Runtime 배포, 온라인 평가 및 CloudWatch 관찰 가능성 기능을 사용하면 AWS 요금이 발생합니다. 지속적인 비용을 방지하려면 실습을 마친 뒤 정리 작업을 실행하세요.

AgentCore Runtime과 온라인 평가에는 요금이 발생합니다. 실습을 마치면 다음과 같이 제거하세요.

```bash
cd PaymentAgent && agentcore remove all -y
```

이 명령은 Runtime 배포, 평가 구성, CloudWatch log group 및 관련 리소스를 제거합니다.

**결제 세션**: 구성된 `expiryTimeInMinutes`(이 튜토리얼에서는 60분)가 지나면 자동으로 만료됩니다. 수동으로 삭제할 필요가 없습니다.

## 마무리

이 튜토리얼에서는 에이전트별 예산, 다중 지갑 지원 및 전체 지출 귀속을 갖춘 멀티 에이전트 결제 오케스트레이션을 살펴봤습니다. 독립적인 결제 세션을 사용하는 전문 에이전트를 조율하고 예산 소진 시 지능적으로 장애 조치하는 오케스트레이터 구축 방법을 보여줍니다.
