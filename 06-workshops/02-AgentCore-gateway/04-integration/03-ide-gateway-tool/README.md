# VS Code + AgentCore Gateway: 서버리스 OAuth 프록시

## 개요

이 문서에서는 AWS에 배포된 **serverless OAuth proxy**를 사용해 **Copilot이 포함된 Visual Studio Code**를 **Amazon Bedrock AgentCore Gateway**에 연결하는 방법을 설명합니다. 백엔드 도구로는 사용자 위임 액세스에 **OAuth 2.0 Authorization Code Grant(3LO)**를 사용하는 **Atlassian Confluence**를 사용합니다.

**주요 이점**: 로컬 서버가 필요하지 않습니다. OAuth proxy와 callback handler가 AWS의 API Gateway 뒤에서 Lambda 함수로 실행되므로 개발자는 VS Code를 클라우드 엔드포인트에 직접 연결할 수 있습니다.

**참고**: 이 예제에는 URL elicitation을 추가하는 `MCP-Protocol-Version: 2025-11-25`가 필요합니다. VS Code의 `mcp.json`에서 `headers` 필드를 사용해 구성합니다.

## 아키텍처

![VS Code + AgentCore Gateway 서버리스 OAuth 프록시](generated-diagrams/vscode-agentcore-serverless-proxy.png)

**흐름 요약:**
1. VS Code가 MCP/HTTP를 통해 Amazon API Gateway(퍼블릭 엔드포인트)에 연결합니다.
2. MCP Proxy Lambda가 OAuth 메타데이터 탐색과 callback interception을 처리합니다.
3. 사용자가 브라우저를 통해 Cognito로 인증합니다.
4. Proxy Lambda가 JWT와 함께 인증된 요청을 AgentCore Gateway에 전달합니다.
5. Confluence 액세스가 필요하면 AgentCore Gateway가 3LO elicitation을 반환합니다.
6. 사용자가 브라우저에서 Atlassian OAuth를 통해 동의합니다.
7. Callback Lambda가 authorization code를 수신하고 `CompleteResourceTokenAuth`를 호출합니다.
8. 이제 AgentCore Gateway가 사용자를 대신해 Confluence API를 호출할 수 있습니다(AgentCore Identity가 토큰 캐시).

## 두 가지 OAuth 흐름

| 흐름 | 목적 | 방향 | 시점 |
|------|---------|-----------|------|
| **Inbound Auth** | VS Code를 AgentCore Gateway에 인증 | VS Code → Cognito → AgentCore Gateway | MCP 서버 연결 시 |
| **Outbound Auth (3LO)** | AgentCore Gateway가 사용자를 대신해 Confluence에 액세스 | AgentCore Gateway → Atlassian → 사용자 동의 | 첫 Confluence 도구 호출 시 |

### 토큰 수명 및 동의 유지

**사용자에게 Confluence 동의를 얼마나 자주 요청하나요?**

AgentCore Identity는 3LO 토큰을 자동으로 관리합니다.
- 사용자가 3LO를 완료하면 AgentCore가 access token과 refresh token을 모두 저장합니다.
- 이후 도구 호출에서는 AgentCore가 저장된 토큰을 사용하므로 사용자 상호 작용이 필요하지 않습니다.
- access token이 만료되면 AgentCore가 refresh token을 사용해 자동으로 갱신합니다.

**동의 수명은 AgentCore가 아니라 OAuth provider인 Atlassian에서 제어합니다.**
- Atlassian refresh token은 수명이 깁니다(약 90일 동안 사용하지 않으면 만료).
- 토큰을 주기적으로 사용하는 동안에는 사용자에게 동의를 다시 요청하지 않습니다.
- 다음과 같은 경우 다시 동의해야 합니다. (a) 사용자가 Atlassian 설정에서 액세스를 취소한 경우, (b) 장기간 사용하지 않아 refresh token이 만료된 경우, (c) 앱이 요청하는 scope가 변경된 경우

**`offline_access` scope**(노트북에서 구성)는 refresh token을 활성화합니다. 이 scope가 없으면 access token이 만료될 때마다(일반적으로 1시간) 사용자가 다시 인증해야 합니다.

**참고**: Cognito는 inbound auth(VS Code → AgentCore Gateway)만 처리합니다. Confluence용 3LO 토큰은 AgentCore Identity가 전적으로 관리합니다.

## Serverless Proxy와 Local Proxy 비교

이 예제를 로컬 callback 및 proxy 서버로 배포할 수도 있습니다. 다음 표는 이러한 서버를 AWS 클라우드에 배치했을 때의 이점을 보여줍니다.

