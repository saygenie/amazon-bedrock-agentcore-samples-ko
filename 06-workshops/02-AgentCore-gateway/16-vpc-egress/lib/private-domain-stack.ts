import * as cdk from "aws-cdk-lib/core";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as elbv2targets from "aws-cdk-lib/aws-elasticloadbalancingv2-targets";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53targets from "aws-cdk-lib/aws-route53-targets";
import * as s3 from "aws-cdk-lib/aws-s3";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

/**
 * Public Certificate가 있는 Internal ALB 뒤에서 REST API를 실행하는 EC2
 * 인스턴스와 VPC 내부에서 ALB를 확인하는 Route 53 Private Hosted Zone을 배포합니다.
 *
 * Private Hosted Zone 이름은 Public Certificate가 적용되는 대상 도메인과
 * 일치하며, apex Alias 레코드는 ALB를 가리킵니다. AgentCore Gateway의
 * 관리형 Resource Gateway는 VPC의 Private DNS를 통해 이 도메인을 확인하므로
 * routingDomain이 필요하지 않습니다.
 */
export interface PrivateDomainStackProps extends cdk.StackProps {
	vpc: ec2.IVpc;
	/** Public Certificate가 적용되는 FQDN(예: "internal.example.com") */
	privateDomain: string;
	publicCertArn: string;
}

export class PrivateDomainStack extends cdk.Stack {
	public readonly instance: ec2.Instance;
	public readonly ec2Sg: ec2.SecurityGroup;

	constructor(scope: Construct, id: string, props: PrivateDomainStackProps) {
		super(scope, id, props);

		const publicCert = acm.Certificate.fromCertificateArn(
			this,
			"PublicCert",
			props.publicCertArn,
		);

		// --- HTTP :8000에서 간단한 REST API를 실행하는 EC2 인스턴스 ---
		this.ec2Sg = new ec2.SecurityGroup(this, "Ec2Sg", {
			vpc: props.vpc,
			description: "Simple API EC2 instance",
			allowAllOutbound: true,
		});
		this.ec2Sg.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);

		this.instance = new ec2.Instance(this, "SimpleApiInstance", {
			vpc: props.vpc,
			instanceType: ec2.InstanceType.of(
				ec2.InstanceClass.T3,
				ec2.InstanceSize.MICRO,
			),
			machineImage: ec2.MachineImage.latestAmazonLinux2023(),
			vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
			securityGroup: this.ec2Sg,
			ssmSessionPermissions: true,
		});

		this.instance.addUserData(
			"#!/bin/bash",
			"dnf update -y",
			"dnf install -y python3-pip",
			"pip3 install fastapi uvicorn",
			"mkdir -p /opt/simple-api",
			"cat > /opt/simple-api/app.py << 'PYEOF'",
			"from fastapi import FastAPI, Depends, Header, HTTPException",
			"",
			'API_KEY = "vpc-egress-lab-api-key"',
			"",
			"",
			"def verify_api_key(x_api_key: str = Header(...)):",
			"    if x_api_key != API_KEY:",
			'        raise HTTPException(status_code=403, detail="Invalid API key")',
			"",
			"",
			"app = FastAPI()",
			"items: list[dict] = []",
			"",
			"",
			'@app.get("/health")',
			"def health():",
			'    return {"status": "ok"}',
			"",
			"",
			'@app.get("/items", dependencies=[Depends(verify_api_key)])',
			"def list_items():",
			"    return items",
			"",
			"",
			'@app.post("/items", dependencies=[Depends(verify_api_key)])',
			"def create_item(item: dict):",
			"    items.append(item)",
			"    return item",
			"PYEOF",
			"cat > /etc/systemd/system/simple-api.service << 'SVCEOF'",
			"[Unit]",
			"Description=Simple API Server",
			"After=network.target",
			"",
			"[Service]",
			"Type=simple",
			"WorkingDirectory=/opt/simple-api",
			"ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000",
			"Restart=always",
			"",
			"[Install]",
			"WantedBy=multi-user.target",
			"SVCEOF",
			"systemctl daemon-reload",
			"systemctl enable simple-api",
			"systemctl start simple-api",
		);

