<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 고급 개념

이 섹션에서는 private DNS, private certificate, static IP egress와 이를 AgentCore Gateway VPC egress에서 작동시키는 데 필요한 패턴을 다룹니다.


## VPC DNS 비활성화: Routing Domain

> **VPC에 DNS가 활성화되어 있지 않을 때만 `routingDomain`을 사용하세요.** VPC에 DNS가 활성화되어 있으면(기본값) AgentCore Gateway VPC egress가 Private DNS를 통해 private endpoint에 자동으로 연결되므로 `routingDomain`이 필요하지 않습니다.

Amazon VPC Lattice에서는 Resource Configuration에 사용하는 도메인을 확인할 수 있어야 합니다. VPC에 DNS가 활성화되어 있지 않고 private endpoint가 VPC 내에서만 확인할 수 있는 도메인(예: Route 53 private hosted zone)을 사용한다면 `routingDomain` 필드를 fallback으로 사용합니다.

![Private domain](./images/private-domain.png)

### 작동 방식

routing domain을 사용할 때는 다음과 같이 동작합니다.

1. **대상 URL**은 리소스의 실제 private DNS 이름(VPC 내에서 확인 가능한 이름)을 사용합니다.
2. **`routingDomain`**은 AgentCore가 VPC Lattice Resource Configuration을 설정할 때만 사용하는 별도의 publicly resolvable domain입니다.
3. 호출 시 AgentCore는 routing domain을 통해 트래픽을 라우팅하지만 private DNS 이름을 **TLS SNI hostname**으로 사용해 요청을 전송하므로, 리소스는 실제 private domain을 대상으로 한 요청을 수신합니다.


### 일반적인 routing domain 옵션

routing domain은 VPC 내의 private resource로 라우팅되는 publicly resolvable domain이면 무엇이든 사용할 수 있습니다.

| 옵션 | Routing Domain | 대상 URL |
|--------|---------------|------------|
| **Internal ALB** | `internal-<name>-<id>.us-west-2.elb.amazonaws.com` | ALB 뒤에 있는 리소스의 private DNS 이름 |
| **Internal NLB** | `internal-<name>-<id>.us-west-2.elb.amazonaws.com` | NLB 뒤에 있는 리소스의 private DNS 이름 |
| **VPC Endpoint(VPCE)** | `<vpce-id>.execute-api.<region>.vpce.amazonaws.com` | Private API Gateway hostname(예: `https://<api-id>.execute-api.<region>.amazonaws.com`) |

## 프라이빗 인증서: ALB 우회 방식

VPC egress를 사용하려면 대상 엔드포인트에 **publicly trusted TLS certificate**가 있어야 합니다. private resource가 private certificate authority(CA)에서 발급한 인증서를 사용하는 경우 리소스 앞에 internal Application Load Balancer(ALB)를 배치하는 것이 권장되는 workaround입니다.

![Private CA](./images/private-ca.png)

### 작동 방식

```
AgentCore Gateway
  → VPC Lattice (routingDomain: ALB DNS)
    → Resource Gateway ENIs
      → Internal ALB (public cert, TLS termination + host header transform)
        → Your resource (private cert, HTTPS)
```

1. **대상 URL**은 public ACM certificate와 일치하는 도메인(예: `https://my-server.my-company.com`)을 사용합니다.
2. **`routingDomain`**은 internal ALB DNS 이름입니다.
3. VPC Lattice가 routing domain을 통해 ALB로 트래픽을 라우팅합니다. TLS SNI가 ALB의 public ACM certificate와 일치하는 `my-server.my-company.com`으로 설정되므로 TLS handshake가 성공합니다.
4. ALB가 **TLS를 종료**하고 **host header transform**을 적용하여 Host header를 public domain에서 private resource의 도메인(예: `my-server.my-company.internal`)으로 재작성합니다.
5. ALB가 private certificate를 사용해 HTTPS를 통해 백엔드 리소스로 요청을 전달합니다. 모든 트래픽은 VPC 내부에 유지됩니다.


도메인 및 인증서 설정 가이드는 [사전 요구 사항](../00-prerequisites/) 폴더를 참조하세요.

## 고정 Gateway IP

외부 MCP 서버에 IP 기반 allowlist가 필요하면 VPC의 **Elastic IP가 연결된 NAT Gateway**를 통해 AgentCore Gateway 트래픽을 라우팅할 수 있습니다. 그러면 모든 아웃바운드 트래픽에 MCP 서버 운영자가 allowlist에 추가할 수 있는 알려진 static source IP가 적용됩니다.

![고정 Gateway IP](./images/gateway-static-ip.png)

### 작동 방식

1. **VPC egress**(managed VPC resource)를 사용해 Resource Gateway를 통해 AgentCore Gateway 트래픽을 VPC로 라우팅합니다.
2. NAT Gateway를 통해 아웃바운드 트래픽(0.0.0.0/0)을 라우팅하는 **private subnet**에 Resource Gateway ENI를 배치합니다.
3. NAT Gateway에는 static public IP 주소인 **Elastic IP**가 있습니다.
4. 외부 MCP 서버로 향하는 모든 트래픽이 이 Elastic IP를 통해 나갑니다.
5. MCP 서버가 Elastic IP를 allowlist에 추가하여 AgentCore Gateway의 트래픽만 허용합니다.

고가용성을 위해 Availability Zone마다 NAT Gateway를 하나씩 배포합니다. 각 NAT Gateway에는 자체 Elastic IP가 있으므로 allowlist에 추가할 모든 EIP를 MCP 서버에 제공합니다.

## 실습

| 노트북 | 설명 |
|----------|-------------|
| [01-private-domain.ipynb](./01-private-domain.ipynb) | AgentCore Gateway를 privately resolvable endpoint에 연결합니다. |
| [02-private-certificate-authority.ipynb](./02-private-certificate-authority.ipynb) | AWS Private CA 인증서를 사용하는 API에 ALB workaround를 적용합니다. |
| [03-self-signed-certificate.ipynb](./03-self-signed-certificate.ipynb) | self-signed certificate를 사용하는 API에 ALB workaround를 적용합니다(Private CA 비용 없음). |
| [04-static-gateway-ip.ipynb](./04-static-gateway-ip.ipynb) | allowlist를 위해 static Elastic IP가 연결된 NAT Gateway를 통해 AgentCore Gateway 트래픽을 라우팅합니다. |

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
