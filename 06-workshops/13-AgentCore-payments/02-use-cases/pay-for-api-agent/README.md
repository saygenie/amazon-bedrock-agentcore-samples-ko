# API 사용료 결제

## 개요

**Amazon Bedrock AgentCore Payments**를 사용하면 AI 에이전트가 디지털 서비스 비용을
자율적으로 결제할 수 있습니다. 에이전트는 프라이빗 키를 보유하지 않으며 거래마다
사람의 승인을 받을 필요가 없습니다.

이 사용 사례에서는 AgentCore Payments를 통해 사용량 기반 HTTP API 액세스 비용을
자율적으로 결제하는 Strands 에이전트를 구축합니다. 에이전트는 구성된
`PaymentInstrument`에 따라 Ethereum Virtual Machine(EVM)(Base Sepolia) 또는
Solana(Solana Devnet)에서 서명합니다. 판매자는 AWS CDK로 배포되는 간단한
"Fun Facts" 서비스입니다. AWS Lambda 함수가 지원하는 Amazon API Gateway HTTP
API로, 호출당 **$0.01**를 청구하고 x402 응답에서 두 네트워크를 모두 허용합니다.

에이전트가 정보를 요청하면 판매자는 결제 요구 사항과 함께 HTTP 402를 반환합니다.
에이전트는 요구 사항을 AgentCore Payments의 `ProcessPayment` 작업으로 전달하고
서명된 증명을 받습니다. 그런 다음 증명을 첨부하여 요청을 다시 시도하고 콘텐츠를
반환합니다. 에이전트는 프라이빗 키를 직접 다루지 않도록 설계되었습니다.

AgentCore Payments는 내부적으로 지갑, 서명 키, 온체인 정산을 관리합니다.
`PaymentManager`가 **Coinbase Developer Platform(CDP)** 또는
**Stripe via Privy**에 연결되어 있더라도 에이전트 코드는 동일합니다. 서비스는
결제 수단에 연결된 커넥터에서 적절한 서명자를 선택합니다.

이 Notebook은 **자체 완결형**입니다. 전체 AgentCore Payments 스택을 인라인으로
프로비저닝하고(§5), 동일한 커넥터 아래에 두 개의
`EMBEDDED_CRYPTO_WALLET` 결제 수단(ETHEREUM + SOLANA)을 생성하며, 함께 제공되는
CDK 스택에서 판매자를 배포합니다(§3). `PaymentManager`와 하나 이상의
`PaymentInstrument`가 이미 존재하면 Notebook이 §4에서 이를 감지하고 인라인
설정을 건너뜁니다.


### 사용 사례 세부 정보

| 항목                | 세부 정보                                                              |
|:--------------------|:----------------------------------------------------------------------|
| 사용 사례 유형      | 자율 소액 결제를 사용하는 에이전트 기반 HTTP API 이용                 |
| AgentCore 구성 요소 | Amazon Bedrock AgentCore Payments                                     |
| 지갑 공급자         | Coinbase CDP ✅   ·   Stripe via Privy ✅                             |
| 결제 프로토콜       | 전송 구간에서 x402(HTTP 402 Payment Required)                         |
| 에이전트 유형       | 단일                                                                  |
| 에이전트 프레임워크 | Strands Agents                                                        |
| LLM 모델            | Anthropic Claude Sonnet 4.5(Amazon Bedrock, `us.` inference profile)  |
| 예제 난이도         | 중급                                                                  |
| 사용 SDK            | boto3                                                                 |

### 아키텍처

모든 유료 요청에는 세 주체가 참여합니다.

1. **Strands 에이전트** - 호출하는 유일한 도구는 `http_request`입니다.
   `AgentCorePaymentsPlugin`이 HTTP 402 응답을 가로채고 결제 핸드셰이크를
   투명하게 처리합니다.
