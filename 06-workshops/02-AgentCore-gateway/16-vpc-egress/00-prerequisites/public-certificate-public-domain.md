<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 퍼블릭 인증서 + 퍼블릭 도메인

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책, DNS 관리 방식 및 인증서 수명 주기 요구 사항을 준수하세요.

## 개요

| 구성 요소 | 유형 | 설명 |
|-----------|------|-------------|
| **Certificate** | Public(ACM) | AgentCore Gateway를 포함한 모든 클라이언트에서 신뢰 |
| **Domain** | Public(Route 53 public hosted zone) | public DNS를 통해 전역에서 확인 가능 |

## 의미

도메인(예: `mcp.example.com`)은 publicly resolvable하므로 누구나 `dig`로 조회할 수 있습니다. 하지만 load balancer가 internal이며 internet-facing이 아니므로 VPC 내부의 **private IP**로 확인됩니다.

도메인은 검색할 수 있지만 인터넷에서 리소스에 연결할 수는 없습니다.

```
dig @8.8.8.8 mcp.example.com → 10.0.2.52, 10.0.3.60 (private IPs)
```

## 사용 시점

- 가장 간단한 설정: 도메인이 전역에서 확인되므로 DNS workaround가 필요 없음
- public DNS에 도메인 이름이 표시되어도 되는 경우
- Route 53의 public hosted zone에 등록된 도메인이 있는 경우(동일 또는 다른 계정)

## 트래픽 흐름

```
AgentCore Gateway → VPC Lattice → Resource Gateway ENIs → Internal LB (TLS) → Your resource
```

AgentCore가 public DNS를 통해 도메인을 확인하고 VPC Lattice가 Resource Gateway ENI를 통해 internal load balancer로 트래픽을 라우팅합니다.

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
