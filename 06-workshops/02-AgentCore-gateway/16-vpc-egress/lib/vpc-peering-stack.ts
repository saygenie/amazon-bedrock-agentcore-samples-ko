import * as cdk from "aws-cdk-lib/core";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as cr from "aws-cdk-lib/custom-resources";
import * as iam from "aws-cdk-lib/aws-iam";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

export interface VpcPeeringStackProps extends cdk.StackProps {
  /** 로컬 VPC(요청자 측) */
  vpc: ec2.IVpc;
  /** Peer VPC ID */
  peerVpcId: string;
  /** Peer 리전(예: 'us-east-1') */
  peerRegion: string;
  /** Peer VPC CIDR(로컬 VPC의 Route용) */
  peerVpcCidr: string;
  /** 로컬 VPC CIDR(Peer VPC의 Route용) */
  localVpcCidr: string;
  /** Peer VPC Private Subnet의 Route Table ID(반환 Route 추가용) */
  peerPrivateRouteTableIds: string[];
}

export class VpcPeeringStack extends cdk.Stack {
  public readonly peeringConnectionId: string;

  constructor(scope: Construct, id: string, props: VpcPeeringStackProps) {
    super(scope, id, props);

    // 1. VPC Peering Connection 생성(요청자 측)
    const peering = new ec2.CfnVPCPeeringConnection(this, "VpcPeering", {
      vpcId: props.vpc.vpcId,
      peerVpcId: props.peerVpcId,
      peerRegion: props.peerRegion,
      tags: [{ key: "Name", value: "agentcore-peering-lab" }],
    });
    this.peeringConnectionId = peering.ref;

    // 2. Peer 리전에서 Peering 수락(Cross-region은 명시적 수락 필요)
    const acceptPeering = new cr.AwsCustomResource(this, "AcceptPeering", {
      onCreate: {
        service: "EC2",
        action: "acceptVpcPeeringConnection",
        parameters: { VpcPeeringConnectionId: peering.ref },
        region: props.peerRegion,
        physicalResourceId: cr.PhysicalResourceId.of("accept-peering"),
      },
      policy: cr.AwsCustomResourcePolicy.fromStatements([
        new iam.PolicyStatement({
          actions: ["ec2:AcceptVpcPeeringConnection"],
          resources: ["*"],
        }),
      ]),
    });
    acceptPeering.node.addDependency(peering);

    // 3. 로컬 VPC Private Subnet에 Peering을 통해 Peer VPC CIDR로 가는 Route 추가
    props.vpc.privateSubnets.forEach((subnet, i) => {
      const route = new ec2.CfnRoute(this, `RouteLocal${i}`, {
        routeTableId: subnet.routeTable.routeTableId,
        destinationCidrBlock: props.peerVpcCidr,
        vpcPeeringConnectionId: peering.ref,
      });
      route.addDependency(peering);
    });

    // 4. Peer VPC Private Subnet에 Peering을 통해 로컬 VPC CIDR로 가는 Route 추가
    //    Route Table이 다른 리전에 있으므로 AwsCustomResource 사용
    props.peerPrivateRouteTableIds.forEach((rtId, i) => {
      const peerRoute = new cr.AwsCustomResource(this, `RoutePeer${i}`, {
        onCreate: {
          service: "EC2",
          action: "createRoute",
          parameters: {
            RouteTableId: rtId,
            DestinationCidrBlock: props.localVpcCidr,
            VpcPeeringConnectionId: peering.ref,
          },
          region: props.peerRegion,
          physicalResourceId: cr.PhysicalResourceId.of(`route-peer-${i}`),
        },
        onDelete: {
          service: "EC2",
          action: "deleteRoute",
          parameters: {
            RouteTableId: rtId,
            DestinationCidrBlock: props.localVpcCidr,
          },
          region: props.peerRegion,
        },
        policy: cr.AwsCustomResourcePolicy.fromStatements([
          new iam.PolicyStatement({
            actions: ["ec2:CreateRoute", "ec2:DeleteRoute"],
            resources: ["*"],
          }),
        ]),
      });
      peerRoute.node.addDependency(acceptPeering);
    });

    new cdk.CfnOutput(this, "PeeringConnectionId", {
      value: peering.ref,
    });

    NagSuppressions.addStackSuppressions(this, [
      {
        id: "AwsSolutions-IAM4",
        reason:
          "AWSLambdaBasicExecutionRole is required by AwsCustomResource Lambda",
      },
      {
        id: "AwsSolutions-IAM5",
        reason: "Custom resources need wildcard for cross-region EC2 API calls",
      },
      {
        id: "AwsSolutions-L1",
        reason: "Lambda runtime managed by AwsCustomResource construct",
      },
    ]);
  }
}
