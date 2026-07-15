import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as targets from "aws-cdk-lib/aws-elasticloadbalancingv2-targets";
import * as certificatemanager from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53targets from "aws-cdk-lib/aws-route53-targets";
import * as wafv2 from "aws-cdk-lib/aws-wafv2";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import * as path from "path";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";
import * as bedrockl1 from 'aws-cdk-lib/aws-bedrock';
import { AgentCorePolicyEngine } from "./agentcore-policy-engine";

export class EnterpriseMcpInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =============================================================================
    // 보안 태세 - 이 스택이 제공하는 항목과 제공하지 않는 항목
    // =============================================================================
    // 제공 항목:
    //   • Cognito User Pool(관리자 전용 가입, MFA 지원 준비, 강력한 암호 정책)과
    //     audience/role claim을 삽입하는 Pre-Token Generation Lambda
    //   • OAuth 2.0 Authorization Code Grant + 사용자 지정 scope(mcp.read / mcp.write)
    //   • AgentCore 호출 전에 프록시 Lambda에서 수행하는 JWT audience 검증
    //   • AgentCore Gateway Cognito authorizer(AWS에서 토큰을 한 번 더 검증)
    //   • 사용자별 세분화된 도구 접근을 적용하는 Cedar policy engine(ENFORCE)
    //   • 인터셉터 계층에 적용되는 Bedrock Guardrails(PII 마스킹/차단)
    //   • Lambda-in-VPC 프록시(private subnet, NAT egress 전용)
    //   • bedrock-agentcore용 VPC Interface Endpoint(InvokeGateway 트래픽이
    //     AWS 사설 네트워크에 머무르며 퍼블릭 인터넷을 통과하지 않음)
    //   • 다음 항목을 갖춘 인터넷 연결 ALB:
    //       – 사용자 지정 도메인의 TLS 1.2+ 종료(ACM 인증서)
    //       – dropInvalidHeaderFields(HTTP request smuggling 완화)
    //       – 모든 전달 규칙의 Host 헤더 조건, 원시 *.elb DNS는 404 반환
    //       – 포트 80에서 HTTP → HTTPS 영구 리디렉션
    //   • WAF WebACL(Regional, ALB에 연결):
    //       – IP 속도 제한(IP당 5분에 요청 1,000개)
    //       – AWS IP Reputation 목록(botnet, TOR exit, scanner)
    //       – Core Rule Set / OWASP Top 10
    //       – Known Bad Inputs
    //       – Bot Control – COMMON 수준(COUNT 모드, 검증 후 BLOCK으로 전환)
    //   • 모든 함수의 Lambda 예약 동시성 상한(DoS 영향 범위 제한)
    //   • InvokeGateway를 VPC로 제한하는 Gateway 리소스 정책
    //   • Shield Standard(퍼블릭 ALB에서 자동 활성화, L3/L4 DDoS 전용)
    //   • S3에 ALB 접근 로그 저장(암호화, 90일 수명 주기, 퍼블릭 접근 차단)
    //   • handle_callback의 Redirect URI allowlist(open redirect 공격 방지)
    //
    // 제공하지 않는 항목 - 프로덕션 전환 전에 추가 고려:
    //   • Shield Advanced(L7 DDoS + SRT + 비용 보호, 구독 필요)
    //   • Bot Control TARGETED 검사 수준(추가 WAF 비용)
    //   • 중앙 집중식 감사를 위한 CloudTrail / Security Hub 통합
    //   • ALB 접근 로그 Athena workgroup / GuardDuty finding
    // =============================================================================

    // =============================================================================
    // CONTEXT에서 가져오는 구성
    // =============================================================================

    // context에서 가져오는 도메인 및 인프라 구성
    const domainName = this.node.tryGetContext("domainName") || "";
    const hostedZoneName = this.node.tryGetContext("hostedZoneName") || "";
    const hostedZoneId = this.node.tryGetContext("hostedZoneId") || "";
    const certificateArn = this.node.tryGetContext("certificateArn") || "";

    // 경로 기반 라우팅을 위한 MCP 메타데이터 키(역방향 DNS 표기법)
    // target별 도구 필터링을 위해 _meta 필드에서 사용
    const mcpMetadataKey = this.node.tryGetContext("mcpMetadataKey") || "com.example/target";

    // =============================================================================
    // RESOURCE SERVER 식별자
    // resource server 식별자는 OAuth audience claim으로도 사용됨
    // (RFC 8707 resource indicator / RFC 9728 protected-resource metadata)
    // MCP 엔드포인트에 발급된 모든 access token은 이를 `aud`로 포함
    // =============================================================================
    const resourceServerIdentifier = "agentcore-gateway";

    // =============================================================================
    // PRE-TOKEN GENERATION LAMBDA
    // =============================================================================

    // pre-token generation용 Lambda 실행 역할 생성
    const preTokenLambdaRole = new iam.Role(this, "PreTokenLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    // Pre-Token Generation Lambda
    const preTokenGenerationLambda = new lambda.Function(
      this,
      "PreTokenGenerationLambda",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: "lambda_function.lambda_handler",
        code: lambda.Code.fromAsset(path.join(__dirname, "../lambda"), {
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: [
              "bash",
              "-c",
              [
                "cp pre_token_generation_lambda.py /asset-output/lambda_function.py",
              ].join(" && "),
            ],
          },
        }),
        role: preTokenLambdaRole,
        timeout: cdk.Duration.seconds(60),
        memorySize: 128,
        // 토큰 생성이 급증해도 다른 워크로드의 리소스를 고갈시키지 않도록 동시성을 제한
        // 최대 로그인 비율에 맞게 이 값을 조정
        reservedConcurrentExecutions: 50,
        description: "Lambda to add custom claims to Cognito tokens based on user email",
        environment: {
          // 프록시 Lambda의 audience validator가 토큰의 적용 범위가 이 resource server인지
          // 확인할 수 있도록 모든 access token에 `aud` claim으로 삽입
          // (RFC 8707 / MCP Authorization 사양)
          RESOURCE_SERVER_ID: resourceServerIdentifier,
        },
      }
    );

    // =============================================================================
    // COGNITO USER POOL
    // =============================================================================

    // Cognito User Pool 생성
    const userPool = new cognito.UserPool(this, "AgentCoreEnterprisePool", {
      userPoolName: `agentcore-enterprise-pool`,
      selfSignUpEnabled: false,
      signInAliases: {
        email: true,
      },
      autoVerify: {
        email: true,
      },
      standardAttributes: {
        email: {
          required: true,
          mutable: true,
        },
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Cognito에 pre-token generation Lambda 호출 권한 부여
    preTokenGenerationLambda.addPermission("CognitoInvokePermission", {
      principal: new iam.ServicePrincipal("cognito-idp.amazonaws.com"),
      sourceArn: userPool.userPoolArn,

    });

    userPool.addTrigger(cognito.UserPoolOperation.PRE_TOKEN_GENERATION_CONFIG, preTokenGenerationLambda, cognito.LambdaVersion.V3_0);


    // Cognito Domain 생성
    const cognitoDomainPrefix = `agentcore-vscode-domain-${this.account}`;
    const cognitoDomain = userPool.addDomain("CognitoDomain", {
      cognitoDomain: {
        domainPrefix: cognitoDomainPrefix,
      },
    });

    const readScope = new cognito.ResourceServerScope({
      scopeName: "mcp.read",
      scopeDescription: "Read MCP",
    });
    const writeScope = new cognito.ResourceServerScope({
      scopeName: "mcp.write",
      scopeDescription: "Write MCP",
    });
    // Resource Server 생성
    const resourceServer = userPool.addResourceServer(
      "AgentCoreResourceServer",
      {
        identifier: resourceServerIdentifier,
        userPoolResourceServerName: "AgentCore Gateway",
        scopes: [readScope, writeScope],
      }
    );

    const mcpScopes = [
      cognito.OAuthScope.resourceServer(resourceServer, readScope),
      cognito.OAuthScope.resourceServer(resourceServer, writeScope),
    ];

    // =============================================================================
    // BEDROCK GUARDRAILS
    // =============================================================================

    const guardrails = new bedrockl1.CfnGuardrail(this, "AgentCoreGuardrail", {
      name: "AgentCore-Enterprise-Guardrail",
      description: "Guardrail for AgentCore Enterprise MCP Gateway",
      blockedInputMessaging: "Your request contains content that violates our policies and cannot be processed.",
      blockedOutputsMessaging: "The response contains content that violates our policies and cannot be displayed.",
      sensitiveInformationPolicyConfig:{
        // 응답에서 익명화할 PII entity type 예시 설정. 구체적인 요구 사항에 따라 사용자 지정 가능
        piiEntitiesConfig:[
          {
            type: 'ADDRESS',
            action: 'ANONYMIZE',
            inputEnabled: true,
            inputAction: 'ANONYMIZE'
          },
          {
            type: 'NAME',
            action: 'ANONYMIZE',
            inputEnabled: true,
            inputAction: 'ANONYMIZE'
          },
          {
            type: 'EMAIL',
            action: 'ANONYMIZE',
            inputEnabled: true,
            inputAction: 'ANONYMIZE'
          },
          {
            type: 'CREDIT_DEBIT_CARD_NUMBER',
            action: 'BLOCK',
            inputEnabled: true,
            inputAction: 'BLOCK'
          }
        ]
      }
    }
    );

    // =============================================================================
    // VPC 설정
    // =============================================================================

    // public subnet 및 internet gateway가 있는 새 VPC 생성
    const vpc = new ec2.Vpc(this, "McpVpc", {
        maxAzs: 2,
        natGateways: 1, // private subnet의 Lambda가 인터넷에 접근하기 위한 NAT Gateway
        subnetConfiguration: [
          {
            name: "Public",
            subnetType: ec2.SubnetType.PUBLIC,
            cidrMask: 24,
          },
          {
            name: "Private",
            subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
            cidrMask: 24,
          },
        ],
      });

      // =============================================================================
      // VPC INTERFACE ENDPOINT - bedrock-agentcore
      // 프록시 Lambda의 모든 InvokeGateway 트래픽을 AWS 사설 네트워크에 유지하며
      // 패킷이 퍼블릭 인터넷을 통과하지 않게 함
      //
      // Security group: VPC 내부 리소스만 엔드포인트를 사용할 수 있도록 VPC CIDR의
      // HTTPS(443) 인바운드만 허용. 그 외 모든 트래픽은 암묵적으로 거부됨
      //
      // 참고: Interface endpoint에는 AZ별 시간당 요금과 GB당 데이터 처리 요금이 부과됨
      // https://aws.amazon.com/privatelink/pricing/ 참조
      // =============================================================================
      const agentcoreEndpointSg = new ec2.SecurityGroup(
        this,
        "AgentCoreEndpointSg",
        {
          vpc,
          description:
            "Allow HTTPS from VPC to bedrock-agentcore interface endpoint",
          allowAllOutbound: false,
        }
      );
      agentcoreEndpointSg.addIngressRule(
        ec2.Peer.ipv4(vpc.vpcCidrBlock),
        ec2.Port.tcp(443),
        "HTTPS from VPC to AgentCore endpoint"
      );

      // AgentCore data plane(InvokeGateway)용 Interface endpoint
      // 프록시 Lambda와 함께 private subnet에 배치하므로 AgentCore API 호출에
      // NAT 경유가 필요하지 않음
      vpc.addInterfaceEndpoint("AgentCoreEndpoint", {
        service: new ec2.InterfaceVpcEndpointService(
          `com.amazonaws.${this.region}.bedrock-agentcore.gateway`,
          443
        ),
        subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        securityGroups: [agentcoreEndpointSg],
        privateDnsEnabled: true,
      });

    // =============================================================================
    // WAF WEB ACL
    // 적용되는 보호 계층(별도 언급이 없으면 모두 프리 티어 관리형 규칙 그룹):
    //   1. IP 수준 속도 제한 - 소스 IP당 5분에 요청 1,000개
    //   2. AWSManagedRulesCommonRuleSet(CRS) - OWASP Top 10 시그니처
    //   3. AWSManagedRulesKnownBadInputsRuleSet - 알려진 공격 패턴
    //   4. AWSManagedRulesAmazonIpReputationList - AWS 위협 인텔리전스 IP 차단 목록
    //   5. AWSManagedRulesBotControlRuleSet(일반 bot, COUNT 모드) - 테스트 중 정상 MCP
    //      클라이언트가 실수로 차단되지 않도록 COUNT로 설정하며, 트래픽 검증 후
    //      프로덕션에서 BLOCK으로 전환
    //
    // 참고: 규칙 2~5는 본문에 정상적으로 패턴(redirect_uri, code_verifier,
    // grant_type 등)이 포함되어 시그니처 기반 규칙이 오탐할 수 있는 OAuth 흐름
    // 엔드포인트(/token, /authorize, /callback, /register)를 제외하도록 범위를 축소
    //
    // DDoS 보호: 모든 public ALB에서 Shield Standard가 추가 비용 없이 자동으로
    // 활성화되어 대규모 L3/L4 공격을 완화. L7 DDoS 보호 및 SRT 접근에는
    // Shield Advanced를 별도로 구독해야 함
    // =============================================================================

    // 헬퍼: 재사용 가능한 OAuth 경로 범위 축소 statement
    // (동일 블록을 네 번 반복하지 않도록 CRS, KBI, IP reputation, Bot Control 규칙에서 공유)
    const oauthScopeDown: wafv2.CfnWebACL.StatementProperty = {
      notStatement: {
        statement: {
          orStatement: {
            statements: [
              {
                byteMatchStatement: {
                  searchString: "/token",
                  fieldToMatch: { uriPath: {} },
                  textTransformations: [{ priority: 0, type: "LOWERCASE" }],
                  positionalConstraint: "EXACTLY",
                },
              },
              {
                byteMatchStatement: {
                  searchString: "/authorize",
                  fieldToMatch: { uriPath: {} },
                  textTransformations: [{ priority: 0, type: "LOWERCASE" }],
                  positionalConstraint: "EXACTLY",
                },
              },
              {
                byteMatchStatement: {
                  searchString: "/callback",
                  fieldToMatch: { uriPath: {} },
                  textTransformations: [{ priority: 0, type: "LOWERCASE" }],
                  positionalConstraint: "EXACTLY",
                },
              },
              {
                byteMatchStatement: {
                  searchString: "/register",
                  fieldToMatch: { uriPath: {} },
                  textTransformations: [{ priority: 0, type: "LOWERCASE" }],
                  positionalConstraint: "EXACTLY",
                },
              },
            ],
          },
        },
      },
    };

    let webAcl: wafv2.CfnWebACL;

    webAcl = new wafv2.CfnWebACL(this, "McpAlbWebAcl", {
        name: "mcp-alb-web-acl",
        scope: "REGIONAL",
        defaultAction: { allow: {} },
        visibilityConfig: {
          cloudWatchMetricsEnabled: true,
          metricName: "mcp-alb-web-acl",
          sampledRequestsEnabled: true,
        },
        rules: [
          // ── 1. IP 수준 속도 제한 ─────────────────────────────────────────────
          // 소스 IP당 5분 동안 요청 1,000개
          {
            name: "RateLimit",
            priority: 1,
            action: { block: {} },
            visibilityConfig: {
              cloudWatchMetricsEnabled: true,
              metricName: "RateLimit",
              sampledRequestsEnabled: true,
            },
            statement: {
              rateBasedStatement: {
                limit: 1000,
                aggregateKeyType: "IP",
              },
            },
          },

          // ── 2. AWS IP Reputation 목록 ─────────────────────────────────────────
          // AWS에서 관리하는 위협 인텔리전스 목록의 IP(botnet, TOR exit node,
          // scanner)를 차단. 비용이 높은 규칙 평가보다 먼저 적용
          {
            name: "AWSManagedRulesIPReputation",
            priority: 2,
            overrideAction: { none: {} },
            visibilityConfig: {
              cloudWatchMetricsEnabled: true,
              metricName: "AWSManagedRulesIPReputation",
              sampledRequestsEnabled: true,
            },
            statement: {
              managedRuleGroupStatement: {
                vendorName: "AWS",
                name: "AWSManagedRulesAmazonIpReputationList",
                scopeDownStatement: oauthScopeDown,
              },
            },
          },

          // ── 3. Core Rule Set(OWASP Top 10) ───────────────────────────────────
          {
            name: "AWSManagedRulesCRS",
            priority: 3,
            overrideAction: { none: {} },
            visibilityConfig: {
              cloudWatchMetricsEnabled: true,
              metricName: "AWSManagedRulesCRS",
              sampledRequestsEnabled: true,
            },
            statement: {
              managedRuleGroupStatement: {
                vendorName: "AWS",
                name: "AWSManagedRulesCommonRuleSet",
                scopeDownStatement: oauthScopeDown,
              },
            },
          },

          // ── 4. Known Bad Inputs ───────────────────────────────────────────────
          {
            name: "AWSManagedRulesKnownBadInputs",
            priority: 4,
            overrideAction: { none: {} },
            visibilityConfig: {
              cloudWatchMetricsEnabled: true,
              metricName: "AWSManagedRulesKnownBadInputs",
              sampledRequestsEnabled: true,
            },
            statement: {
              managedRuleGroupStatement: {
                vendorName: "AWS",
                name: "AWSManagedRulesKnownBadInputsRuleSet",
                scopeDownStatement: oauthScopeDown,
              },
            },
          },

          // ── 5. Bot Control(일반 bot - COUNT 모드) ─────────────────────────────
          // 테스트/파일럿 중 자동화된 MCP 클라이언트가 실수로 차단되지 않도록 COUNT로 실행
          // 트래픽이 검증되면 CloudWatch 지표를 검토하고 overrideAction을
          // { none: {} }(BLOCK)로 전환
          {
            name: "AWSManagedRulesBotControl",
            priority: 5,
            overrideAction: { count: {} },
            visibilityConfig: {
              cloudWatchMetricsEnabled: true,
              metricName: "AWSManagedRulesBotControl",
              sampledRequestsEnabled: true,
            },
            statement: {
              managedRuleGroupStatement: {
                vendorName: "AWS",
                name: "AWSManagedRulesBotControlRuleSet",
                managedRuleGroupConfigs: [
                  { awsManagedRulesBotControlRuleSet: { inspectionLevel: "COMMON" } },
                ],
                scopeDownStatement: oauthScopeDown,
              },
            },
          },
        ],
      });

    // =============================================================================
    // LAMBDA 함수
    // =============================================================================

    // ---------------------------------------------------------------------------
    // 보안: Lambda 함수 그룹별 전용 최소 권한 IAM role
    //
    // Role              │ 사용 주체                       │ 권한
    // ──────────────────┼────────────────────────────────┼────────────────────────
    // proxyLambdaRole   │ McpProxyLambda (VPC-resident)  │ VPC execution +
    //                   │                                │ bedrock-agentcore:InvokeGateway(생성 후 gateway ARN으로 범위 제한)
    //                   │                                │ bedrock-agentcore:CompleteResourceTokenAuth / GetResourceOauth2Token
    // interceptorRole   │ McpInterceptorLambda           │ Basic execution +
    //                   │                                │ bedrock:ApplyGuardrail (scoped to this guardrail)
    // toolLambdaRole    │ WeatherLambda, InventoryLambda,│ 기본 실행 권한만 사용 -
    //                   │ UserDetailsLambda              │ tool Lambda는 AgentCore에서 이벤트를 수신하며
    //                   │                                │ AWS API 권한이 필요하지 않음
    // ---------------------------------------------------------------------------

    // ── 프록시 Lambda role ───────────────────────────────────────────────────────
    // VPC 접근(private subnet) + AgentCore gateway 호출이 필요함
    // 참고: 여기서는 secretsmanager 리소스 범위에 자리 표시자로 "*"를 사용
    //       OAuth 클라이언트 자격 증명용 Secrets Manager secret을 생성한 뒤
    //       정확한 secret ARN으로 교체
    const proxyLambdaRole = new iam.Role(this, "McpProxyLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Least-privilege role for the MCP proxy Lambda (VPC-resident)",
      managedPolicies: [
        // 기본 CloudWatch Logs 권한
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
        // VPC 배치를 위한 ENI 생성/조회/삭제
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaVPCAccessExecutionRole"
        ),
      ],
    });

    // AgentCore identity token exchange - gateway 생성 후 추가되는 gateway ARN으로 범위 제한
    // (gateway 블록 아래의 proxyLambdaRole.addToPolicy 참조)
    proxyLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "AgentCoreIdentityTokenExchange",
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock-agentcore:CompleteResourceTokenAuth",
          "bedrock-agentcore:GetResourceOauth2Token",
        ],
        // 현재 AgentCore IAM 참조에서 이 작업들은 리소스 수준 조건을 지원하지 않음
        // 지원되면 범위를 제한
        resources: ["*"],
      })
    );

    // 특정 gateway ARN으로 범위를 제한할 수 있도록 bedrock-agentcore:InvokeGateway는
    // 아래의 gateway construct 이후에 추가

    // ── 인터셉터 Lambda role ─────────────────────────────────────────────────────
    // 이 특정 guardrail에서 bedrock:ApplyGuardrail만 호출하면 됨
    const interceptorLambdaRole = new iam.Role(this, "McpInterceptorLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Least-privilege role for the MCP interceptor Lambda",
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    interceptorLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "ApplyGuardrailThisGuardrailOnly",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:ApplyGuardrail"],
        // 이 스택에서 생성된 정확한 guardrail로 범위 제한
        resources: [guardrails.attrGuardrailArn],
      })
    );

    // ── 도구 Lambda role ─────────────────────────────────────────────────────────
    // WeatherLambda, InventoryLambda, UserDetailsLambda에서 공유
    // 이 Lambda들은 AgentCore에서 호출하며 CloudWatch Logs 접근만 필요함
    // Bedrock, Secrets Manager, AgentCore 권한은 필요하지 않음
    const toolLambdaRole = new iam.Role(this, "McpToolLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description:
        "Least-privilege role for MCP tool Lambdas (weather, inventory, user-details) - no AWS API permissions required",
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    // MCP 프록시 Lambda(ALB를 위해 timeout 증가)
    // 예약 동시성: 트래픽 급증이 계정 한도를 고갈시켜 다른 워크로드에 영향을 주지 않도록
    // 동시성을 제한. 트래픽 프로필에 맞게 조정
    const proxyLambda = new lambda.Function(this, "McpProxyLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp mcp_proxy_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: proxyLambdaRole,
      timeout: cdk.Duration.seconds(300), // ALB용 5분
      memorySize: 256,
      vpc: vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      reservedConcurrentExecutions: 100,
      environment: {
        GATEWAY_URL: "", // gateway 생성 후 업데이트
        COGNITO_DOMAIN: `https://${cognitoDomain.domainName}.auth.${this.region}.amazoncognito.com`,
        CLIENT_ID: "", // VS Code 클라이언트 생성 후 업데이트
        // CLIENT_SECRET: "",
        CALLBACK_LAMBDA_URL: "", // ALB 생성 후 업데이트
        // resource server 식별자는 audience 검증에 사용됨
        // `aud` claim에 이 값이 없는 토큰은 AgentCore Gateway로 전달되기 전에 거부됨
        RESOURCE_SERVER_ID: resourceServerIdentifier,
        COGNITO_USER_POOL_ID: userPool.userPoolId,
        COGNITO_REGION: this.region,
        // 경로 기반 라우팅을 위한 MCP 메타데이터 키
        MCP_METADATA_KEY: mcpMetadataKey,
      },
    });

    // Weather Lambda
    const weatherLambda = new lambda.Function(this, "WeatherLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/mcp-servers/weather"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp weather_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: toolLambdaRole,
      timeout: cdk.Duration.seconds(300), // ALB용 5분
      memorySize: 256,
      reservedConcurrentExecutions: 50,
    });

    // Inventory Lambda
    const inventoryLambda = new lambda.Function(this, "InventoryLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/mcp-servers/inventory"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp inventory_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: toolLambdaRole,
      timeout: cdk.Duration.seconds(300), // ALB용 5분
      memorySize: 256,
      reservedConcurrentExecutions: 50,
    });

    // User Details Lambda
    const userDetailsLambda = new lambda.Function(this, "UserDetailsLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/mcp-servers/user_details"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp user_details_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: toolLambdaRole,
      timeout: cdk.Duration.seconds(300), // ALB용 5분
      memorySize: 256,
      reservedConcurrentExecutions: 50,
    });


    // Interceptor Lambda
    const interceptorLambda = new lambda.Function(this, "McpInterceptorLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/interceptor"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp interceptor.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: interceptorLambdaRole,
      timeout: cdk.Duration.seconds(300), // ALB용 5분
      memorySize: 256,
      reservedConcurrentExecutions: 50,
      environment: {
        "GUARDRAIL_ID": guardrails.attrGuardrailId,
        "GUARDRAIL_VERSION": guardrails.attrVersion,
        "MCP_METADATA_KEY": mcpMetadataKey,
      },
    });

    // =============================================================================
    // APPLICATION LOAD BALANCER
    // =============================================================================

    let endpointUrl: string;

    // Security group: HTTPS(443)와 HTTP(80)만 허용
    // 그 외 모든 인바운드 트래픽은 암묵적으로 거부됨
    const albSecurityGroup = new ec2.SecurityGroup(this, "AlbSecurityGroup", {
      vpc: vpc,
        description: "ALB security group - HTTPS/HTTP ingress only",
        allowAllOutbound: true,
      });
      albSecurityGroup.addIngressRule(
        ec2.Peer.anyIpv4(),
        ec2.Port.tcp(443),
        "Allow HTTPS from the internet"
      );
      albSecurityGroup.addIngressRule(
        ec2.Peer.anyIpv4(),
        ec2.Port.tcp(80),
        "Allow HTTP from the internet (redirected to HTTPS)"
      );
      albSecurityGroup.addIngressRule(
        ec2.Peer.anyIpv6(),
        ec2.Port.tcp(443),
        "Allow HTTPS from the internet (IPv6)"
      );
      albSecurityGroup.addIngressRule(
        ec2.Peer.anyIpv6(),
        ec2.Port.tcp(80),
        "Allow HTTP from the internet (IPv6, redirected to HTTPS)"
      );

      // =============================================================================
      // ALB 접근 로그 버킷
      // 암호화와 수명 주기를 설정하고 퍼블릭 접근을 차단한 ALB 접근 로그용 S3 버킷
      // CDK logAccessLogs() 헬퍼는 버킷 정책을 통해 올바른 리전 ELB 서비스 계정에
      // 쓰기 권한을 자동으로 부여함
      // stack env에 구체적인 리전이 필요함(bin/enterprise-mcp-infra.ts에서 설정)
      // =============================================================================
      const albLogBucket = new s3.Bucket(this, "AlbAccessLogBucket", {
        bucketName: `mcp-alb-access-logs-${this.account}-${this.region}`,
        encryption: s3.BucketEncryption.S3_MANAGED,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        enforceSSL: true,
        versioned: false,
        lifecycleRules: [
          {
            id: "ExpireAfter90Days",
            expiration: cdk.Duration.days(90),
          },
        ],
        removalPolicy: cdk.RemovalPolicy.DESTROY,
        autoDeleteObjects: true, // 참고: 프로덕션에서는 우발적인 로그 손실을 방지하도록 false로 설정
      });

      // Application Load Balancer 생성
      // dropInvalidHeaderFields: RFC 7230 허용 집합에 없는 문자가 헤더에 포함된 요청을
      // 거부하여 여러 request smuggling / header injection 공격 경로를 차단
      const alb = new elbv2.ApplicationLoadBalancer(this, "McpOAuthProxyALB", {
        vpc: vpc,
        internetFacing: true,
        loadBalancerName: "mcp-oauth-proxy-alb",
        securityGroup: albSecurityGroup,
        dropInvalidHeaderFields: true,
      });

      // ALB 접근 로깅 활성화. logAccessLogs()가 리전 ELB 계정에 올바른 버킷 정책을
      // 자동으로 설정
      alb.logAccessLogs(albLogBucket, "alb");

      // WAF WebACL을 ALB와 연결
      new wafv2.CfnWebACLAssociation(this, "AlbWebAclAssociation", {
        resourceArn: alb.loadBalancerArn,
        webAclArn: webAcl.attrArn,
      });

      // 인증서 가져오기
      const certificate = certificatemanager.Certificate.fromCertificateArn(
        this,
        "AlbCertificate",
        certificateArn
      );

      // HTTPS Listener 생성
      const mainListener = alb.addListener("HttpsListener", {
        port: 443,
        protocol: elbv2.ApplicationProtocol.HTTPS,
        certificates: [certificate],
        defaultAction: elbv2.ListenerAction.fixedResponse(404, {
          contentType: "text/plain",
          messageBody: "Not Found",
        }),
      });

      // HTTPS로 리디렉션하는 HTTP listener 추가
      alb.addListener("HttpListener", {
        port: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        defaultAction: elbv2.ListenerAction.redirect({
          protocol: "HTTPS",
          port: "443",
          permanent: true,
        }),
      });

      // hosted zone 가져오기
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        "HostedZone",
        {
          hostedZoneId: hostedZoneId,
          zoneName: hostedZoneName,
        }
      );

      // ALB를 가리키는 DNS record 생성
      new route53.ARecord(this, "AlbAliasRecord", {
        zone: hostedZone,
        recordName: domainName,
        target: route53.RecordTarget.fromAlias(
          new route53targets.LoadBalancerTarget(alb)
        ),
      });

      // Lambda Target Group 생성
      const proxyTargetGroup = new elbv2.ApplicationTargetGroup(
        this,
        "ProxyTargetGroup",
        {
          vpc,
          targetType: elbv2.TargetType.LAMBDA,
          targets: [new targets.LambdaTarget(proxyLambda)],
          healthCheck: {
            enabled: true,
            path: "/ping",
            interval: cdk.Duration.seconds(300),
          },
        }
      );

      // ALB에 Lambda 호출 권한 부여
      proxyLambda.grantInvoke(
        new iam.ServicePrincipal("elasticloadbalancing.amazonaws.com")
      );

      // Host 헤더 조건: 모든 전달 규칙은 Host 헤더가 사용자 지정 도메인과 일치해야 함
      // 원시 ALB DNS 이름(*.elb.amazonaws.com)으로 들어온 요청은 listener의 기본
      // 404 작업으로 넘어가며 Lambda로 전달되지 않음
      // 이를 통해 virtual hosting 악용을 방지하고 WAF / 사용자 지정 도메인 TLS 정책을
      // 우회하는 유효한 진입점에서 원시 DNS 이름을 제외
      const hostHeaderCondition = elbv2.ListenerCondition.hostHeaders([
        `${domainName}.${hostedZoneName}`,
      ]);

      // 프록시 Lambda 경로 - 특정 경로
      mainListener.addTargetGroups("ProxyWellKnownAuthRule", {
        priority: 40,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns([
            "/.well-known/oauth-authorization-server",
          ]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyWellKnownResourceRule", {
        priority: 50,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns([
            "/.well-known/oauth-protected-resource",
          ]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyAuthorizeRule", {
        priority: 60,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns(["/authorize"]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyCallbackRule", {
        priority: 70,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns(["/callback"]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyTokenRule", {
        priority: 80,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns(["/token"]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyRegisterRule", {
        priority: 90,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns(["/register"]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      // MCP 경로 - 동적 target 필터링을 위한 wildcard 패턴
      // 일치 경로: /mcp, /gitlab/mcp, /weather/mcp, /inventory/mcp, /*/mcp
      // 새 도구 그룹을 추가할 때 ALB를 업데이트할 필요 없음
      mainListener.addTargetGroups("ProxyMcpWildcardRule", {
        priority: 95,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns(["/mcp", "/*/mcp"]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      // 프록시 Lambda의 기본 catch-all 규칙(계속 Host 헤더로 제한)
      mainListener.addTargetGroups("ProxyDefaultRule", {
        priority: 100,
        conditions: [
          hostHeaderCondition,
          elbv2.ListenerCondition.pathPatterns(["/*"]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      // 사용자 지정 도메인을 엔드포인트로 사용
      endpointUrl = `https://${domainName}.${hostedZoneName}`;

      // ALB 출력
      new cdk.CfnOutput(this, "AlbEndpoint", {
        value: endpointUrl,
        description: "ALB Endpoint (HTTPS with Custom Domain)",
      });

      new cdk.CfnOutput(this, "CustomDomain", {
        value: domainName,
        description: "Custom Domain Name",
      });

      new cdk.CfnOutput(this, "AlbDnsName", {
        value: alb.loadBalancerDnsName,
        description: "ALB DNS Name",
      });

    // =============================================================================
    // VS CODE COGNITO 클라이언트(callback URL 포함)
    // =============================================================================

    const callbackUrls = [
      "http://127.0.0.1:33418",
      "http://127.0.0.1:33418/",
      "http://localhost:33418",
      "http://localhost:33418/",
      "http://localhost:54038",
      "http://localhost:54038/",
      `${endpointUrl}/callback`,
      `${endpointUrl}/callback/`,
      "https://vscode.dev/redirect",
      "https://insiders.vscode.dev/redirect",
    ];

    const vscodeClient = userPool.addClient("VSCodeClient", {
      userPoolClientName: `agentcore-vscode`,
      generateSecret: false,
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
        },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PHONE,
          ...mcpScopes,
        ],
        callbackUrls: callbackUrls,
      },
      authFlows: {
        userSrp: true,
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
    });

    // VS Code client ID 및 엔드포인트로 Lambda 환경 변수 업데이트
    proxyLambda.addEnvironment("CLIENT_ID", vscodeClient.userPoolClientId);
    proxyLambda.addEnvironment("CALLBACK_LAMBDA_URL", endpointUrl);
    // 프록시 Lambda가 handle_callback에서 redirect_uri를 검증할 수 있도록
    // Cognito에 등록된 callback URL 전달(open redirect 방지)
    proxyLambda.addEnvironment("ALLOWED_REDIRECT_URIS", JSON.stringify(callbackUrls));

    const gatewayRole = new iam.Role(this, "GatewayRole", {
      assumedBy: iam.ServicePrincipal.fromStaticServicePrincipleName(
        "bedrock-agentcore.amazonaws.com"
      ),
      inlinePolicies: {
        getAccessToken: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                "bedrock-agentcore:GetWorkloadAccess*",
                "bedrock-agentcore:GetResourceOauth2Token",
                "bedrock-agentcore:GetPolicyEngine",
                "bedrock-agentcore:AuthorizeAction",
                "bedrock-agentcore:PartiallyAuthorizeActions",
                "bedrock-agentcore:CheckAuthorizePermissions"
              ],
              resources: ["*"],
              effect: iam.Effect.ALLOW,
            }),
          ],
        }),
      },
    });

    const gateway = new agentcore.Gateway(this, "AgentCoreMcpGateway", {
      gatewayName: `agentcore-mcp-gateway-${this.account}`,
      description: "AgentCore Gateway for VS Code IDE integration",
      protocolConfiguration: agentcore.GatewayProtocol.mcp({
        searchType: agentcore.McpGatewaySearchType.SEMANTIC,
        supportedVersions: [
          agentcore.MCPProtocolVersion.MCP_2025_03_26,
          agentcore.MCPProtocolVersion.MCP_2025_06_18,
          "2025-11-25" as agentcore.MCPProtocolVersion,
        ],
      }),
      role: gatewayRole,
      exceptionLevel: agentcore.GatewayExceptionLevel.DEBUG,
      authorizerConfiguration: agentcore.GatewayAuthorizer.usingCognito({
        userPool: userPool,
        allowedClients: [vscodeClient],
        allowedAudiences: [vscodeClient.userPoolClientId],
        allowedScopes: mcpScopes.map((s) => s.scopeName),
      }),
      interceptorConfigurations: [
        agentcore.LambdaInterceptor.forRequest(interceptorLambda, { passRequestHeaders: true }),
        agentcore.LambdaInterceptor.forResponse(interceptorLambda, { passRequestHeaders: true })
      ],
    });

    const toolSchema = agentcore.ToolSchema.fromInline([
			{
				name: 'get_weather',
				description: "Get weather for a location",
				inputSchema: {
					type: agentcore.SchemaDefinitionType.OBJECT,
					properties: {
						timezone: {
							type: agentcore.SchemaDefinitionType.STRING,
							description: "the location e.g. seattle, wa"
						}
					}
				}
			}
		]);

    gateway.addLambdaTarget("WeatherLambdaTarget", {
      lambdaFunction: weatherLambda,
      gatewayTargetName: "weather-tool",
      toolSchema: toolSchema,
      credentialProviderConfigurations:[agentcore.GatewayCredentialProvider.fromIamRole()]
    });

    const inventoryToolSchema = agentcore.ToolSchema.fromInline([
			{
				name: 'get_inventory',
				description: "Get inventory for a product",
				inputSchema: {
					type: agentcore.SchemaDefinitionType.OBJECT,
					properties: {
						productId: {
							type: agentcore.SchemaDefinitionType.STRING,
							description: "the product ID to check inventory for"
						}
					}
				}
			}
		]);

    const userDetailsToolSchema = agentcore.ToolSchema.fromInline([
      {
        name: 'get_user_email',
        description: "Get user email for a user",
        inputSchema: {
          type: agentcore.SchemaDefinitionType.OBJECT,
          properties: {
            userId: {
              type: agentcore.SchemaDefinitionType.STRING,
              description: "the user ID to get email for"
            }
          }
        }
      },
      {
        name: 'get_user_cc_number',
        description: "Get user credit card number for a user",
        inputSchema: {
          type: agentcore.SchemaDefinitionType.OBJECT,
          properties: {
            userId: {
              type: agentcore.SchemaDefinitionType.STRING,
              description: "the user ID to get credit card number for"
            }
          }
        }
      }
    ]);

    gateway.addLambdaTarget("InventoryLambdaTarget", {
      lambdaFunction: inventoryLambda,
      gatewayTargetName: "inventory-tool",
      toolSchema: inventoryToolSchema,
      credentialProviderConfigurations:[agentcore.GatewayCredentialProvider.fromIamRole()]
    });

    gateway.addLambdaTarget("UserDetailsLambdaTarget", {
      lambdaFunction: userDetailsLambda,
      gatewayTargetName: "user-details-tool",
      toolSchema: userDetailsToolSchema,
      credentialProviderConfigurations:[agentcore.GatewayCredentialProvider.fromIamRole()]
    });

    proxyLambda.addEnvironment("GATEWAY_URL", gateway.gatewayUrl ?? "");

    // 이제 gateway ARN을 알 수 있으므로 InvokeGateway 범위를 이 gateway로만 제한
    // CDK가 ARN token을 확인할 수 있도록 gateway construct 이후에 배치해야 함
    proxyLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "InvokeThisGatewayOnly",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock-agentcore:InvokeGateway"],
        // wildcard "*"가 아닌 특정 gateway ARN으로 범위 제한
        resources: [gateway.gatewayArn],
      })
    );

    // =============================================================================
    // GATEWAY 리소스 기반 정책(VPC 제한)
    // =============================================================================

    // VPC 기반 정책을 gateway에 연결할 사용자 지정 리소스 생성
    const policyCustomResourceRole = new iam.Role(
        this,
        "GatewayPolicyCustomResourceRole",
        {
          assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
          managedPolicies: [
            iam.ManagedPolicy.fromAwsManagedPolicyName(
              "service-role/AWSLambdaBasicExecutionRole"
            ),
          ],
        }
      );

      // gateway 리소스 정책 관리 권한 추가
      policyCustomResourceRole.addToPolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "bedrock-agentcore:PutResourcePolicy",
            "bedrock-agentcore:GetResourcePolicy",
            "bedrock-agentcore:DeleteResourcePolicy",
          ],
          resources: [gateway.gatewayArn],
        })
      );

      // boto3 1.42.69로 Lambda layer 생성
      const boto3Layer = new lambda.LayerVersion(this, "Boto3Layer", {
        code: lambda.Code.fromAsset(path.join(__dirname, "../lambda"), {
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: [
              "bash",
              "-c",
              [
                "pip install boto3==1.42.69 -t /asset-output/python",
              ].join(" && "),
            ],
          },
        }),
        compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
        description: "boto3 1.42.69 for AgentCore Gateway policy management",
      });

      // gateway 리소스 정책을 관리하는 사용자 지정 리소스 Lambda
      const gatewayPolicyCustomResource = new lambda.Function(
        this,
        "GatewayPolicyCustomResource",
        {
          runtime: lambda.Runtime.PYTHON_3_12,
          handler: "index.handler",
          layers: [boto3Layer],
          code: lambda.Code.fromInline(`
import json
import boto3
import cfnresponse

bedrock_agentcore = boto3.client('bedrock-agentcore-control')

def handler(event, context):
    try:
        request_type = event['RequestType']
        gateway_id = event['ResourceProperties']['GatewayId']
        vpc_id = event['ResourceProperties']['VpcId']
        gateway_arn = event['ResourceProperties']['GatewayArn']

        if request_type in ['Create', 'Update']:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowInvokeFromVPC",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "bedrock-agentcore:InvokeGateway",
                        "Resource": gateway_arn,
                        "Condition": {
                            "StringEquals": {
                                "aws:SourceVpc": vpc_id
                            }
                        }
                    }
                ]
            }

            bedrock_agentcore.put_resource_policy(
                resourceArn=gateway_arn,
                policy=json.dumps(policy)
            )

            cfnresponse.send(event, context, cfnresponse.SUCCESS,
                           {'PolicyApplied': 'true'})

        elif request_type == 'Delete':
            try:
                bedrock_agentcore.delete_resource_policy(
                    resourceArn=gateway_arn
                )
            except bedrock_agentcore.exceptions.ResourceNotFoundException:
                pass  # Policy already deleted

            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

    except Exception as e:
        print(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED,
                       {'Error': str(e)})
`),
          role: policyCustomResourceRole,
          timeout: cdk.Duration.minutes(2),
        }
      );

      // 사용자 지정 리소스 생성
      const gatewayPolicy = new cdk.CustomResource(
        this,
        "GatewayVpcPolicy",
        {
          serviceToken: gatewayPolicyCustomResource.functionArn,
          properties: {
            GatewayId: gateway.gatewayId,
            VpcId: vpc.vpcId,
            GatewayArn: gateway.gatewayArn,
          },
        }
      );

      // gateway 생성 후 정책이 적용되도록 보장
      gatewayPolicy.node.addDependency(gateway);

    // policy engine 생성
    const agentCorePolicyEngine = new AgentCorePolicyEngine(this, "AgentCorePolicyEngine", {
      policyEngineName: `enterprise_mcp_policy_engine`,
      description: "Policy engine for AgentCore Enterprise MCP Gateway",
      region: this.region,
      gatewayRole: gatewayRole,
    });

    // engine에 policy를 먼저 추가
    const policyEngineStatementInventoryTool = `permit (principal is AgentCore::OAuthUser, action in [AgentCore::Action::"inventory-tool", AgentCore::Action::"weather-tool"],resource == AgentCore::Gateway::"${gateway.gatewayArn}") when {principal.hasTag("user_tag") && principal.getTag("user_tag") == "admin_user"};`;
    const policyEngineStatementWeatherTool = `permit (principal is AgentCore::OAuthUser,action in [AgentCore::Action::"weather-tool"],resource == AgentCore::Gateway::"${gateway.gatewayArn}") when {principal.hasTag("user_tag") && principal.getTag("user_tag") == "regular_user"};`;
    const policyEngineStatementUserDetailsTool = `permit (principal is AgentCore::OAuthUser,action in [AgentCore::Action::"user-details-tool"],resource == AgentCore::Gateway::"${gateway.gatewayArn}") when {principal.hasTag("user_tag")};`;

    // 관리자 사용자 policy 추가(inventory 및 weather 도구)
    const adminUserPolicy = agentCorePolicyEngine.addPolicy(
      "admin_user_policy",
      "Policy for admin users to access inventory and weather tools",
      policyEngineStatementInventoryTool
    );

    // 일반 사용자 policy 추가(weather 도구만)
    const regularUserPolicy = agentCorePolicyEngine.addPolicy(
      "regular_user_policy",
      "Policy for regular users to access weather tool only",
      policyEngineStatementWeatherTool
    );

    // user details 도구 policy 추가(user_tag가 있는 사용자만 접근 가능)
    const userDetailsToolPolicy = agentCorePolicyEngine.addPolicy(
      "user_details_policy",
      "Policy for users to access user details tool only if they have user_tag defined",
      policyEngineStatementUserDetailsTool
    );

    // 모든 policy가 추가된 후 gateway와 연결
    agentCorePolicyEngine.associateWithGateway(gateway.gatewayId, 'ENFORCE');
    agentCorePolicyEngine.node.addDependency(interceptorLambda); // policy engine 연결 전에 interceptor Lambda가 생성되도록 보장

    // 모든 Cedar policy 이후에 gateway VPC 리소스 정책이 적용되도록 보장
    gatewayPolicy.node.addDependency(agentCorePolicyEngine);

    // =============================================================================
    // 출력
    // =============================================================================

    new cdk.CfnOutput(this, "UserPoolId", {
      value: userPool.userPoolId,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "UserPoolArn", {
      value: userPool.userPoolArn,
      description: "Cognito User Pool ARN",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: cognitoDomain.domainName,
      description: "Cognito Domain",
    });

    new cdk.CfnOutput(this, "CognitoDomainUrl", {
      value: `https://${cognitoDomain.domainName}.auth.${this.region}.amazoncognito.com`,
      description: "Cognito Domain URL",
    });

    new cdk.CfnOutput(this, "DiscoveryUrl", {
      value: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`,
      description: "OIDC Discovery URL",
    });

    new cdk.CfnOutput(this, "VSCodeClientId", {
      value: vscodeClient.userPoolClientId,
      description: "VS Code Client ID",
    });

    new cdk.CfnOutput(this, "EndpointUrl", {
      value: endpointUrl,
      description: "Service Endpoint URL",
    });

    new cdk.CfnOutput(this, "ProxyLambdaName", {
      value: proxyLambda.functionName,
      description: "MCP Proxy Lambda Function Name",
    });

    new cdk.CfnOutput(this, "VSCodeMcpConfig", {
      value: JSON.stringify(
        {
          servers: {
            [`enterprise-mcp-server`]: {
              type: "http",
              url: endpointUrl + "/mcp",
            },
          },
        },
        null,
        2
      ),
      description: "VS Code MCP Configuration (add to .vscode/mcp.json)",
    });

    new cdk.CfnOutput(this, "Gateway", {
      value: gateway.gatewayId,
      description: "Gateway ID",
    });

    new cdk.CfnOutput(this, "PreTokenGenerationLambdaName", {
      value: preTokenGenerationLambda.functionName,
      description: "Pre-Token Generation Lambda Function Name",
    });

    new cdk.CfnOutput(this, "PreTokenGenerationLambdaArn", {
      value: preTokenGenerationLambda.functionArn,
      description: "Pre-Token Generation Lambda Function ARN",
    });
  }
}
