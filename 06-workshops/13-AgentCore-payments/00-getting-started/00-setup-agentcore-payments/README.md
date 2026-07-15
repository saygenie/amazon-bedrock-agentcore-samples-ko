# AgentCore payments 설정

> **비용 알림:** 이 자습서는 IAM 역할, CloudWatch log group, AgentCore payment 리소스를 생성합니다. AWS 비용이 발생할 수 있습니다. 완료 후 정리 셀을 실행하고 IAM 역할과 log group을 삭제하세요.

## 개요

이 자습서는 AWS SDK(boto3)를 사용한 Amazon Bedrock AgentCore payments 전체 설정을 안내합니다. 결제 지원 에이전트를 구축하기 전에 필요한 IAM 역할 생성, wallet 자격 증명 구성, payment stack 프로비저닝을 수행합니다.

AgentCore payments는 wallet 제공업체에 독립적입니다. 이 자습서는 Coinbase CDP와 Stripe(Privy) 제공업체를 모두 다룹니다.

### 리소스 계층

애플리케이션당 하나의 PaymentManager를 사용합니다. Connector와 instrument는 하위 리소스입니다.

```
PaymentManager(앱당 1개 - 인증 구성 + 서비스 역할 보유)
  ├── Connector: CoinbaseCDP(credential provider에 연결)
  │    └── Instrument(사용자 및 네트워크별 embedded wallet)
  ├── Connector: StripePrivy(credential provider에 연결)
  │    └── Instrument(사용자 및 네트워크별 embedded wallet)
  └── Session(예산 + 만료, 모든 instrument와 함께 작동)
```

Wallet 제공업체별로 manager를 따로 생성할 필요가 없습니다. 하나의 manager에 여러 connector를 사용합니다. 에이전트가 어떤 instrument를 사용하든 세션 예산이 적용됩니다.

### 자습서 세부 정보

| 정보                | 세부 정보                                                  |
|:--------------------|:-----------------------------------------------------------|
| 자습서 유형         | 작업 기반                                                   |
| 에이전트 유형       | 해당 없음(설정만 수행)                                     |
| 에이전틱 프레임워크 | 해당 없음                                                  |
| LLM 모델            | 해당 없음                                                  |
| 자습서 구성 요소    | IAM 역할, Payment Manager, Connector, Instrument, Session |
| 자습서 분야         | 여러 산업 분야                                             |
| 예제 난이도         | 쉬움                                                       |
| 사용 SDK            | boto3(AWS SDK)                                             |

### 자습서 주요 기능

* IAM 역할 분리(4개 역할: ControlPlane, Management, ProcessPayment, ResourceRetrieval)
* Control Plane 설정: Credential Provider → Payment Manager → Payment Connector
* Data Plane 설정: Payment Instrument(wallet) → Payment Session(예산)
* Coinbase CDP 및 Stripe(Privy) wallet 제공업체 모두 지원
* Wallet 자금 충전 지침(testnet USDC)
* 전체 정리

## 사전 요구 사항

* Python 3.10+
* AWS 자격 증명 구성(`aws sts get-caller-identity`로 확인)
* AgentCore payments preview allowlist에 등록된 AWS 계정
* Coinbase: https://portal.cdp.coinbase.com/ 에서 발급한 CDP API key
* Stripe(Privy): https://dashboard.privy.io/ 의 개발자 계정

## 수동 단계(Notebook 외부 작업)

이 자습서의 대부분은 자동화되어 있어 셀을 위에서 아래로 실행하면 됩니다. 다음 세 단계는 Notebook 외부 작업이 필요합니다.

| 시점 | 작업 | 위치 | 시간 |
|------|------|-------|------|
| **실행 전** | Wallet 제공업체 자격 증명 발급 | `providers/coinbase_cdp_account_setup.ipynb` 또는 `providers/stripe_privy_account_setup.ipynb` 실행 | 약 15분 |
| **7b단계** | Wallet 자금 충전 - 1단계: faucet 열기 | [faucet.circle.com](https://faucet.circle.com/)으로 이동 | 약 2분 |
| **7b단계** | Wallet 자금 충전 - 2단계: 주소 붙여넣기 | Faucet form에 wallet 주소 붙여넣기 | |
| **7b단계** | Wallet 자금 충전 - 3단계: USDC 요청 | 10 USDC를 요청하고 확인 대기 | |
| **7b단계** | 서명 위임 - Coinbase 1단계 | CDP Portal 열기 | 약 5분 |
| **7b단계** | 서명 위임 - Coinbase 2단계 | Wallets → Embedded Wallet → Policies로 이동 | |
| **7b단계** | 서명 위임 - Coinbase 3단계 | Delegated Signing 활성화 | |
| **7b단계** | 서명 위임 - Privy 1단계 | localhost:3000에서 Privy reference frontend 열기 | |
| **7b단계** | 서명 위임 - Privy 2단계 | 최종 사용자 이메일로 로그인 | |
| **7b단계** | 서명 위임 - Privy 3단계 | **Connect agent**를 선택한 다음 **Give access** 선택 | |

자금 충전 및 위임 단계를 완료하지 않으면 자습서 01의 `ProcessPayment`가 실패합니다. Notebook의 7b단계에 도달하면 명확한 ACTION 안내가 출력됩니다.

## 검증

Notebook을 완료한 후 설정 성공 여부를 확인합니다.

1. `.env`에 `PAYMENT_MANAGER_ARN`, `INSTRUMENT_ID`, `SESSION_ID`가 있는지 확인합니다.
2. `aws sts get-caller-identity`를 실행하여 AWS 자격 증명이 활성 상태인지 확인합니다.
3. 7단계의 instrument 잔액 출력을 확인하여 wallet에 testnet USDC가 있는지 확인합니다.

## 정리

> **경고:** 정리는 되돌릴 수 없으며 모든 결제 리소스(Manager, Connector, Instrument)와 관련 transaction 기록을 영구 삭제합니다. 정리를 실행하기 전에 이후의 모든 자습서를 완료했는지 확인하세요.

모든 자습서를 마치면 비용이 발생하지 않도록 리소스를 정리하세요.

1. `setup_agentcore_payments.ipynb` 하단의 정리 셀을 실행하여 Payment Manager와 모든 하위 리소스를 삭제합니다.
2. 4개의 IAM 역할이 더 이상 필요하지 않으면 IAM console에서 삭제합니다.
3. CloudWatch log group `/aws/vendedlogs/bedrock-agentcore/<manager-id>`를 삭제합니다.

Payment session은 구성된 `expiryTimeInMinutes`가 지나면 자동으로 만료됩니다.

## 결론

이 자습서는 IAM 역할, wallet 자격 증명, payment stack을 포함한 전체 AgentCore payments 인프라를 설정합니다. 이후의 모든 자습서(01~07)는 이 리소스를 사용합니다.
