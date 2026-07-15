# 프라이빗 IdP 연결: VPC Lattice를 통한 PingFederate와 AgentCore Identity 연결

> **면책 조항:** 이 샘플은 실험 및 교육 목적으로만 제공되며 프로덕션 용도로는 적합하지 않습니다.

이 샘플에서는 **Amazon VPC Lattice**를 사용하여 **Amazon Bedrock AgentCore Identity**를 프라이빗하게 호스팅된 **PingFederate** Identity Provider(IdP)에 연결하는 방법을 보여 줍니다. 이 방식을 사용하면 IdP를 퍼블릭 인터넷에 노출할 필요가 없습니다.

이 샘플에서는 두 가지 AgentCore Identity 패턴을 다룹니다.

1. **아웃바운드 OAuth** - 에이전트 Runtime이 AgentCore Identity와 VPC Lattice를 통해 프라이빗 PingFederate IdP에서 OAuth 토큰을 가져옵니다(IdP로 연결되는 퍼블릭 네트워크 경로 없음).
2. **Gateway 인바운드 인증** - 에이전트가 CUSTOM_JWT 권한 부여로 구성된 AgentCore Gateway에 PingFederate 토큰을 제시하여, Gateway가 VPC Lattice를 통해 프라이빗 IdP의 JWT를 검증할 수 있음을 보여 줍니다.

토큰은 보안 자격 증명이므로 LLM에 노출되거나 호출자에게 반환되지 않습니다. 성공 여부를 확인하기 위해 민감하지 않은 메타데이터(client_id, scope, expiry)와 Gateway tools/list 응답만 반환됩니다.

## 배포 모드

이 샘플은 두 가지 VPC Lattice 배포 모드를 지원합니다.

| 모드 | 배포 명령 | 설명 |
|------|---------------|-------------|
| **AgentCore 관리형**(기본값) | `./deploy_sample.sh` | AgentCore Identity가 VPC Lattice 리소스를 자동으로 생성하고 관리합니다. VPC 및 서브넷 ID를 제공하며 설정이 더 간단합니다. |
| **자체 관리형** | `./deploy_sample.sh --self-managed-lattice` | CDK를 통해 VPC Lattice 리소스(리소스 게이트웨이 + 구성)를 배포합니다. Lattice 수명 주기를 직접 관리하며 더 세밀하게 제어할 수 있습니다. |

## 아키텍처

