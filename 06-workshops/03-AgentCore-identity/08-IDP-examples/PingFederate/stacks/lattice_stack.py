# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""프라이빗 IdP 연결을 위한 Resource Gateway 및 리소스 구성을 포함하는 VPC Lattice 스택입니다."""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_vpclattice as vpclattice
from constructs import Construct


class LatticeStack(Stack):
    """내부 PingFederate ALB를 AgentCore Identity에 노출하는 VPC Lattice 리소스를 생성합니다.

    이 스택이 생성하는 리소스:
    1. Resource Gateway: Lattice 트래픽의 수신 지점 역할을 하는 VPC 내 ENI
    2. Resource Configuration: AgentCore Identity가 OAuth2 자격 증명 공급자의
       ``selfManagedLatticeResource`` 속성을 통해 비공개로 접근할 수 있도록
       PingFederate ALB(DNS + 포트)를 설명하는 구성
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        alb: elbv2.IApplicationLoadBalancer,
        alb_listener: elbv2.IApplicationListener,
        suffix: str,
        **kwargs,
    ):
        """Lattice 스택을 초기화합니다."""
        super().__init__(scope, id, **kwargs)

        # Lattice에서 ALB로 향하는 HTTPS 트래픽을 허용하는 Resource Gateway 보안 그룹
        gw_sg = ec2.SecurityGroup(
            self,
            "ResourceGatewaySg",
            vpc=vpc,
            description="VPC Lattice resource gateway security group",
            allow_all_outbound=True,
        )
        gw_sg.add_ingress_rule(ec2.Peer.ipv4(vpc.vpc_cidr_block), ec2.Port.tcp(443), "HTTPS from VPC")

        # Resource Gateway: PingFederate가 실행되는 VPC의 프라이빗 서브넷에 ENI 배치
        private_subnet_ids = [s.subnet_id for s in vpc.private_subnets]

        resource_gateway = vpclattice.CfnResourceGateway(
            self,
            "ResourceGateway",
            name=f"ping-idp-gw-{suffix}",
            vpc_identifier=vpc.vpc_id,
            subnet_ids=private_subnet_ids,
            security_group_ids=[gw_sg.security_group_id],
            ip_address_type="IPV4",
        )

        # Resource Configuration: DNS 이름으로 내부 ALB를 가리키는 SINGLE 리소스
        # AgentCore Identity는 resourceConfigurationIdentifier(rcfg-xxx)를 사용해
        # VPC Lattice를 통해 PingFederate에 비공개로 접근
        resource_config = vpclattice.CfnResourceConfiguration(
            self,
            "ResourceConfiguration",
            name=f"ping-idp-rcfg-{suffix}",
            resource_configuration_type="SINGLE",
            protocol_type="TCP",
            port_ranges=["443"],
            resource_gateway_id=resource_gateway.attr_id,
            resource_configuration_definition=vpclattice.CfnResourceConfiguration.ResourceConfigurationDefinitionProperty(
                dns_resource=vpclattice.CfnResourceConfiguration.DnsResourceProperty(
                    domain_name=alb.load_balancer_dns_name,
                    ip_address_type="IPV4",
                ),
            ),
            allow_association_to_sharable_service_network=True,
        )
        resource_config.add_dependency(resource_gateway)

        # AgentCore Identity에 필요한 리소스 구성 ID(rcfg-xxx)
        self.resource_configuration_id = resource_config.attr_id

        CfnOutput(
            self,
            "ResourceGatewayId",
            value=resource_gateway.attr_id,
            description="VPC Lattice Resource Gateway ID",
        )
        CfnOutput(
            self,
            "ResourceConfigurationId",
            value=resource_config.attr_id,
            description="VPC Lattice Resource Configuration ID — use this in the AgentCore Identity OAuth2 provider",
        )
