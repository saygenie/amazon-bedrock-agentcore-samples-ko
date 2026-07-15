# 엔터프라이즈 MCP 인프라

Amazon Bedrock AgentCore와 Model Context Protocol(MCP)을 통합하기 위한 엔터프라이즈급 AWS 인프라로, OAuth 2.0 인증 및 정책 기반 액세스 제어를 통해 IDE(VS Code)를 안전하게 통합하도록 설계되었습니다.

![아키텍처 다이어그램](./assets/architecture.png)

## 개요

이 CDK 인프라는 VS Code와 기타 IDE가 Model Context Protocol을 통해 Amazon Bedrock AgentCore에 안전하게 연결할 수 있는 완전한 MCP Gateway 솔루션을 배포합니다. 이 솔루션은 다음과 같은 엔터프라이즈 기능을 제공합니다.

- Amazon Cognito를 통한 **OAuth 2.0 인증**
- custom Cedar 정책을 사용한 **정책 기반 액세스 제어**
- 로깅 및 변환을 위한 **요청/응답 가로채기**
- Bedrock Guardrails를 사용한 **PII 보호**
- SSL/TLS를 통한 **Custom Domain 지원**
- 암호화 및 수명 주기 관리가 적용된 S3로의 **ALB 액세스 로깅**

## 아키텍처

### 핵심 구성 요소

#### 1. **인증 계층**
- **Amazon Cognito User Pool**: 사용자 인증 및 OAuth 2.0 흐름 관리
- **Pre-Token Generation Lambda**: 정책 평가를 위해 JWT 토큰에 custom claim(user tag) 주입
- **OAuth Client**:
  - VS Code Client(PKCE를 사용하는 Authorization Code Grant)

#### 2. **Application Load Balancer**
Custom Domain, SSL/TLS, WAF 및 액세스 로깅이 적용된 프로덕션급 인터넷 연결 ALB입니다.

#### 3. **MCP Proxy Lambda**
다음 작업을 처리하는 중앙 구성 요소입니다.
- OAuth metadata endpoint(`/.well-known/oauth-*`)
- Authorization flow(`/authorize`, `/callback`, `/token`)
- Dynamic Client Registration(`/register`)
- AgentCore Gateway로 MCP 프로토콜 proxy
- 원활한 통합을 위한 요청/응답 재작성

#### 4. **Amazon Bedrock AgentCore Gateway**
- semantic search 기능을 갖춘 MCP 프로토콜 handler
- 여러 MCP 버전 지원(2025-03-26, 2025-06-18, 2025-11-25)
- Lambda 기반 MCP 서버와 통합
- Cognito를 통한 인증 적용
- policy engine 결정 적용

#### 5. **MCP Server Lambdas**
MCP 도구를 구현하는 Lambda 함수 예시입니다.
- **Weather Lambda**: 날씨 정보 도구 제공(`get_weather`)
- **Inventory Lambda**: 재고 관리 도구 제공(`get_inventory`)
- **User Details Lambda**: 사용자 정보 도구 제공(`get_user_email`, `get_user_cc_number`)

#### 6. **Interceptor Lambda**
- Gateway로 들어오고 나가는 요청과 응답을 가로챔
- 로깅, 변환 및 custom business logic 활성화
- 컨텍스트 인식 처리를 위한 요청 header 수신

#### 7. **Policy Engine**
- Lambda를 통해 배포되는 custom Cedar 기반 policy engine
- JWT claim을 기준으로 사용자 권한 평가
- 정책 예시:
  - Admin 사용자는 모든 도구에 액세스 가능(weather + inventory)
  - 일반 사용자는 weather 도구에만 액세스 가능

#### 8. **Bedrock Guardrails**
- 요청과 응답의 PII 익명화
- 구성된 PII entity 유형:
  - **ADDRESS**: 입력 및 출력에서 익명화
  - **NAME**: 입력 및 출력에서 익명화
  - **EMAIL**: 입력 및 출력에서 익명화
  - **CREDIT_DEBIT_CARD_NUMBER**: 입력 및 출력에서 차단