```
                        ┌──────────────────────┐
                        │  AgentCore Runtime    │
                        │  (agent)              │
                        └──────┬───────┬───────┘
           1. Get token        │       │  2. Call tools/list
           (outbound OAuth)    │       │  (Bearer token)
                               ▼       ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│  AgentCore Identity      │  │  AgentCore Gateway       │
│  (credential provider    │  │  (CUSTOM_JWT auth with   │
│   with privateEndpoint)  │  │   privateEndpoint)       │
└────────────┬─────────────┘  └────────────┬─────────────┘
             │                              │
             │  VPC Lattice                 │  VPC Lattice
             │  (private connectivity)      │  (JWKS validation)
             ▼                              ▼
┌─────────────────────────────────────────────────────────┐
│  Your VPC (private subnets)                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Internal ALB (HTTPS:443)                        │    │
│  │  + Private Hosted Zone (ping.example.com → ALB)  │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         ▼                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │  PingFederate (ECS Fargate)                      │    │
│  │  OAuth2/OIDC Identity Provider                   │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 프라이빗 IdP 연결이 필요한 이유

많은 기업이 퍼블릭 인터넷에 노출되지 않은 프라이빗 네트워크에서 Identity Provider(IdP)를 운영합니다. AgentCore Identity는 OAuth2 흐름(토큰 획득, 검색, JWKS 검색)을 수행하기 위해 IdP와 통신해야 합니다.

**VPC Lattice**는 다음 항목 없이도 AgentCore Identity에서 IdP로 향하는 프라이빗하고 안전한 단방향 네트워크 연결을 제공하여 이 문제를 해결합니다.
- 퍼블릭 로드 밸런서
- VPN 또는 Direct Connect
- VPC 피어링
- IdP용 NAT 게이트웨이

## 핵심 개념

### 프라이빗 호스팅 영역

핵심 요구 사항은 VPC Lattice 리소스 게이트웨이가 **VPC 내부에서** 검색 URL 도메인을 해석해야 한다는 점입니다. 인증서 도메인(예: `ping.example.com`)을 내부 ALB에 매핑하는 Route 53 **프라이빗 호스팅 영역**을 생성해야 합니다. 이 CDK 샘플은 프라이빗 호스팅 영역을 자동으로 생성합니다.

프라이빗 호스팅 영역이 없으면 VPC 내에서 도메인을 해석할 수 없으므로 AgentCore Identity에서 "HTTP request failed against private endpoint" 오류가 발생합니다.

### VPC Lattice 리소스 게이트웨이

**리소스 게이트웨이**는 IdP가 실행되는 VPC의 프라이빗 서브넷에 배포된 Elastic Network Interface(ENI) 세트입니다. VPC로 들어오는 Lattice 트래픽의 인그레스 지점 역할을 합니다.

### VPC Lattice 리소스 구성

**리소스 구성**은 Lattice가 트래픽을 라우팅할 위치를 알 수 있도록 대상 리소스(PingFederate ALB)를 설명합니다. DNS 이름, 포트 및 프로토콜을 지정합니다. 자체 관리형 모드에서는 AgentCore Identity에 `rcfg-xxx` ID를 제공합니다.

### AgentCore Identity 프라이빗 엔드포인트

OAuth2 자격 증명 공급자의 `privateEndpoint` 속성은 AgentCore Identity가 퍼블릭 인터넷 대신 VPC Lattice를 통해 IdP에 연결하도록 지정합니다.

- **AgentCore 관리형 모드**: VPC ID 및 서브넷 ID와 함께 `managedVpcResource`를 제공합니다. AgentCore가 Lattice 리소스를 생성합니다.
- **자체 관리형 모드**: CDK로 배포한 Lattice 리소스의 `rcfg-xxx` 리소스 구성 ID와 함께 `selfManagedLatticeResource`를 제공합니다.

## 배포되는 항목

### CDK 스택

| 스택 | 리소스 | 항상 배포 여부 |
|-------|-----------|-----------------|
| **PrivateIdpVpcStack** | 퍼블릭/프라이빗 서브넷이 있는 VPC(AZ 2개, NAT 게이트웨이 1개) | 예 |
| **PrivateIdpPingFederateStack** | ECR 리포지토리, ECS Fargate 서비스, 내부 ALB, Route 53 프라이빗 호스팅 영역, Lambda 사용자 지정 리소스(PingFederate OAuth/OIDC 구성), Secrets Manager | 예 |
| **PrivateIdpGatewayInfraStack** | MCP Echo Lambda(Gateway 대상), Gateway용 IAM 역할 | 예 |
| **PrivateIdpLatticeStack** | VPC Lattice 리소스 게이트웨이 + 리소스 구성 | `--self-managed-lattice`에서만 |

### 수동 단계(CDK 배포 후)

1. **자격 증명 공급자** - `privateEndpoint` 구성과 함께 AWS CLI를 통해 생성
2. **Gateway** - CUSTOM_JWT 인증 및 JWKS 검증용 `privateEndpoint`와 함께 AWS CLI를 통해 생성
3. **Gateway 대상** - AWS CLI를 통해 MCP Echo Lambda를 Gateway 대상으로 추가
4. **Runtime** - `agent/`의 코드와 [agentcore-cli](https://github.com/aws/agentcore-cli)를 사용하여 배포

## 사전 요구 사항

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) v2.27+
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html) v2 (`npm install -g aws-cdk`)
- Python 종속성 관리용 [uv](https://docs.astral.sh/uv/)
- [Python 3.12+](https://www.python.org/downloads/)
- PingFederate 컨테이너 이미지 빌드/푸시용 [Docker](https://docs.docker.com/get-docker/)
- [agentcore-cli](https://github.com/aws/agentcore-cli) (`npm install -g @aws/agentcore`)
- agentcore-cli 및 CDK용 [Node.js 20+](https://nodejs.org/)
- **PingFederate DevOps 자격 증명** - [여기에서 가입](https://devops.pingidentity.com/get-started/devopsRegistration/)
- **공개적으로 신뢰할 수 있는 ACM 인증서** - AgentCore Identity가 VPC Lattice를 통해 연결하려면 공개적으로 신뢰할 수 있는 TLS 인증서가 필요합니다. ALB 자체는 내부에 유지됩니다.
- VPC, ECS, VPC Lattice, Route 53, AgentCore Identity 및 AgentCore Runtime 리소스를 생성할 권한이 있는 AWS 계정

## 설정

### 1. 구성

```bash
cd 06-workshops/03-AgentCore-identity/08-IDP-examples/PingFederate
```

`.env` 파일을 생성합니다.

```bash
cat <<EOF > .env
PING_IDENTITY_DEVOPS_USER=your-email@example.com
PING_IDENTITY_DEVOPS_KEY=your-devops-key
CERTIFICATE_ARN=arn:aws:acm:us-east-1:123456789012:certificate/abc-123
PING_DOMAIN=ping.example.com
EOF
```

| 변수 | 설명 |
|----------|-------------|
| `PING_IDENTITY_DEVOPS_USER` | PingFederate DevOps 이메일 |
| `PING_IDENTITY_DEVOPS_KEY` | PingFederate DevOps 키 |
| `CERTIFICATE_ARN` | 도메인에 대한 **공개적으로 신뢰할 수 있는** ACM 인증서의 ARN |
| `PING_DOMAIN` | 인증서와 일치하는 도메인 이름(예: `ping.example.com`) |

배포 리전은 셸 환경의 `AWS_REGION` 또는 AWS CLI 기본 리전에 따라 결정됩니다. `AWS_REGION`이 설정되지 않은 경우 기본값은 `us-east-1`입니다.

### 2. 인프라 배포

```bash
./deploy_sample.sh                    # AgentCore 관리형 Lattice(기본값)
./deploy_sample.sh --self-managed-lattice  # 자체 관리형 Lattice
```

배포에는 약 15~20분이 걸립니다. 스크립트는 다음 작업을 수행합니다.
1. 사전 요구 사항 검증
2. Python 종속성 설치
3. CDK 부트스트랩
4. 모든 스택 배포
5. 자격 증명 공급자, Gateway 및 Gateway 대상을 생성하는 AWS CLI 명령 출력

### 3. AgentCore Identity 자격 증명 공급자 생성

배포 후 스크립트가 정확한 AWS CLI 명령을 출력합니다. 배포 모드에 따라 선택하세요.

**AgentCore 관리형 모드**(기본값):

```bash
aws bedrock-agentcore-control create-oauth2-credential-provider \
    --name "ping-private-idp" \
    --credential-provider-vendor "CustomOauth2" \
    --oauth2-provider-config-input '{
        "customOauth2ProviderConfig": {
            "oauthDiscovery": {
                "discoveryUrl": "https://ping.example.com/.well-known/openid-configuration"
            },
            "clientId": "agentcore-client",
            "clientSecret": "agentcore-test-secret-12345",
            "privateEndpoint": {
                "managedVpcResource": {
                    "vpcIdentifier": "vpc-xxx",
                    "subnetIds": ["subnet-xxx", "subnet-yyy"],
                    "endpointIpAddressType": "IPV4"
                }
            }
        }
    }'
