# AgentCore Identity: Runtime 인바운드 및 아웃바운드 인증(Cognito)

## 개요

이 샘플에서는 Amazon Cognito를 Identity Provider(IdP)로 사용하여 **AgentCore Runtime** 에이전트에 인바운드 및 아웃바운드 인증을 모두 적용하는 방법을 보여 줍니다.

- **인바운드 인증**: Runtime 엔드포인트는 Cognito JWT로 보호됩니다. 호출자는 유효한 bearer 토큰을 제시해야 하며, 그렇지 않으면 `AccessDeniedException`을 받습니다.
- **아웃바운드 인증**: 에이전트는 실행 시 AgentCore Identity(AWS Secrets Manager 기반)에서 API 키를 가져옵니다. 키는 환경 변수나 에이전트 코드에 저장되지 않습니다.

### 아키텍처

```
Caller
  │  Authorization: Bearer <Cognito JWT>
  ▼
AgentCore Runtime  ──validates JWT──▶  Cognito User Pool
  │
  │  @requires_api_key("OutboundApiKey")
  ▼
AgentCore Identity  ──fetches secret──▶  AWS Secrets Manager
  │
  ▼
External API (weather service, OpenAI, etc.)
```

### 튜토리얼 세부 정보

| 정보                | 세부 정보                                             |
|:--------------------|:------------------------------------------------------|
| 튜토리얼 유형       | CLI 실습                                              |
| 에이전트 유형       | 단일                                                   |
| 에이전트 프레임워크 | Strands Agents                                        |
| LLM 모델            | Anthropic Claude Haiku 4.5                            |
| 인바운드 인증       | Amazon Cognito(CUSTOM_JWT)                            |
| 아웃바운드 인증     | AgentCore Identity - API 키 자격 증명 공급자          |
| 예제 난이도         | 쉬움                                                   |
| CLI 도구            | `agentcore`(npm: `@aws/agentcore`)                    |

---

## 사전 요구 사항

- **Node.js** 20.x 이상
- **Python** 3.10+
- **uv**([설치](https://docs.astral.sh/uv/getting-started/installation/))
- 구성된 **AWS 자격 증명**(`aws configure` 또는 환경 변수)
- 설치된 **AgentCore CLI**:

```bash
npm install -g @aws/agentcore
```

- **Amazon Bedrock 모델 액세스**: [Bedrock 콘솔](https://console.aws.amazon.com/bedrock/home#/models)에서 `claude-haiku-4-5`를 활성화합니다.

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
- 테스트 사용자 1명(`testuser` / `AgentCoreTest1!`)이 포함된 Cognito User Pool
- `USER_PASSWORD_AUTH`가 활성화된 App Client
- 풀 ID, 클라이언트 ID 및 검색 URL을 `cognito_config.json`에 저장

마지막에 출력되는 두 값을 기록해 두세요. 4단계에서 필요합니다.

```
--discovery-url    https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
--allowed-clients  <client_id>
```

---

## 3단계: AgentCore 프로젝트 생성

```bash
agentcore create --name RuntimeAuthDemo --defaults --no-agent
cd RuntimeAuthDemo
```

배포 대상을 설정합니다(CLI에서 빈 `aws-targets.json`을 생성함).

```bash
cat > agentcore/aws-targets.json << 'EOF'
[{"name":"default","description":"Default deployment target","account":"YOUR_AWS_ACCOUNT_ID","region":"us-east-1"}]
EOF
```

> `YOUR_AWS_ACCOUNT_ID`를 12자리 AWS 계정 ID로 바꾸세요. `aws sts get-caller-identity --query Account --output text`로 확인할 수 있습니다.

---

## 4단계: 에이전트 추가(Bring Your Own Code)

배포 시 인바운드 JWT 인증을 구성하려면 `--authorizer-type CUSTOM_JWT` 플래그를 사용합니다. 자리 표시자 값을 2단계에서 확인한 검색 URL 및 클라이언트 ID로 바꾸세요.

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
  --allowed-clients YOUR_COGNITO_CLIENT_ID
```

---

## 5단계: 아웃바운드 ID 자격 증명 추가

에이전트가 호출하는 [OpenWeatherMap API](https://openweathermap.org/api)에는 API 키가 필요합니다. 무료 키를 발급받으세요.

1. [openweathermap.org](https://home.openweathermap.org/users/sign_up)에서 가입합니다(무료 티어).
2. [API 키](https://home.openweathermap.org/api_keys)로 이동하여 키를 복사합니다.

AgentCore Identity에 키를 안전하게 저장합니다.

```bash
agentcore add credential \
  --name OutboundApiKey \
  --api-key YOUR_OPENWEATHERMAP_API_KEY
```

> CLI는 AgentCore Identity를 통해 AWS Secrets Manager에 키를 저장합니다. 실행 시 에이전트는 `@requires_api_key("OutboundApiKey")`로 키를 가져옵니다. 키는 코드나 환경 변수에 노출되지 않습니다.

---

## 6단계: 배포

```bash
agentcore deploy -y
```

배포에는 몇 분이 걸립니다. 진행 상황을 확인합니다.

```bash
agentcore status
```

---

## 7단계: 인바운드 및 아웃바운드 인증 테스트

샘플 루트 디렉터리로 돌아가 호출 스크립트를 실행합니다.

```bash
cd ..
python invoke.py "What is the weather in Seattle?"
```

스크립트는 다음 두 가지 테스트를 실행합니다.

1. **bearer 토큰 없이 호출** — `AccessDeniedException` 예상
2. **유효한 Cognito bearer 토큰으로 호출** — 에이전트의 성공 응답 예상

예상 출력:

```
[Test 1] Invoking WITHOUT bearer token (expect AccessDeniedException)...
  Correctly rejected: An error occurred (AccessDeniedException) ...

[Test 2] Invoking WITH valid Cognito bearer token...
  Token obtained (first 20 chars): eyJraWQiOiJxT...

Agent response:
The weather in Seattle is currently Sunny, 72F.
```

---

## Streamlit UI(선택 사항)

CLI 대신 브라우저 기반의 대화형 환경을 사용하려면 다음 명령을 실행합니다.

```bash
pip install streamlit
cd ..
streamlit run streamlit_app.py
```

로그인한 다음 채팅 인터페이스에서 날씨 쿼리를 테스트합니다. 403 거부를 테스트하려면 사이드바의 Bearer Token 필드를 비우세요.

---

## 8단계: 정리

```bash
cd RuntimeAuthDemo
agentcore remove agent --name MyAgent --force
agentcore remove credential --name OutboundApiKey --force
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

## 핵심 개념

| 개념 | 이 샘플의 작동 방식 |
|:--------|:---------------------------|
| **인바운드 JWT 검증** | AgentCore Runtime은 에이전트를 실행하기 전에 Cognito JWKS 엔드포인트를 기준으로 `Authorization: Bearer <token>`을 확인합니다. |
| **아웃바운드 API 키** | `@requires_api_key(provider_name="OutboundApiKey")`는 실행 시 `bedrock-agentcore:GetResourceApiKey` + `secretsmanager:GetSecretValue`를 호출합니다. |
| **보안 암호가 없는 에이전트 코드** | API 키는 Secrets Manager에 있으며, 에이전트 코드는 데코레이터를 통해 메모리에서만 키를 사용합니다. |
