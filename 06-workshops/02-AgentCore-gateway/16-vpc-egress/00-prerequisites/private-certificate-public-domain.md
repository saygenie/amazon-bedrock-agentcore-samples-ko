<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 프라이빗 인증서 + 퍼블릭 도메인

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책, DNS 관리 방식 및 인증서 수명 주기 요구 사항을 준수하세요.

## 개요

| 구성 요소 | 유형 | 설명 |
|-----------|------|-------------|
| **Certificate** | Private(AWS Private CA) | CA를 신뢰하도록 구성된 시스템에서만 신뢰 |
| **Domain** | Public(Route 53 public hosted zone) | public DNS를 통해 전역에서 확인 가능 |

## 의미

도메인은 publicly resolvable하지만 TLS 인증서는 private Certificate Authority(예: [AWS Private CA](https://docs.aws.amazon.com/privateca/latest/userguide/PcaWelcome.html))가 발급합니다. CA의 root certificate가 설치된 클라이언트만 연결을 신뢰합니다.

## AgentCore Gateway의 제한 사항

AgentCore Gateway는 **private certificate를 지원하지 않습니다**. AgentCore는 엔드포인트에 연결할 때 public root CA만을 기준으로 TLS 인증서를 검증합니다. private certificate를 사용하면 TLS handshake가 실패합니다.

## 해결 방법

AgentCore Gateway에서 private certificate를 사용하려면 리소스 앞에 **public certificate**가 구성된 load balancer를 배치합니다.

```
AgentCore Gateway
  → VPC Lattice → Resource Gateway ENIs
    → Load Balancer (public cert, TLS termination)
      → Your resource (private cert or plain HTTP)
```

load balancer가 public cert로 TLS를 종료한 다음 백엔드로 트래픽을 전달합니다. 필요한 경우 백엔드가 내부 통신에 private cert를 사용할 수 있지만 AgentCore에서는 load balancer의 public cert만 보입니다.

실제로는 [퍼블릭 인증서 + 퍼블릭 도메인](./public-certificate-public-domain.md) 또는 [퍼블릭 인증서 + 프라이빗 도메인](./public-certificate-private-domain.md) 패턴이 됩니다.

## Private certificate 사용 시점

- **내부 서비스 간**(AgentCore는 관여하지 않음): microservice-to-microservice mTLS
- **load balancer 뒤**: LB가 public TLS를 종료하고 백엔드는 private TLS 사용
- **규정 준수 요구 사항**: 조직에서 백엔드 암호화에 내부 CA의 인증서 사용을 의무화

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