| 항목 | Local Proxy(notebook 02) | Serverless Proxy(notebook 03) |
|--------|---------------------------|--------------------------------|
| **설정** | 로컬 Python 서버 2개 실행 | 노트북으로 한 번 배포 |
| **개발자 경험** | 각 세션 전에 서버 시작 | VS Code 구성만 필요 |
| **엔드포인트** | `http://127.0.0.1:8080` | `https://<api-id>.execute-api.<region>.amazonaws.com` |
| **확장성** | 단일 개발자 | 팀 전체 배포 |
| **비용** | 무료(로컬) | 사용량 기반 과금(Lambda + API Gateway) |

## 구성 요소

| 구성 요소 | 목적 |
|-----------|---------|
| **Amazon API Gateway** | VS Code용 퍼블릭 HTTPS 엔드포인트(HTTP API) |
| **MCP Proxy Lambda** | OAuth 메타데이터, callback interception, token proxying, MCP 전달 |
| **Callback Lambda** | 3LO OAuth callback, `CompleteResourceTokenAuth` |
| **Cognito User Pool** | 인바운드 인증용 JWT 토큰 |
| **AgentCore Gateway** | Confluence 대상이 연결된 AWS 관리형 MCP 서버 |

**용어 참고**: 이 아키텍처에서는 서로 다른 두 "Gateway"를 사용합니다.
- **Amazon API Gateway**: Lambda 함수를 퍼블릭 엔드포인트로 노출하는 HTTP API
- **AgentCore Gateway**: 도구 호출을 Confluence로 라우팅하는 AWS 관리형 MCP 서버

## 주요 기술 세부 정보

### Proxy 아키텍처가 필요한 이유

이 솔루션은 VS Code와 AgentCore Gateway 사이의 proxy 계층으로 Amazon API Gateway와 AWS Lambda 함수를 사용합니다. 이 아키텍처가 필요한 이유는 두 가지입니다.

1. **OAuth Authorization Server Facade**: VS Code의 MCP 클라이언트는 MCP 서버 URL의 OAuth 엔드포인트(`/authorize`, `/token`)와 상호 작용할 것으로 예상합니다. AgentCore Gateway는 수신 JWT를 검증하지만 OAuth Authorization Server 역할은 하지 않습니다. MCP Proxy Lambda는 이 facade를 제공하여 OAuth 요청을 Cognito로 proxy하는 동시에 redirect interception과 state 관리를 처리합니다. 또한 `resource` 식별자는 기반 Gateway URL이 아니라 클라이언트가 연결하는 URL(proxy URL)과 일치해야 하므로, proxy는 자체 RFC 9728 Protected Resource Metadata(`/.well-known/oauth-protected-resource`)도 제공합니다.

2. **Session Binding을 사용한 3LO Callback 처리**: 사용자가 3LO 동의(예: Confluence 액세스 허용)를 완료하면 OAuth callback을 수신하고 사용자의 identity와 함께 `CompleteResourceTokenAuth` API를 호출해 토큰을 바인딩해야 합니다. Callback Lambda가 이 흐름을 처리합니다. 현재 AgentCore Gateway는 관리형 3LO callback 엔드포인트를 기본 지원하지 않으므로, 이 Lambda가 callback 처리와 session binding을 제공합니다.

### MCP-Protocol-Version Header

3LO elicitation에는 `MCP-Protocol-Version: 2025-11-25` header가 필요합니다. VS Code의 `mcp.json`에서 다음과 같이 구성합니다.

```json
{
  "servers": {
    "agentcore-confluence": {
      "type": "http",
      "url": "https://<api-gateway-url>",
      "headers": {
        "MCP-Protocol-Version": "2025-11-25"
      }
    }
  }
}
```

### 3LO Elicitation 응답

도구에 사용자의 OAuth 동의가 필요하면 Gateway는 오류 코드 `-32042`를 반환합니다.

```json
{
  "error": {
    "code": -32042,
    "message": "This request requires more information.",
    "data": {
      "elicitations": [{
        "mode": "url",
        "elicitationId": "...",
        "url": "https://bedrock-agentcore.us-west-2.amazonaws.com/identities/oauth2/authorize?...",
        "message": "Please login to this URL for authorization."
      }]
    }
  }
}
```

## 설정

### 사전 요구 사항
- Python 3.10+
- Lambda, API Gateway, Cognito, IAM, Bedrock AgentCore 권한이 구성된 AWS 자격 증명
- Confluence를 사용할 수 있는 Atlassian Cloud 계정
- GitHub Copilot이 포함된 VS Code 1.107 이상 - 이 버전부터 3LO URL elicitation 지원

