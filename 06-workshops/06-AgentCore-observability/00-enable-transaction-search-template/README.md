# Amazon Bedrock AgentCore Observability용 Transaction Search 활성화

이 자습서에서는 AgentCore Observability를 위해 Amazon CloudWatch Transaction Search를 활성화하는 방법을 살펴봅니다. Transaction Search는 분산 시스템 전반에서 애플리케이션 트랜잭션 span과 트레이스를 완전하게 파악할 수 있는 대화형 분석 환경을 제공합니다.

## 시작하기

프로젝트 폴더에는 다음 항목이 있습니다.

- CloudFormation을 사용하여 Transaction Search를 활성화하는 방법을 보여 주는 Jupyter 노트북
- 자동 배포를 위한 CloudFormation 템플릿(transaction_search.yml)
- Transaction Search 활성화 전후를 보여 주는 샘플 이미지

## 정리

자습서를 완료한 후 다음을 수행합니다.

1. CloudFormation 스택 `transaction-search`를 삭제합니다.
2. 그러면 리소스 정책이 제거되고 Transaction Search가 비활성화됩니다.
3. 기존 트레이스와 로그는 보존 정책에 따라 유지됩니다.
