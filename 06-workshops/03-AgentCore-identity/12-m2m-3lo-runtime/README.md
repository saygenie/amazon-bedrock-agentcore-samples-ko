# AgentCore Identity: Runtime의 M2M 및 Auth Code 흐름(Cognito)

## 개요

이 샘플에서는 단일 **AgentCore Runtime** 에이전트에서 두 가지 아웃바운드 OAuth2 흐름을 보여 줍니다.

| 흐름 | Grant 유형 | 사용 사례 |
|:-----|:-----------|:---------|
| **M2M**(machine-to-machine) | `client_credentials` | 에이전트가 에이전트 자신으로 내부/다운스트림 API 호출. 사용자 상호 작용 없음 |
| **Auth Code**(3LO) | `authorization_code` | 에이전트가 사용자 소유 리소스(Google Calendar)에 액세스. 일회성 사용자 동의 필요 |

**인바운드 인증**: Runtime 엔드포인트는 Cognito JWT로 보호됩니다. 두 흐름 모두 호출자가 유효한 bearer 토큰을 제시해야 합니다.

### 아키텍처

```
Caller
  │  Authorization: Bearer <Cognito JWT>
  ▼
AgentCore Runtime  ──validates JWT──▶  Cognito User Pool
  │
  ├─── M2M Tool ──@requires_access_token(auth_flow="M2M")──▶
  │              AgentCore Identity (client credentials)    ──▶  Internal API
  │
  └─── 3LO Tool ──@requires_access_token(auth_flow="USER_FEDERATION")──▶
                 AgentCore Identity (auth code)             ──▶  Google Calendar API
                         │
                         │ (first call only: returns consent URL)
                         ▼
                     User's browser ──consents──▶ Google ──callback──▶ localhost:9090
```

### 튜토리얼 세부 정보

| 정보                | 세부 정보                                                            |
|:--------------------|:---------------------------------------------------------------------|
| 튜토리얼 유형       | CLI 실습                                                             |
| 에이전트 유형       | 단일                                                                  |
| 에이전트 프레임워크 | Strands Agents                                                       |
| LLM 모델            | Anthropic Claude Haiku 4.5                                           |
| 인바운드 인증       | Amazon Cognito(CUSTOM_JWT)                                           |
| 아웃바운드 인증(M2M) | OAuth2 client credentials - `@requires_access_token(auth_flow="M2M")` |
| 아웃바운드 인증(3LO) | OAuth2 auth code - `@requires_access_token(auth_flow="USER_FEDERATION")` |
| 예제 난이도         | 보통                                                                  |
| CLI 도구            | `agentcore`(npm: `@aws/agentcore`)                                   |

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

- **Amazon Bedrock 모델 액세스**: Bedrock 콘솔에서 `claude-haiku-4-5`를 활성화합니다.
- **M2M용**: `client_credentials` grant를 지원하는 OAuth2 권한 부여 서버
- **3LO용**: Calendar API가 활성화된 Google Cloud 프로젝트(4단계 참조)

---

## 1단계: 종속성 설치

```bash
pip install -r requirements.txt
```

---

## 2단계: Cognito 설정(인바운드 인증)

```bash
python setup_cognito.py
```

Cognito User Pool과 테스트 사용자를 생성하고 `cognito_config.json`을 저장합니다.

6단계에 사용할 출력 값을 기록해 두세요.
```
--discovery-url    https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
--allowed-clients  <client_id>
```

---

## 3단계: AgentCore 프로젝트 생성

```bash
agentcore create --name M2MAuthDemo --defaults --no-agent
cd M2MAuthDemo
```

배포 대상을 설정합니다(CLI에서 빈 `aws-targets.json`을 생성함).

```bash
cat > agentcore/aws-targets.json << 'EOF'
[{"name":"default","description":"Default deployment target","account":"YOUR_AWS_ACCOUNT_ID","region":"us-east-1"}]
EOF
```

> `YOUR_AWS_ACCOUNT_ID`를 12자리 AWS 계정 ID로 바꾸세요. `aws sts get-caller-identity --query Account --output text`로 확인할 수 있습니다.

---

## 4단계: OAuth 자격 증명 공급자 설정

### 4a. GitHub OAuth App 생성(GitHub 3LO용)

