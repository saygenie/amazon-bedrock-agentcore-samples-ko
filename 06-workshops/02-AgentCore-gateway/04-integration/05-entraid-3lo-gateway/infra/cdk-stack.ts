// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwv2integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import { Construct } from "constructs";
import * as path from "path";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";

export class CdkEntraIdStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================================
    // 모든 EntraID + OAuth 구성은 CDK context에서 가져옴
    // (설정 스크립트 또는 -c 플래그로 지정). 여러 독립 배포를 지원함
    // =========================================================================
    const entraConfig = {
      tenantId: this.requireContext("entra:tenantId"),
      appAClientId: this.requireContext("entra:appAClientId"),
      appBClientId: this.requireContext("entra:appBClientId"),
      // "ciam" 또는 "standard" - discovery/authority URL 결정
      tenantType: (this.node.tryGetContext("entra:tenantType") as string) || "standard",
      // CIAM tenant에만 필요(예: "your-domain")
      ciamDomain: (this.node.tryGetContext("entra:ciamDomain") as string) || "",
      // CLI를 통해 사전 생성
      oauthProviderArn: this.requireContext("oauth:providerArn"),
      oauthSecretArn: this.requireContext("oauth:secretArn"),
      oauthCallbackUrl: this.requireContext("oauth:callbackUrl"),
      // Credential provider 이름(SPA 표시용)
      oauthProviderName: (this.node.tryGetContext("oauth:providerName") as string) || "entraid-weather-3lo",
    };

    // tenant 유형에 따라 URL 파생
    const isCiam = entraConfig.tenantType === "ciam";
    const authorityHost = isCiam
      ? `${entraConfig.ciamDomain}.ciamlogin.com`
      : "login.microsoftonline.com";
    const issuerHost = isCiam
      ? `${entraConfig.tenantId}.ciamlogin.com`
      : "login.microsoftonline.com";

    const discoveryUrl = `https://${authorityHost}/${entraConfig.tenantId}/v2.0/.well-known/openid-configuration`;
    const weatherScope = `api://${entraConfig.appBClientId}/weather.read`;
    const authority = `https://${authorityHost}/${entraConfig.tenantId}`;
    const issuer = `https://${issuerHost}/${entraConfig.tenantId}/v2.0`;

    // 리소스 이름의 고유 접미사(배포 간 충돌 방지)
    const suffix = (this.node.tryGetContext("resourceSuffix") as string) || "";
    const nameSuffix = suffix ? `-${suffix}` : "";

    // =========================================================================
    // IAM OIDC IDENTITY PROVIDER(EntraID → STS AssumeRoleWithWebIdentity)
    // =========================================================================
    // IAM OIDC provider는 계정 내 issuer URL별로 고유함
    // 같은 tenant에 여러 스택을 배포할 경우 기존 provider ARN을 전달
    const existingOidcArn = this.node.tryGetContext("oidc:providerArn") as string;
    const oidcProvider = existingOidcArn
      ? iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
          this,
          "EntraIdOidcProvider",
          existingOidcArn
        )
      : new iam.OpenIdConnectProvider(this, "EntraIdOidcProvider", {
          url: issuer,
          clientIds: [entraConfig.appAClientId],
        });

    const authOnboardingRole = new iam.Role(this, "AuthOnboardingWebRole", {
      roleName: `auth-onboarding-web-role${nameSuffix}`,
      assumedBy: new iam.WebIdentityPrincipal(
        oidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            [`${issuerHost}/${entraConfig.tenantId}/v2.0:aud`]:
              entraConfig.appAClientId,
          },
        }
      ),
      maxSessionDuration: cdk.Duration.hours(1),
      inlinePolicies: {
        agentcoreIdentity: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                "bedrock-agentcore:GetResourceOauth2Token",
                "bedrock-agentcore:CompleteResourceTokenAuth",
              ],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default/oauth2credentialprovider/*`,
              ],
            }),
            new iam.PolicyStatement({
              actions: ["secretsmanager:GetSecretValue"],
              resources: [
                `arn:aws:secretsmanager:${this.region}:${this.account}:secret:bedrock-agentcore-identity!default/oauth2/*`,
              ],
              conditions: {
                "ForAnyValue:StringEquals": {
                  "aws:CalledVia": ["bedrock-agentcore.amazonaws.com"],
                },
              },
            }),
          ],
        }),
      },
    });

    // =========================================================================
    // LAMBDA 함수
    // =========================================================================
    const lambdaRole = new iam.Role(this, "McpProxyLambdaRole", {
      roleName: `mcp-proxy-entraid-lambda-role${nameSuffix}`,
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock-agentcore:InvokeGateway"],
        // 이 계정/리전의 모든 gateway로 범위 지정. 이 시점에는 gateway가 나중에
        // 생성되므로 스택에서 gateway ARN을 사용할 수 없음. 프로덕션에서는 Lazy 값을
        // 사용하거나 gateway 생성 후 addToPolicy를 사용
        resources: [
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:gateway/*`,
        ],
      })
    );

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["secretsmanager:GetSecretValue"],
        resources: [entraConfig.oauthSecretArn],
      })
    );

    // Elicitation 인터셉터 Lambda
    const elicitationInterceptorLambda = new lambda.Function(
      this,
      "ElicitationInterceptor",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: "elicitation_interceptor.lambda_handler",
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda"),
          {
            bundling: {
              image: lambda.Runtime.PYTHON_3_12.bundlingImage,
              command: [
                "bash",
                "-c",
                "cp elicitation_interceptor.py /asset-output/elicitation_interceptor.py",
              ],
              local: {
                tryBundle(outputDir: string) {
                  const fs = require("fs");
                  fs.copyFileSync(
                    path.join(
                      __dirname,
                      "../lambda/elicitation_interceptor.py"
                    ),
                    path.join(outputDir, "elicitation_interceptor.py")
                  );
                  return true;
                },
              },
            },
          }
        ),
        timeout: cdk.Duration.seconds(10),
        memorySize: 128,
        environment: {
          AUTH_ONBOARDING_URL: "", // API Gateway 생성 후 설정
        },
      }
    );

    // 프록시 Lambda
    const proxyLambda = new lambda.Function(this, "McpProxyLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../lambda"),
        {
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: [
              "bash",
              "-c",
              "pip install boto3 -t /asset-output && cp mcp_proxy_lambda.py /asset-output/lambda_function.py",
            ],
            local: {
              tryBundle(outputDir: string) {
                const fs = require("fs");
                const { execSync } = require("child_process");
                fs.copyFileSync(
                  path.join(__dirname, "../lambda/mcp_proxy_lambda.py"),
                  path.join(outputDir, "lambda_function.py")
                );
                execSync(`pip install boto3 -t "${outputDir}" --quiet`);
                return true;
              },
            },
          },
        }
      ),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(29),
      memorySize: 256,
      environment: {
        GATEWAY_URL: "",
        ENTRA_TENANT_ID: entraConfig.tenantId,
        ENTRA_APP_A_CLIENT_ID: entraConfig.appAClientId,
        ENTRA_DISCOVERY_URL: discoveryUrl,
        CALLBACK_LAMBDA_URL: "",
        AUTH_ONBOARDING_ROLE_ARN: authOnboardingRole.roleArn,
        OAUTH_CREDENTIAL_PROVIDER_NAME: entraConfig.oauthProviderName,
        ENTRA_WEATHER_SCOPE: weatherScope,
        // Authority URL - Lambda가 authorize/token 엔드포인트에 사용
        ENTRA_AUTHORITY: authority,
        ENTRA_AUTHORITY_HOST: authorityHost,
        ENTRA_TENANT_TYPE: entraConfig.tenantType,
      },
    });

    // Weather REST API Lambda(기본 실행 역할만 필요하며 AWS API를 호출하지 않음)
    const weatherApiLambda = new lambda.Function(this, "WeatherApiLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../lambda"),
        {
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: [
              "bash",
              "-c",
              "cp weather_api_lambda.py /asset-output/lambda_function.py",
            ],
            local: {
              tryBundle(outputDir: string) {
                const fs = require("fs");
                fs.copyFileSync(
                  path.join(__dirname, "../lambda/weather_api_lambda.py"),
                  path.join(outputDir, "lambda_function.py")
                );
                return true;
              },
            },
          },
        }
      ),
      timeout: cdk.Duration.seconds(10),
      memorySize: 128,
    });

    // =========================================================================
    // API GATEWAY HTTP API
    // =========================================================================
    const httpApi = new apigwv2.HttpApi(this, "McpProxyApi", {
      apiName: `mcp-entraid-proxy-api${nameSuffix}`,
      description: "MCP OAuth Proxy with EntraID - API Gateway HTTP API",
    });

    const proxyIntegration = new apigwv2integrations.HttpLambdaIntegration(
      "ProxyIntegration",
      proxyLambda,
      { payloadFormatVersion: apigwv2.PayloadFormatVersion.VERSION_1_0 }
    );

    const weatherIntegration = new apigwv2integrations.HttpLambdaIntegration(
      "WeatherIntegration",
      weatherApiLambda,
      { payloadFormatVersion: apigwv2.PayloadFormatVersion.VERSION_1_0 }
    );

    httpApi.addRoutes({
      path: "/weather",
      methods: [apigwv2.HttpMethod.GET],
      integration: weatherIntegration,
    });

    httpApi.addRoutes({
      path: "/auth",
      methods: [apigwv2.HttpMethod.GET],
      integration: proxyIntegration,
    });
    httpApi.addRoutes({
      path: "/auth/callback",
      methods: [apigwv2.HttpMethod.GET],
      integration: proxyIntegration,
    });
    httpApi.addRoutes({
      path: "/{proxy+}",
      methods: [apigwv2.HttpMethod.ANY],
      integration: proxyIntegration,
    });
    httpApi.addRoutes({
      path: "/",
      methods: [apigwv2.HttpMethod.ANY],
      integration: proxyIntegration,
    });

    const apiEndpoint = httpApi.apiEndpoint;

    proxyLambda.addEnvironment("CALLBACK_LAMBDA_URL", apiEndpoint);
    elicitationInterceptorLambda.addEnvironment(
      "AUTH_ONBOARDING_URL",
      cdk.Fn.join("", [apiEndpoint, "/auth"])
    );

    // =========================================================================
    // AGENTCORE GATEWAY
    // =========================================================================
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
              ],
              resources: ["*"],
              effect: iam.Effect.ALLOW,
            }),
            new iam.PolicyStatement({
              actions: ["secretsmanager:GetSecretValue"],
              resources: ["*"],
              effect: iam.Effect.ALLOW,
              conditions: {
                "ForAnyValue:StringEquals": {
                  "aws:CalledVia": ["bedrock-agentcore.amazonaws.com"],
                },
              },
            }),
          ],
        }),
      },
    });

    const gateway = new agentcore.Gateway(this, "AgentCoreMcpGateway", {
      gatewayName: `agentcore-mcp-gateway-entraid${nameSuffix}`,
      description:
        "AgentCore Gateway with EntraID inbound + outbound 3LO auth",
      protocolConfiguration: agentcore.GatewayProtocol.mcp({
        searchType: agentcore.McpGatewaySearchType.SEMANTIC,
        supportedVersions: [
          agentcore.MCPProtocolVersion.MCP_2025_03_26,
          agentcore.MCPProtocolVersion.MCP_2025_06_18,
          "2025-11-25" as agentcore.MCPProtocolVersion,
        ],
      }),
      role: gatewayRole,
      // DEBUG exception 수준은 개발 중 문제 해결에 도움이 됨
      // 프로덕션에서는 GatewayExceptionLevel.NONE 또는 GatewayExceptionLevel.ERROR 사용
      exceptionLevel: agentcore.GatewayExceptionLevel.DEBUG,
      authorizerConfiguration: agentcore.GatewayAuthorizer.usingCustomJwt({
        discoveryUrl: discoveryUrl,
        allowedAudience: [entraConfig.appAClientId],
      }),
      interceptorConfigurations: [
        agentcore.LambdaInterceptor.forResponse(elicitationInterceptorLambda),
      ],
    });

    // =========================================================================
    // OAuth 3LO를 사용하는 OPENAPI TARGET
    // =========================================================================
    // OpenAPI spec - 제공되면 배포별 파일을 사용하고, 아니면 기본값 사용
    const openapiPath = (this.node.tryGetContext("openapi:path") as string)
      || path.join(__dirname, "../openapi/weather-api.json");
    const weatherApiSchema = agentcore.ApiSchema.fromLocalAsset(openapiPath);

    const weatherTarget = gateway.addOpenApiTarget("WeatherApiTarget", {
      gatewayTargetName: "weather-api",
      description: "Weather REST API with EntraID 3LO auth",
      apiSchema: weatherApiSchema,
      credentialProviderConfigurations: [
        agentcore.GatewayCredentialProvider.fromOauthIdentityArn({
          providerArn: entraConfig.oauthProviderArn,
          secretArn: entraConfig.oauthSecretArn,
          scopes: [weatherScope],
        }),
      ],
    });

    // Escape hatch: grantType 및 defaultReturnUrl 삽입
    const cfnTarget = weatherTarget.node.defaultChild as cdk.CfnResource;
    cfnTarget.addPropertyOverride(
      "CredentialProviderConfigurations.0.CredentialProvider.OauthCredentialProvider.GrantType",
      "AUTHORIZATION_CODE"
    );
    cfnTarget.addPropertyOverride(
      "CredentialProviderConfigurations.0.CredentialProvider.OauthCredentialProvider.DefaultReturnUrl",
      cdk.Fn.join("", [apiEndpoint, "/auth/callback"])
    );

    const rolePolicy = gatewayRole.node.tryFindChild("DefaultPolicy");
    if (rolePolicy) {
      cfnTarget.addDependency(rolePolicy.node.defaultChild as cdk.CfnResource);
    }

    proxyLambda.addEnvironment("GATEWAY_URL", gateway.gatewayUrl ?? "");

    // =========================================================================
    // 출력
    // =========================================================================
    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: apiEndpoint,
      description: "API Gateway HTTP API Endpoint",
    });

    new cdk.CfnOutput(this, "GatewayId", {
      value: gateway.gatewayId,
    });

    new cdk.CfnOutput(this, "GatewayUrl", {
      value: gateway.gatewayUrl ?? "N/A",
    });

    new cdk.CfnOutput(this, "OAuthCallbackUrl", {
      value: entraConfig.oauthCallbackUrl,
      description: "Callback URL to register as redirect URI in EntraID App B",
    });

    new cdk.CfnOutput(this, "AuthOnboardingUrl", {
      value: cdk.Fn.join("", [apiEndpoint, "/auth"]),
      description: "URL for the auth onboarding web app",
    });

    new cdk.CfnOutput(this, "VSCodeMcpConfig", {
      value: cdk.Fn.join("", [
        '{"servers":{"agentcore-weather-entraid":{"type":"http","url":"',
        apiEndpoint,
        '/mcp","headers":{"MCP-Protocol-Version":"2025-11-25"}}}}',
      ]),
      description: "VS Code MCP Configuration (add to .vscode/mcp.json)",
    });
  }

  /** 필수 CDK context 값을 읽고, 없으면 오류를 발생시킵니다. */
  private requireContext(key: string): string {
    const value = this.node.tryGetContext(key) as string;
    if (!value) {
      throw new Error(
        `Missing required CDK context: -c ${key}=<value>`
      );
    }
    return value;
  }
}
