# 제공업체 계정 설정 가이드

자습서 00을 실행하려면 지원되는 wallet 제공업체의 자격 증명이 필요합니다.
이 가이드는 계정을 생성하고 자습서 00이 `.env` 파일에서 사용하는 자격 증명을
발급하는 과정을 안내합니다.

---

## 어떤 가이드를 따라야 하나요?

| 사용하려는 제공업체 | 가이드 |
|:----------------------|:-----------------|
| **Coinbase Developer Platform(CDP)** | [Coinbase CDP 계정 설정](coinbase_cdp_account_setup.ipynb) |
| **Privy를 통한 Stripe** | [Stripe / Privy 계정 설정](stripe_privy_account_setup.ipynb) |

관련 가이드를 완료한 후 [자습서 00](../setup_agentcore_payments.ipynb)으로 돌아가세요.

---

## 필요한 자격 증명

필요한 자격 증명은 선택한 제공업체에 따라 다릅니다.

### Coinbase CDP

| 변수 | 설명 |
|:---------|:------------|
| `COINBASE_API_KEY_ID` | Coinbase CDP API key ID |
| `COINBASE_API_KEY_SECRET` | Coinbase CDP API key secret |
| `COINBASE_WALLET_SECRET` | Coinbase CDP wallet secret |

`.env`에서 `CREDENTIAL_PROVIDER_TYPE=CoinbaseCDP`를 설정합니다.

### Stripe / Privy

Vendor 이름은 `StripePrivy`이지만 구성에는 Privy 자격 증명만 사용합니다. Stripe 측 field는 없습니다.

| 변수 | 설명 |
|:---------|:------------|
| `PRIVY_APP_ID` | Privy dashboard의 App ID |
| `PRIVY_APP_SECRET` | Privy dashboard → API keys의 App secret |
| `PRIVY_AUTHORIZATION_ID` | P-256 authorization key의 Authorization ID(Wallet infrastructure → Authorization keys) |
| `PRIVY_AUTHORIZATION_PRIVATE_KEY` | P-256 private key(raw base64, `wallet-auth:` 접두사 제거) |

`.env`에서 `CREDENTIAL_PROVIDER_TYPE=StripePrivy`를 설정합니다.

> **중요:** `PRIVY_AUTHORIZATION_ID`는 API key가 아니라 P-256 authorization key의 ID입니다. `authorizationPrivateKey`에서는 `wallet-auth:` 접두사를 제거해야 합니다. Bedrock AgentCore validation은 접두사가 있는 형식을 거부합니다.

## 정리

`.env`에 저장된 자격 증명은 자습서에서만 사용됩니다. 배포된 workload에서는 자격 증명을 `.env` 파일 대신 [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)에 저장하세요.

> **참고:** 이 자격 증명으로 생성한 AWS 리소스(IAM 역할, Payment Manager, Connector, Instrument)는 명시적으로 삭제할 때까지 유지됩니다. 더 이상 필요하지 않으면 자습서 00의 정리 셀을 실행하여 제거하세요.

## 결론

관련 제공업체 설정 가이드를 완료하면 필요한 자격 증명이 `.env` 파일에 저장됩니다. [자습서 00](../setup_agentcore_payments.ipynb)으로 돌아가 이 자격 증명으로 AgentCore payments stack을 프로비저닝하세요.
