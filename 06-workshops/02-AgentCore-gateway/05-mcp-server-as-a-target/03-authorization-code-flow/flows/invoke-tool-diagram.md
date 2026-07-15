```mermaid
sequenceDiagram
    participant User as Gateway 사용자
    participant Gateway as AgentCore Gateway
    participant Cred as AgentCore Identity Credential Provider
    participant IdP as OAuth 2.0 권한 부여 서버
    participant MCP as MCP Server (대상)

    Note over User, MCP: List tools(인증 불필요 - 캐시에서 제공)
    User->>Gateway: list/tools<br/>Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
    Gateway-->>User: 캐시된 도구 정의

    Note over User, MCP: Invoke tool(특정 MCP server에 대한 OAuth 흐름 시작)
    User->>Gateway: MCP server에서 Invoke tool<br/>Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
    Gateway->>Cred: workload identity 및 JWT로<br/>workload access token 가져오기
    Cred-->>Gateway: workload access token 반환
    Gateway->>Cred: workload access token으로<br/>GitHub OAuth2 access token 요청
    Cred-->>Gateway: GitHub authorization URL 및 session URI 반환
    Gateway-->>User: GitHub authorization URL 및 session URI 반환

    User->>IdP: GitHub에 로그인하고 액세스 권한 부여
    IdP-->>Cred: GitHub authorization code 반환
    rect rgb(80, 80, 60)
        Note over User, IdP: Session Binding API
        Cred-->>User: Session URI를 포함하여 callback endpoint로 리디렉션
        User->>Cred: JWT 및 session URI로<br/>CompleteResourceTokenAuth 호출
        Cred->>IdP: 로그인한 사용자를 session URI의 사용자와 대조하여 검증한 후<br/>authorization code로 GitHub OAuth2 access token 요청
    end
    IdP-->>Cred: GitHub OAuth2 access token 반환
    Cred->>Cred: workload identity 및 사용자 기준으로<br/>Token vault에 token 캐시
    User->>Gateway: MCP server에서 Invoke tool<br/>Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
    Gateway->>Cred: workload identity 및 JWT로<br/>workload access token 가져오기
    Cred-->>Gateway: workload access token 반환
    Gateway->>Cred: workload access token으로<br/>GitHub OAuth2 access token 요청
    Cred-->>Gateway: GitHub OAuth2 access token 반환
    Gateway->>MCP: Invoke tool
    MCP-->>Gateway: 도구 결과
    Gateway-->>User: 도구 결과
```