### 1단계: Atlassian OAuth App 생성
1. https://developer.atlassian.com/console/myapps/ 로 이동합니다.
2. Create → OAuth 2.0 integration을 선택합니다.
3. **Permissions**에서 Confluence용 **granular scope**를 추가합니다.
   - `read:space:confluence`
   - `read:page:confluence`
4. Client ID와 Client Secret을 복사합니다.
5. 노트북 실행 후 표시되는 AgentCore callback URL을 추가합니다.

**참고**: refresh token용 `offline_access` scope는 표준 OAuth scope이므로 콘솔에서 구성하지 않습니다. AgentCore가 권한 부여 요청을 보낼 때 자동으로 요청합니다.

### 2단계: 설정 노트북 실행

`01_vscode_agentcore_confluence_serverless.ipynb`를 실행하여 다음을 생성합니다.
- Lambda 통합이 구성된 API Gateway
- MCP Proxy Lambda 함수
- Callback Lambda 함수
- app client가 구성된 Cognito User Pool
- Cognito JWT auth가 구성된 AgentCore Gateway
- Atlassian credential provider
- 3LO OAuth가 구성된 Confluence 대상

노트북은 API Gateway URL과 VS Code 구성을 출력합니다.

### 3단계: VS Code 구성

노트북 출력의 값을 사용해 `.vscode/mcp.json`에 다음 내용을 추가합니다.

```json
{
  "servers": {
    "agentcore-confluence": {
      "type": "http",
      "url": "https://<api-gateway-id>.execute-api.<region>.amazonaws.com",
      "headers": {
        "MCP-Protocol-Version": "2025-11-25"
      }
    }
  }
}
```

### 4단계: 연결 및 사용
1. VS Code를 다시 로드합니다.
2. 메시지가 표시되면 Cognito OAuth를 완료합니다(user: `vscode-user`, password: `TempPassword123!`).
3. Confluence 도구를 사용합니다. 처음 사용할 때 3LO 동의가 시작됩니다.
4. Atlassian 동의를 허용한 후 도구 호출을 다시 시도합니다.

## 문제 해결

### "Cannot initiate authorization code grant flow"
**원인**: Gateway가 `MCP-Protocol-Version: 2025-11-25` header를 수신하지 못했습니다.
**해결 방법**: mcp.json 구성에 `"headers": {"MCP-Protocol-Version": "2025-11-25"}`를 추가합니다.

### "Client is not enabled for OAuth2.0 flows"
**원인**: Cognito app client에 `AllowedOAuthFlowsUserPoolClient=True`가 없습니다.
**해결 방법**: 노트북을 다시 실행하여 리소스를 다시 생성합니다.

### Cognito의 "redirect_mismatch"
**원인**: Callback URL이 Cognito에 등록되지 않았습니다.
**해결 방법**: API Gateway callback URL이 등록되어 있는지 확인합니다. 필요한 경우 노트북을 다시 실행합니다.

### Lambda timeout 오류
**원인**: MCP 전달 중 Lambda 함수의 제한 시간이 초과되었습니다.
**해결 방법**: AWS 콘솔에서 Lambda 제한 시간을 늘리거나 더 긴 제한 시간으로 다시 배포합니다.

### 3LO를 완료했지만 도구가 계속 실패하는 경우
**원인**: VS Code는 3LO 완료 후 자동으로 다시 시도하지 않습니다.
**해결 방법**: 브라우저에서 3LO 흐름을 완료한 후 도구를 다시 호출합니다.

## 파일

| 파일 | 설명 |
|------|-------------|
| `01_vscode_agentcore_confluence_serverless.ipynb` | Serverless 배포용 설정 노트북 |
| `lambda/mcp_proxy_lambda.py` | MCP Proxy Lambda 소스 코드 |
| `lambda/callback_lambda.py` | 3LO Callback Lambda 소스 코드 |

## 정리

노트북 끝의 cleanup 셀을 실행하거나, 새 노트북 실행에서 Step 1b를 실행하여 다음을 삭제합니다.
- API Gateway
- Lambda 함수
- AgentCore Gateway 및 대상
- Credential provider
- Cognito User Pool
- IAM 역할

## 참고 자료

- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [VS Code MCP 문서](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
- [AgentCore Gateway 문서](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AWS Lambda 문서](https://docs.aws.amazon.com/lambda/)
- [Amazon API Gateway 문서](https://docs.aws.amazon.com/apigateway/)
- [Confluence REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/)
