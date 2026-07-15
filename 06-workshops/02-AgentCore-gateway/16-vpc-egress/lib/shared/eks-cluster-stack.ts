import * as cdk from "aws-cdk-lib/core";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as eks from "aws-cdk-lib/aws-eks";
import * as iam from "aws-cdk-lib/aws-iam";
import { KubectlV31Layer } from "@aws-cdk/lambda-layer-kubectl-v31";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

export interface EksClusterStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
}

export class EksClusterStack extends cdk.Stack {
  public readonly cluster: eks.Cluster;

  constructor(scope: Construct, id: string, props: EksClusterStackProps) {
    super(scope, id, props);

    const clusterAdminRole = new iam.Role(this, "ClusterAdminRole", {
      assumedBy: new iam.AccountRootPrincipal(),
    });

    this.cluster = new eks.Cluster(this, "EksCluster", {
      vpc: props.vpc,
      version: eks.KubernetesVersion.V1_31,
      kubectlLayer: new KubectlV31Layer(this, "KubectlLayer"),
      defaultCapacity: 0,
      mastersRole: clusterAdminRole,
      endpointAccess: eks.EndpointAccess.PRIVATE,
      authenticationMode: eks.AuthenticationMode.API_AND_CONFIG_MAP,
      vpcSubnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
      clusterLogging: [
        eks.ClusterLoggingTypes.API,
        eks.ClusterLoggingTypes.AUDIT,
        eks.ClusterLoggingTypes.AUTHENTICATOR,
        eks.ClusterLoggingTypes.CONTROLLER_MANAGER,
        eks.ClusterLoggingTypes.SCHEDULER,
      ],
    });

    // 스택 간 Lambda가 kubectl 역할을 수임하도록 허용
    // 다른 스택에서 fromClusterAttributes로 manifest를 배포할 때 필요
    const kubectlRole = this.cluster.kubectlRole! as iam.Role;
    kubectlRole.assumeRolePolicy!.addStatements(
      new iam.PolicyStatement({
        actions: ["sts:AssumeRole"],
        principals: [new iam.AccountRootPrincipal()],
      }),
    );

    // 하위 스택의 kubectl Lambda가 EKS API에 접근하도록 허용
    // fromClusterAttributes는 Security Group이 자동 추가되지 않는 새 Lambda를 생성함
    this.cluster.clusterSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      "Allow kubectl Lambdas and bastion to reach EKS API",
    );

