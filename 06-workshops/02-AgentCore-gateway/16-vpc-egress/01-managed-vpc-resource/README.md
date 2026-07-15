<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Managed VPC Resource

> VPC egress를 위한 AgentCore Gateway 관리형 모드입니다. 내부적으로 Amazon VPC Lattice를 사용하며 Lattice 리소스를 직접 관리하지 않습니다.

Amazon Bedrock AgentCore Gateway가 VPC Lattice Resource Gateway와 Resource Configuration을 대신 생성하고 관리합니다. VPC, subnet 및 선택적 security group을 제공하면 나머지는 AgentCore가 처리합니다.

![아키텍처](./images/arch.png)

## 작동 방식

`privateEndpoint.managedVpcResource`와 함께 `CreateGatewayTarget`을 호출하면 AgentCore가 다음 작업을 수행합니다.

1. VPC에 **Resource Gateway 생성** - 지정한 각 subnet에 ENI를 하나씩 프로비저닝합니다. 이 ENI는 AgentCore 트래픽이 VPC로 들어오는 진입점입니다.
2. 대상 엔드포인트로 범위가 지정된 **Resource Configuration 생성** - AgentCore가 Resource Gateway를 통해 연결할 수 있는 대상을 정의합니다.
3. Resource Configuration을 AgentCore service network에 **연결** - end-to-end 연결을 활성화합니다.
4. **Private DNS를 통해 대상 엔드포인트 확인** - 호출 시 Resource Gateway가 VPC의 DNS resolver(연결된 Route 53 private hosted zone 포함)를 사용해 엔드포인트 도메인을 조회합니다. 아래의 [프라이빗 DNS](#private-dns)를 참조하세요.

계정에 동일한 VPC, subnet 및 security group ID를 가진 Resource Gateway가 이미 있으면 AgentCore가 새로 생성하지 않고 재사용합니다.

AgentCore는 `AWSServiceRoleForBedrockAgentCoreGatewayNetwork` service-linked role을 사용해 이러한 리소스를 관리합니다. managed private endpoint를 사용하는 Gateway 대상을 처음 생성할 때 이 역할이 자동으로 생성됩니다. 자체 IAM 정책에 VPC Lattice 권한을 추가할 필요는 없습니다.

- [AgentCore Gateway managed VPC resource](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html#lattice-vpc-egress-managed-lattice)에 필요한 올바른 IAM 권한이 있는지 확인하세요.
- Amazon Bedrock AgentCore Gateway의 [Service Linked role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html#lattice-vpc-egress-slr)을 알아보세요.


## 제공해야 하는 항목

```json
{
  "privateEndpoint": {
    "managedVpcResource": {
      "vpcIdentifier": "vpc-0abc123def456",
      "subnetIds": ["subnet-0abc123", "subnet-0def456"],
      "endpointIpAddressType": "IPV4",
      "securityGroupIds": ["sg-0abc123def"]
    }
  }
}
```

### 파라미터

| 파라미터 | 필수 | 설명 |
|-----------|----------|-------------|
| `vpcIdentifier` | 예 | private resource가 포함된 VPC의 ID입니다. |
| `subnetIds` | 예 | Resource Gateway ENI를 배치할 subnet ID입니다. |
| `endpointIpAddressType` | 예 | IP 주소 유형입니다. 유효한 값: `IPV4`, `IPV6`. |
| `securityGroupIds` | 아니요 | Resource Gateway ENI의 security group입니다. [보안 그룹](#security-groups)을 참조하세요. |
| `routingDomain` | 아니요 | DNS가 활성화되지 않은 VPC의 fallback입니다. VPC Lattice 라우팅에 사용하는 publicly resolvable domain입니다. [라우팅 도메인](#routing-domain)을 참조하세요. |
| `tags` | 아니요 | managed Resource Gateway의 tag입니다. `BedrockAgentCoreGatewayManaged`는 예약되어 있습니다. |

<a id="security-groups"></a>

## 보안 그룹

Security group은 Resource Gateway ENI가 VPC 내부 리소스로 전송할 수 있는 **아웃바운드 트래픽**을 제어합니다.

**`securityGroupIds`를 전달하지 않으면** AgentCore가 VPC의 default security group을 사용합니다. default SG는 일반적으로 자체 트래픽만 허용하므로 ENI가 리소스에 연결할 수 없으며, 대상 생성이 timeout 오류로 실패합니다.

리소스가 수신하는 포트(예: HTTPS의 포트 443)에서 아웃바운드 트래픽을 허용하는 **security group을 항상 전달하세요**. 가장 간단한 방법은 load balancer 또는 VPC endpoint가 사용하는 것과 동일한 security group을 전달하는 것입니다.

[시작하기 실습](./01-getting-started.ipynb)의 예시:
```python
"securityGroupIds": [VPCE_SG_ID]  # VPCE SG가 VPC CIDR의 443 inbound 허용
```

<a id="private-dns"></a>

## 프라이빗 DNS

DNS 지원이 활성화된 VPC의 기본값인 **Private DNS**를 사용하면 Resource Gateway가 VPC의 DNS resolver로 대상 엔드포인트 도메인을 확인합니다. 해당 도메인의 Route 53 private hosted zone이 VPC에 연결되어 있으면 resolver가 그 record를 반환하므로 `https://internal.example.com/api` 같은 대상이 추가 구성 없이 private resource에 연결됩니다.

### 요구 사항

- **VPC DNS 지원** - VPC에서 `enableDnsSupport` 및 `enableDnsHostnames`가 모두 `true`여야 합니다(새 VPC의 기본값).
- **Hosted zone association** - Route 53 private hosted zone이 Resource Gateway ENI가 있는 VPC에 연결되어 있어야 합니다.
- **Publicly trusted TLS certificate** - AgentCore Gateway는 public root CA를 기준으로 인증서를 검증합니다. 엔드포인트는 대상 FQDN을 포함하는 인증서(일반적으로 load balancer에 있음)를 제공해야 합니다.

### 필요하지 않은 항목

- 대상 도메인의 public DNS record
- `routingDomain` 파라미터
- 사용자 지정 TLS SNI 우회 방식

<a id="routing-domain"></a>

## 라우팅 도메인(대체 경로)

> **VPC에 DNS가 활성화되어 있지 않을 때만 `routingDomain`을 사용하세요.** VPC에 DNS가 활성화되어 있으면(기본값) Private DNS가 자동으로 확인하므로 `routingDomain`이 필요하지 않습니다.

대상 엔드포인트가 publicly resolvable하지 않은 도메인(예: Route 53 private hosted zone)을 사용하고 VPC에 DNS 지원이 활성화되어 있지 않다면 `routingDomain`을 중간 publicly resolvable domain(일반적으로 load balancer의 DNS 이름)으로 설정합니다.

`routingDomain`이 설정되면 AgentCore는 routing domain을 통해 트래픽을 라우팅하지만 실제 엔드포인트 도메인을 TLS SNI hostname으로 사용하여 요청을 전송하므로, 리소스는 실제 도메인을 대상으로 한 요청을 수신합니다.

## 실습

| 노트북 | 설명 |
|----------|-------------|
| [01-getting-started.ipynb](./01-getting-started.ipynb) | mock integration이 구성된 private API Gateway를 배포하고 AgentCore Gateway에 연결합니다. API-VPCE DNS 형식을 사용하므로 도메인이나 인증서가 필요하지 않습니다. |
| [02-peering.ipynb](./02-peering.ipynb) | managed VPC resource와 VPC peering을 사용해 peered VPC(교차 리전)의 Private API Gateway에 연결합니다. |

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