2. **Amazon Bedrock AgentCore Payments** - `ProcessPayment`를 수신하고 결제
   수단에 연결된 지갑(Coinbase CDP 또는 Privy)을 사용하여 서명된 x402 증명을
   반환합니다.
3. **판매자(CDK 스택)** - Amazon API Gateway 뒤에서 실행되는 AWS Lambda
   함수로, 402 요청을 발행하고 증명을 검증한 후 콘텐츠를 제공합니다.

네 개의 IAM 역할은 **최소 권한 원칙**에 따라 운영 책임을 분리합니다. 각 역할에는
해당 작업에 필요한 권한만 있으며, 다른 역할 전용 작업에는 명시적인 `Deny`
문이 적용됩니다.

- `AgentCorePaymentsControlPlaneRole` - Manager, Connector, Credential Provider 관리
- `AgentCorePaymentsManagementRole` - Instrument 및 Session 관리(`ProcessPayment`에 명시적 `Deny`)
- `AgentCorePaymentsProcessPaymentRole` - 결제 서명, Instrument 및 Session 읽기
- `AgentCorePaymentsResourceRetrievalRole` - 자격 증명 검색을 위해 런타임에 AgentCore Payments가 수임

`test/integration/setup-roles.sh`는 적절한 정책을 사용하여 네 역할을 모두
생성합니다. 전체 정책 세부 정보와 직무 분리 모델에 관한 설명은 공개
[AgentCore Payments용 IAM 역할](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html)
문서를 참조하세요.

<div style="text-align:left">
    <img src="images/architecture_pay_for_api.png" alt="API 사용료 결제 아키텍처 다이어그램: 사용자가 AgentCore Runtime의 Strands 에이전트에 프롬프트를 보내면 에이전트가 Amazon API Gateway와 AWS Lambda의 유료 HTTP API를 호출합니다. 판매자는 결제 요구 사항과 함께 HTTP 402를 반환하고, AgentCore Payments는 Coinbase CDP 또는 Stripe via Privy를 통해 결제에 서명합니다. 에이전트가 서명된 증명으로 요청을 다시 시도하면 판매자는 x402 facilitator를 통해 온체인에서 정산하고 200 OK를 반환하며, 운영자는 GetPaymentSession을 통해 지출을 감사할 수 있습니다." width="75%"/>
</div>

**번호가 지정된 흐름(다이어그램과 일치)**

1. **사용자**가 **에이전트**(AgentCore Runtime + Strands)에 쿼리를 보냅니다.
2. 에이전트가 **Amazon API Gateway** → **AWS Lambda**에 호스팅된 유료 API를 호출합니다.
3. 판매자가 **HTTP 402 Payment Required**와 결제 요구 사항 페이로드로 응답합니다.
4. 에이전트가 요구 사항을 **AgentCore Payments**에 전달합니다. AgentCore Payments는
   일치하는 `PaymentInstrument`를 선택하고 세션 예산을 확인한 후 구성된 지갑
   공급자(Coinbase CDP 또는 Stripe via Privy)를 통해 결제에 서명합니다.
5. 에이전트가 서명된 `X-PAYMENT` 헤더를 사용하여 요청을 다시 시도합니다. 판매자는
   이를 검증하고 x402 facilitator를 통해 온체인에서 정산한 후 콘텐츠와 함께
   **200 OK**를 반환합니다.
6. 에이전트가 사용자에게 응답합니다. 운영자는 `GetPaymentSession`을 통해 지출을 감사합니다.

### 사용 사례의 주요 기능

* 에이전트가 프라이빗 키를 보유하지 않도록 설계 - AgentCore Payments가 구성된
  `PaymentManager`와 `PaymentConnector`를 통해 모든 청구에 서명
* 지갑 공급자 독립적 - 동일한 에이전트 코드가 Coinbase CDP 결제 수단 또는
  Stripe-via-Privy 결제 수단에서 실행
