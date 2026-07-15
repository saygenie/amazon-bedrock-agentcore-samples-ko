# test/integration/

**Pay-For-API** 사용 사례를 위한 운영 스크립트입니다. 사용 사례 루트
(`02-use-cases/01-pay-for-api/`)에서 실행하세요. 각 스크립트는 이 폴더를
기준으로 경로를 확인하므로 저장소 구조가 유지되어 있다면 어느 디렉터리에서
호출해도 됩니다.

[`agentcore-payments/test/integration/`](../../../../agentcore-payments/test/integration)에서
사용한 패턴을 따릅니다.

| 스크립트 | 수행 작업 |
|--------|--------------|
| `setup-roles.sh` | 기본 [README](../../README.md)에 설명된 직무 분리 정책 모델에 따라 Notebook에서 assume할 IAM role 4개(`ControlPlane`, `Management`, `ProcessPayment`, `ResourceRetrieval`)를 생성합니다. 멱등성을 가지므로 안전하게 다시 실행할 수 있습니다. role ARN을 `.env`에 기록합니다. |
| `setup-env.sh` | 대화형 환경 설정입니다. 처음 실행할 때 `env-sample.txt`를 `.env`로 복사한 다음 빈 값(role ARN, Coinbase CDP 자격 증명, 판매자 지급 지갑)을 살펴보고 아직 비어 있는 항목만 입력하라는 메시지를 표시합니다. 이미 설정한 값을 바꾸려면 `--force-reprompt`로 다시 실행하세요. |
| `deploy-seller.sh` | 판매자 Lambda의 `node_modules`에 대해 `npm install`을 실행한 다음 `cdk bootstrap`(최초 실행 시에만)과 `cdk deploy`로 판매자 stack을 배포합니다. `seller/cdk/outputs.json`을 작성하고 `SellerApiUrl`을 출력합니다. |
| `destroy-seller.sh` | 판매자 stack에 대해 `cdk destroy --force`를 실행합니다. |

## 일반적인 실행 순서

```bash
# 02-use-cases/01-pay-for-api/에서 실행
bash test/integration/setup-roles.sh   # IAM role 생성(계정별로 한 번)
bash test/integration/setup-env.sh     # Coinbase 자격 증명 및 기타 secret 입력
bash test/integration/deploy-seller.sh # 유료 API 배포
# SellerApiUrl을 .env에 SELLER_API_URL로 붙여넣기
jupyter notebook pay-for-api.ipynb
# Notebook 실습 진행
bash test/integration/destroy-seller.sh   # 완료 후 실행
```

Notebook의 §3에서도 `deploy-seller.sh`를 대신 호출하므로, 원하는 경우에만
스크립트를 수동으로 실행하면 됩니다.
