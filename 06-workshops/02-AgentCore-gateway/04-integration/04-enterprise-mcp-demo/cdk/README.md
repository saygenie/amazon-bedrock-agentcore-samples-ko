# Enterprise MCP Gateway - CDK 인프라

이 CDK 스택은 완전한 보안 강화가 적용된 Application Load Balancer(ALB)를 사용하여 Amazon Bedrock AgentCore 기반의 엔터프라이즈급 MCP(Model Context Protocol) Gateway를 배포합니다.

## 아키텍처 개요

스택은 다음 리소스를 프로비저닝합니다.

- OAuth 2.0 Authorization Code Grant, 사용자 지정 scope(`mcp.read`/`mcp.write`), audience/role claim 주입용 Pre-Token Generation Lambda가 포함된 **Cognito User Pool**
- Cognito authorizer, Cedar policy engine(ENFORCE 모드), Bedrock Guardrails(PII 마스킹/차단)가 포함된 **AgentCore Gateway**
- MCP 프록시, 날씨 도구, 인벤토리 도구, 사용자 세부 정보 도구, interceptor, pre-token generation을 위한 **Lambda 함수**
- 프라이빗 서브넷, NAT gateway, AgentCore용 VPC Interface Endpoint가 포함된 **VPC**
- TLS termination, WAF WebACL, 액세스 로깅이 적용된 **인터넷 연결 ALB**

## 사전 요구 사항

- 설치된 AWS CDK v2(`npm install -g aws-cdk`)
- Node.js 18+
- 사용자 지정 도메인용 ACM 인증서와 Route 53 hosted zone
- Python 3.12(Lambda 번들링용)

## 구성

`cdk.context.json` 또는 `-c` 플래그를 통해 CDK context 변수를 설정합니다.

| 변수 | 설명 | 기본값 |
|---|---|---|
| `domainName` | 사용자 지정 도메인 이름(예: `enterprise-mcp`) | `""` |
| `hostedZoneName` | Route 53 hosted zone 이름 | `""` |
| `hostedZoneId` | Route 53 hosted zone ID | `""` |
| `certificateArn` | ACM 인증서 ARN | `""` |

## 배포

```bash
# cdk/ 디렉터리에서 실행
npm install
npx cdk synth
npx cdk deploy
```

> **참고:** 스택은 `bin/enterprise-mcp-infra.ts`에서 `us-east-1`로 고정되어 있습니다. 다른 리전이 필요하면 해당 파일의 `region` 값을 업데이트하세요.

## 유용한 명령

| 명령 | 설명 |
|---|---|
| `npm run build` | TypeScript를 JS로 컴파일 |
| `npm run watch` | 변경 사항을 감시하고 컴파일 |
| `npm run test` | Jest 단위 테스트 실행 |
| `npx cdk synth` | 합성된 CloudFormation 템플릿 출력 |
| `npx cdk diff` | 배포된 스택과 현재 상태 비교 |
| `npx cdk deploy` | 이 스택 배포 |
| `npx cdk destroy` | 스택 해제 |

## 보안 상태

### 구현됨

