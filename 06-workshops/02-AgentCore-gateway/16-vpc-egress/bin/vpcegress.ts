#!/usr/bin/env node
import * as cdk from "aws-cdk-lib/core";
import { AwsSolutionsChecks } from "cdk-nag";
import { VpcegressStack } from "../lib/vpcegress-stack";
import { McpEcsStack } from "../lib/test1-mcp-ecs-stack";
import { McpEksStack } from "../lib/test2-mcp-eks-stack";
import { ApiEksStack } from "../lib/test3-api-eks-stack";
import { PrivateApigwStack } from "../lib/test4-private-apigw-stack";
import { PrivateApiPublicCertStack } from "../lib/test5-private-api-public-cert-stack";
import { PublicDnsPrivateCertStack } from "../lib/test6-public-dns-private-cert-stack";
import { PrivateDnsPrivateCertStack } from "../lib/test7-private-dns-private-cert-stack";
import { PrivateCertBackendStack } from "../lib/private-cert-backend-stack";
// PublicCertProxyStack 제거 - 이제 Notebook에서 boto3로 프록시 ALB 생성
import { PrivateDomainStack } from "../lib/private-domain-stack";
import { ShortLivedCaStack } from "../lib/shared/short-lived-ca-stack";
import { EksClusterStack } from "../lib/shared/eks-cluster-stack";
import { PrivateCaStack } from "../lib/shared/private-ca-stack";
import { AgentCoreGatewayStack } from "../lib/shared/agentcore-gateway-stack";
import { VpcPeeringStack } from "../lib/vpc-peering-stack";

const app = new cdk.App();
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

const accountA = process.env.ACCOUNT_A_ID || app.node.tryGetContext("accountA");
const accountB = process.env.ACCOUNT_B_ID || app.node.tryGetContext("accountB");
const baseDomain =
	app.node.tryGetContext("baseDomain") || "egress-test.example.com";
const privateDomain =
	app.node.tryGetContext("privateDomain") || `internal.${baseDomain}`;
const publicCertArn = app.node.tryGetContext("publicCertArn") || "";
const hostedZoneId = app.node.tryGetContext("hostedZoneId") || "";
if (!accountA) {
	throw new Error(
		"Account A ID is required. Set ACCOUNT_A_ID env var or pass -c accountA=<id>\n" +
			"Example: ACCOUNT_A_ID=123456789012 cdk deploy ...\n" +
			"Or:      cdk deploy -c accountA=123456789012 ...",
	);
}

const envA = { account: accountA, region: "us-west-2" };

// 기존 VPC 스택
const vpcUsWest2 = new VpcegressStack(app, "VpcegressStack-USWest2", {
	env: envA,
	vpcCidr: "10.0.0.0/16",
});

const vpcUsEast1 = new VpcegressStack(app, "VpcegressStack-USEast1", {
	env: { account: accountA, region: "us-east-1" },
	vpcCidr: "10.1.0.0/16",
	crossRegionReferences: true,
});

// Peering Lab: us-east-1의 Private API Gateway + VPC Peering
new PrivateApigwStack(app, "PeeringApigw-USEast1", {
	env: { account: accountA, region: "us-east-1" },
	vpc: vpcUsEast1.vpc,
	peerVpcCidr: "10.0.0.0/16",
	privateDnsEnabled: false,
});

new VpcPeeringStack(app, "VpcPeeringStack", {
	env: envA,
	crossRegionReferences: true,
	vpc: vpcUsWest2.vpc,
	peerVpcId: vpcUsEast1.vpc.vpcId,
	peerRegion: "us-east-1",
	peerVpcCidr: "10.1.0.0/16",
	localVpcCidr: "10.0.0.0/16",
	peerPrivateRouteTableIds: vpcUsEast1.vpc.privateSubnets.map(
		(s) => s.routeTable.routeTableId,
	),
});

if (accountB) {
	const vpcAccountB = new VpcegressStack(
		app,
		"VpcegressStack-USWest2-AccountB",
		{
			env: { account: accountB, region: "us-west-2" },
			vpcCidr: "10.2.0.0/16",
		},
	);

	// Cross-account Lab: Account B의 Private API Gateway
	new PrivateApigwStack(app, "CrossAccountApigw-AccountB", {
		env: { account: accountB, region: "us-west-2" },
		vpc: vpcAccountB.vpc,
	});
}