* 결제 세션의 `maxSpendAmount`를 통해 사람이 예산을 제어
* IAM 역할 분리: `ManagementRole`은 세션을 생성하고 `ProcessPaymentRole`은
  결제에 서명(양방향에 명시적인 `Deny`가 있으며 문서가 아닌 IAM으로 적용)
* `GetPaymentSession`을 통한 전체 감사 추적 - 운영자가 에이전트의 정확한 지출 확인
* 자체 완결형 - 깨끗한 AWS 계정에서 Notebook 실행 가능

---

## 결제 프로토콜 가용성

AgentCore Payments는 여러 지갑 공급자를 지원합니다. 전송 형식(암호화폐 정산용
x402)은 구현 세부 사항입니다. 이 사용 사례의 에이전트 코드는 공급자에 따라
달라지지 않습니다. 서비스는 결제 수단에 연결된 커넥터에서 적절한 서명자를
선택합니다.

| 지갑 공급자 | 커넥터 유형 | 상태 | 참고 |
|:----------------|:---------------|:-------|:------|
| **Coinbase CDP** | `CoinbaseCDP` | ✅ 사용 가능 - EVM + Solana | API Key ID, API Key Secret, Wallet Secret. 사용하기 전에 Project → Wallet → Embedded Wallets → Policies에서 **"Delegated signing"을 활성화**하세요. §5의 인라인 설정에서 Coinbase CDP 지갑을 프로비저닝합니다. |
| **Stripe**(via Privy) | `StripePrivy` | ✅ 사용 가능 - EVM + Solana | App ID, App Secret, Authorization Key ID, P-256 Authorization Private Key. Privy는 `wallet-auth:` 접두사가 붙은 프라이빗 키를 반환합니다. 저장하기 전에 **접두사를 제거**하세요. §5의 인라인 설정에서 Privy 기반 지갑을 프로비저닝합니다. Privy에는 허브 리디렉션이 필요하지 않습니다. 자격 증명 공급자에 등록된 권한 부여 키가 서명 위임 역할을 합니다. |

---

## 사전 요구 사항

