<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 자체 관리형 Amazon VPC Lattice

VPC Lattice Resource Gateway와 Resource Configuration을 직접 생성한 다음 Resource Configuration 식별자를 AgentCore에 제공합니다. 교차 계정 연결이 필요하거나, VPC Lattice 리소스가 이미 설정되어 있거나, Lattice 구성을 세밀하게 제어해야 할 때 이 옵션을 사용합니다.

![대상 생성](./images/create-target.png)

## Self-managed Lattice 사용 시점

- VPC Lattice 리소스가 이미 구성되어 있는 경우
- **교차 계정 연결**이 필요한 경우(Gateway와 다른 계정의 리소스)
- 여러 Gateway 대상에서 Resource Configuration을 공유해야 하는 경우
- Lattice 리소스 수명 주기(예: ENI당 IP 수, subnet 배치)를 제어해야 하는 경우

## 사전 요구 사항

self-managed private endpoint를 사용하는 Gateway 대상을 생성하기 전에 다음 단계를 완료합니다.

- [AgentCore Gateway managed VPC resource](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html#lattice-vpc-egress-self-managed-lattice)에 필요한 올바른 IAM 권한이 있는지 확인하세요.

### 1단계: Resource Gateway 생성

![Resource Gateway](./images/resource-gateway.png)

private resource가 포함된 VPC에 [VPC Lattice Resource Gateway](https://docs.aws.amazon.com/vpc/latest/privatelink/resource-gateway.html)를 생성합니다.

```bash
aws vpc-lattice create-resource-gateway \
  --name my-resource-gateway \
  --vpc-identifier vpc-0abc123def456 \
  --subnet-ids subnet-0abc123 subnet-0def456 \
  --security-group-ids sg-0abc123def \
  --ip-address-type IPV4
```


지정한 security group의 제어를 받는 ENI를 각 subnet에 하나씩 프로비저닝합니다. 기본적으로 각 ENI에는 IP 주소가 하나씩 할당됩니다. `--ip-addresses-per-eni` 파라미터를 사용해 ENI당 최대 62개의 IP를 구성할 수 있습니다.

응답의 `resourceGatewayId`를 기록합니다.

### 2단계: Resource Configuration 생성

![Resource Configuration](./images/resource-config.png)


AgentCore가 Resource Gateway를 통해 연결할 수 있는 특정 엔드포인트를 정의하는 [Resource Configuration](https://docs.aws.amazon.com/vpc/latest/privatelink/resource-configuration.html)을 생성합니다.

**도메인 이름 대상:**

```bash
aws vpc-lattice create-resource-configuration \
  --name my-resource-config \
  --type SINGLE \
  --resource-gateway-identifier <resource-gateway-id> \
  --resource-configuration-definition '{
    "dnsResource": {
      "domainName": "my-service.internal.example.com",
      "ipAddressType": "IPV4"
    }
  }' \
  --port-ranges "443"
```

**IP 주소 대상:**

```bash
aws vpc-lattice create-resource-configuration \
  --name my-resource-config-ip \
  --type SINGLE \
  --resource-gateway-identifier <resource-gateway-id> \
  --resource-configuration-definition '{
    "ipResource": {
      "ipAddress": "10.0.1.100"
    }
  }' \
  --port-ranges "443"
```

`--port-ranges` 파라미터는 Resource Gateway ENI가 트래픽을 전달할 수 있는 포트를 제한하여 security group과 함께 추가 액세스 제어 계층을 제공합니다.

응답의 `resourceConfigurationArn`을 기록합니다.

### 3단계(교차 계정만 해당): AWS RAM을 통해 공유

![AWS RAM](./images/ram.png)

리소스가 AgentCore Gateway와 다른 계정에 있다면 [AWS Resource Access Manager](https://docs.aws.amazon.com/ram/latest/userguide/what-is.html)를 사용해 Resource Configuration을 공유합니다.

**리소스 소유자 계정:**

```bash
aws ram create-resource-share \
  --name my-resource-config-share \
  --resource-arns <resource-configuration-arn> \
  --principals <gateway-owner-account-id>
```

**Gateway 소유자 계정(공유 수락):**

```bash
aws ram accept-resource-share-invitation \
  --resource-share-invitation-arn <invitation-arn>
```

공유를 수락하면 Gateway 소유자 계정에서 공유된 Resource Configuration ARN을 확인할 수 있습니다.

## API 참조

![AWS RAM 대상](./images/ram-target.png)

self-managed private endpoint를 사용하는 Gateway 대상을 생성하려면 [CreateGatewayTarget](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateGatewayTarget.html) 요청에 `privateEndpoint.selfManagedLatticeResource`를 포함합니다.

```json
{
  "privateEndpoint": {
    "selfManagedLatticeResource": {
      "resourceConfigurationIdentifier": "arn:aws:vpc-lattice:us-east-1:123456789012:resourceconfiguration/rcfg-abc123"
    }
  }
}
```

### 파라미터

| 파라미터 | 필수 | 설명 |
|-----------|----------|-------------|
| `resourceConfigurationIdentifier` | 예 | VPC Lattice Resource Configuration의 ARN 또는 ID입니다. |

AgentCore는 Forward Access Sessions를 통해 사용자의 자격 증명을 사용하여 Resource Configuration을 AgentCore service network에 연결합니다.

### 생성 후 동작

- AgentCore가 Resource Configuration을 service network에 연결합니다.
- `Get` API 응답의 `privateEndpointManagedResources` 필드에 `resourceAssociationArn`이 포함됩니다.
- 동일한 Resource Configuration을 가리키는 여러 대상을 생성하면 AgentCore가 기존 Service Network Resource Association을 재사용합니다.

## 실습

| 노트북 | 설명 |
|----------|-------------|
| [01-getting-started.ipynb](./01-getting-started.ipynb) | self-managed Resource Gateway 및 Resource Configuration을 생성한 다음 AgentCore Gateway에 연결합니다. |
| [02-cross-account.ipynb](./02-cross-account.ipynb) | AWS RAM을 사용해 계정 간에 Resource Configuration을 공유합니다. |

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
