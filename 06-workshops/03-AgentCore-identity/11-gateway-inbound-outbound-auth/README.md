# AgentCore Identity: Gateway 인바운드 및 아웃바운드 인증(Cognito)

## 개요

이 샘플에서는 Amazon Cognito를 Identity Provider로 사용하여 **AgentCore Gateway**에 인바운드 및 아웃바운드 인증을 모두 적용하는 방법을 보여 줍니다.

- **인바운드 인증**: Gateway 엔드포인트는 Cognito JWT(`CUSTOM_JWT` 권한 부여자)로 보호됩니다. 호출자는 유효한 bearer 토큰을 제시해야 합니다.
- **아웃바운드 인증**: Gateway는 OAuth2 client credentials를 사용해 업스트림 MCP 서버에 인증합니다(`mcp.json`에서 선언적으로 구성하므로 에이전트 코드를 변경할 필요가 없음).

에이전트는 도구를 검색하고 호출하기 위해 Gateway에 연결합니다. Gateway는 에이전트를 대신해 모든 인증을 처리합니다.

### 아키텍처

```
Caller
  │  Authorization: Bearer <Cognito JWT>
  ▼
AgentCore Gateway  ──validates JWT──▶  Cognito User Pool
  │
  │  OAuth2 client credentials (outbound)
  ▼
Upstream MCP Server  (e.g., internal tool service, third-party API)
  ▲
  │  tools response
AgentCore Runtime Agent
```

### 튜토리얼 세부 정보

| 정보                | 세부 정보                                               |
|:--------------------|:--------------------------------------------------------|
| 튜토리얼 유형       | CLI 실습                                                |
| 에이전트 유형       | 단일(Gateway 포함)                                      |
| 에이전트 프레임워크 | Strands Agents                                          |
| LLM 모델            | Anthropic Claude Haiku 4.5                              |
| 인바운드 인증       | Gateway의 Amazon Cognito(CUSTOM_JWT)                    |
| 아웃바운드 인증     | Gateway 대상의 OAuth2 client credentials                |
| 예제 난이도         | 보통                                                     |
| CLI 도구            | `agentcore`(npm: `@aws/agentcore`)                      |

---

## 사전 요구 사항

