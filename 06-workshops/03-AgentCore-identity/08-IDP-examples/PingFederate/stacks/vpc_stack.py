# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""PingFederate와 VPC Lattice가 공유하는 네트워크 인프라용 VPC 스택입니다."""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class VpcStack(Stack):
    """퍼블릭 및 프라이빗 서브넷이 있는 VPC를 생성합니다.

    독립적으로 삭제할 수 있도록 이 스택을 PingFederateStack과 분리합니다.
    VPC Lattice Resource Gateway가 생성한 ENI는 삭제 후 해제까지 최대 8시간이
    걸릴 수 있습니다. VPC를 분리하면 다른 스택을 먼저 삭제한 후 나중에 VPC
    삭제를 다시 시도할 수 있습니다.
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        """VPC 스택을 초기화합니다."""
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=False,
                ),
            ],
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join([s.subnet_id for s in self.vpc.private_subnets]),
            description="Private subnet IDs (for AgentCore Identity managedVpcResource)",
        )