    this.cluster.addNodegroupCapacity("ManagedNodeGroup", {
      instanceTypes: [new ec2.InstanceType("t3.medium")],
      minSize: 1,
      maxSize: 3,
      desiredSize: 1,
      subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    // --- AWS Load Balancer Controller ---
    // Kubernetes Service annotation을 통한 NLB 생성에 필요
    const lbControllerSa = this.cluster.addServiceAccount("LbControllerSa", {
      name: "aws-load-balancer-controller",
      namespace: "kube-system",
    });

    // 공식 AWS Load Balancer Controller 문서에서 가져온 IAM 정책:
    // https://kubernetes-sigs.github.io/aws-load-balancer-controller/
    // Controller가 배포 시점에 ARN을 알 수 없는 NLB/ALB를 관리하므로
    // wildcard 리소스가 필요함
    const lbControllerPolicy = new iam.Policy(this, "LbControllerPolicy", {
      statements: [
        new iam.PolicyStatement({
          actions: [
            "ec2:DescribeAccountAttributes",
            "ec2:DescribeAddresses",
            "ec2:DescribeAvailabilityZones",
            "ec2:DescribeInternetGateways",
            "ec2:DescribeVpcs",
            "ec2:DescribeVpcPeeringConnections",
            "ec2:DescribeSubnets",
            "ec2:DescribeSecurityGroups",
            "ec2:DescribeInstances",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DescribeTags",
            "ec2:DescribeCoipPools",
            "ec2:GetCoipPoolUsage",
            "ec2:DescribeTargetGroups",
            "ec2:DescribeTargetHealth",
            "ec2:DescribeListeners",
            "ec2:DescribeRules",
            "elasticloadbalancing:DescribeLoadBalancers",
            "elasticloadbalancing:DescribeLoadBalancerAttributes",
            "elasticloadbalancing:DescribeListeners",
            "elasticloadbalancing:DescribeListenerCertificates",
            "elasticloadbalancing:DescribeSSLPolicies",
            "elasticloadbalancing:DescribeRules",
            "elasticloadbalancing:DescribeTargetGroups",
            "elasticloadbalancing:DescribeTargetGroupAttributes",
            "elasticloadbalancing:DescribeTargetHealth",
            "elasticloadbalancing:DescribeTags",
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          actions: [
            "ec2:AuthorizeSecurityGroupIngress",
            "ec2:RevokeSecurityGroupIngress",
            "ec2:CreateSecurityGroup",
            "ec2:DeleteSecurityGroup",
            "ec2:CreateTags",
            "ec2:DeleteTags",
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          actions: [
            "elasticloadbalancing:CreateLoadBalancer",
            "elasticloadbalancing:CreateTargetGroup",
            "elasticloadbalancing:CreateListener",
            "elasticloadbalancing:CreateRule",
            "elasticloadbalancing:DeleteLoadBalancer",
            "elasticloadbalancing:DeleteTargetGroup",
            "elasticloadbalancing:DeleteListener",
            "elasticloadbalancing:DeleteRule",
            "elasticloadbalancing:AddTags",
            "elasticloadbalancing:RemoveTags",
            "elasticloadbalancing:ModifyLoadBalancerAttributes",
            "elasticloadbalancing:ModifyTargetGroup",
            "elasticloadbalancing:ModifyTargetGroupAttributes",
            "elasticloadbalancing:ModifyListener",
            "elasticloadbalancing:ModifyRule",
            "elasticloadbalancing:SetIpAddressType",
            "elasticloadbalancing:SetSecurityGroups",
            "elasticloadbalancing:SetSubnets",
            "elasticloadbalancing:RegisterTargets",
            "elasticloadbalancing:DeregisterTargets",
            "elasticloadbalancing:SetWebAcl",
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          actions: ["iam:CreateServiceLinkedRole"],
          resources: ["*"],
          conditions: {
            StringEquals: {
              "iam:AWSServiceName": "elasticloadbalancing.amazonaws.com",
            },
          },
        }),
        new iam.PolicyStatement({
          actions: [
            "cognito-idp:DescribeUserPoolClient",
            "acm:ListCertificates",
            "acm:DescribeCertificate",
            "wafv2:GetWebACL",
            "wafv2:GetWebACLForResource",
            "wafv2:AssociateWebACL",
            "wafv2:DisassociateWebACL",
            "shield:GetSubscriptionState",
            "shield:DescribeProtection",
            "shield:CreateProtection",
            "shield:DeleteProtection",
          ],
          resources: ["*"],
        }),
      ],
    });

    lbControllerSa.role.attachInlinePolicy(lbControllerPolicy);

    const lbControllerChart = this.cluster.addHelmChart("LbController", {
      chart: "aws-load-balancer-controller",
      repository: "https://aws.github.io/eks-charts",
      namespace: "kube-system",
      release: "aws-load-balancer-controller",
      wait: true,
      values: {
        clusterName: this.cluster.clusterName,
        serviceAccount: {
          create: false,
          name: "aws-load-balancer-controller",
        },
        region: cdk.Stack.of(this).region,
        vpcId: props.vpc.vpcId,
      },
    });
    lbControllerChart.node.addDependency(lbControllerSa);

    // --- NGINX Ingress Controller(Service 없음 - NLB는 McpEksStack에서 생성) ---
    const nginxIngressChart = this.cluster.addHelmChart("NginxIngress", {
      chart: "ingress-nginx",
      repository: "https://kubernetes.github.io/ingress-nginx",
      namespace: "ingress-nginx",
      release: "ingress-nginx",
      createNamespace: true,
      values: {
        controller: {
          // 기본 LoadBalancer Service 비활성화 - AWS LB Controller의 named-port
          // 확인 문제를 피하기 위해 McpEksStack에서 숫자 targetPort로
          // NLB를 명시적으로 생성함
          service: {
            enabled: false,
          },
          config: {
            "use-forwarded-headers": "true",
          },
        },
      },
    });
    nginxIngressChart.node.addDependency(lbControllerChart);

    const suppressions = [
      {
        id: "AwsSolutions-IAM4",
        reason:
          "EKS managed policies are required by CDK EKS construct internals",
      },
      {
        id: "AwsSolutions-IAM5",
        reason:
          "Wildcard permissions required by CDK EKS construct internals and LB controller",
      },
      {
        id: "AwsSolutions-L1",
        reason:
          "Lambda runtime is managed by CDK EKS construct, cannot override",
      },
      {
        id: "AwsSolutions-SF1",
        reason:
          "Step Function is managed by CDK EKS construct, cannot override",
      },
      {
        id: "AwsSolutions-SF2",
        reason:
          "Step Function is managed by CDK EKS construct, cannot override",
      },
    ];
    NagSuppressions.addStackSuppressions(this, suppressions, true);
  }
}
