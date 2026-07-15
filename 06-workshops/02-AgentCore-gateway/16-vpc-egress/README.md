<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# VPC Lattice를 사용해 Gateway Target의 Amazon Bedrock AgentCore Gateway VPC Egress 구성

[Amazon VPC Lattice를 사용해 VPC의 private resource에 연결](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html)하고 [Gateway Target의 Amazon Bedrock AgentCore Gateway VPC Egress를 구성](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-vpc-egress.html)하는 방법을 알아봅니다.

Amazon Bedrock AgentCore는 private MCP 서버 및 내부 REST API와 같이 AWS VPC 내부 또는 VPC에 연결된 온프레미스 환경에 호스팅된 리소스를 퍼블릭 인터넷에 노출하지 않고 private connectivity를 제공합니다.

![아키텍처](./images/architecture.png)

Private connectivity는 [Amazon VPC Lattice](https://docs.aws.amazon.com/vpc-lattice/latest/ug/what-is-vpc-lattice.html) Resource Gateway와 Resource Configuration을 사용해 설정합니다. 이 연결을 구성하는 두 가지 모드를 지원합니다.

- Managed VPC Resource - 이 모드에서는 AgentCore Gateway가 모든 작업을 대신 처리합니다. 대상 구성의 일부로 VPC ID, subnet ID 및 security group을 제공하면 AgentCore가 계정에서 VPC Resource를 자동으로 생성하고 관리합니다. 동일 리전 또는 교차 리전 연결에 VPC peering을 사용하거나, multi-VPC 및 hybrid 환경에 AWS Transit Gateway를 사용하는 hub-and-spoke 모델을 사용하는 등 기존 네트워크 아키텍처와 통합할 수 있습니다.

![Managed VPC Resource](./images/managed.png)

- Self-managed Lattice - 이 모드에서는 AgentCore Gateway에서 대상을 생성할 때 참조할 VPC Lattice Resource Gateway를 미리 직접 생성하고 관리합니다. ENI당 IPv4 주소 수, subnet 배치, security group 규칙 등 Resource Gateway 구성을 완전히 파악하고 제어할 수 있습니다. 특히 Resource Configuration 자체를 직접 확인하고 AWS RAM을 사용해 공유하며, 연결된 모든 association을 확인하고 언제든지 취소할 수 있습니다. 이 모드를 사용하면 VPC Peering 또는 AWS Transit Gateway를 사용하지 않고 Resource VPC에 대한 네트워크 액세스를 직접 활성화할 수 있습니다.

![Self-managed Lattice](./images/self-managed.png)

## 주요 용어

- Resource VPC: private 호스팅 MCP 서버 또는 API 엔드포인트와 같은 private resource가 있는 [Amazon VPC](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html)입니다. AgentCore Gateway가 연결해야 하는 VPC입니다.

- Gateway account: Amazon Bedrock AgentCore Gateway를 소유한 AWS 계정입니다. Resource VPC는 Gateway account와 동일한 AWS 계정 또는 다른 계정에 있을 수 있습니다.

- Resource Gateway: [VPC Lattice의 Resource Gateway](https://docs.aws.amazon.com/vpc/latest/privatelink/resource-gateway.html)는 Resource VPC로 들어오는 private 진입점 역할을 합니다. 생성 시 지정한 각 subnet에 Elastic Network Interface(ENI)를 하나씩 프로비저닝합니다. AgentCore Gateway에서 private resource로 향하는 모든 트래픽은 이러한 ENI를 통해 들어옵니다.

- Resource Configuration: [VPC 리소스용 Resource Configuration](https://docs.aws.amazon.com/vpc/latest/privatelink/resource-configuration.html)은 AgentCore Gateway가 Resource Gateway를 통해 연결할 수 있는 특정 리소스를 정의하며, 도메인 이름, IP 주소 또는 AWS ARN으로 식별합니다. 전체 VPC에 대한 액세스를 허용하는 대신 단일 엔드포인트로 연결 범위를 제한합니다.

- Service Network Resource Association: Resource Configuration을 AgentCore service network에 연결하여 AgentCore Gateway 서비스가 private endpoint를 호출할 수 있게 합니다. 어떤 모드를 사용하든 AgentCore가 항상 이 association을 대신 생성하고 관리합니다.

## 실습

> **참고:** 이 실습에서는 AgentCore Gateway의 **인바운드 인증에 Cognito를 사용**하고 **AgentCore Gateway와 대상 사이에는 권한 부여를 구성하지 않습니다**. VPC 연결 패턴에 집중하기 위한 구성입니다. 프로덕션 워크로드에서는 인바운드 인증에 OAuth 2.0 호환 identity provider(예: Entra ID, Auth0, Okta)를 구성할 수 있습니다. [Identity provider 설정](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idps.html)을 참조하세요. AgentCore Gateway와 대상 간 아웃바운드 권한 부여에는 [AgentCore Gateway Identity 자격 증명 관리](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-identity.html)를 설정하는 것이 좋습니다.

### 비용 경고

| 리소스 | 비용 | 실습 |
|----------|------|------|
| **AWS Private CA**(short-lived mode) | 월 $50 | 02-private-certificate-authority |
| **Internal ALB** | 시간당 약 $0.0225 + LCU 요금 | 모든 실습 |
| **EC2 instance**(t3.micro) | 시간당 약 $0.0104 | 모든 실습 |
| **NAT Gateway** | 시간당 약 $0.045 + 데이터 처리 요금 | 모든 실습(VPC 스택을 통해), 04-static-gateway-ip |
| **Elastic IP**(연결됨) | 요금 없음 | 04-static-gateway-ip |

지속적인 요금이 발생하지 않도록 실습을 완료한 후 각 노트북의 **Cleanup** 섹션을 반드시 실행하세요.

| 실습 | 폴더 | 설명 |
|-----|--------|-------------|
| **사전 요구 사항** | [`00-prerequisites/`](./00-prerequisites/) | 계정 및 리전에 VPC를 배포하고, CDK를 bootstrap하며, Cognito M2M 인증을 사용하는 공유 AgentCore Gateway를 설정합니다. 이후 모든 실습은 이 실습에 의존합니다. |
| **Managed VPC Resource** | [`01-managed-vpc-resource/`](./01-managed-vpc-resource/) | AgentCore Gateway managed VPC resource를 시작합니다. AgentCore가 Resource Gateway, Resource Configuration 및 service network association을 자동 생성합니다. VPC peering 예제가 포함됩니다. |
| **Self-Managed Lattice** | [`02-self-managed-lattice/`](./02-self-managed-lattice/) | VPC Lattice Resource Gateway 및 Resource Configuration을 직접 생성하고 관리합니다. AWS Resource Access Manager(RAM)를 통한 교차 계정 연결이 포함됩니다. |
| **고급 개념**  | [`03-advanced-concepts/`](./03-advanced-concepts/) | AgentCore Gateway VPC egress에서 private domain(Route 53 private hosted zone), private certificate(AWS Private CA 및 self-signed), static IP egress(allowlist를 위한 Elastic IP가 연결된 NAT Gateway)를 살펴봅니다. |
| **ECS 배포** | [`04-ecs-deployment/`](./04-ecs-deployment/) | TLS termination이 적용된 internal ALB 뒤의 Amazon ECS Fargate에 MCP 서버를 배포한 다음 managed VPC resource를 사용해 AgentCore Gateway에 연결합니다. |
| **EKS 배포** | [`05-eks-deployment/`](./05-eks-deployment/) | private hosted zone을 사용하고 TLS termination이 적용된 internal NLB 뒤의 Amazon EKS에 MCP 서버와 REST API를 배포합니다. |

### 리전 및 계정

이 실습은 기본 리전인 **us-west-2**에서 테스트되었습니다. 사용 중인 리전에서 AgentCore Gateway 및 해당 기능을 사용할 수 있는지 [AgentCore 지원 리전](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)을 확인하세요. 다음 실습에는 추가 설정이 필요합니다.

- [VPC Peering 실습](./01-managed-vpc-resource/02-peering.ipynb): **us-east-1**의 VPC 필요(Lab 0, Step 5에서 배포)
- [교차 계정 실습](./02-self-managed-lattice/02-cross-account.ipynb): us-west-2에 VPC가 있는 **두 번째 AWS 계정** 필요(Lab 0, Step 7에서 배포)

### 모든 실습의 사전 요구 사항

- **AWS CLI** v2 - [설치 가이드](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Node.js** v18 이상 및 **npm** - [다운로드](https://nodejs.org/en/download)
- **AWS CDK CLI** - [시작하기](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)
- **Docker** - [Docker 설치](https://docs.docker.com/engine/install/)
- **Python 3.12 이상** - Jupyter 노트북 실행용
- **IAM 권한** - IAM identity에 Amazon Bedrock AgentCore, Amazon VPC Lattice, Amazon EC2 및 AWS CloudFormation 권한이 필요합니다. 자세한 내용은 [IAM 권한 가이드](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/security-iam.html)를 참조하세요.
- [AgentCore Gateway - Amazon VPC Lattice](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html)에 필요한 올바른 IAM 권한이 있는지 확인하세요.

### 도메인 및 인증서 요구 사항

load balancer 뒤에 private resource를 배포하는 실습(ECS, EKS)에는 다음 항목이 필요합니다.
- Route 53 hosted zone에 등록된 소유 **도메인 이름**(어떤 AWS 계정에 있어도 됨)
- 해당 도메인의 **ACM public certificate**

public domain 및 private domain을 다루는 도메인 및 인증서 설정 가이드는 [사전 요구 사항](./00-prerequisites/) 폴더를 참조하세요.

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](LICENSE.txt) 파일을 참조하세요.