// ECS의 MCP Server(publicCertArn 필요)
if (publicCertArn) {
	new McpEcsStack(app, "McpEcs", {
		env: envA,
		vpc: vpcUsWest2.vpc,
		certificateArn: publicCertArn,
		privateDomain,
	});
}

// 공유 EKS Cluster
const eksCluster = new EksClusterStack(app, "SharedEksCluster", {
	env: envA,
	vpc: vpcUsWest2.vpc,
});

// EKS의 MCP Server(NLB TLS용 NGINX Ingress + publicCertArn 필요)
if (publicCertArn) {
	new McpEksStack(app, "McpEks", {
		env: envA,
		clusterName: eksCluster.cluster.clusterName,
		kubectlRoleArn: eksCluster.cluster.kubectlRole!.roleArn,
		kubectlSecurityGroupId:
			eksCluster.cluster.kubectlSecurityGroup!.securityGroupId,
		kubectlPrivateSubnetIds: eksCluster.cluster.kubectlPrivateSubnets!.map(
			(s) => s.subnetId,
		),
		vpc: vpcUsWest2.vpc,
		certificateArn: publicCertArn,
		privateDomain,
	});

	// EKS의 REST API
	new ApiEksStack(app, "ApiEks", {
		env: envA,
		clusterName: eksCluster.cluster.clusterName,
		kubectlRoleArn: eksCluster.cluster.kubectlRole!.roleArn,
		kubectlSecurityGroupId:
			eksCluster.cluster.kubectlSecurityGroup!.securityGroupId,
		kubectlPrivateSubnetIds: eksCluster.cluster.kubectlPrivateSubnets!.map(
			(s) => s.subnetId,
		),
		vpc: vpcUsWest2.vpc,
		certificateArn: publicCertArn,
		privateDomain,
	});
}

// Private API Gateway
new PrivateApigwStack(app, "PrivateApigw", {
	env: envA,
	vpc: vpcUsWest2.vpc,
});

// 테스트 5: Private DNS + Public Certificate
new PrivateApiPublicCertStack(app, "Test5-PrivateApiPublicCert", {
	env: envA,
	vpc: vpcUsWest2.vpc,
	baseDomain,
	publicCertArn,
});

// 공유 Private CA(테스트 6 및 7용)
const privateCa = new PrivateCaStack(app, "SharedPrivateCa", {
	env: envA,
	baseDomain,
});

// 테스트 6: Public DNS + Private Certificate
new PublicDnsPrivateCertStack(app, "Test6-PublicDnsPrivateCert", {
	env: envA,
	vpc: vpcUsWest2.vpc,
	baseDomain,
	certificateAuthorityArn: privateCa.caArn,
	hostedZoneId,
});

// 공유 AgentCore Gateway(Cognito M2M 인증)
new AgentCoreGatewayStack(app, "SharedAgentCoreGateway", {
	env: envA,
});

// 테스트 7: Private DNS + Private Certificate(ALB 우회 방식에 publicCertArn 필요)
if (publicCertArn) {
	new PrivateDnsPrivateCertStack(app, "Test7-PrivateDnsPrivateCert", {
		env: envA,
		vpc: vpcUsWest2.vpc,
		baseDomain,
		certificateAuthorityArn: privateCa.caArn,
		publicCertArn,
	});
}

// Private Domain Lab: Public Certificate가 있는 ALB + Private Hosted Zone(Private DNS)
if (publicCertArn) {
	new PrivateDomainStack(app, "PrivateDomain", {
		env: envA,
		vpc: vpcUsWest2.vpc,
		privateDomain,
		publicCertArn,
	});
}

// Private Certificate Authority Lab용 단기 Private CA(월 50달러)
const shortLivedCa = new ShortLivedCaStack(app, "ShortLivedPrivateCa", {
	env: envA,
	baseDomain,
});

// Private CA Lab: Private CA Certificate를 사용하는 백엔드(EC2가 HTTPS:443 제공)
new PrivateCertBackendStack(app, "PrivateCaBackend", {
	env: envA,
	vpc: vpcUsWest2.vpc,
	baseDomain,
	certificateAuthorityArn: shortLivedCa.caArn,
});

// Self-signed Lab: 자체 서명 Certificate를 사용하는 백엔드
new PrivateCertBackendStack(app, "SelfSignedBackend", {
	env: envA,
	vpc: vpcUsWest2.vpc,
	baseDomain,
});
