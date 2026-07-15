<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EKS 배포


Amazon EKS에 MCP 서버와 REST API를 배포하고 VPC egress를 사용해 AgentCore Gateway에 연결합니다.

## 범위

이 섹션의 실습은 **public certificate**와 `routingDomain`이 구성된 **private hosted zone**을 사용합니다. 엔드포인트 도메인은 VPC 내부에서만 확인할 수 있으며, VPC Lattice는 NLB의 publicly resolvable DNS를 통해 트래픽을 라우팅합니다. 다른 도메인 및 인증서 조합은 [고급 개념](../03-advanced-concepts/)을 참조하세요.

## 아키텍처

![EKS MCP 아키텍처](./images/eks-mcp.png)

[NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)가 단일 internal Network Load Balancer(NLB) 뒤에서 실행됩니다. NLB는 다음 기능을 제공합니다.

- **Static IP**: AZ당 하나씩 제공되어 allowlist에 유용
- **TLS termination**: ACM public certificate로 TLS를 종료하고 일반 HTTP를 NGINX에 전달

NGINX는 여러 백엔드 서비스에 **path-based routing**을 수행하므로 하나의 NLB가 여러 MCP 서버(예: `/mcp-server/mcp`, `/stock-mcp/mcp`)를 제공할 수 있습니다.

```bash
AgentCore Gateway
  → VPC Lattice (routingDomain: NLB *.elb.amazonaws.com)
    → Resource Gateway ENIs
      → Internal NLB (TLS :443, public cert)
        → NGINX Ingress (HTTP :80, path-based routing)
          → EKS Pods (HTTP :8000 or :8080)
```

## 사전 요구 사항

- [Lab 0: 사전 요구 사항](../00-prerequisites/) 완료(VPC + AgentCore Gateway 배포)
- ACM public certificate: [ACM Public Certificate 생성](../00-prerequisites/create-acm-public-certificate.md) 참조
- private hosted zone의 parent domain: [퍼블릭 인증서 + 프라이빗 도메인](../00-prerequisites/public-certificate-private-domain.md) 참조

> **비용 경고:** EKS cluster를 실행하면 지속적인 요금(control plane 시간당 $0.10 + EC2 node group instance)이 발생합니다. internal NLB에도 추가 비용이 발생합니다. 불필요한 비용을 방지하려면 실습을 완료한 후 각 노트북의 **Cleanup** 섹션을 반드시 실행하고, 모든 EKS 실습을 완료한 후 `SharedEksCluster` 스택을 삭제하세요. 자세한 내용은 [Amazon EKS 요금](https://aws.amazon.com/eks/pricing/) 및 [Elastic Load Balancing 요금](https://aws.amazon.com/elasticloadbalancing/pricing/)을 참조하세요.

## 실습

| 노트북 | 설명 |
|----------|-------------|
| [mcp-server-gateway-managed.ipynb](./mcp-server-gateway-managed.ipynb) | private hosted zone 및 `routingDomain`과 함께 NGINX Ingress Controller(단일 NLB, path-based routing) 뒤의 EKS에 FastMCP 서버를 배포합니다. managed VPC resource를 사용합니다. |
| [api-server-gateway-managed.ipynb](./api-server-gateway-managed.ipynb) | internal NLB 뒤의 EKS에 REST API(FastAPI)를 배포하고 OpenAPI 스키마를 사용해 AgentCore Gateway에 연결합니다. private hosted zone 및 `routingDomain`을 사용합니다. |

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
