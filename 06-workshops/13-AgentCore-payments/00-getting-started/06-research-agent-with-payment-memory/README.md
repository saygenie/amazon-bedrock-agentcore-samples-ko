# 결제 Memory를 사용하는 리서치 에이전트

> 전체 단계별 튜토리얼은 `research_agent_with_memory.ipynb`를 참조하세요.

## 개요

이 튜토리얼에서는 AgentCore payments와 AgentCore Memory를 결합해 사용할수록 더 똑똑해지는 리서치 에이전트를 구축합니다. 에이전트는 최신 데이터에 비용을 지불하기 전에 이미 알고 있는 내용을 확인하므로 여러 세션에 걸쳐 비용을 절감합니다.

### 학습 내용

| AgentCore payments 기능 | 이 튜토리얼에서 다루는 내용 |
|---------------------------|-------------------------------|
| 결제 처리 | 최신 데이터 호출 시 `AgentCorePaymentsPlugin`이 x402를 자동 처리 |
| 결제 한도 | API 수준에서 세션 예산($0.20)을 적용하고 Memory가 해당 예산 내 지출을 최적화 |
| 지갑 통합 | 특정 지갑에 종속되지 않아 동일한 코드가 Coinbase CDP 또는 Stripe (Privy)에서 동작 |

### payments와 Memory의 연동 방식

| Memory를 사용하지 않는 경우 | Memory를 사용하는 경우 |
|---------------|-------------|
| 세션마다 동일한 데이터에 다시 결제 | 에이전트가 먼저 Memory를 확인하고 새 데이터에만 결제 |
| 세션 간 비용 정보가 없음 | 에이전트가 현재 세션과 이전 세션의 비용을 비교 |
| 모든 세션을 아무런 컨텍스트 없이 시작 | 에이전트가 사용자 기본 설정과 도구 품질을 기억 |

### 아키텍처

```
┌─────────────────────────────────┐
│  Strands Agent                  │
│  + recall_user_context (@tool)  │
│  + http_request                 │
│  + AgentCorePaymentsPlugin      │
└──────┬──────────┬───────────────┘
       │          │
┌──────▼────┐  ┌──▼──────────────────┐
│  AgentCore│  │  AgentCore payments  │
│  Memory   │  │  ProcessPayment      │
│  (recall) │  │  Session budget      │
└───────────┘  └──────────┬──────────┘
                          │
               ┌──────────▼──────────┐
               │  Wallet Provider     │
               │  Coinbase CDP — or — │
               │  Stripe Privy        │
               └─────────────────────┘
```

워크플로: RECALL(Memory 확인) → DECIDE(결제 또는 건너뛰기) → FETCH(플러그인이 402 처리) → REPORT(비용 투명성)

### 튜토리얼 세부 정보

| 정보                 | 세부 정보                                                       |
|:--------------------|:----------------------------------------------------------------|
| 튜토리얼 유형        | 대화형                                                          |
| 에이전트 유형        | 단일                                                            |
| 에이전트 프레임워크  | Strands Agents                                                  |
| LLM 모델             | Anthropic Claude Sonnet                                         |
| 튜토리얼 구성 요소   | AgentCore payments, AgentCore Memory, AgentCorePaymentsPlugin   |
| 예제 난이도          | 중급                                                            |
| 사용 SDK             | bedrock-agentcore SDK, Strands Agents SDK                       |

## 사전 요구 사항

* Tutorial 00 완료(payment manager와 instrument가 설정된 `.env`가 있어야 함)
* https://faucet.circle.com/ 에서 테스트넷 USDC를 받아 지갑에 충전
* `pip install -r requirements.txt`

이 튜토리얼은 Tutorial 00에서 구성한 Coinbase CDP 또는 Stripe/Privy 지갑 공급자에서 동작합니다. 어느 공급자를 선택하더라도 에이전트 코드는 동일합니다.

> **테스트넷 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC를 사용해 Base Sepolia (Ethereum)에서 실행됩니다. 테스트넷 USDC는 실제 가치가 없습니다.

### IAM 권한

이 Notebook을 실행하는 호출자 자격 증명에는 Tutorial 00의 payments 권한 외에 AgentCore Memory 권한이 필요합니다. 관리자 프로필을 사용하는 로컬 노트북에서는 자동으로 적용됩니다. SageMaker 또는 기타 제한된 환경에서는 실행 역할에 다음 action을 연결하세요.

리소스 ARN의 범위를 AWS 계정과 리전에 맞게 지정하세요. `CreateMemory`와 `ListMemories`는 계정 수준 action이므로 `Resource: "*"`가 필요합니다. 필요한 경우 condition key(예: `aws:RequestTag`)를 사용해 범위를 더 제한하세요.

```json
[
  {
    "Effect": "Allow",
    "Action": [
      "bedrock-agentcore:CreateMemory",
      "bedrock-agentcore:ListMemories"
    ],
    "Resource": "*"
  },
  {
    "Effect": "Allow",
    "Action": [
      "bedrock-agentcore:GetMemory",
      "bedrock-agentcore:DeleteMemory",
      "bedrock-agentcore:BatchCreateMemoryRecords",
      "bedrock-agentcore:RetrieveMemoryRecords"
    ],
    "Resource": "arn:aws:bedrock-agentcore:<REGION>:<ACCOUNT_ID>:memory/*"
  }
]
```

이 권한이 없으면 Step 3에서 `create_memory`가 `AccessDeniedException`을 반환합니다.

## 파일

| 파일 | 설명 |
|------|-------------|
| `research_agent_with_memory.ipynb` | 튜토리얼 Notebook(로컬, Memory + payments 흐름) |
| `requirements.txt` | Python 종속성 |

## 정리

이 튜토리얼에서 생성한 Memory 리소스는 Notebook 마지막의 정리 셀에서 삭제됩니다. 결제 세션은 구성된 `expiryTimeInMinutes`가 지나면 자동으로 만료됩니다. 결제 리소스(Manager, Connector, Instrument)는 Tutorial 00에서 생성한 것이므로 모든 튜토리얼을 마친 뒤 Tutorial 00의 정리 셀에서 삭제하세요.

AgentCore Memory는 저장 및 검색 사용량에 따라 AWS 요금이 발생할 수 있습니다. 실습을 마치면 Notebook의 정리 셀을 실행해 Memory 리소스를 제거하세요.

## 마무리

이 튜토리얼에서는 AgentCore payments와 AgentCore Memory를 결합해 사용할수록 더 똑똑해지고 비용도 절감되는 에이전트를 구축했습니다. Memory는 이전 데이터와 사용자 기본 설정을 불러와 세션 예산 내의 지출을 최적화하며, 세션 예산은 API 수준에서 적용되는 절대 한도로 유지됩니다.

## 다음 단계

- **Tutorial 07** - `../07-multi-agent-payment-orchestrator/` - 에이전트별 예산과 공급자별로 분리된 지갑을 사용하는 멀티 에이전트 오케스트레이션