- `tools/call` method에서 interceptor Lambda를 통해 적용
- custom message와 함께 콘텐츠 정책 적용

## 기술 스택

### 인프라
- **AWS CDK** 2.232.2+ (TypeScript)
- **Node.js** 24.x with TypeScript 5.9
- **AWS Bedrock AgentCore** (Alpha) 2.238.0-alpha.0+

### Runtime
- **Python** 3.12(모든 Lambda 함수)
- **Boto3** (AWS SDK for Python)

### AWS 서비스
| 서비스 | 목적 |
|---------|---------|
| Amazon Cognito | OAuth 2.0 인증 및 사용자 관리 |
| AWS Lambda | proxy, MCP 서버 및 policy engine을 위한 serverless 컴퓨팅 |
| Amazon Bedrock AgentCore | MCP Gateway 및 프로토콜 처리 |
| Application Load Balancer | TLS, WAF 및 액세스 로깅이 적용된 인터넷 연결 ALB |
| Amazon VPC | private subnet 및 VPC endpoint를 통한 네트워크 격리 |
| AWS IAM | Identity 및 액세스 관리 |
| Amazon Route53 | Custom Domain의 DNS 관리 |
| AWS Certificate Manager | SSL/TLS 인증서 |
| Amazon S3 | ALB 액세스 로그 저장(암호화, 90일 수명 주기) |
| Bedrock Guardrails | 콘텐츠 필터링 및 PII 보호 |

## 사전 요구 사항

1. 적절한 권한이 있는 **AWS 계정**
2. 자격 증명이 구성된 **AWS CLI**
3. **Node.js** 18.x 이상
4. **AWS CDK** CLI 설치: `npm install -g aws-cdk`
5. **Python** 3.12(Lambda 함수용)

### Custom Domain 설정(선택 사항)
- Route53 hosted zone
- 동일한 리전의 ACM 인증서
- 사용 가능한 도메인 이름

## 배포

### 1. 종속성 설치

```bash
cd cdk
npm install
```

### 2. CDK bootstrap(최초 한 번만)

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### 3. 배포 파라미터 구성

`cdk/cdk.context.json`을 편집하여 배포를 구성합니다.

```json
{
  "domainName": "enterprise-mcp",
  "hostedZoneName": "example.com",
  "hostedZoneId": "Z1234567890ABC",
  "certificateArn": "arn:aws:acm:region:account:certificate/xxx"
}
```

**구성 파라미터:**

| 파라미터 | 설명 | 필수 | 기본값 |
|-----------|-------------|----------|---------|
| `domainName` | Custom Domain 이름(예: `enterprise-mcp`) | 예 | `""` |
| `hostedZoneName` | Route53 hosted zone 이름(예: `example.com`) | 예 | `""` |
| `hostedZoneId` | Route53 hosted zone ID(예: `Z1234567890ABC`) | 예 | `""` |
| `certificateArn` | HTTPS용 ACM 인증서 ARN | 예 | `""` |

### 4. 스택 배포

```bash
cdk deploy
```

> **참고:** 스택의 리전은 `cdk/bin/enterprise-mcp-infra.ts`에서 `us-east-1`로 고정되어 있습니다. 다른 리전이 필요하면 해당 파일의 `region` 값을 업데이트하세요.

### 5. CDK 출력 저장

배포가 완료되면 CDK가 중요한 구성 값을 출력합니다. 다음 단계에서 필요하므로 **전체 출력을 복사**합니다.

출력 예시:
```
EnterpriseMcpInfraStack.UserPoolId = us-east-1_XXXXXXXXX
EnterpriseMcpInfraStack.VSCodeClientId = xxxxxxxxxxxxxxxxxxxx
EnterpriseMcpInfraStack.EndpointUrl = https://enterprise-mcp.example.com
EnterpriseMcpInfraStack.VSCodeMcpConfig = {...}
EnterpriseMcpInfraStack.Gateway = agentcore-mcp-gateway-xxxxx
...
```

