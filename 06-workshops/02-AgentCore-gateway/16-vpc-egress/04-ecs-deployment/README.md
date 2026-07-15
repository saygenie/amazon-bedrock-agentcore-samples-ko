<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ECS 배포


Amazon ECS에 MCP 서버를 배포하고 VPC egress를 사용해 AgentCore Gateway에 연결합니다.

## 아키텍처

![ECS Fargate 아키텍처](./images/ecs-fargate.png)

internal Application Load Balancer(ALB)가 ECS 서비스 앞에 배치됩니다. Route 53 private hosted zone은 private domain을 ALB에 매핑합니다. `routingDomain` 파라미터는 ALB의 publicly resolvable DNS를 통해 라우팅하도록 VPC Lattice에 지시합니다.

- **Private domain**: VPC 내부에서만 확인 가능(예: `ecs-mcp.example.com`)
- **TLS termination**: ALB가 ACM public certificate로 HTTPS를 종료하고 일반 HTTP를 ECS task에 전달
- **Public DNS 불필요**: CNAME record 또는 도메인 소유권이 필요하지 않음

```
AgentCore Gateway → VPC Lattice (routingDomain: ALB *.elb.amazonaws.com)
    → Resource Gateway ENIs → Internal ALB (HTTPS :443, public cert) → ECS Fargate Tasks (HTTP :8000)
```

## 사전 요구 사항

- [Lab 0: 사전 요구 사항](../00-prerequisites/) 완료(VPC + AgentCore Gateway 배포)
- Docker 실행(CDK container image build용)
- ACM public certificate: [ACM Public Certificate 생성](../00-prerequisites/create-acm-public-certificate.md) 참조

## 실습

| 노트북 | 설명 |
|----------|-------------|
| [fargate-mcp-gateway-managed.ipynb](./fargate-mcp-gateway-managed.ipynb) | private DNS 및 `routingDomain`이 구성된 internal ALB 뒤의 ECS Fargate에 FastMCP 서버를 배포한 다음 managed VPC resource를 사용해 AgentCore Gateway에 연결합니다. |

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