		// --- Public Certificate가 있는 Internal ALB ---
		const albSg = new ec2.SecurityGroup(this, "AlbSg", {
			vpc: props.vpc,
			description: "Internal ALB with public cert - HTTPS from VPC",
			allowAllOutbound: true,
		});
		albSg.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
		albSg.addIngressRule(
			ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
			ec2.Port.tcp(443),
			"Allow HTTPS from VPC",
		);

		this.ec2Sg.addIngressRule(
			albSg,
			ec2.Port.tcp(8000),
			"Allow traffic from ALB",
		);

		const accessLogBucket = new s3.Bucket(this, "AlbAccessLogs", {
			removalPolicy: cdk.RemovalPolicy.DESTROY,
			autoDeleteObjects: true,
			enforceSSL: true,
			encryption: s3.BucketEncryption.S3_MANAGED,
			lifecycleRules: [{ expiration: cdk.Duration.days(30) }],
		});

		const alb = new elbv2.ApplicationLoadBalancer(this, "InternalAlb", {
			vpc: props.vpc,
			internetFacing: false,
			securityGroup: albSg,
			vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
		});

		alb.logAccessLogs(accessLogBucket, "alb-logs");

		const httpsListener = alb.addListener("HttpsListener", {
			port: 443,
			protocol: elbv2.ApplicationProtocol.HTTPS,
			certificates: [publicCert],
		});

		httpsListener.addTargets("Ec2Target", {
			port: 8000,
			protocol: elbv2.ApplicationProtocol.HTTP,
			targets: [new elbv2targets.InstanceTarget(this.instance, 8000)],
			healthCheck: {
				path: "/health",
				port: "8000",
				healthyHttpCodes: "200",
			},
		});

		// --- Route 53 Private Hosted Zone ---
		// Zone 이름은 대상 FQDN과 일치합니다. apex Alias 레코드가 ALB를
		// 가리키므로 VPC 내부에서 `https://<privateDomain>`이 ALB Private IP로
		// 확인됩니다. AgentCore Resource Gateway는 Private DNS로 이 도메인을
		// 확인하므로 routingDomain 우회 방식이 필요하지 않습니다.
		const privateZone = new route53.PrivateHostedZone(this, "PrivateZone", {
			zoneName: props.privateDomain,
			vpc: props.vpc,
		});

		new route53.ARecord(this, "AlbAliasRecord", {
			zone: privateZone,
			target: route53.RecordTarget.fromAlias(
				new route53targets.LoadBalancerTarget(alb),
			),
		});

		// --- 출력 ---
		new cdk.CfnOutput(this, "AlbDnsName", {
			value: alb.loadBalancerDnsName,
			description: "Internal ALB DNS (private IPs behind this DNS)",
		});

		new cdk.CfnOutput(this, "AlbSgId", {
			value: albSg.securityGroupId,
		});

		new cdk.CfnOutput(this, "Ec2InstanceId", {
			value: this.instance.instanceId,
			description: "SSM Session Manager: aws ssm start-session --target <id>",
		});

		new cdk.CfnOutput(this, "Ec2PrivateIp", {
			value: this.instance.instancePrivateIp,
		});

		new cdk.CfnOutput(this, "PrivateDomain", {
			value: props.privateDomain,
			description:
				"Private domain (Alias → ALB, resolvable via Private DNS inside the VPC)",
		});

		new cdk.CfnOutput(this, "ApiKey", {
			value: "vpc-egress-lab-api-key",
			description: "API key for the simple REST API (x-api-key header)",
		});

		NagSuppressions.addStackSuppressions(this, [
			{
				id: "AwsSolutions-IAM4",
				reason: "SSM managed policy required for Session Manager access",
			},
			{ id: "AwsSolutions-IAM5", reason: "SSM managed policies use wildcards" },
			{
				id: "AwsSolutions-EC26",
				reason: "EBS encryption not needed for lab instance",
			},
			{
				id: "AwsSolutions-EC28",
				reason: "Detailed monitoring not needed for lab instance",
			},
			{
				id: "AwsSolutions-EC29",
				reason: "Lab instance does not need termination protection",
			},
			{
				id: "AwsSolutions-S1",
				reason: "Access log bucket does not need its own access logs",
			},
			{
				id: "AwsSolutions-EC23",
				reason: "ALB is internal, SG allows VPC CIDR only",
			},
			{
				id: "CdkNagValidationFailure",
				reason: "Security group uses VPC CIDR intrinsic reference",
			},
		]);
	}
}