## 구성

### Cognito 사용자 생성

#### 자동화 스크립트 사용(권장)

1. `scripts/script.py`를 **편집**합니다.
   - `output` 변수의 내용을 4단계에서 얻은 실제 CDK 출력으로 교체합니다.
   - 원하는 이메일 주소와 암호로 사용자 목록을 사용자 지정합니다.

2. 사용자를 생성하도록 **스크립트를 실행**합니다.
```bash
cd scripts
python script.py
```

스크립트는 다음 작업을 수행합니다.
- CDK 출력을 파싱하여 User Pool ID 추출
- 기본 사용자 3명 생성(admin, regular, read-only)
- 영구 암호 설정(최초 로그인 시 암호 재설정 불필요)
- 이미 존재하는 사용자 건너뛰기

**생성되는 기본 사용자:**
- `vscode-admin@example.com` / `TempPassword123!`
- `vscode-user@example.com` / `TempPassword1234!`
- `vscode-readonly@example.com` / `TempPassword1235!`

#### 수동 사용자 생성(대안)

수동으로 생성하려면 다음 명령을 실행합니다.

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username admin@example.com \
  --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <UserPoolId> \
  --username admin@example.com \
  --password 'YourSecurePassword123!' \
  --permanent
```

**참고**: Pre-Token Generation Lambda는 사용자의 이메일 주소를 기준으로 ID token과 access token 모두에 `user_tag` claim을 자동으로 주입합니다.
- `vscode-admin@example.com`에는 `user_tag: "admin_user"`가 부여됩니다.
- 그 외 모든 사용자에게는 `user_tag: "regular_user"`가 부여됩니다.

Policy Engine은 이 claim을 사용해 Gateway 도구 액세스에 관한 권한 부여 규칙을 적용합니다.

### VS Code 구성

워크스페이스에서 `.vscode/mcp.json`을 생성하거나 업데이트합니다.

```json
{
  "servers": {
    "enterprise-mcp-server": {
      "type": "http",
      "url": "https://enterprise-mcp.example.com/mcp",
      "headers": {
        "MCP-Protocol-Version": "2025-11-25"
      }
    }
  }
}
```

## 사용법

### 1. VS Code 시작
MCP extension이 구성을 자동으로 감지하고 인증을 요청합니다.

### 2. 인증
- 메시지가 표시되면 "Sign In"을 클릭합니다.
- Cognito 자격 증명을 입력합니다.
- OAuth 흐름을 완료합니다.

### 3. MCP 도구 사용
인증을 마치면 VS Code Copilot 또는 MCP extension을 통해 MCP 도구를 사용할 수 있습니다.
- 날씨 정보: 현재 날씨 질문(인증된 모든 사용자)
- 재고 쿼리: 제품 재고 확인(admin 사용자만)
- 사용자 세부 정보: 사용자 이메일 및 신용 카드 정보 조회(user_tag가 있는 인증된 모든 사용자)

## 정책 관리

### Policy Engine 이해

Policy Engine은 Cedar 정책을 사용하여 JWT 토큰에 주입된 사용자 속성을 기준으로 MCP 도구 액세스를 제어합니다.

**정책 예시**(기본으로 배포):

```cedar
// Admin 사용자는 inventory 및 weather 도구에 액세스할 수 있음
permit (
  principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"inventory-tool", AgentCore::Action::"weather-tool"],
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  principal.hasTag("user_tag") &&
  principal.getTag("user_tag") == "admin_user"
};

// 일반 사용자는 weather 도구에만 액세스할 수 있음
permit (
  principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"weather-tool"],
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  principal.hasTag("user_tag") &&
  principal.getTag("user_tag") == "regular_user"
};

