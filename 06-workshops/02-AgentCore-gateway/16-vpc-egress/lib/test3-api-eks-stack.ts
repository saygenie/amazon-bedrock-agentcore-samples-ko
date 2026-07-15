import * as cdk from "aws-cdk-lib/core";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as eks from "aws-cdk-lib/aws-eks";
import * as route53 from "aws-cdk-lib/aws-route53";
import { KubectlV31Layer } from "@aws-cdk/lambda-layer-kubectl-v31";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

export interface ApiEksStackProps extends cdk.StackProps {
	clusterName: string;
	kubectlRoleArn: string;
	kubectlSecurityGroupId: string;
	kubectlPrivateSubnetIds: string[];
	vpc: ec2.IVpc;
	certificateArn: string;
	/** Public Certificate가 적용되는 FQDN(예: "internal.example.com") */
	privateDomain: string;
}

export class ApiEksStack extends cdk.Stack {
	constructor(scope: Construct, id: string, props: ApiEksStackProps) {
		super(scope, id, props);

		const cluster = eks.Cluster.fromClusterAttributes(this, "ImportedCluster", {
			clusterName: props.clusterName,
			kubectlRoleArn: props.kubectlRoleArn,
			kubectlSecurityGroupId: props.kubectlSecurityGroupId,
			kubectlPrivateSubnetIds: props.kubectlPrivateSubnetIds,
			vpc: props.vpc,
			kubectlLayer: new KubectlV31Layer(this, "KubectlLayer"),
		});

		// --- Kubernetes 리소스 ---
		const namespace = cluster.addManifest("ApiNamespace", {
			apiVersion: "v1",
			kind: "Namespace",
			metadata: { name: "rest-api" },
		});

		const deployment = cluster.addManifest("ApiDeployment", {
			apiVersion: "apps/v1",
			kind: "Deployment",
			metadata: {
				name: "rest-api",
				namespace: "rest-api",
			},
			spec: {
				replicas: 1,
				selector: { matchLabels: { app: "rest-api" } },
				template: {
					metadata: { labels: { app: "rest-api" } },
					spec: {
						containers: [
							{
								name: "rest-api",
								image: "python:3.12-slim",
								command: [
									"sh",
									"-c",
									'pip install fastapi uvicorn && python -c "\n' +
										"from fastapi import FastAPI\n" +
										"app = FastAPI()\n" +
										"items = []\n" +
										"@app.get('/health')\n" +
										"def health():\n" +
										"    return {'status': 'ok'}\n" +
										"@app.get('/items')\n" +
										"def list_items():\n" +
										"    return items\n" +
										"@app.post('/items')\n" +
										"def create_item(item: dict):\n" +
										"    items.append(item)\n" +
										"    return item\n" +
										"import uvicorn\n" +
										"uvicorn.run(app, host='0.0.0.0', port=8080)\n" +
										'"',
								],
								ports: [{ containerPort: 8080 }],
							},
						],
					},
				},
			},
		});
		deployment.node.addDependency(namespace);

		// AWS annotation이 포함된 Kubernetes LoadBalancer 유형 Service를 통해 NLB 생성
		const privateSubnetIds = props.kubectlPrivateSubnetIds.join(",");
		const nlbService = cluster.addManifest("ApiNlbService", {
			apiVersion: "v1",
			kind: "Service",
			metadata: {
				name: "rest-api-nlb",
				namespace: "rest-api",
				annotations: {
					"service.beta.kubernetes.io/aws-load-balancer-type": "nlb",
					"service.beta.kubernetes.io/aws-load-balancer-scheme": "internal",
					"service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
					"service.beta.kubernetes.io/aws-load-balancer-ssl-cert":
						props.certificateArn,
					"service.beta.kubernetes.io/aws-load-balancer-ssl-ports": "443",
					"service.beta.kubernetes.io/aws-load-balancer-subnets":
						privateSubnetIds,
				},
			},
			spec: {
				type: "LoadBalancer",
				selector: { app: "rest-api" },
				ports: [
					{
						name: "https",
						port: 443,
						targetPort: 8080,
						protocol: "TCP",
					},
				],
			},
		});
		nlbService.node.addDependency(deployment);

		// kubectl Lambda 제한 시간을 피하도록 스택 삭제 시 K8s manifest를 유지함
		// NLB 프로비저닝 해제에 Lambda의 15분 제한을 초과해 cdk destroy가 중단될 수 있음
		// 이 리소스는 EKS Cluster가 삭제될 때 정리됨
		for (const manifest of [namespace, deployment, nlbService]) {
			manifest.node.findAll().forEach((child) => {
				if (child instanceof cdk.CfnResource) {
					child.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
				}
			});
		}

		// --- Route 53 Private Hosted Zone ---
		// VPC에 연결된 빈 Zone입니다. K8s 관리형 NLB가 프로비저닝되면
		// Notebook에서 이를 가리키는 Alias A 레코드를 추가합니다.
		// 배포 시점에는 NLB DNS를 알 수 없습니다. AgentCore Resource Gateway는
		// Private DNS로 이 도메인을 확인하므로 routingDomain이 필요하지 않습니다.
		const privateZone = new route53.PrivateHostedZone(this, "PrivateZone", {
			zoneName: props.privateDomain,
			vpc: props.vpc,
		});

		new cdk.CfnOutput(this, "PrivateDomain", {
			value: props.privateDomain,
			description:
				"Private domain — notebook adds an Alias A record to the NLB",
		});

		new cdk.CfnOutput(this, "PrivateZoneId", {
			value: privateZone.hostedZoneId,
			description:
				"Route 53 private hosted zone ID (used by the notebook to UPSERT the NLB alias record)",
		});

		NagSuppressions.addStackSuppressions(
			this,
			[
				{
					id: "AwsSolutions-IAM4",
					reason: "EKS kubectl provider uses CDK-managed policies",
				},
				{
					id: "AwsSolutions-IAM5",
					reason: "EKS kubectl provider uses CDK-managed wildcard permissions",
				},
				{
					id: "AwsSolutions-L1",
					reason: "Lambda runtime is managed by CDK EKS construct",
				},
			],
			true,
		);
	}
}