1. [github.com](https://github.com) > **Settings** > **Developer settings** > **OAuth Apps**로 이동합니다.
2. **New OAuth App**을 클릭하고 다음 항목을 입력합니다.
   - **Application Name**: 원하는 이름(예: "AgentCore GitHub Demo")
   - **Homepage URL**: `https://github.com/awslabs/amazon-bedrock-agentcore-samples`
   - **Authorization callback URL**: `https://bedrock-agentcore.us-east-1.amazonaws.com/identities/oauth2/callback/placeholder`(설정 스크립트를 실행한 후 업데이트)
3. **Register application**을 클릭합니다.

![GitHub OAuth App 설정](images/github_details.png)

4. **Client ID**를 복사하고 **Client Secret**을 생성한 다음 저장합니다. Client Secret은 한 번만 표시됩니다.

### 4b. Google OAuth App 생성(Google 3LO용)

1. [Google Cloud Console](https://console.developers.google.com/)로 이동하여 프로젝트를 생성하거나 선택합니다.
2. **APIs & Services > Library**로 이동하고 **Google Calendar API**를 검색한 다음 **Enable**을 클릭합니다.
3. **APIs & Services > OAuth consent screen**으로 이동하고 **Get started**를 클릭합니다.
   - App Name과 Support Email을 입력합니다.
   - 대상 유형을 선택하고(테스트에는 External) 나머지 단계를 완료합니다.
4. **APIs & Services > OAuth consent screen > Audience**로 이동하고 **+ Add Users**를 클릭한 다음 Gmail 주소를 추가합니다.
5. **APIs & Services > Credentials**로 이동하고 **Create Credentials > OAuth client ID**를 클릭합니다.
   - Application type: **Web application**
   - Name: 원하는 이름
   - **Create**를 클릭한 다음 **Client ID**와 **Client Secret**을 복사합니다.
6. **APIs & Services > Credentials**로 이동하여 OAuth 클라이언트를 클릭한 다음 **Data access** > **Add or remove scopes**를 선택합니다.
   - "Manually add scopes" 아래에 `https://www.googleapis.com/auth/calendar.readonly`를 추가합니다.
   - **Update**를 클릭한 다음 **Save**를 클릭합니다.

### 4c. `.env` 파일 생성 및 설정 스크립트 실행

샘플 루트 디렉터리에 자격 증명을 포함한 `.env` 파일을 생성합니다.

```bash
M2M_CLIENT_ID=YOUR_COGNITO_MACHINE_CLIENT_ID
M2M_CLIENT_SECRET=YOUR_COGNITO_MACHINE_CLIENT_SECRET
M2M_DISCOVERY_URL=https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
GITHUB_CLIENT_ID=YOUR_GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET=YOUR_GITHUB_CLIENT_SECRET
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET
```

> M2M 값은 2단계의 `cognito_config.json`에서 가져옵니다. `machine_client_id`와 `machine_client_secret`을 사용하세요.

그런 다음 다음 명령을 실행합니다.

```bash
cd ..
python setup_oauth_providers.py
cd M2MAuthDemo
```

스크립트가 각 공급자의 콜백 URL을 출력합니다.

### 4d. 콜백 URL 등록

**GitHub**: OAuth App 설정 > **Authorization callback URL**로 이동하고 스크립트 출력의 GitHub 콜백 URL을 붙여넣은 다음 **Update application**을 클릭합니다.

**Google**: Google Cloud Console > **APIs & Services > Credentials**로 이동하고 OAuth 클라이언트를 클릭한 다음, **Authorised redirect URIs** 아래에 스크립트 출력의 Google 콜백 URL을 추가하고 **Save**를 클릭합니다.

---

## 5단계: 에이전트 추가

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

`YOUR_COGNITO_DISCOVERY_URL`과 `YOUR_COGNITO_CLIENT_ID`를 2단계에서 `setup_cognito.py`가 출력한 값으로 바꾸세요.

---

## 6단계: 배포

```bash
agentcore deploy -y
```

---

## 7단계: 배포 후 구성

이제 CLI가 배포 시 JWT 인증을 적용합니다. 다음 배포 후 스크립트를 실행하여 필수 IAM 권한과 토큰 볼트용 KMS 액세스를 연결하고 3LO 흐름의 콜백 URL을 등록합니다.

```bash
cd ..
python configure_inbound_auth.py
```

변경 사항이 전파될 때까지 약 30초 동안 기다립니다.

---

## 8단계: M2M 흐름 테스트

M2M 도구는 client credentials 토큰과 AgentCore Identity의 API 키를 사용하여 [OpenWeatherMap API](https://openweathermap.org/api)를 호출합니다.

이미 [샘플 10](../10-runtime-inbound-outbound-auth/)을 완료했다면 `OutboundApiKey` 자격 증명이 있습니다. 그렇지 않다면 [openweathermap.org](https://home.openweathermap.org/users/sign_up)에서 무료 API 키를 발급받아 추가하세요.

```bash
cd M2MAuthDemo
agentcore add credential --name OutboundApiKey --api-key YOUR_OPENWEATHERMAP_KEY
agentcore deploy -y
cd ..
```

그런 다음 테스트합니다.

```bash
cd ..
python invoke.py --flow m2m
```

예상 출력:

```
=== M2M Flow Test ===

Agent response:
The weather in Seattle is 47F, partly cloudy...
```

M2M 토큰은 client credentials를 사용해 자동으로 가져오므로 브라우저 상호 작용이 필요하지 않습니다.

---

## 9단계: Auth Code(3LO) 흐름 테스트

```bash
python invoke.py --flow authcode
```

**첫 번째 호출** - 동의 URL 반환:

```
=== Auth Code (3LO) Flow Test ===
Starting OAuth2 callback server...

Agent response:
User authorization required. Please visit this URL and grant access:
https://accounts.google.com/o/oauth2/auth?...

After authorizing, invoke the agent again to retrieve your calendar events.

Waiting for you to complete the Google consent flow...
After authorizing in your browser, press Enter to re-invoke the agent.
```

1. URL을 클릭하거나 브라우저에 복사하여 붙여넣습니다.
2. Google로 로그인하고 Calendar 액세스를 허용합니다.
3. `localhost:9090`의 콜백 서버가 리디렉션을 처리하고 `CompleteResourceTokenAuth`를 호출합니다.
4. 다시 호출하려면 **Enter**를 누릅니다.

**두 번째 호출** - 캘린더 이벤트 검색:

```
Agent response:
Calendar events for 2025-03-20:
  - 09:00: Standup
  - 14:00: Design Review
  - 16:30: 1:1 with Manager
```

---

## Streamlit UI(선택 사항)

CLI 대신 브라우저 기반의 대화형 환경을 사용하려면 다음 명령을 실행합니다.

```bash
pip install streamlit
cd ..
streamlit run streamlit_app.py
```

로그인하고 흐름(M2M / GitHub 3LO / Google 3LO)을 선택한 다음 채팅 인터페이스를 사용합니다. 3LO 흐름에서는 앱이 동의 URL과 콜백 서버를 자동으로 처리합니다.

---

## 10단계: 정리

```bash
cd M2MAuthDemo
agentcore remove agent --name MyAgent --force
agentcore remove credential --name M2MProvider --force
agentcore remove credential --name Google3LOProvider --force
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

| 개념 | 세부 정보 |
|:--------|:--------|
| **M2M(client credentials)** | `auth_flow="M2M"` - AgentCore Identity가 클라이언트 ID + 보안 암호를 사용해 토큰 엔드포인트를 직접 호출합니다. 사용자는 관여하지 않습니다. 토큰은 에이전트 인스턴스별로 캐시됩니다. |
| **Auth Code / 3LO** | `auth_flow="USER_FEDERATION"` - 첫 번째 호출에서 `on_auth_url` 콜백을 통해 동의 URL을 반환합니다. 동의 후 AgentCore Identity가 토큰을 저장하고 자동으로 갱신합니다. |
| **Session binding** | `oauth2_callback_server.py`는 에이전트를 호출한 사용자와 OAuth 콜백을 보낸 사용자가 같은지 검증하여 CSRF/세션 고정 공격을 방지합니다. |
| **토큰 저장소** | 모든 토큰은 AgentCore Identity(Secrets Manager 기반)에 저장됩니다. 에이전트 코드는 데코레이터를 통해 메모리에서만 토큰을 받습니다. |
