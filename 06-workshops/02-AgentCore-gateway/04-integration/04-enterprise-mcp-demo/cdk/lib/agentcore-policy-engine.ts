import { Construct } from 'constructs';
import { CustomResource, Duration } from 'aws-cdk-lib';
import { Function as LambdaFunction, Runtime, Code } from 'aws-cdk-lib/aws-lambda';
import { PolicyStatement, Effect, Policy, IRole } from 'aws-cdk-lib/aws-iam';
import * as path from 'path';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import * as lambda from "aws-cdk-lib/aws-lambda";

export interface AgentCorePolicyEngineProps {
  readonly policyEngineName: string;
  readonly description?: string;
  readonly region: string;
  readonly gatewayRole?: IRole;
}

export interface PolicyProps {
  readonly policyName: string;
  readonly description?: string;
  readonly policyStatement: string;
}

/**
 * Bedrock AgentCore Policy Engine 및 policy를 관리하는 construct입니다.
 *
 * 이 construct는 다음 작업을 수행합니다.
 * 1. Policy Engine 생성
 * 2. engine에 policy를 추가하는 메서드 제공
 * 3. 각 policy에 이름과 statement 지정
 */
export class AgentCorePolicyEngine extends Construct {
  public readonly policyFunction: LambdaFunction;
  public readonly policyEngineResource: CustomResource;
  public readonly policyEngineId: string;
  public readonly policyEngineArn: string;
  private readonly provider: Provider;
  private readonly policies: Map<string, CustomResource> = new Map();

  constructor(scope: Construct, id: string, props: AgentCorePolicyEngineProps) {
    super(scope, id);

    // policy engine 및 policy 작업을 처리할 Lambda 함수 생성
    this.policyFunction = new lambda.Function(
          this,
          "PolicyFunction",
          {
            runtime: Runtime.PYTHON_3_12,
            handler: 'lambda_function.lambda_handler',
            description: 'Lambda to setup Bedrock AgentCore policy Engine',
            code: Code.fromAsset(path.join(__dirname, "../lambda/agentcore-policy-engine/"), {
              bundling: {
                image: Runtime.PYTHON_3_12.bundlingImage,
                command: [
                  "bash",
                  "-c",
                  [
                    "pip install -r requirements.txt -t /asset-output",
                    "cp agentcore_policy_engine.py /asset-output/lambda_function.py",
                  ].join(" && "),
                ],
              },
            }),
            timeout: Duration.minutes(2),
            memorySize: 256,
          }
        );

    // policy engine 및 policy 관리 권한 부여
    this.policyFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['bedrock-agentcore:*'],
        resources: ['*'],
      }),
    );
    this.policyFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['iam:GetRole', 'iam:GetRolePolicy', 'iam:ListAttachedRolePolicies', 'iam:ListRolePolicies'],
        resources: ["arn:aws:iam::*:role/*"],
      }),
    );

    // gateway role이 제공된 경우 전달 권한 부여
    if (props.gatewayRole) {
      this.policyFunction.addToRolePolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ['iam:PassRole'],
          resources: [props.gatewayRole.roleArn],
        }),
      );
    }

    // 사용자 지정 리소스 공급자 생성
    this.provider = new Provider(this, 'Provider', {
      onEventHandler: this.policyFunction,
      logRetention: RetentionDays.ONE_MONTH,
    });

    // policy engine 생성
    this.policyEngineResource = new CustomResource(this, 'PolicyEngineResource', {
      serviceToken: this.provider.serviceToken,
      properties: {
        ResourceType: 'PolicyEngine',
        PolicyEngineName: props.policyEngineName,
        Description: props.description ?? `Policy Engine: ${props.policyEngineName}`,
        Region: props.region,
        Date: Date.now().toString(),
      },
    });

    // policy engine ID 추출
    this.policyEngineId = this.policyEngineResource.getAttString('PolicyEngineId');
    this.policyEngineArn = this.policyEngineResource.getAttString('PolicyEngineArn');
  }

  /**
   * policy engine에 policy를 추가합니다.
   * @param policyName - policy 이름
   * @param description - policy 설명
   * @param policyStatement - Cedar policy statement
   * @returns policy ID
   */
  public addPolicy(policyName: string, description: string, policyStatement: string): string {
    // 이 이름의 policy가 이미 있는지 확인
    if (this.policies.has(policyName)) {
      throw new Error(`Policy with name '${policyName}' already exists`);
    }

    // policy의 사용자 지정 리소스 생성
    const policyResource = new CustomResource(this, `Policy-${policyName}`, {
      serviceToken: this.provider.serviceToken,
      properties: {
        ResourceType: 'Policy',
        PolicyEngineId: this.policyEngineId,
        PolicyName: policyName,
        PolicyDescription: description,
        PolicyEngineArn: this.policyEngineArn,
        PolicyStatement: policyStatement,
        Date: Date.now().toString(),
      },
    });

    // engine 생성 후 policy가 생성되도록 보장
    policyResource.node.addDependency(this.policyEngineResource);

    // policy 리소스 저장
    this.policies.set(policyName, policyResource);

    // policy ID 반환
    return policyResource.getAttString('PolicyId');
  }

  /**
   * 이름으로 policy 리소스를 가져옵니다.
   * @param policyName - policy 이름
   * @returns policy의 CustomResource이며, 찾지 못하면 undefined
   */
  public getPolicy(policyName: string): CustomResource | undefined {
    return this.policies.get(policyName);
  }

  /**
   * 모든 policy 이름을 가져옵니다.
   * @returns policy 이름 배열
   */
  public getPolicyNames(): string[] {
    return Array.from(this.policies.keys());
  }

  public associateWithGateway(gatewayId: string, policyEngineConfigurationMode: string) {
    // policy engine을 gateway와 연결할 사용자 지정 리소스 생성
    const associationResource = new CustomResource(this, 'PolicyEngineGatewayAssociation', {
      serviceToken: this.provider.serviceToken,
      properties: {
        ResourceType: 'PolicyEngineGatewayAssociation',
        PolicyEngineId: this.policyEngineId,
        PolicyEngineArn: this.policyEngineArn,
        GatewayId: gatewayId,
        PolicyEngineConfigurationMode:policyEngineConfigurationMode,
        Date: Date.now().toString(),
      },
    });

    // policy engine 생성 후 연결되도록 보장
    associationResource.node.addDependency(this.policyEngineResource);

    // 모든 policy가 추가된 후 연결되도록 보장
    for (const policyResource of this.policies.values()) {
      associationResource.node.addDependency(policyResource);
    }

    return associationResource;
  }
}