```

**자체 관리형 모드**(`--self-managed-lattice`):

```bash
aws bedrock-agentcore-control create-oauth2-credential-provider \
    --name "ping-private-idp" \
    --credential-provider-vendor "CustomOauth2" \
    --oauth2-provider-config-input '{
        "customOauth2ProviderConfig": {
            "oauthDiscovery": {
                "discoveryUrl": "https://ping.example.com/.well-known/openid-configuration"
            },
            "clientId": "agentcore-client",
            "clientSecret": "agentcore-test-secret-12345",
            "privateEndpoint": {
                "selfManagedLatticeResource": {
                    "resourceConfigurationIdentifier": "rcfg-xxx"
                }
            }
        }
    }'
```

### 4. 자격 증명 공급자 확인

자격 증명 공급자가 READY 상태가 될 때까지 약 3분 동안 기다립니다.

```bash
aws bedrock-agentcore-control get-oauth2-credential-provider \
    --name "ping-private-idp" \
    --query '{name: name, status: status}'
```

### 5. AgentCore Gateway 생성

Gateway는 PingFederate를 토큰 발급자로 사용하는 CUSTOM_JWT 인바운드 인증을 사용합니다. `privateEndpoint`는 Gateway가 VPC Lattice(프라이빗 연결)를 통해 PingFederate의 JWKS 엔드포인트에 연결하여 JWT를 검증하도록 지정합니다.

배포 스크립트는 스택 값이 미리 채워진 정확한 명령을 출력합니다. 이 명령은 `PrivateIdpGatewayInfraStack`의 IAM 역할과 VPC 구성을 사용합니다.

```bash
aws bedrock-agentcore-control create-gateway \
    --name "PingGateway" \
    --protocol-type "MCP" \
    --role-arn "GATEWAY_ROLE_ARN"  \
    --authorizer-type "CUSTOM_JWT" \
    --authorizer-configuration '{
        "customJWTAuthorizer": {
            "discoveryUrl": "https://ping.example.com/.well-known/openid-configuration",
            "allowedClients": ["agentcore-client"],
            "privateEndpoint": {
                "managedVpcResource": {
                    "vpcIdentifier": "vpc-xxx",
                    "subnetIds": ["subnet-xxx", "subnet-yyy"],
                    "endpointIpAddressType": "IPV4"
                }
            }
        }
    }' \
    --exception-level "DEBUG"
