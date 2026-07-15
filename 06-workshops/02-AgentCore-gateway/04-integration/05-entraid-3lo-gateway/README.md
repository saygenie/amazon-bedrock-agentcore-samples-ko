# EntraID 인증을 사용하는 AgentCore MCP Gateway

EntraID 인바운드 인증과 다운스트림 API에 대한 사용자 위임 액세스용 아웃바운드 3LO(three-legged OAuth)를 사용하는 AgentCore MCP Gateway의 자동 설정 예제입니다. 액세스를 미리 승인할 수 있는 브라우저 기반 auth onboarding SPA가 포함되어 있습니다.

## 사전 요구 사항

- 대상 계정의 자격 증명으로 구성된 AWS CLI v2
- Azure CLI(`az`): `brew install azure-cli`(macOS) 또는 [설치 가이드](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- Node.js 18+ 및 npm
- CDK CLI: `npm install -g aws-cdk`
- `jq` 설치
- Microsoft Entra ID tenant(CIAM/External ID 또는 standard)에 대한 액세스

## 빠른 시작(자동화)

설정 스크립트는 EntraID app 등록, OAuth credential provider, CDK 배포, redirect URI 연결, OpenAPI 사양 구성 등 모든 작업을 자동화하고 이후 재배포에 사용할 env 파일을 생성합니다.

### 1. 두 클라우드에 로그인

```bash
# Azure - EntraID 관리자 계정 사용
az login --tenant <your-tenant-id> --allow-no-subscriptions

# AWS - 자격 증명이 구성되어 있는지 확인
export CDK_DEFAULT_ACCOUNT=<your-aws-account-id>
export CDK_DEFAULT_REGION=<your-region>
```

> `--allow-no-subscriptions`는 Azure 구독이 없는 CIAM 전용 tenant에 필요합니다.

### 2. 설정 스크립트 실행

CIAM(External ID) tenant의 경우:
```bash
cd 05-entraid-3lo-gateway
./scripts/setup.sh \
  --tenant-id <your-tenant-id> \
  --tenant-type ciam \
  --ciam-domain <your-ciam-domain> \
  --region <aws-region> \
  --stack-name <stack-name>
```

standard EntraID tenant의 경우:
```bash
cd 05-entraid-3lo-gateway
./scripts/setup.sh \
  --tenant-id <your-tenant-id> \
  --tenant-type standard \
  --region <aws-region> \
  --stack-name <stack-name>
```

스크립트는 다음 작업을 수행합니다.
1. Graph API를 통해 EntraID에 App A(SPA, public client)와 App B(Web, confidential client)를 생성합니다.
2. `gateway.access` 및 `weather.read` scope를 노출합니다.
3. AgentCore에 OAuth credential provider를 생성합니다.
4. App B에 credential provider callback URL을 등록합니다.
5. CDK 스택을 배포합니다.
6. App A에 API Gateway redirect URI를 등록합니다.
7. workload identity return URL을 업데이트합니다.
8. 실제 API 엔드포인트로 OpenAPI 사양을 업데이트하고 다시 배포합니다.
9. `redeploy-cdk.sh`에서 사용할 `.env.<StackName>`을 생성합니다.

### 3. 테스트

설정 마지막에 출력되는 auth onboarding URL을 엽니다.
```
https://<api-endpoint>/auth
```

## 개발 중 재배포

최초 설정 후 Lambda 코드, CDK 스택 변경 사항 또는 OpenAPI 사양 업데이트를 반복 적용할 때는 `redeploy-cdk.sh`를 사용합니다. 이 스크립트는 설정 과정에서 생성된 `.env.<StackName>` 파일을 읽고 올바른 모든 context 변수와 함께 `cdk deploy`를 실행합니다.

```bash
# env 파일이 하나뿐이면 자동 감지
./scripts/redeploy-cdk.sh

# 또는 명시적으로 지정
./scripts/redeploy-cdk.sh .env.MyStack
```

코드 변경 시 전체 설정 스크립트를 다시 실행할 필요가 없습니다.

## 여러 배포

테스트 등의 목적으로 두 번째 독립 인스턴스를 배포하려면 `--suffix`를 추가합니다.

```bash
./scripts/setup.sh \
  --tenant-id <tenant-id> \
  --tenant-type ciam \
  --ciam-domain <domain> \
  --region eu-west-1 \
  --stack-name MySecondStack \
  --suffix v2
```

suffix는 IAM 역할, API Gateway, Gateway, credential provider의 리소스 이름을 고유하게 만듭니다. 동일한 tenant에 OIDC provider가 이미 있으면 자동으로 재사용하며, 새 App A client ID를 해당 audience 목록에 추가합니다.

---

## Tenant 유형

이 솔루션은 다음 두 EntraID tenant 유형을 지원합니다.

| 유형 | Authority Host | 사용 시점 |
|------|---------------|-------------|
| `ciam` | `<domain>.ciamlogin.com` | External ID / CIAM tenant |
| `standard` | `login.microsoftonline.com` | 일반 EntraID(workforce) tenant |

CIAM tenant에서는 `--ciam-domain`(`.ciamlogin.com` 앞의 하위 도메인)을 제공해야 합니다.

핵심 차이점은 CIAM tenant가 discovery/token 엔드포인트에 `ciamlogin.com`을 사용한다는 것입니다. 잘못된 host를 사용하면 AgentCore가 잘못된 token endpoint에서 authorization code를 교환하려고 하므로 `authorizationCode must not be null` 오류가 발생합니다.

---

## 데모 사용자 생성

```bash
./scripts/create-demo-user.sh \
  --tenant-id <tenant-id> \
  --domain <tenant-domain> \
  <username> [password]
```

설정 스크립트는 tenant-id와 domain이 미리 입력된, 바로 복사할 수 있는 명령을 출력합니다.

스크립트는 `az login` 자격 증명을 사용하며 application permission은 필요하지 않습니다. 로그인한 계정에 User Administrator 또는 Global Admin 역할이 있어야 합니다.

---

## Auth 흐름 테스트

### Auth Onboarding(브라우저)

1. 시크릿 창에서 `https://<api-endpoint>/auth`를 엽니다.
2. Microsoft(EntraID)로 로그인합니다.
3. SPA가 `_meta.rawElicitation`과 함께 `tools/call`을 호출합니다. 아직 권한이 부여되지 않았다면 "Authorization needed"가 표시됩니다.
4. "Authorize" 클릭 → EntraID 동의 페이지 → 수락 순서로 진행합니다.
5. Callback 페이지가 브라우저에서 SigV4를 통해 `CompleteResourceTokenAuth`를 호출합니다.
6. "Authorization Successful"이 표시됩니다.

### VS Code MCP

`.vscode/mcp.json`에 추가합니다.
```json
{
  "servers": {
    "agentcore-weather-entraid": {
      "type": "http",
      "url": "https://<api-endpoint>/mcp"
    }
  }
}
```

사용자가 권한을 부여하기 전에 도구를 호출하면 response interceptor가 elicitation을 auth onboarding SPA로 안내하는 친숙한 메시지로 재작성합니다. SPA를 통해 권한을 부여한 후에는 elicitation 없이 도구 호출이 작동합니다.

---

## 응답 Interceptor

Gateway에는 elicitation 응답(-32042)을 처리하는 response interceptor Lambda가 있습니다.

- VS Code의 경우: VS Code가 3LO 동의 redirect를 처리할 수 없으므로 elicitation을 "auth onboarding app을 방문하세요"라는 친숙한 메시지로 재작성합니다.
- auth onboarding SPA의 경우: SPA가 authorization URL을 추출하고 동의 흐름을 진행할 수 있도록 원시 elicitation을 그대로 전달합니다.

SPA는 JSON-RPC 요청에 `_meta: { rawElicitation: true }`를 포함하여 의도를 전달합니다. interceptor는 이 flag를 확인하고 재작성을 건너뜁니다.

interceptor는 다음과 같은 Gateway 특이 동작도 처리합니다.
- 202 notification 응답의 `body: null` → 빈 dict 반환
- JSON 문자열인 `body` → 반환하기 전에 dict로 다시 파싱

---

## 설정 스크립트가 생성하는 항목

### EntraID에서

| 리소스 | 목적 |
|----------|---------|
| App A(SPA, public client) | VS Code와 auth onboarding SPA가 공유하는 identity. `gateway.access` scope 노출. |
| App B(Web, confidential client) | 다운스트림 resource server. `weather.read` scope 노출. Client secret은 AgentCore에 저장. |

### AWS에서

| 리소스 | 목적 |
|----------|---------|
| API Gateway HTTP API | proxy, weather API, auth SPA용 퍼블릭 엔드포인트 |
| Proxy Lambda | OAuth intermediary, MCP proxy, SPA HTML 제공 |
| Weather API Lambda | mock 날씨 데이터 엔드포인트 |
| Elicitation Interceptor Lambda | VS Code용 elicitation 재작성, SPA에는 그대로 전달 |
| AgentCore Gateway | MCP 프로토콜 처리, custom JWT auth, 도구 라우팅 |
| Gateway Target(weather-api) | 3LO credential provider가 구성된 OpenAPI target |
| OAuth Credential Provider | App B client 자격 증명 저장 및 token exchange 처리 |
| IAM OIDC Provider | EntraID JWT를 사용한 STS federation 활성화 |
| IAM Role(auth-onboarding-web-role) | AgentCore API 호출을 위한 브라우저 임시 자격 증명 |

### 생성되는 파일

| 파일 | 목적 |
|------|---------|
| `.env.<StackName>` | `redeploy-cdk.sh`용 CDK context 변수 |
| `openapi/weather-api-<StackName>.json` | 배포별 OpenAPI 사양 |

---

## 문제 해결

### `authorizationCode failed to satisfy constraint: Member must not be null`

credential provider가 잘못된 discovery URL을 사용하고 있습니다. CIAM tenant에는 `login.microsoftonline.com`이 아니라 `ciamlogin.com`이 필요합니다. `--tenant-type ciam`으로 다시 생성합니다.

### Gateway의 `Invalid Bearer token`

Gateway authorizer는 `allowedAudience`만 사용하고 `allowedClients`는 사용하지 않습니다. EntraID v2.0 토큰은 client ID에 `client_id`가 아니라 `azp`를 사용합니다. AgentCore는 EntraID 토큰에 없는 `client_id`를 기준으로 `allowedClients`를 검증합니다.

### callback 페이지의 `Incorrect token audience`

IAM OIDC provider의 audience 목록에 이 배포의 App A client ID가 없습니다. 병렬 배포에서는 설정 스크립트가 이를 자동으로 처리하지만 OIDC provider를 수동으로 생성했다면 client ID를 추가합니다: `aws iam add-client-id-to-open-id-connect-provider`.

### `InterceptorException - Received invalid response from interceptor`

interceptor가 Gateway에서 파싱할 수 없는 응답을 반환했습니다. 일반적인 원인은 `body`가 `null`이거나(빈 응답은 `{}`여야 함), `body`가 dict가 아닌 JSON 문자열인 경우입니다.

### 토큰 교환 중 `AADSTS9010010`

proxy Lambda는 token 요청에서 `resource` 파라미터를 제거합니다. EntraID v2.0은 resource가 아닌 scope를 사용합니다. VS Code는 RFC 9728에 따라 `resource`를 전송하지만 EntraID는 이를 거부합니다.

### `AADSTS9002327: Tokens issued for the 'Single-Page Application' client-type may only be redeemed via cross-origin requests`

proxy Lambda는 EntraID의 token endpoint를 호출할 때 `Origin` header를 추가합니다. SPA(public client)의 token redemption에 필요합니다.

### `tools/list`는 작동하지만 `tools/call`이 elicitation을 시작하는 경우

예상된 동작입니다. `tools/list`에는 다운스트림 토큰이 필요하지 않습니다. `tools/call`만 Gateway가 weather token을 가져오도록 하며, 토큰이 없으면 elicitation을 시작합니다.

### Callback 페이지에 "Missing session data"가 표시되는 경우

`sessionStorage`에서 JWT를 찾지 못했습니다. `/auth`에서 흐름을 다시 시작합니다.

### CDK 배포 중 OIDC provider의 `EntityAlreadyExistsException`

IAM OIDC provider는 계정의 issuer URL마다 고유합니다. 동일한 tenant에 여러 스택을 배포하면 설정 스크립트가 기존 provider를 자동으로 감지하여 재사용합니다.

### 재배포 후 VS Code MCP 서버 연결에서 auth 오류가 발생하는 경우

이전 세션에서 누적된 inbound auth 자격 증명으로 인해 stale state 오류가 발생할 수 있습니다. command palette(`F1` 또는 `⇧⌘P`)를 열고 "Remove Dynamic Authentication Providers"를 실행하여 자격 증명을 지운 다음 다시 연결합니다.

---

## 아키텍처 참고 자료

모든 흐름의 상세 sequence diagram은 [out-of-band 아웃바운드 인증](./docs/out-of-band-outbound-auth.md)을 참조하세요.
