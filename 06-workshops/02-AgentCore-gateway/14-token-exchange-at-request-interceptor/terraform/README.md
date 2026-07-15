# Request Interceptor에서 Token Exchange를 사용하는 AgentCore Gateway - Terraform

이 Terraform 구성은 함께 제공되는 Jupyter 노트북(`token-exchange-at-request-interceptor.ipynb`)과 동일한 인프라를 프로비저닝하며, AgentCore Gateway를 사용하는 multi-hop 에이전트 워크플로에서 안전한 token exchange 및 identity 전파를 지원합니다.

## 아키텍처

1. **Client**가 Cognito OAuth2 토큰(client credentials flow)으로 요청을 시작합니다.
2. **AgentCore Gateway**가 token exchange를 위해 interceptor를 통해 요청을 라우팅합니다.
3. **Gateway Interceptor Lambda**가 인바운드 토큰을 검증하고 Cognito를 통해 범위가 지정된 다운스트림 토큰으로 교환합니다.
4. **API Gateway(OpenAPI Target)**가 교환된 토큰이 포함된 처리 완료 요청을 수신합니다.
5. Terraform이 프로비저닝하지 않는 **Strands Agent**가 streamable HTTP transport를 통해 Gateway에 연결할 수 있습니다.

## 사전 요구 사항

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- 자격 증명이 구성된 [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
- AWS provider >= 5.0(`aws_bedrockagentcore_*` 리소스 지원)

## 파일 구조

```
terraform/
├── providers.tf          # AWS, archive, null, random provider
├── variables.tf          # region, name_prefix
├── data.tf               # Account ID, region, 고유 이름용 random suffix
├── cognito.tf            # User Pool, Domain, Resource Server, App Client
├── lambda.tf             # Pre Token Generation + Gateway Interceptor Lambda
├── apigateway.tf         # REST API(OpenAPI), Authorizer, API Key, Usage Plan
├── agentcore.tf          # Credential Provider, Gateway IAM Role, Gateway, Target
├── outputs.tf            # 주요 output(ID, ARN, URL)
└── lambda_src/
    ├── pre_token_generation/
    │   └── lambda_function.py
    └── gateway_interceptor/
        └── lambda_function.py
```

## 생성되는 리소스

| 리소스 | Terraform 리소스 |
|---|---|
| Cognito User Pool(Essentials tier) | `aws_cognito_user_pool.this` + `null_resource.configure_user_pool` |
| Cognito Resource Server(read/write scope) | `aws_cognito_resource_server.this` |
| Cognito App Client(client_credentials) | `aws_cognito_user_pool_client.this` |
| Cognito User Pool Domain | `aws_cognito_user_pool_domain.this` |
| Pre Token Generation Lambda + IAM Role | `aws_lambda_function.pre_token_generation` |
| Gateway Interceptor Lambda + IAM Role | `aws_lambda_function.gateway_interceptor` |
| API Gateway REST API(OpenAPI import) | `aws_api_gateway_rest_api.this` |
| Cognito Authorizer | `aws_api_gateway_authorizer.cognito` |
| API Key + Usage Plan | `aws_api_gateway_api_key.this` + `aws_api_gateway_usage_plan.this` |
| AgentCore API Key Credential Provider | `aws_bedrockagentcore_api_key_credential_provider.this` |
| AgentCore Gateway(Custom JWT + Interceptor) | `aws_bedrockagentcore_gateway.this` |
| AgentCore Gateway Target(OpenAPI) | `aws_bedrockagentcore_gateway_target.this` |

## 사용법

```bash
cd terraform
terraform init
terraform apply
```

배포를 사용자 지정하려면 다음 명령을 실행합니다.

```bash
terraform apply -var="region=us-west-2" -var="name_prefix=myproject"
```

## 변수

| 이름 | 설명 | 기본값 |
|---|---|---|
| `region` | AWS 리전 | `us-east-1` |
| `name_prefix` | 리소스 이름의 prefix | `agentcore` |

## 출력

| 이름 | 설명 |
|---|---|
| `cognito_user_pool_id` | Cognito User Pool ID |
| `cognito_client_id` | Cognito App Client ID |
| `cognito_client_secret` | Cognito App Client Secret(민감 정보) |
| `cognito_token_endpoint` | Cognito OAuth2 token endpoint |
| `api_gateway_url` | API Gateway 호출 URL |
| `gateway_id` | AgentCore Gateway ID |
| `gateway_url` | AgentCore Gateway URL |
| `gateway_target_id` | AgentCore Gateway Target ID |

## Strands Agent로 테스트

배포 후 출력 값을 사용해 Strands Agent를 연결합니다.

```python
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# Terraform 출력 값 사용
gateway_url = "<gateway_url from terraform output>"
access_token = "<obtain via cognito token endpoint>"

client = MCPClient(lambda: streamablehttp_client(
    gateway_url,
    headers={"Authorization": f"Bearer {access_token}"}
))

model = BedrockModel(model_id="us.amazon.nova-pro-v1:0")

with client:
    tools = client.list_tools_sync()
    agent = Agent(model=model, tools=tools)
    response = agent("List all tools available to you")
```

## 정리

```bash
terraform destroy
```

## 설계 참고 사항

- 모든 plan/apply에서 리소스가 다시 생성되는 것을 방지하기 위해 timestamp 대신 `random_id` suffix를 사용합니다.
- Terraform AWS provider는 `UserPoolTier`를 기본 지원하지 않으므로 AWS CLI와 `null_resource`를 사용해 Cognito User Pool을 Essentials tier로 업그레이드하고 V3_0 Pre Token Generation trigger를 연결합니다.
- Gateway, 대상 및 credential provider에는 native `aws_bedrockagentcore_*` Terraform 리소스를 사용합니다.