```

Gateway가 READY 상태가 될 때까지 약 2~3분 동안 기다립니다.

```bash
aws bedrock-agentcore-control list-gateways \
    --query 'items[?name==`PingGateway`].{id:gatewayId,status:status,url:gatewayUrl}'
```

### 6. MCP Echo Lambda 대상 추가

Gateway가 READY 상태가 되면 Lambda 대상을 추가합니다. `GATEWAY_ID`를 5단계에서 확인한 `gatewayId`로 바꾸세요.

```bash
aws bedrock-agentcore-control create-gateway-target \
    --gateway-identifier GATEWAY_ID \
    --name "McpEchoTarget" \
    --target-configuration '{
        "mcp": {
            "lambda": {
                "lambdaArn": "MCP_ECHO_LAMBDA_ARN",
                "toolSchema": {
                    "inlinePayload": [
                        {
                            "name": "get_time",
                            "description": "Get the current UTC time",
                            "inputSchema": { "type": "object", "properties": {}, "required": [] }
                        },
                        {
                            "name": "echo",
                            "description": "Echo a message back",
                            "inputSchema": {
                                "type": "object",
                                "properties": { "message": { "type": "string", "description": "Message to echo" } },
                                "required": ["message"]
                            }
                        }
                    ]
                }
            }
        }
    }' \
    --credential-provider-configurations '[{"credentialProviderType": "GATEWAY_IAM_ROLE"}]'
```

배포 스크립트는 실제 Lambda ARN이 미리 채워진 이 명령을 출력합니다.

### 7. Runtime 배포

`agent/` 디렉터리에는 완전한 [agentcore-cli](https://github.com/aws/agentcore-cli) 프로젝트가 있으므로 스캐폴딩이 필요하지 않습니다. 배포 스크립트는 계정 ID와 리전을 사용해 `aws-targets.json`을 자동으로 구성합니다.

배포하기 전에 에이전트가 인증된 요청을 보낼 위치를 알 수 있도록 Gateway URL을 구성합니다.
`agent/private-idp-ping-agent/agentcore/agentcore.json`을 열고 Runtime 정의의 `envVars` 배열에 `GATEWAY_URL`을 추가합니다.

```json
"envVars": [
  {
    "name": "GATEWAY_URL",
    "value": "https://YOUR-GATEWAY-ID.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
  }
]
```

`YOUR-GATEWAY-ID`를 5단계에서 확인한 `gatewayId`로 바꾸세요. 전체 URL은
`https://<gatewayId>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp` 패턴을 따릅니다.

그런 다음 배포합니다.

```bash
cd agent/private-idp-ping-agent
agentcore deploy -y
```

> **참고:** `agentcore create`를 실행할 필요가 **없습니다**. 프로젝트 구조와 CDK 구성은 이미 커밋되어 있습니다. `agentcore deploy`는 구성된 AWS 자격 증명에서 계정과 리전을 확인합니다.

### 8. Runtime 테스트

```bash
agentcore invoke --prompt "test"
```

예상 출력:

```json
{
  "success": true,
  "claims": {
    "scope": "openid",
    "client_id": "agentcore-client",
    "iss": "https://ping.example.com",
    "iat": 1234567890,
    "exp": 1234575090
  },
  "gateway": {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
      "tools": [
        {
          "name": "McpEchoTarget___echo",
          "description": "Echo a message back"
        },
        {
          "name": "McpEchoTarget___get_time",
          "description": "Get the current UTC time"
        }
      ]
    }
  }
}
```

Runtime은 다음 작업을 수행합니다.
1. AgentCore Identity를 통해 PingFederate에서 OAuth 토큰 획득(VPC Lattice를 통한 아웃바운드 OAuth)
2. AgentCore Gateway에 토큰을 Bearer 토큰으로 제시(인바운드 JWT 인증)
3. Gateway가 VPC Lattice(프라이빗 연결)를 통해 PingFederate의 JWKS를 가져와 JWT 검증
4. MCP Echo Lambda 대상의 tools/list 응답 반환

## 정리

### 1. Gateway 및 자격 증명 공급자 삭제

```bash
# Gateway 삭제(대상도 함께 삭제됨)
aws bedrock-agentcore-control delete-gateway --gateway-identifier GATEWAY_ID

# Credential provider 삭제
aws bedrock-agentcore-control delete-oauth2-credential-provider \
    --name "ping-private-idp"
```

### 2. Runtime 삭제

```bash
cd agent/private-idp-ping-agent
agentcore destroy -y
cd ../..
```

### 3. CDK 스택 삭제

```bash
./cleanup_sample.sh
```

정리 스크립트는 PrivateIdpLatticeStack → PrivateIdpGatewayInfraStack → PrivateIdpPingFederateStack → PrivateIdpVpcStack 순서로 스택을 삭제합니다.

> **참고:** 자체 관리형 및 AgentCore 관리형 VPC Lattice ENI가 AWS에서 해제되기까지 최대 8시간이 걸릴 수 있습니다. PrivateIdpVpcStack 삭제에 실패하면 기다린 후 `uv run cdk destroy PrivateIdpVpcStack --force`로 다시 시도하세요.

## Runtime 프로젝트 구조

```
agent/private-idp-ping-agent/
├── agentcore/
│   ├── agentcore.json      # Runtime 구성 + credential provider 선언
│   ├── aws-targets.json    # 배포 대상(비어 있음 - 자격 증명에서 확인)
│   ├── .gitignore
│   └── cdk/                # CDK 인프라(커밋되어 있으며 배포 준비 완료)
└── app/
    └── private-idp-ping-agent/
        ├── main.py         # @requires_access_token을 사용하는 Runtime
        └── pyproject.toml  # Python 종속성
```

Runtime은 다음 항목을 사용합니다.
- 자격 증명 공급자를 통해 OAuth 토큰을 얻기 위한 `bedrock_agentcore.identity`의 **`@requires_access_token`** 데코레이터
- Runtime 수명 주기를 위한 `bedrock_agentcore.runtime`의 **`BedrockAgentCoreApp`**
- 획득한 토큰으로 AgentCore Gateway를 호출하기 위한 **`GATEWAY_URL`** 환경 변수

LLM이나 에이전트 프레임워크는 필요하지 않습니다. 이 샘플은 프라이빗 IdP 연결을 검증하는 데만 중점을 둡니다. 토큰은 데코레이터가 적용된 함수 내에서 안전하게 처리되며 함수 외부에 노출되지 않습니다.

> **참고:** agentcore-cli는 아직 `privateEndpoint` 파라미터를 지원하지 않으므로 자격 증명 공급자와 Gateway는 AWS CLI를 통해 수동으로 생성합니다. `agentcore.json`은 Runtime에서 참조할 자격 증명 공급자 이름을 선언합니다.

## 작동 방식

```python
from bedrock_agentcore.identity import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

CREDENTIAL_PROVIDER_NAME = "ping-private-idp"
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")

@requires_access_token(
    provider_name=CREDENTIAL_PROVIDER_NAME,
    scopes=["openid"],
    auth_flow="M2M",
)
def fetch_token_from_private_idp(*, access_token: str) -> dict:
    # Decorator에서 처리하는 작업:
    # 1. 이 Runtime의 workload identity token 가져오기
    # 2. Credential provider를 통해 OAuth access token으로 교환
    # 3. Credential provider가 VPC Lattice를 통해 PingFederate에 연결
    # 4. 결과 access_token을 이 함수에 주입

    # 토큰을 사용하여 AgentCore Gateway 호출(인바운드 JWT 인증)
    if GATEWAY_URL:
        gateway_result = call_gateway(access_token)
    ...
```

