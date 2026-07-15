import * as cdk from 'aws-cdk-lib/core';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as elbv2targets from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

/**
 * Public ACM Certificate를 사용하는 우회용 ALB입니다. 이 ALB는 AgentCore가
 * 검증할 수 있는 공개 신뢰 TLS 종료 지점을 제공합니다.
 *
 * 고객의 기존 Private Certificate ALB와 동일한 백엔드 EC2 인스턴스를 대상으로
 * 하여 AgentCore용 대체 진입점을 제공합니다.
 */
export interface PublicCertProxyStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  publicCertArn: string;
  backendInstance: ec2.Instance;
}

export class PublicCertProxyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: PublicCertProxyStackProps) {
    super(scope, id, props);

    const publicCert = acm.Certificate.fromCertificateArn(this, 'PublicCert', props.publicCertArn);

    // --- Public Certificate가 있는 Internal ALB ---
    const albSg = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc: props.vpc,
      description: 'Public cert proxy ALB - HTTPS from VPC',
      allowAllOutbound: true,
    });
    albSg.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
    albSg.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      'Allow HTTPS from VPC',
    );

    // 백엔드 EC2 Security Group이 이미 VPC CIDR에서 8000 포트를 허용하며
    // 이 ALB도 포함합니다. 추가 인바운드 규칙은 필요하지 않고, 추가할 경우
    // 스택 간 순환 종속성이 생성됩니다.

    const accessLogBucket = new s3.Bucket(this, 'AlbAccessLogs', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [{ expiration: cdk.Duration.days(30) }],
    });

    const alb = new elbv2.ApplicationLoadBalancer(this, 'PublicCertAlb', {
      vpc: props.vpc,
      internetFacing: false,
      securityGroup: albSg,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    alb.logAccessLogs(accessLogBucket, 'alb-logs');

    // Public Certificate가 있는 HTTPS Listener - TLS를 종료하고 EC2에 HTTP 전달
    const httpsListener = alb.addListener('HttpsListener', {
      port: 443,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      certificates: [publicCert],
    });

    httpsListener.addTargets('BackendTarget', {
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new elbv2targets.InstanceTarget(props.backendInstance, 8000)],
      healthCheck: {
        path: '/health',
        port: '8000',
        healthyHttpCodes: '200',
      },
    });

    // --- 출력 ---
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: alb.loadBalancerDnsName,
      description: 'Public cert ALB DNS (publicly resolvable, use as routingDomain)',
    });

    new cdk.CfnOutput(this, 'AlbSgId', {
      value: albSg.securityGroupId,
    });

    NagSuppressions.addStackSuppressions(this, [
      { id: 'AwsSolutions-S1', reason: 'Access log bucket does not need its own access logs' },
      { id: 'AwsSolutions-EC23', reason: 'ALB is internal, SG allows VPC CIDR only' },
      { id: 'CdkNagValidationFailure', reason: 'Security group uses VPC CIDR intrinsic reference' },
    ]);
  }
}