| 기능 | 세부 정보 |
|---|---|
| Cognito User Pool | 관리자 전용 가입, 강력한 암호 정책, audience/role claim용 Pre-Token Generation Lambda |
| OAuth 2.0 | 사용자 지정 scope(`mcp.read`, `mcp.write`)를 사용하는 Authorization Code Grant |
| JWT audience 검증 | Proxy Lambda가 AgentCore로 전달하기 전에 `aud` claim 검증 |
| AgentCore Cognito authorizer | Gateway 수준에서 AWS가 토큰을 두 번째로 검증 |
| Cedar policy engine | ENFORCE 모드에서 사용자별 세분화된 도구 액세스 |
| Bedrock Guardrails | interceptor를 통한 PII 마스킹(주소, 이름, 이메일) 및 차단(신용 카드 번호) |
| Lambda-in-VPC 프록시 | 프라이빗 서브넷, NAT 송신만 허용 |
| VPC Interface Endpoint | AgentCore 트래픽이 AWS 프라이빗 네트워크에 머물며 퍼블릭 인터넷을 통과하지 않음 |
| ALB TLS termination | ACM 인증서를 통해 사용자 지정 도메인에 TLS 1.2+ 적용 |
| ALB `dropInvalidHeaderFields` | 잘못된 헤더 거부(request smuggling 완화) |
| ALB Host header 제한 | 모든 전달 규칙에 Host header 일치가 필요하며 원시 `*.elb` DNS는 404 반환 |
| HTTP → HTTPS 리디렉션 | 포트 80에서 영구 리디렉션 |
| WAF WebACL | IP 속도 제한(5분당 요청 1,000개), AWS IP Reputation 목록, Core Rule Set(OWASP Top 10), Known Bad Inputs |
| WAF Bot Control | COUNT 모드의 COMMON 수준(트래픽 검증 후 BLOCK으로 전환) |
| 예약된 Lambda 동시성 | DoS 영향 범위를 제한하도록 모든 함수에 상한 설정 |
| Gateway 리소스 정책 | `InvokeGateway`를 VPC로 제한 |
| Shield Standard | 퍼블릭 ALB에 자동 L3/L4 DDoS 보호 |
| ALB 액세스 로깅 | SSE가 적용되고 퍼블릭 액세스가 차단되며 SSL이 강제되는 S3 버킷, 90일 수명 주기 만료 |
| Redirect URI 허용 목록 | `handle_callback`이 302 리디렉션을 발행하기 전에 등록된 Cognito callback URL과 `redirect_uri`를 대조하여 검증(open redirect/auth code 탈취 방지) |
| Lambda별 IAM 역할 | 전용 최소 권한 역할 4개: `preTokenLambdaRole`(Cognito trigger), `proxyLambdaRole`(VPC + AgentCore 호출), `interceptorLambdaRole`(Bedrock Guardrails 전용), `toolLambdaRole`(CloudWatch Logs 전용) |

### 미구현 - 프로덕션 전 고려 사항

| 기능 | 세부 정보 |
|---|---|
| Shield Advanced | L7 DDoS 보호, SRT 액세스, 비용 보호(구독 필요) |
| Bot Control TARGETED | WAF Bot Control의 상위 검사 수준(추가 비용) |
| CloudTrail/Security Hub | 중앙 집중식 감사 및 보안 조사 결과 |
| ALB 액세스 로그 Athena workgroup | 포렌식 분석을 위해 Athena로 액세스 로그 쿼리 |
| GuardDuty 조사 결과 | 위협 탐지 통합 |
| MFA 적용 | Cognito User Pool은 MFA를 지원하지만 적용되지 않음(`mfa: cognito.Mfa.REQUIRED`) |
| 범위가 지정된 IAM 리소스 | 여러 정책에서 `Resource: "*"`를 사용하므로 특정 ARN으로 범위 제한 필요 |
| PKCE 적용 | client secret이 없는 Cognito public client에 PKCE가 적용되는지 확인 |
| 로그 암호화 | Lambda CloudWatch 로그가 기본 설정 사용(KMS CMK 암호화 없음) |
| 로그 보존 정책 | Lambda CloudWatch 로그 보존 기간은 기본적으로 무기한 |

## 프로젝트 구조

```
cdk/
├── bin/
│   └── enterprise-mcp-infra.ts          # CDK 앱 진입점(리전은 us-east-1로 고정)
├── lib/
│   ├── enterprise-mcp-infra-stack.ts     # 기본 인프라 스택
│   └── agentcore-policy-engine.ts        # Cedar policy engine construct
├── lambda/
│   ├── mcp_proxy_lambda.py              # MCP OAuth 프록시 Lambda
│   ├── pre_token_generation_lambda.py   # Cognito pre-token generation trigger
│   ├── interceptor/
│   │   └── interceptor.py               # Guardrails interceptor Lambda
│   ├── mcp-servers/
│   │   ├── weather/                     # 날씨 도구 Lambda
│   │   ├── inventory/                   # 인벤토리 도구 Lambda
│   │   └── user_details/               # 사용자 세부 정보 도구 Lambda
│   └── agentcore-policy-engine/         # Policy engine 사용자 지정 리소스 Lambda
├── test/
│   └── enterprise-mcp-infra.test.ts     # Jest 테스트
├── cdk.json
├── cdk.context.json
├── tsconfig.json
└── package.json
```
