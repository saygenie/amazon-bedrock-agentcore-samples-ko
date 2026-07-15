# Entra ID 설정

이 문서에서는 샘플에 필요한 두 개의 Microsoft Entra ID 앱을 등록하는 과정을 안내합니다. 단순히 클릭할 항목뿐 아니라 각 단계가 **필요한 이유**도 설명하므로 노트북의 사전 요구 사항 섹션보다 내용이 많습니다.

간단한 절차만 필요하다면 노트북의 사전 요구 사항 셀 한 페이지에서 모든 내용을 확인할 수 있습니다. 문제가 발생하거나 각 설정의 역할을 이해하려면 이 문서를 사용하세요.

---

## 전체 구성

**두 개**의 Entra 앱을 등록합니다.

1. **`AgentCore - Agent`** - 사용자가 로그인하는 앱으로, OBO를 수행하여 Graph 토큰을 가져오고 M2M으로 MCP 서버에도 인증합니다. 하나의 앱이 세 가지 역할을 수행합니다.
2. **`AgentCore - MCP Server`** - 앱 ID가 MCP 서버에서 M2M 토큰의 예상 대상이 되는 앱입니다. 보안 암호를 포함하지 않으며 로그인에 사용되지 않습니다.

Agent 앱은 로그인, OBO 토큰 교환 및 MCP 서버에 대한 M2M 인증을 처리합니다. MCP Server 앱은 MCP 권한 부여자가 검증할 고유한 대상(`api://<MCP_CLIENT_ID>`)과 앱 역할(`mcp_invoke`)을 제공하는 별도의 리소스 ID입니다. Microsoft의 OBO 문서에서는 로그인과 중간 계층 역할에 단일 앱을 사용하는 방식을 권장합니다([*"Use of a single application"*](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow#use-of-a-single-application) 참조).

---

## 사전 요구 사항

- **tenant admin** 또는 **Application Administrator + Cloud Application Administrator** 권한으로 [https://entra.microsoft.com](https://entra.microsoft.com)에 로그인합니다. 이 과정에서 관리자 동의를 두 번 부여합니다.
- Authentication 블레이드에 Preview UI가 표시되면 먼저 클래식 UI로 전환합니다. 상단 근처에서 *"To switch to the old experience, please click here"* 배너 링크를 찾으세요.
- Entra 관리 센터의 **Overview** 페이지에서 **Tenant ID**를 기록합니다. 노트북의 `ENTRA_TENANT_ID`에 해당합니다.

총 소요 시간: 10~20분

---

## 1부 - Agent 앱 등록

### 1.1 앱 생성

1. 왼쪽 탐색 메뉴: **Applications → App registrations**
2. 상단의 **+ New registration** 클릭
3. 다음 항목 입력:
   - **Name**: `AgentCore - Agent`
   - **Supported account types**: **Accounts in this organizational directory only (Single tenant)**
   - **Redirect URI**: 비워 둠
4. **Register** 클릭

표시되는 Overview 페이지에서 **Application (client) ID**를 복사합니다. 이 값이 `ENTRA_AGENT_CLIENT_ID`입니다.

### 1.2 Authentication - 디바이스 코드 흐름 활성화

**이유**: 노트북은 MSAL의 디바이스 코드 흐름("go to aka.ms/devicelogin and enter code XXXXX" 패턴)을 통해 사용자를 인증합니다. Microsoft는 디바이스 코드 흐름을 **public client** 흐름으로 분류하며, 앱에 특정 리디렉션 URI(`https://login.microsoftonline.com/common/oauth2/nativeclient`)를 등록해야 합니다. 또한 앱 등록이 이 흐름의 유효한 대상임을 나타내도록 "Allow public client flows"를 활성화해야 합니다.

1. 앱의 왼쪽 탐색 메뉴: **Authentication**
2. **Platform configurations** 아래에서 **+ Add a platform** 클릭
3. 열리는 패널에서 **Mobile and desktop applications** 타일 클릭(설명에 Windows, UWP, Console, IoT, Classic iOS + Android가 언급된 타일). iOS/macOS나 Android를 선택하지 마세요. 해당 항목은 특정 SDK로 빌드된 앱용이며 여기에는 없는 번들 ID가 필요합니다.
4. 다음 패널에서 `https://login.microsoftonline.com/common/oauth2/nativeclient` 옆의 확인란 선택. 다른 항목은 선택하지 않음
5. **Configure** 클릭
6. 기본 Authentication 페이지로 돌아가 **Advanced settings**까지 아래로 스크롤
7. **Allow public client flows**를 찾아 토글을 **Yes**로 전환
8. 상단의 **Save** 클릭

### 1.3 Certificates & secrets - 클라이언트 보안 암호 생성

**이유**: 이 앱은 디바이스 코드 로그인을 위한 public-client 흐름을 허용하지만, OBO를 수행할 때는 *confidential client* 역할도 합니다. Confidential client는 클라이언트 보안 암호 또는 인증서로 Microsoft에 인증합니다. AgentCore가 에이전트를 대신해 OBO 교환을 수행할 수 있도록 노트북의 AgentCore Identity 자격 증명 공급자에 보안 암호를 구성합니다.

1. 왼쪽 탐색 메뉴: **Certificates & secrets**
2. **Client secrets** 탭에서 **+ New client secret** 클릭
3. 다음 항목 입력:
   - **Description**: `AgentCore OBO sample secret`
   - **Expires**: 조직 정책에서 허용하는 기간. 샘플에는 6개월 또는 12개월이면 충분
4. **Add** 클릭
5. **Value** 열이 있는 새 행이 표시됩니다. **지금 Value를 복사하세요**. 이 값이 `ENTRA_AGENT_CLIENT_SECRET`입니다. 페이지를 벗어나면 Entra가 값을 영구적으로 마스킹하므로 복사하지 못한 경우 이 보안 암호를 삭제하고 새로 생성해야 합니다.

### 1.4 Expose an API - Application ID URI 및 위임 scope

**이유**: 이 앱에 발급된 토큰이 안정적인 대상 값을 갖도록 Application ID URI가 필요합니다. 아래에 노출하는 scope는 로그인 성공에 필요하며, 없으면 `AADSTS65002` 오류와 함께 로그인에 실패합니다.

1. 왼쪽 탐색 메뉴: **Expose an API**
2. **Application ID URI** 옆의 **Add** 또는 **Set** 클릭. Entra가 제안하는 `api://<client-id>`를 확인하고 **Save** 클릭
3. **Scopes defined by this API** 아래에서 **+ Add a scope**를 클릭하고 다음 항목 입력:
   - **Scope name**: `user_delegation`
   - **Who can consent**: **Admins and users**
   - **Admin consent display name**: `Delegate to the agent on the signed-in user's behalf`
   - **Admin consent description**: `Allows the agent to call downstream APIs such as Microsoft Graph on behalf of the signed-in user, via Microsoft's OAuth 2.0 On-Behalf-Of flow.`
   - **User consent display name**: `Let the agent act on your behalf`
   - **User consent description**: `Allows the agent to read your profile on your behalf.`
   - **State**: **Enabled**
4. **Add scope** 클릭

이제 State = Enabled인 `api://<AGENT_CLIENT_ID>/user_delegation` 행이 표시되어야 합니다.

### 1.5 API permissions - Microsoft Graph 위임 권한

**이유**: OBO 교환에서 Graph 토큰을 생성하려면 먼저 Agent 앱에 위임된 Graph 권한을 부여해야 합니다. 사용자가 로그인할 때 동의하면 Entra가 이 권한을 동의 요청에 포함하므로 사용자가 에이전트에 자신을 대신하여 Graph를 사용할 권한을 부여하게 됩니다. 사용자마다 개별적으로 요청하지 않도록 여기에서 관리자 동의를 부여합니다.

1. 왼쪽 탐색 메뉴: **API permissions**
2. **+ Add a permission** 클릭
3. **Microsoft Graph** 클릭
4. **Delegated permissions** 클릭
5. 검색 상자에 `User.Read`를 입력하고 옆의 확인란 선택
6. 하단의 **Add permissions** 클릭
7. API permissions 목록으로 돌아가 `User.Read`가 **"Not granted for \<tenant\>"** 상태로 표시되는지 확인
8. 목록 상단 근처의 **Grant admin consent for \<tenant\>** 클릭 후 확인

계속하기 전에 행이 녹색 확인 표시와 함께 **"Granted for \<tenant\>"** 상태로 바뀌어야 합니다. 버튼이 비활성화되어 있다면 관리자 권한이 필요하므로 테넌트 관리자에게 이 단계를 요청하세요.

### 1.6 API permissions - MCP Server 앱(2부 후에 다시 진행)

Agent 앱에는 자신으로서 MCP 서버를 호출하는 M2M 권한도 필요합니다. 이 권한은 아직 생성되지 않은 MCP Server 앱에 정의됩니다. **2부로 이동**한 다음 여기로 돌아오세요.

---

## 2부 - MCP Server 앱 등록

이 앱의 역할은 MCP 서버의 권한 부여자가 검증할 대상과 앱 역할을 정의하는 것입니다. 보안 암호, 로그인 또는 scope는 없습니다.

### 2.1 앱 생성

1. 왼쪽 탐색 메뉴에서 **Applications → App registrations**로 이동하고 **+ New registration** 클릭
2. 다음 항목 입력:
   - **Name**: `AgentCore - MCP Server`
   - **Supported account types**: **Accounts in this organizational directory only (Single tenant)**
   - **Redirect URI**: 비워 둠
3. **Register** 클릭

Overview에서 **Application (client) ID**를 복사합니다. 이 값이 `ENTRA_MCP_CLIENT_ID`입니다.

### 2.2 Expose an API - Application ID URI만 설정

**이유**: 에이전트가 MCP 서버로 보낼 M2M 토큰에 안정적인 대상 값이 필요합니다. MCP 서버의 `customJWTAuthorizer`는 `aud = "api://<MCP_CLIENT_ID>"`를 검증합니다. scope가 아닌 **앱 역할**을 통해 권한을 부여하므로 scope는 필요하지 않습니다.

1. 왼쪽 탐색 메뉴: **Expose an API**
2. **Application ID URI** 옆의 **Add**를 클릭하고 제안된 `api://<client-id>`를 수락한 다음 **Save** 클릭

여기에는 의도적으로 scope를 추가하지 않습니다.

### 2.3 App roles - `mcp_invoke` 정의

**이유**: Agent 앱이 client-credentials(M2M) 토큰으로 MCP 서버를 호출할 때는 사용자가 관여하지 않으므로 해당 토큰의 권한 부여 claim이 `scp`가 아니라 `roles`입니다. MCP 서버의 `customJWTAuthorizer`는 `roles` claim에서 `mcp_invoke` 문자열을 찾습니다. 여기에서 역할을 정의하고 3부에서 부여합니다.

1. 왼쪽 탐색 메뉴: **App roles**
2. **+ Create app role** 클릭
3. 다음 항목 입력:
   - **Display name**: `Invoke MCP Server`
   - **Allowed member types**: **Applications**(중요: Users/Groups가 아닌 앱 전용 역할)
   - **Value**: `mcp_invoke`
   - **Description**: `Apps that can invoke tools on this MCP Server.`
   - **Do you want to enable this app role?**: 선택
4. **Apply** 클릭

---

## 3부 - Agent 앱에서 1.6단계 완료

이제 `mcp_invoke` 역할이 있는 MCP Server 앱을 생성했으므로 Agent 앱으로 돌아가 해당 역할을 부여합니다.

1. 왼쪽 탐색 메뉴에서 **Applications → App registrations**로 이동하고 **AgentCore - Agent** 선택
2. 왼쪽 탐색 메뉴: **API permissions**
3. **+ Add a permission** 클릭
4. **APIs my organization uses** 탭 클릭
5. `AgentCore - MCP Server`를 검색하고 결과에서 클릭
6. **Application permissions** 선택(Delegated가 아님. M2M용 권한)
7. `mcp_invoke` 선택
8. **Add permissions** 클릭

API permissions 목록으로 돌아오면 다음 두 행이 표시되어야 합니다.

| 권한 | 유형 | 상태 |
|---|---|---|
| `User.Read` (Microsoft Graph) | Delegated | Granted for \<tenant\> |
| `mcp_invoke` (AgentCore - MCP Server) | Application | Not granted for \<tenant\> |

9. **Grant admin consent for \<tenant\>**를 클릭하고 확인합니다.

계속하기 전에 두 행 모두 녹색 확인 표시가 있어야 합니다.

---

## 4부 - 네 가지 값 수집

| 환경 변수 | 출처 |
|---|---|
| `ENTRA_TENANT_ID` | Entra admin center → Overview → **Tenant ID** |
| `ENTRA_AGENT_CLIENT_ID` | Agent app → Overview → **Application (client) ID** |
| `ENTRA_AGENT_CLIENT_SECRET` | 1.3단계에서 복사한 보안 암호 값 |
| `ENTRA_MCP_CLIENT_ID` | MCP Server app → Overview → **Application (client) ID** |

이 네 가지 값을 노트북의 **Step 2** 셀에 입력합니다.

---

## 실행 시 구성 요소가 연동되는 방식

- 사용자가 MSAL 디바이스 코드 흐름을 통해 Agent 앱에 로그인합니다. Entra가 사용자 JWT를 발급합니다.
- AgentCore Runtime이 JWT를 검증하고 에이전트 요청을 전달합니다. 에이전트가 `ON_BEHALF_OF_TOKEN_EXCHANGE`와 함께 `GetResourceOauth2Token`을 호출하면 AgentCore Identity가 에이전트를 대신하여 사용자 JWT를 Microsoft Graph 위임 토큰으로 교환합니다.
- 이와 별도로 AgentCore Identity는 MCP Server 앱을 대상으로 하고 `mcp_invoke` 역할을 포함하는 에이전트용 M2M 토큰(동일한 Agent 앱에 대한 client_credentials)을 가져옵니다.
- 에이전트는 `Authorization`의 M2M 토큰과 사용자 지정 요청 헤더의 Graph 위임 토큰을 사용해 MCP 서버를 호출합니다. MCP 서버의 권한 부여자는 대상과 역할을 기준으로 M2M 토큰을 수락하고, 도구는 위임 토큰을 사용해 Graph를 호출합니다.

---

## 앱 매니페스트를 통한 점검

실행 중 문제가 발생하면 각 앱의 **Manifest**(왼쪽 탐색 메뉴)를 열고 다음 사항을 확인하세요.

**Agent 앱:**
- `"allowPublicClient": true`
- `"identifierUris": ["api://<AGENT_CLIENT_ID>"]`
- `"oauth2Permissions"`에 `"value": "user_delegation"` 및 `"isEnabled": true`인 항목이 하나 있음
- `"requiredResourceAccess"`에 `User.Read` scope ID가 포함된 Microsoft Graph(resource appId `00000003-0000-0000-c000-000000000000`) 항목 하나와 `mcp_invoke` 역할 ID가 포함된 MCP Server 앱 항목 하나가 있음

**MCP Server 앱:**
- `"identifierUris": ["api://<MCP_CLIENT_ID>"]`
- `"appRoles"`에 `"value": "mcp_invoke"` 및 `"allowedMemberTypes": ["Application"]`인 항목이 하나 있음
- `"oauth2Permissions"` 아래에 항목이 없음(scope를 의도적으로 추가하지 않음)

---

## 일반적인 오류 및 해결 방법

| 증상 | 가능성이 가장 높은 원인 | 해결 방법 |
|---|---|---|
| 로그인: `AADSTS65002: Resource for this token request is not a valid scope` | Application ID URI가 설정되지 않았거나 `user_delegation` scope가 없거나 비활성화됨 | 1.4단계 다시 수행 |
| 로그인: `AADSTS500011: resource principal does not exist` | Application ID URI가 설정되지 않았거나 사용자가 다른 테넌트에 속함 | 1.4단계가 저장되었는지 확인하고 `ENTRA_TENANT_ID` 확인 |
| 로그인 시 디바이스 코드에서 중단되고 진행되지 않음 | "Allow public client flows"가 **No**이거나 `nativeclient` URI가 없음 | 1.2단계 다시 수행 |
| 에이전트가 권한 부여자에서 401 반환 | Agent 앱의 `allowedAudience`는 `api://` 접두사가 없는 GUID `<ENTRA_AGENT_CLIENT_ID>`여야 함 | 노트북에서 에이전트의 `configure()` 호출 확인 |
| OBO: `AADSTS500131: Assertion audience does not match the Client app` | MSAL scope가 `aud = <ENTRA_AGENT_CLIENT_ID>`인 JWT를 생성해야 함 | MSAL 로그인 셀 확인 |
| 로그인: `AADSTS90009: Application is requesting a token for itself. This scenario is supported only if resource is specified using the GUID based App Identifier.` | MSAL scope는 `api://`가 아니라 GUID 형식 `<ENTRA_AGENT_CLIENT_ID>/.default`를 사용해야 함 | MSAL 로그인 셀 확인 |
| OBO: `AADSTS65001: user or administrator has not consented` | Graph 위임 권한이 있지만 관리자 동의를 부여하지 않음 | 1.5단계에서 관리자 동의 다시 수행 |
| MCP에서 401을 반환하거나 에이전트가 도구를 사용할 수 없다고 응답 | M2M 토큰에 `roles` claim이 없음. `mcp_invoke`의 Allowed member types가 잘못되었거나(**Applications**여야 함) 관리자 동의를 부여하지 않음 | 2.3단계 및 3부의 동의 확인 |

---

## 참고 자료

- [Microsoft identity platform - OAuth 2.0 On-Behalf-Of 흐름](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)
- [Microsoft identity platform - 단일 애플리케이션 사용(OBO 단순화)](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow#use-of-a-single-application)
- [Amazon Bedrock AgentCore - On-behalf-of 토큰 교환](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/on-behalf-of-token-exchange.html)