`@requires_access_token` 데코레이터는 전체 토큰 획득 흐름을 추상화합니다. 코드에서는 필요한 자격 증명 공급자와 scope만 선언하면 됩니다. SDK가 워크로드 ID, OAuth 교환 및 VPC Lattice를 통한 프라이빗 네트워크 라우팅을 처리합니다.

Gateway 호출에서는 인바운드 인증을 보여 줍니다. 동일한 PingFederate 토큰을 Gateway에 `Bearer` 토큰으로 제시하면, Gateway는 VPC Lattice를 통해 PingFederate의 JWKS를 가져와 토큰을 검증합니다.

## PingFederate 구성

배포 중 VPC 내에서 실행되는 Lambda 사용자 지정 리소스(`lambda/configure_pingfed/index.py`)가 Admin API를 통해 PingFederate를 구성합니다.

- JWT 토큰 서명용 **RSA Signing Key**
- RS256을 사용하는 **JWT Access Token Manager**
- scope가 `openid`, `profile`, `email`인 **OAuth Authorization Server**
- 표준 claim이 포함된 **OIDC Policy**
- client credentials grant용으로 구성된 **OAuth Client**(`agentcore-client`)
- OIDC 검색에 적합한 기본 URL이 포함된 **서버 설정**

클라이언트 ID(`agentcore-client`)와 보안 암호(`agentcore-test-secret-12345`)는 `lambda/configure_pingfed/index.py`에 정의되어 있습니다. 프로덕션에서는 이 값을 교체하고 안전하게 저장하세요.

## 비용 고려 사항

이 샘플은 AWS 요금이 발생하는 리소스를 생성합니다.

| 리소스 | 예상 비용 |
|----------|-----------------|
| NAT Gateway | 월 약 $32 + 데이터 전송 비용 |
| ECS Fargate(2 vCPU, 4GB) | 월 약 $70 |
| Application Load Balancer | 월 약 $16 + LCU |
| VPC Lattice(자체 관리형만 해당) | 처리된 데이터 기준 |
| EFS | 사용한 스토리지 기준 |

**지속적인 요금 발생을 방지하려면 테스트 직후 `./cleanup_sample.sh`를 실행하세요.**

## 문제 해결

### "HTTP request failed against private endpoint"

일반적으로 이 오류는 VPC 내에서 검색 URL 도메인을 해석할 수 없음을 의미합니다. 다음 사항을 확인하세요.
1. 프라이빗 호스팅 영역이 존재하고 VPC에 연결되어 있는지 확인
2. 프라이빗 영역의 A 레코드가 내부 ALB를 가리키는지 확인
3. 검색 URL의 도메인이 프라이빗 호스팅 영역 이름과 일치하는지 확인

CDK 스택은 프라이빗 호스팅 영역을 자동으로 생성합니다. 이 샘플을 기존 IdP에 맞게 조정하는 경우 IdP 도메인을 내부 엔드포인트에 매핑하는 프라이빗 호스팅 영역이 있는지 확인하세요.

### VPC 스택 삭제 실패

VPC Lattice ENI가 해제되기까지 최대 8시간이 걸릴 수 있습니다. 기다린 후 다시 시도하세요.

```bash
uv run cdk destroy PrivateIdpVpcStack --force
```

ENI 상태를 확인하려면 다음 명령을 실행합니다.

```bash
VPC_ID=$(aws cloudformation describe-stacks --stack-name PrivateIdpVpcStack \
    --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' --output text)
aws ec2 describe-network-interfaces --filters Name=vpc-id,Values=$VPC_ID
```

## 참고

PingFederate는 AWS 서비스가 아닙니다. 비용과 라이선스는 PingIdentity 문서를 참조하세요. PingFederate 컨테이너 이미지는 PingIdentity DevOps 프로그램에 따라 Docker Hub에서 가져옵니다.
