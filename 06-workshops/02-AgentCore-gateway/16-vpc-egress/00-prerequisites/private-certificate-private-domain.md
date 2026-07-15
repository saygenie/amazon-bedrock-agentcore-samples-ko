<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 프라이빗 인증서 + 프라이빗 도메인

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책, DNS 관리 방식 및 인증서 수명 주기 요구 사항을 준수하세요.

## 개요

| 구성 요소 | 유형 | 설명 |
|-----------|------|-------------|
| **Certificate** | Private(AWS Private CA) | CA를 신뢰하도록 구성된 시스템에서만 신뢰 |
| **Domain** | Private(Route 53 private hosted zone) | VPC 내부에서만 확인 가능 |

## 의미

DNS와 인증서가 모두 완전히 private입니다. 도메인은 VPC 내부에서만 확인할 수 있으며, 인증서는 private CA의 root certificate가 설치된 클라이언트에서만 신뢰합니다. 퍼블릭 인터넷에는 아무것도 노출되지 않습니다.

## AgentCore Gateway의 제한 사항

AgentCore Gateway는 **private certificate를 지원하지 않습니다**. public root CA만을 기준으로 TLS 인증서를 검증합니다. 완전한 private 설정(private cert + private domain)은 TLS handshake 오류로 실패합니다.

또한 VPC Lattice의 라우팅에 publicly resolvable domain이 필요하므로 private domain에는 `routingDomain`이 필요합니다.

## 해결 방법

리소스 앞에 **public certificate**가 구성된 load balancer를 배치하고 private domain에 `routingDomain`을 사용합니다.

```
AgentCore Gateway
  → VPC Lattice (routes via routingDomain: *.elb.amazonaws.com)
    → Resource Gateway ENIs
      → Load Balancer (public cert, TLS termination)
        → Your resource (private cert or plain HTTP)
```

이 구성은 AgentCore 계층에서 [퍼블릭 인증서 + 프라이빗 도메인](./public-certificate-private-domain.md) 패턴으로 전환되며, 백엔드는 내부 암호화에 계속 private certificate를 사용할 수 있습니다.

## 이 패턴의 사용 시점

- **퍼블릭 노출 없음**: public DNS record가 없고 백엔드 서비스에 public certificate가 없음
- **심층 방어**: load balancer가 AgentCore의 public cert 요구 사항을 처리하고 백엔드 서비스는 조직의 private PKI 사용
- **규제 요구 사항**: 모든 내부 통신에 승인된 내부 CA의 인증서를 사용해야 하는 환경

## 설정 단계

1. load balancer용 [ACM public certificate를 생성](./create-acm-public-certificate.md)합니다(public parent domain을 기준으로 검증).
2. VPC에 연결된 [private hosted zone을 생성](./create-private-hosted-zone.md)합니다.
3. 선택 사항으로 백엔드 인증서용 [AWS Private CA](https://docs.aws.amazon.com/privateca/latest/userguide/PcaWelcome.html)를 설정합니다.
4. load balancer에 public cert를 구성하여 CDK 스택을 배포합니다.
5. AgentCore Gateway 대상을 생성할 때 `routingDomain`을 구성합니다.

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