// user_tag가 있는 모든 사용자는 user details 도구에 액세스할 수 있음
permit (
  principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"user-details-tool"],
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  principal.hasTag("user_tag")
};
```

### 정책 사용자 지정

스택은 기본적으로 세 가지 Cedar 정책을 배포합니다. 사용자 지정하려면 `cdk/lib/enterprise-mcp-infra-stack.ts`의 정책 구문을 편집합니다.

```typescript
// 예시: Admin 사용자 정책 수정
const policyEngineStatementInventoryTool = `
  permit (
    principal is AgentCore::OAuthUser,
    action in [AgentCore::Action::"inventory-tool", AgentCore::Action::"weather-tool", AgentCore::Action::"user-details-tool"],
    resource == AgentCore::Gateway::"${gateway.gatewayArn}"
  ) when {
    principal.hasTag("user_tag") &&
    principal.getTag("user_tag") == "admin_user"
  };
`;

// 예시: 특정 도구에 대한 새 정책 추가
const customPolicy = `
  permit (
    principal is AgentCore::OAuthUser,
    action in [AgentCore::Action::"user-details-tool"],
    resource == AgentCore::Gateway::"${gateway.gatewayArn}"
  ) when {
    principal.hasTag("department") &&
    principal.getTag("department") == "finance"
  };
`;

// 사용자 지정 정책 추가
agentCorePolicyEngine.addPolicy(
  "finance_user_details_policy",
  "Policy for finance users to access user details",
  customPolicy
);
```

그런 다음 다시 배포합니다.

```bash
cdk deploy
```

**중요**: 정책 tag 이름은 Pre-Token Generation Lambda가 주입하는 claim 이름과 일치해야 합니다(예: `custom:user_tag`가 아닌 `user_tag`).

## 모니터링 및 디버깅

### Lambda 로그

CDK 스택은 가장 자주 디버깅하는 두 Lambda의 함수 이름(`ProxyLambdaName`, `PreTokenGenerationLambdaName`)을 출력합니다. 다른 Lambda는 AWS 콘솔에서 자동 생성된 이름을 찾거나(Lambda → Functions에서 스택 이름으로 필터링) AWS CLI를 사용합니다.

```bash
# MCP Proxy Lambda - CDK 출력의 이름: EnterpriseMcpInfraStack.ProxyLambdaName
aws logs tail /aws/lambda/$(aws cloudformation describe-stacks \
  --stack-name EnterpriseMcpInfraStack \
  --query "Stacks[0].Outputs[?OutputKey=='ProxyLambdaName'].OutputValue" \
  --output text) --follow

# Pre-Token Generation Lambda - CDK 출력의 이름: EnterpriseMcpInfraStack.PreTokenGenerationLambdaName
aws logs tail /aws/lambda/$(aws cloudformation describe-stacks \
  --stack-name EnterpriseMcpInfraStack \
  --query "Stacks[0].Outputs[?OutputKey=='PreTokenGenerationLambdaName'].OutputValue" \
  --output text) --follow

# Interceptor Lambda - AWS Console에서 이름 확인(스택 기준 필터: EnterpriseMcpInfraStack)
# aws logs tail /aws/lambda/<McpInterceptorLambda-name> --follow