- 선택한 리전에서 Amazon Bedrock AgentCore Payments를 사용할 수 있는 **AWS 계정**
- 선택한 리전에서 **Anthropic Claude Sonnet 4.5**에 대한 **Amazon Bedrock 액세스** 활성화(cross-region inference profile `us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Jupyter 커널이 포함된 **Python 3.10+**. "Running cells requires the ipykernel package"가 표시되면 `python3 -m pip install ipykernel --user`를 한 번 실행하여 설치합니다. JupyterLab(4.0+), 클래식 Jupyter Notebook(7.0+), VS Code, Kiro 등 모든 Jupyter 프런트엔드를 사용할 수 있습니다.
- 자격 증명이 구성된 **AWS Command Line Interface(AWS CLI) v2**(`aws configure`)
- 전역으로 설치된 **AWS Cloud Development Kit(CDK) v2**(`npm install -g aws-cdk`). Notebook에서 판매자를 배포할 때 사용합니다.
- **Node.js 18+** - CDK에 필요
- **지갑 공급자 계정** - Coinbase Developer Platform(CDP)(API Key ID, API Key Secret, Wallet Secret) 또는 Stripe via Privy(App ID, App Secret, Authorization Key ID, P-256 Authorization Private Key)
- §5에서 네트워크별로 지갑을 하나씩 생성하므로 **Base Sepolia**와 **Solana Devnet** 모두에서 [Circle 테스트넷 faucet](https://faucet.circle.com/)을 통해 받은 **테스트넷 USD Coin(USDC)**

---

## 보안

이 사용 사례에서는 AgentCore Identity의 **결제 자격 증명 공급자**를 사용하여
지갑 공급자 보안 정보를 관리합니다. §4에서 `CreatePaymentCredentialProvider`를
실행하면 AgentCore Identity가 Coinbase/Privy API 키, 앱 보안 정보, 지갑 또는
권한 부여 보안 정보를 **AWS Secrets Manager**에 저장하고 **AWS Key Management
Service(KMS)** 키로 암호화한 후 에이전트에는 보안 정보 ARN만 노출합니다
([자격 증명 공급자 구성](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-providers.html) 참조).
에이전트 런타임은 서명 시점에 `GetResourcePaymentToken`을 호출하여 수명이 짧은
공급자별 토큰을 받으며 원시 API 키나 지갑 보안 정보는 볼 수 없습니다.

AgentCore Payments가 처리하는 항목:

- **보안 정보 저장** - 지갑 공급자 보안 정보는 AgentCore Identity 아래의
  AWS Secrets Manager에 저장되며 AWS 소유 KMS 키로 암호화됩니다(고객 관리형
  KMS 키도 지원).
- **보안 정보 검색** - 에이전트는 `GetResourcePaymentToken`을 호출하고 공급자
  토큰을 받습니다. 에이전트 런타임은 기반 API 키, 앱 보안 정보 또는 지갑 보안
  정보를 받지 않습니다.
- **감사 추적** - 모든 `ProcessPayment` 호출은 AWS CloudTrail과 AgentCore
  Payments 관리형 로그 그룹에 기록됩니다. 운영자가 확인할 수 있는 총지출에는
  `GetPaymentSession`을 사용합니다.
- **예산 적용** - 운영자가 결제 세션에 `maxSpendAmount`를 설정합니다. AgentCore
  Payments는 이를 초과하는 모든 `ProcessPayment`를 거부합니다.
- **IAM 최소 권한** - §2의 네 역할은 각 작업 하나에 필요한 작업 및 리소스만
  받습니다. 역할 간 권한은 명시적으로 거부됩니다(`ManagementRole`은
  `ProcessPayment`를 호출할 수 없고, `ProcessPaymentRole`은 세션이나 결제 수단을
  관리할 수 없음).

로컬에서 직접 처리하는 항목:

- **최초 자격 증명 입력** - §4를 실행하기 전에 Coinbase/Privy 보안 정보를
  `.env`에 한 번 붙여 넣습니다. Notebook은 `CreatePaymentCredentialProvider`를
  호출할 때만 이를 읽습니다. 호출이 반환된 후 보안 정보는 AgentCore Identity
  관리형 보관소(Secrets Manager)에 있으며, 에이전트에는 로컬 `.env` 사본이 더
  이상 필요하지 않습니다. §4를 다시 실행해도 멱등성을 유지할 수 있도록
  `.env`에는 남아 있습니다.
- **전송 중 암호화** - AgentCore Payments, Amazon Bedrock, 판매자 HTTP API에
  대한 모든 호출은 TLS(`https://`)를 사용합니다. Dockerfile 상태 확인만 HTTP
  URL을 사용하며 루프백으로 제한됩니다.

### 프로덕션 강화

이 문서는 L100 튜토리얼입니다. 이 샘플과 유사한 항목을 프로덕션에 배포하기 전에
다음을 수행하세요.

- **첫 실행 후 `.env`를 비웁니다.** §4에서
  `CreatePaymentCredentialProvider`를 호출한 후 `.env`의 보안 정보 값을
  비웁니다. 이후 Notebook 실행에서는 민감하지 않은 자격 증명 공급자 ARN을
  `.env`에서 읽고 실제 보안 정보는 Secrets Manager에 유지됩니다.
- **고객 관리형 KMS 키를 사용합니다.** AgentCore Identity는 기본적으로 AWS 소유
  KMS 키를 사용합니다. 추가 감사 및 교체 제어가 필요하면 고객 관리형 키로
  전환합니다.
- **IAM 역할 와일드카드를 축소합니다.** Manager ID가 안정화되면
  `payment-manager/*`를 특정 Manager ARN으로 바꾸거나 태그를 기준으로 범위를
  지정합니다.
- **AgentCore Runtime을 VPC 모드로 전환합니다.** 프라이빗 서브넷과 AWS API용
  VPC 엔드포인트를 사용합니다(튜토리얼에서는 `networkMode=PUBLIC` 사용).
- **판매자의 Amazon API Gateway CORS를 제한합니다.** 호출이 필요한 특정 에이전트
  런타임 도메인만 허용합니다.
- **`bedrock-agentcore` Python SDK와 `@x402/*` Node 패키지 버전을 고정합니다.**
  프로덕션 빌드에서는 특정 버전을 사용합니다.

---

## 사용 사례 실행

Notebook을 열기 전에 Python 가상 환경을 생성하여 종속 항목 설치와 Notebook
상태를 전역 Python 환경에서 분리합니다.

**옵션 1 - 터미널(크로스 플랫폼)**

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
python3 -m pip install --upgrade pip ipykernel
python3 -m ipykernel install --user --name pay-for-api-venv --display-name "Python (pay-for-api-venv)"
```

**옵션 2 - VS Code/Kiro**

1. `pay-for-api.ipynb`를 엽니다.
2. Notebook 오른쪽 위의 커널 선택기(또는 아래쪽 상태 표시줄의 Python 버전
   표시기)를 선택합니다.
3. **Python: Create Environment...**를 선택합니다.
4. **Venv**를 선택합니다.
5. Python 3.10+ 인터프리터를 선택합니다. IDE가 `.venv/`를 생성하고 자동으로
   선택합니다.
6. 커널 종속 항목(`ipykernel`) 설치 메시지가 표시되면 수락합니다.

가상 환경을 활성화한 후 `pay-for-api.ipynb`를 열고 셀을 순서대로 실행합니다.
Notebook을 여는 것과 같은 CLI 명령은 다음과 같습니다.

```bash
jupyter notebook pay-for-api.ipynb
```

Notebook은 종속 항목 설치, IAM 역할 생성, 자격 증명 입력, 판매자 배포, 결제
프로비저닝, 에이전트 실행 및 해제를 처리합니다.

- §1: `requirements.txt`에서 Python 종속 항목 설치
- §2: 네 개의 IAM 역할을 생성하고 지갑 공급자 자격 증명(Coinbase CDP 또는 Stripe via Privy)을 대화형으로 요청
- §3: CDK를 통해 Fun Facts 판매자 스택을 배포하고 URL 캡처
- §4: 인라인 설정을 실행할지 기존 AgentCore Payments 인프라를 재사용할지 결정
- §5: 선택한 공급자의 Credential Provider + Manager + Connector를 프로비저닝한 후 동일한 커넥터 아래에 두 개의 Payment Instrument(ETHEREUM + SOLANA) 생성
- §6: 네트워크별로 하나씩, 예산이 제한된 결제 세션 두 개 생성
- §7: 전달된 (instrument, session, network)에 `AgentCorePaymentsPlugin`을 래핑하는 단일 패턴으로 Strands 에이전트 팩토리 구축
- §8: 동일한 판매자를 대상으로 EVM과 Solana에서 에이전트를 한 번씩 실행
- §9: 선택적으로 `agent/cdk/`를 통해 에이전트를 AgentCore Runtime에 배포하고 원격 호출
- §10: 두 네트워크의 데이터 플레인 검사: GetPaymentSession, balance, ListPaymentInstruments, ListPaymentSessions
- §11: 세션, 판매자 스택, 에이전트 런타임(§9를 실행한 경우), AgentCore Payments 리소스(선택 사항)를 모두 해제

---

## 주요 참고 사항

- 판매자 스택은 `.env`의 `AWS_REGION`으로 설정된 AgentCore Payments와 동일한
  리전에 배포됩니다.
- USDC 금액은 소수점 이하 6자리를 사용합니다. 전송 구간에서 `"$0.01"` →
  `10000` atomic unit으로 표현되며 `@x402/hono` 라이브러리가 변환을 처리합니다.
- 두 지급 지갑을 모두 구성하면 판매자가 여러 네트워크의 `accepts`를 내보냅니다.
  EVM(Base Sepolia) 항목 하나와 Solana(Devnet) 항목 하나가 포함되며, 에이전트는
  결제 수단의 네트워크와 일치하는 항목을 선택합니다.
- 판매자를 AgentCore Registry/Bazaar Model Context Protocol(MCP)에서 검색할 수
  있도록 응답은 `{ x402_content, x402_meta }` 형식을 사용합니다.
- `ProcessPaymentRole`에는 모든 세션 및 결제 수단 관리에 대한 명시적인 IAM
  `Deny`가 있고, `ManagementRole`에는 `ProcessPayment`에 대한 명시적인
  `Deny`가 있습니다. 신뢰 경계는 문서가 아닌 IAM으로 적용됩니다.
- 판매자는 공개 x402 facilitator(`https://x402.org/facilitator`)를 기준으로 결제
  증명을 검증합니다. 비공개 facilitator를 사용하려면 `seller/lambda/index.js`를
  편집하고 다시 배포합니다.
- `StripePrivy` 결제 수단을 사용해도 에이전트와 판매자는 변경되지 않습니다.
  AgentCore Payments는 서명 요청을 Privy의 키 관리 서비스로 투명하게
  라우팅합니다. Privy 기반 결제 수단은 EVM(Base/Base Sepolia)과
  Solana(Solana/Solana Devnet) 모두에서 정산됩니다.
- 에이전트는 플러그인의 읽기 전용 관리 도구(`get_payment_instrument`,
  `list_payment_instruments`, `get_payment_session`)를 호출하지 않습니다. 이러한
  도구는 운영자 디버그 흐름용입니다. §7의 system prompt는 모델에
  `http_request`만 사용하도록 지시합니다.

---

## 정리

> ⚠️ **비용 알림:** 이 사용 사례에서 배포하는 리소스는 실행 중에 AWS 요금이
> 발생합니다. AWS Lambda, Amazon API Gateway, AgentCore Runtime, AgentCore
> Memory, AgentCore Payments는 요청 및 리소스 기준으로 요금을 부과합니다.
> 작업을 마치면 Notebook의 §11을 실행하여 리소스를 해제하세요.

Notebook의 §11은 전체 해제 과정을 처리합니다.

| 단계 | 수행 작업 | 제거 대상 |
|------|--------------|-----------------|
| 세션 취소 | §6에서 생성한 각 세션에 `DeletePaymentSession` 실행 | 활성 세션 예산(복구 불가) |
| 판매자 스택 해제 | 판매자 CDK 앱에 `cdk destroy` 실행 | Amazon API Gateway HTTP API, AWS Lambda 함수, IAM 실행 역할 |
| 에이전트 런타임 해제 | 에이전트 CDK 앱에 `cdk destroy` 실행(§9를 실행한 경우에만) | AgentCore Runtime, AgentCore Memory, Amazon ECR 리포지토리, AWS CodeBuild 프로젝트, IAM 실행 역할 |
| AgentCore Payments 리소스 해제 | 종속성 순서대로 `DeletePaymentInstrument`, `DeletePaymentConnector`, `DeletePaymentManager`, `DeletePaymentCredentialProvider` 호출 | §5에서 생성한 모든 Manager/Connector/Instrument/Credential Provider 리소스 |
| 로컬 빌드 아티팩트 제거 | `.venv/`, `cdk.out/`, `__pycache__/`, `outputs.json`, `privy-delegation/`, `seller/lambda/node_modules/` 삭제 | 로컬 작업 사본 파일만 해당하며 클라우드 리소스는 제거하지 않음 |

§2에서 `setup-roles.sh`로 생성한 IAM 역할에는 상시 비용이 없으며 재실행을 위해
유지됩니다. 수동으로 삭제하려면 다음 명령을 사용합니다.

```bash
aws iam delete-role --role-name AgentCorePaymentsControlPlaneRole
aws iam delete-role --role-name AgentCorePaymentsManagementRole
aws iam delete-role --role-name AgentCorePaymentsProcessPaymentRole
aws iam delete-role --role-name AgentCorePaymentsResourceRetrievalRole
```

해제 후에도 이전 추적을 검토할 수 있도록 `/aws/bedrock-agentcore/` 및
`/bedrock-agentcore/payments/` 아래의 CloudWatch 로그 그룹은 유지됩니다.
이전 데이터를 지우려면 CloudWatch 콘솔에서 삭제합니다.

### 수동 정리(Notebook을 사용하지 않는 경우)

Notebook을 사용할 수 없으면 셸에서 동일한 해제 작업을 실행합니다.

```bash
# 1. Seller 스택 삭제
bash test/integration/destroy-seller.sh

# 2. Agent Runtime 스택 삭제(§9를 실행한 경우에만)
bash test/integration/destroy-agent.sh

# 3. AgentCore Payments 리소스에는 boto3 호출이 필요함 - 정확한 API
#    순서는 노트북의 §11 참조
```

### 정리 성공 여부 확인

남아 있는 CloudFormation 스택이 없는지 확인합니다.

```bash
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query "StackSummaries[?starts_with(StackName, 'AgentCorePayments')].StackName"
```

출력이 비어 있어야 합니다.

---

## 결론

이 사용 사례에서는 Amazon Bedrock AgentCore Payments를 통해 AI 에이전트가
프라이빗 키를 보유하거나 거래마다 사람의 승인을 받지 않고도 유료 HTTP API에
자율적으로 소액을 결제하는 방법을 보여 줍니다. 동일한 에이전트 코드가 서로 다른
두 지갑 공급자(Coinbase CDP와 Stripe via Privy) 및 두 네트워크(EVM과 Solana)를
통해 동일한 콘텐츠 비용을 결제하여 공급자 및 네트워크 독립적 설계를 보여 줍니다.

주요 내용:

- **책임 분리** - IAM 역할이 세션 생성, 결제 서명, 자격 증명 검색을 분리합니다.
  신뢰 경계는 코드가 아닌 IAM으로 적용됩니다.
- **예산 제어** - 운영자가 세션별 최대 지출을 설정합니다. AgentCore Payments가
  이를 적용하고 `GetPaymentSession`이 전체 감사 추적을 제공합니다.
- **전송 형식** - x402(HTTP 402 Payment Required)는 전송 구간의 공개 사양입니다.
  판매자 측의 `@x402/hono` 라이브러리와 에이전트 측의
  `AgentCorePaymentsPlugin`이 프로토콜을 처리하므로 애플리케이션 코드는 일반
  HTTP 요청 형태를 유지합니다.

자세한 내용은 [추가 자료](#learn-more) 링크를 참조하고 이 Notebook의 패턴을
자체 유료 API 통합에 맞게 조정하세요.

---

<a id="learn-more"></a>

## 추가 자료

공개 AgentCore Payments 문서:

- [개요](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments.html)
- [작동 방식](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-how-it-works.html)
- [핵심 개념](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-concepts.html)
- [사전 요구 사항](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-prerequisites.html)
- [IAM 역할](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html)
- [자격 증명 공급자 설정](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-setup-credential-provider.html)
- [Payment Manager 생성](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-manager.html)
- [Payment Instrument 생성](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-instrument.html)
- [Payment Session 생성](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-session.html)
- [결제 처리](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-process-payment.html) - 플러그인 참조, interrupt 계약, 네트워크 기본 설정, human-in-the-loop 흐름용 `auto_payment=False`
- [Bazaar 연결](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-connect-bazaar.html) - AgentCore Registry를 통해 판매자를 검색할 수 있도록 설정

발표:
[거래하는 에이전트 - Coinbase와 Stripe를 기반으로 구축된 Amazon Bedrock AgentCore Payments 소개](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/)
