<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 퍼블릭 인증서 + 프라이빗 도메인

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책, DNS 관리 방식 및 인증서 수명 주기 요구 사항을 준수하세요.

## 개요

| 구성 요소 | 유형 | 설명 |
|-----------|------|-------------|
| **Certificate** | Public(ACM) | AgentCore Gateway를 포함한 모든 클라이언트에서 신뢰 |
| **Domain** | Private(Route 53 private hosted zone) | VPC 내부에서만 확인 가능 |

## 의미

도메인(예: `internal-mcp.example.com`)은 private hosted zone에 연결된 VPC 내부에서만 확인할 수 있으며 퍼블릭 인터넷에서는 보이지 않습니다.

ACM은 private hosted zone이 아니라 **public parent domain**(`example.com`)을 기준으로 도메인 소유권을 검증하므로 인증서는 계속 공개적으로 신뢰됩니다. 인증서는 Runtime에서 DNS가 확인되는 방식과 무관합니다.

```
dig @8.8.8.8 internal-mcp.example.com        → NXDOMAIN (not found)
dig (from inside VPC) internal-mcp.example.com → 10.0.2.52 (load balancer private IP)
```

## AgentCore Gateway에서의 작동 방식

VPC Lattice Resource Gateway에서 **Private DNS**가 활성화되어 있으면(Gateway-managed 모드의 기본값) AgentCore가 VPC의 DNS resolver를 사용해 엔드포인트 도메인을 조회합니다. VPC가 private hosted zone에 연결되어 있으므로 `internal-mcp.example.com`이 internal load balancer의 private IP로 확인되고, load balancer의 publicly trusted certificate를 기준으로 TLS가 완료됩니다.

- **`endpoint`**: `https://internal-mcp.example.com/mcp`(VPC의 private hosted zone을 통해 확인)
- **VPC 요구 사항**: VPC에서 `enableDnsSupport` 및 `enableDnsHostnames`가 `true`여야 함(기본값)
- **Private hosted zone**: Resource Gateway가 있는 VPC에 연결되어 있어야 함

> private hosted zone association은 가장 놓치기 쉬운 사전 요구 사항입니다. AgentCore의 엔드포인트 연결을 확인하기 전에 VPC 내부의 EC2 인스턴스에서 `dig internal-mcp.example.com`으로 검증하세요.

## 사용 시점

- public DNS에 도메인을 노출하지 않으려는 경우
- public hosted zone을 수정하지 않으려는 경우
- private hosted zone을 VPC와 동일한 계정에서 자체적으로 관리하려는 경우
- publicly trusted certificate가 계속 필요한 경우(AgentCore Gateway 요구 사항)

## 트래픽 흐름

```
AgentCore Gateway
  → VPC Lattice Resource Gateway (resolves domain via VPC private DNS)
    → Resource Gateway ENIs
      → Internal Load Balancer (TLS termination with public cert)
        → Your private resource
```

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
