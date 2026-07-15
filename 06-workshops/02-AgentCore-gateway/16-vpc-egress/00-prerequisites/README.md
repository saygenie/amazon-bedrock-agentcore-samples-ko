<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 사전 요구 사항

이 폴더에는 실습을 실행하기 전에 필요한 설정 노트북과 참고 가이드가 포함되어 있습니다.

![Multi-account 아키텍처](./images/multi-account.png)

## 설정 노트북

| 노트북 | 설명 |
|----------|-------------|
| [00-vpc-gateway-setup.ipynb](./00-vpc-gateway-setup.ipynb) | 두 리전(us-west-2, us-east-1)에 VPC를 배포하고, CDK를 bootstrap하며, Cognito M2M 인증을 사용하는 공유 AgentCore Gateway를 생성하는 기반 인프라를 배포합니다. [VPC Peering](../01-managed-vpc-resource/02-peering.ipynb)(us-east-1 VPC + API Gateway + peering connection) 및 [교차 계정](../02-self-managed-lattice/02-cross-account.ipynb)(Account B VPC) 설정을 위한 선택 섹션도 포함합니다. 이후 모든 실습은 이 노트북에 의존합니다. |

## 도메인 및 인증서 가이드

AgentCore Gateway VPC egress를 사용하려면 대상 엔드포인트에 **publicly trusted TLS certificate**가 있어야 합니다. DNS가 public인지 private인지에 따라 다른 패턴이 적용됩니다. 이 가이드에서는 각 조합을 설명합니다.

> **VPC에 DNS가 활성화되어 있으면 AgentCore Gateway VPC egress가 Private DNS를 통해 private endpoint에 자동으로 연결됩니다. VPC에 DNS가 활성화되어 있지 않으면 `routingDomain`을 fallback으로 사용하세요.**

### 방법 안내

| 가이드 | 설명 |
|-------|-------------|
| [ACM Public Certificate 생성](./create-acm-public-certificate.md) | ACM public certificate를 요청하고 DNS를 통해 검증한 다음 확인하는 단계별 안내입니다. |
| [Public DNS Record 생성](./create-public-dns-record.md) | internal load balancer를 가리키는 CNAME record를 public hosted zone에 생성합니다. |
| [Private Hosted Zone 생성](./create-private-hosted-zone.md) | Route 53 private hosted zone을 생성하고 load balancer의 Alias record를 추가한 후 확인합니다. |

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