# Policy Engine Lambda - AWS Console에서 이름 확인(스택 기준 필터: EnterpriseMcpInfraStack)
# aws logs tail /aws/lambda/<AgentCorePolicyEngine-PolicyFunction-name> --follow
```

### CloudWatch Insights 쿼리

**OAuth 흐름 추적:**
```
fields @timestamp, @message
| filter @message like /HANDLE_AUTHORIZE|HANDLE_CALLBACK/
| sort @timestamp desc
```

**Gateway 요청:**
```
fields @timestamp, method, path, statusCode
| filter @message like /proxy_to_gateway/
| sort @timestamp desc
```

## 보안 상태

### 구현됨

| 기능 | 세부 정보 |
|---|---|
| Cognito User Pool | Admin 전용 가입, 강력한 암호 정책, audience/role claim용 Pre-Token Generation Lambda |
| OAuth 2.0 | custom scope(`mcp.read`, `mcp.write`)를 사용하는 Authorization Code Grant |
| JWT audience 검증 | AgentCore에 전달하기 전에 Proxy Lambda가 `aud` claim 검증 |
| AgentCore Cognito authorizer | Gateway 수준에서 AWS가 토큰을 두 번째로 검증 |
| Cedar policy engine | ENFORCE 모드에서 사용자별 세분화된 도구 액세스 |
| Bedrock Guardrails | interceptor를 통한 PII 마스킹(주소, 이름, 이메일) 및 차단(신용 카드 번호) |
| Lambda-in-VPC proxy | Private subnet, NAT egress만 허용 |
| VPC Interface Endpoint | AgentCore 트래픽이 AWS private network에 유지되며 퍼블릭 인터넷을 통과하지 않음 |
| ALB TLS termination | ACM 인증서를 통해 Custom Domain에 TLS 1.2 이상 적용 |
| ALB `dropInvalidHeaderFields` | 잘못된 형식의 header 거부(request-smuggling 완화) |
| ALB Host-header gating | 모든 전달 규칙에 Host header 일치 필요. 원시 `*.elb` DNS는 404 반환 |
| HTTP → HTTPS redirect | 포트 80에서 영구 redirect |
| WAF WebACL | IP 속도 제한(5분당 요청 1,000건), AWS IP Reputation 목록, Core Rule Set(OWASP Top 10), Known Bad Inputs |
| WAF Bot Control | COUNT 모드의 COMMON 수준(트래픽 검증 후 BLOCK으로 전환) |
| 예약된 Lambda 동시성 | DoS 영향 범위를 제한하도록 모든 함수에 상한 적용 |
| Gateway 리소스 정책 | `InvokeGateway`를 VPC로 제한 |
| Shield Standard | 퍼블릭 ALB에 자동 L3/L4 DDoS 보호 |
| ALB 액세스 로깅 | SSE가 적용되고 퍼블릭 액세스가 차단되며 SSL이 강제되는 S3 버킷, 90일 후 만료 |
| Redirect URI allowlist | `handle_callback`이 302 redirect를 실행하기 전에 등록된 Cognito callback URL을 기준으로 `redirect_uri` 검증(open redirect/auth code 탈취 방지) |
| Lambda별 IAM 역할 | 전용 최소 권한 역할 4개: `preTokenLambdaRole`(Cognito trigger), `proxyLambdaRole`(VPC + AgentCore 호출), `interceptorLambdaRole`(Bedrock Guardrails 전용), `toolLambdaRole`(CloudWatch Logs 전용) |

### 미구현 - 프로덕션 도입 전 고려

| 기능 | 세부 정보 |
|---|---|
| Shield Advanced | L7 DDoS 보호, SRT 액세스, 비용 보호(구독 필요) |
| Bot Control TARGETED | WAF Bot Control의 상위 검사 수준(추가 비용) |
| CloudTrail / Security Hub | 중앙 집중식 감사 및 보안 탐지 결과 |
| ALB access-log Athena workgroup | 포렌식 분석을 위해 Athena로 액세스 로그 쿼리 |
| GuardDuty findings | 위협 탐지 통합 |
| MFA 적용 | Cognito User Pool은 MFA를 사용할 수 있지만 적용되지 않음(`mfa: cognito.Mfa.REQUIRED`) |
| 범위가 지정된 IAM 리소스 | 여러 정책에서 `Resource: "*"`를 사용하므로 특정 ARN으로 범위 제한 필요 |
| PKCE 적용 | Cognito public client(client secret 없음)에 PKCE가 적용되는지 확인 |
| 로그 암호화 | Lambda CloudWatch 로그에 기본 설정 사용(KMS CMK 암호화 없음) |
| 로그 보존 정책 | Lambda CloudWatch 로그는 기본적으로 무기한 보존 |

### 추가 보안 세부 정보

#### 인증
- PKCE(Proof Key for Code Exchange)를 사용하는 OAuth 2.0
- custom claim이 포함된 JWT 토큰
- VS Code의 안전한 토큰 저장

#### 권한 부여
- Cedar를 사용한 정책 기반 액세스 제어
- Lambda trigger를 통한 사용자 속성 주입
- Gateway 수준 권한 부여 적용

#### 데이터 보호
- 전송 중 SSL/TLS 암호화
- Bedrock Guardrails를 통한 PII 익명화
- private subnet 및 VPC endpoint를 통한 VPC 격리

#### Secret 관리
- 환경 변수에 Client secret 저장
- 로그에 OAuth 토큰을 노출하지 않음
- Lambda 함수에 IAM 역할 기반 액세스 적용

## 문제 해결

### 문제: "Failed to authenticate"
**해결 방법**: Cognito 사용자 자격 증명을 확인하고 사용자에게 올바른 custom attribute가 있는지 확인합니다.

### 문제: "Tool not available"
**해결 방법**: 사용자의 `custom:user_tag` attribute가 정책 요구 사항과 일치하는지 확인합니다.

### 문제: "Gateway timeout"
**해결 방법**: Lambda timeout 설정(기본값: 300초)과 Gateway 연결을 확인합니다.

### 문제: "Invalid redirect_uri"
**해결 방법**: callback URL이 Cognito client 구성에 올바르게 등록되어 있는지 확인합니다.

### 문제: ALB health check 실패
**해결 방법**: `/ping` 엔드포인트가 200을 반환해야 합니다. Lambda 로그에서 오류를 확인합니다.

## 정리

모든 리소스를 제거하려면 다음 명령을 실행합니다.

```bash
cdk destroy
```

**경고**: Cognito 사용자, Lambda 함수 및 구성을 포함한 모든 리소스가 삭제됩니다.

## 아키텍처 결정

### ALB를 사용하는 이유

- Custom Domain, SSL/TLS 및 세분화된 라우팅을 제공하는 프로덕션급 서비스
- OWASP Top 10, 속도 제한 및 bot control을 위한 WAF WebACL 통합
- 포렌식 분석을 위한 S3 액세스 로깅
- 네트워크 격리를 위한 VPC 통합

### MCP Server에 Lambda를 사용하는 이유

- Serverless 및 자동 확장
- 사용량 기반 요금
- AgentCore Gateway와 간편한 통합
- 인프라 관리 불필요

### Custom Policy Engine을 사용하는 이유

- 유연한 속성 기반 액세스 제어
- 복잡한 권한 부여 로직을 위한 Cedar 정책 언어
- 재배포 없이 Runtime에서 정책 평가
- JWT custom claim과 통합

## 솔루션 확장

### 새 MCP 도구 추가

1. `cdk/lambda/mcp-servers/`에 새 Lambda 함수를 생성합니다.
2. 도구 스키마를 정의합니다.
3. `enterprise-mcp-infra-stack.ts`에서 Lambda 대상을 Gateway에 추가합니다.
4. 필요한 경우 정책을 업데이트합니다.

### 사용자 지정 Interceptor

`cdk/lambda/interceptor/interceptor.py`를 수정하여 custom logic을 추가합니다.
- 요청 검증
- 응답 변환
- 로깅 및 메트릭
- 외부 시스템과 통합

### 외부 MCP Server

Credential provider를 사용해 HTTP/HTTPS를 통해 외부 MCP 서버에 연결하도록 Gateway를 구성합니다.

## 참고 자료

- [AWS CDK 문서](https://docs.aws.amazon.com/cdk/)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/)
- [Model Context Protocol 사양](https://modelcontextprotocol.io/)
- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [Cedar Policy Language](https://www.cedarpolicy.com/)

## 라이선스

이 프로젝트는 데모 목적으로 있는 그대로 제공됩니다.

## 지원

문제나 질문이 있는 경우 다음을 확인하세요.
1. Lambda 함수의 CloudWatch Logs를 확인합니다.
2. CloudFormation 스택 이벤트를 검토합니다.
3. IAM 권한을 확인합니다.
4. AWS Bedrock AgentCore 문서를 참조합니다.
