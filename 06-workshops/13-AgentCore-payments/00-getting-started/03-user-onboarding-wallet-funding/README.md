# 사용자 온보딩 및 Backend Wallet 작업

> 전체 단계별 자습서는 `user_onboarding.ipynb`를 참조하세요.

## 개요

자습서 00은 인프라를 생성하고 첫 wallet에 자금을 충전합니다. 이 자습서는 전체 wallet 수명 주기를 다음 두 부분으로 나누어 자세히 다룹니다.

- **1부 - 온보딩(최종 사용자별):** 에이전트가 사용자를 대신해 지출할 수 있도록 wallet을 생성하고 자금을 충전한 뒤 서명을 위임합니다.
- **2부 - Backend 작업:** 잔액 확인, 멀티 네트워크 wallet, session 예산, instrument 목록, 잔여 예산 조회를 다룹니다. 최종 사용자가 아닌 애플리케이션 backend에서 실행되는 작업이며, 전체 수명 주기를 한곳에서 확인할 수 있도록 포함했습니다.

### 학습 내용

| 주제 | 부분 | 세부 정보 |
|-------|------|---------|
| Embedded wallet 생성 | 1 | 최종 사용자별 `CreatePaymentInstrument` |
| Crypto-to-crypto 자금 충전 | 1 | Testnet faucet, 직접 USDC 전송 |
| Fiat-to-crypto onramp | 1 | Coinbase Onramp URL, Stripe Onramp(credit card, bank, Apple Pay) |
| 위임 | 1 | Coinbase project-level signing과 Privy key quorum consent 비교 |
| 잔액 확인 | 2 | Session 생성 전 `GetPaymentInstrumentBalance` |
| 멀티 네트워크 wallet | 2 | 동일한 사용자의 Ethereum + Solana wallet |
| Session 패턴 | 2 | 빠른 조회와 심층 조사에 서로 다른 예산 적용 |
| Instrument 목록 | 2 | 운영 및 wallet selector용 `ListPaymentInstruments` |
| 잔여 예산 확인 | 2 | 작업 중 `GetPaymentSession` |

## 사전 요구 사항

* 자습서 00 완료(`.env`가 있음)
* https://faucet.circle.com/ 에서 받은 testnet USDC로 wallet 자금 충전

이 자습서는 자습서 00에서 구성한 두 wallet 제공업체(Coinbase CDP 또는 Stripe/Privy) 중 어느 쪽에서도 작동합니다.

## 정리

Payment instrument는 명시적으로 삭제할 때까지 유지됩니다. 이 자습서에서 생성한 세 개의 payment session(빠른 조회, 조사 작업, 심층 분석)은 구성된 `expiryTimeInMinutes`가 지나면 자동으로 만료됩니다. 모든 결제 리소스(Manager, Connector, Instrument)를 삭제하려면 자습서 00의 정리 셀을 실행하세요.

## 결론

이 자습서는 온보딩(생성, 자금 충전, 위임) 및 backend 작업(잔액 확인, 멀티 네트워크 wallet, session 예산)을 포함한 전체 wallet 수명 주기를 다룹니다. 최종 사용자의 embedded wallet을 관리하고 일반적인 backend wallet 작업을 구현하는 방법을 보여 줍니다.