- **Node.js** 20.x 이상
- **Python** 3.10+
- **uv**([설치](https://docs.astral.sh/uv/getting-started/installation/))
- 구성된 **AWS 자격 증명**
- 설치된 **AgentCore CLI**:

```bash
npm install -g @aws/agentcore
```

- **Amazon Bedrock 모델 액세스**: [Bedrock 콘솔](https://console.aws.amazon.com/bedrock/home#/models)에서 `claude-haiku-4-5`를 활성화합니다.
- OAuth2가 필요한 **MCP 서버 엔드포인트**(테스트에는 `--outbound-auth none` 사용 가능)

---

## 1단계: 설정 종속성 설치

```bash
pip install -r requirements.txt
```

---

## 2단계: Cognito 설정(인바운드 IdP)

```bash
python setup_cognito.py
```

이 명령은 다음 리소스와 파일을 생성합니다.
- 테스트 사용자(`testuser` / `AgentCoreTest1!`)가 포함된 Cognito User Pool
- **사용자용 앱 클라이언트**(Gateway로 인증하는 호출자용)
- **에이전트용 앱 클라이언트**(CLI에서 관리형 자격 증명을 생성할 때 사용)
- 모든 값을 `cognito_config.json`에 저장

마지막에 출력되는 값을 기록해 두세요. 4단계에서 필요합니다.

```
--discovery-url    https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
--allowed-clients  <user_client_id>,<agent_client_id>
--client-id        <agent_client_id>
--client-secret    <from cognito_config.json>
```

---

## 3단계: AgentCore 프로젝트 생성

```bash
agentcore create --name GatewayAuthDemo --defaults --no-agent
cd GatewayAuthDemo
```

배포 대상을 설정합니다(CLI에서 빈 `aws-targets.json`을 생성함).

```bash
cat > agentcore/aws-targets.json << 'EOF'
[{"name":"default","description":"Default deployment target","account":"YOUR_AWS_ACCOUNT_ID","region":"us-east-1"}]
EOF
```

> `YOUR_AWS_ACCOUNT_ID`를 12자리 AWS 계정 ID로 바꾸세요. `aws sts get-caller-identity --query Account --output text`로 확인할 수 있습니다.

---

## 4단계: Cognito JWT 인바운드 인증을 사용하는 Gateway 추가

자리 표시자 값을 `cognito_config.json`의 값으로 바꾸세요.

```bash
agentcore add gateway \
  --name MyGateway \
  --authorizer-type CUSTOM_JWT \
  --discovery-url YOUR_COGNITO_DISCOVERY_URL \
  --allowed-clients YOUR_USER_CLIENT_ID,YOUR_AGENT_CLIENT_ID \
  --client-id YOUR_AGENT_CLIENT_ID \
  --client-secret YOUR_AGENT_CLIENT_SECRET
```

CLI는 에이전트가 Gateway를 호출할 Bearer 토큰을 얻을 수 있도록 **관리형 OAuth 자격 증명**을 자동으로 생성합니다. 이 자격 증명은 `agentcore/agentcore.json`에 `"managed": true`로 표시됩니다.

---

## 5단계: Gateway 대상 추가

1단계에서 배포한 MCP 서버를 Gateway 대상으로 추가합니다. `mcp_server_config.json`의 엔드포인트 URL을 사용하세요.

```bash
agentcore add gateway-target \
  --name MyTools \
  --type mcp-server \
  --endpoint YOUR_MCP_SERVER_ENDPOINT \
  --gateway MyGateway
```

> `YOUR_MCP_SERVER_ENDPOINT`를 `setup_mcp_server.py`에서 출력한 엔드포인트(예: `https://abc123.execute-api.us-east-1.amazonaws.com/mcp`)로 바꾸세요.
>
> 대상에 OAuth 아웃바운드 인증을 추가하려면(MCP 서버에서 필요한 경우) `--outbound-auth oauth --credential-name YOUR_CREDENTIAL`을 사용하세요.

---

## 6단계: 에이전트 추가

```bash
agentcore add agent \
  --name MyAgent \
  --type byo \
  --code-location ../app/MyAgent \
  --entrypoint main.py \
  --language Python \
  --framework Strands \
  --model-provider Bedrock \
  --authorizer-type CUSTOM_JWT \
  --discovery-url YOUR_COGNITO_DISCOVERY_URL \
  --allowed-clients YOUR_USER_CLIENT_ID
```

`YOUR_COGNITO_DISCOVERY_URL`과 `YOUR_USER_CLIENT_ID`를 `cognito_config.json`의 값으로 바꾸세요. 그러면 배포 시 Runtime에 JWT 인바운드 인증이 구성됩니다.

---

## 7단계: 배포

```bash
agentcore deploy -y
```

상태를 확인합니다.

```bash
agentcore status
```

---

## 8단계: 배포 후 구성

다음 배포 후 스크립트를 실행하여 Runtime에 JWT 인바운드 인증을 적용하고, Gateway URL 환경 변수를 설정하고, 아웃바운드 자격 증명 검색에 필요한 IAM 권한을 연결하고, 관리형 Gateway 자격 증명이 있는지 확인합니다.

```bash
cd ..
python configure_inbound_auth.py
```

변경 사항이 전파될 때까지 약 30초 동안 기다립니다.

---

## 9단계: 인바운드 및 아웃바운드 인증 테스트

```bash
cd ..
python invoke.py "What tools do you have available?"
```

예상 출력:

```
[Test 1] Invoking WITHOUT bearer token (expect AccessDeniedException)...
  Correctly rejected: An error occurred (AccessDeniedException) ...

[Test 2] Invoking WITH Cognito bearer token (expect success)...
  Token obtained (first 20 chars): eyJraWQiOiJxT...

Agent response:
I have access to the following tools through the gateway: [tool list]
```

---

## 아웃바운드 인증 작동 방식

에이전트가 Gateway 도구를 호출할 때 다음 과정이 진행됩니다.

1. **에이전트 → Gateway**: 에이전트가 관리형 Cognito 자격 증명(Bearer 토큰)을 제시합니다. 이 과정은 `GatewayClient`에서 자동으로 처리됩니다.
2. **Gateway 검증**: Cognito를 기준으로 인바운드 JWT를 검증합니다.
3. **Gateway → MCP 서버**: Gateway가 저장된 OAuth2 client credentials를 액세스 토큰으로 교환하고 요청을 전달합니다.
4. **MCP 서버**: 도구 결과로 응답합니다.

에이전트 코드는 업스트림 자격 증명을 알지 못하며, 자격 증명은 Gateway 내에서 완전히 관리됩니다.

---

## Streamlit UI(선택 사항)

CLI 대신 브라우저 기반의 대화형 환경을 사용하려면 다음 명령을 실행합니다.

```bash
pip install streamlit
cd ..
streamlit run streamlit_app.py
```

로그인한 다음 채팅 인터페이스에서 Gateway 도구(get_time, echo)를 테스트합니다. 403 거부를 테스트하려면 사이드바의 Bearer Token 필드를 비우세요.

---

## 10단계: 정리

```bash
cd GatewayAuthDemo
agentcore remove gateway-target --name MyTools --force
agentcore remove gateway --name MyGateway --force
agentcore remove agent --name MyAgent --force
```

Cognito 리소스를 삭제합니다.

```python
import boto3, json

with open("../cognito_config.json") as f:
    config = json.load(f)

boto3.client("cognito-idp", region_name=config["region"]).delete_user_pool(
    UserPoolId=config["pool_id"]
)
print("Cognito User Pool deleted.")
```

---
