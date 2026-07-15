# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""CDK 애플리케이션 진입점입니다."""

import aws_cdk as cdk

from config import CdkConfig
from stacks.lattice_stack import LatticeStack
from stacks.gateway_infra_stack import GatewayInfraStack
from stacks.ping_federate_stack import PingFederateStack
from stacks.vpc_stack import VpcStack

app = cdk.App()

config = CdkConfig(
    aws_account=app.node.try_get_context("aws_account") or None,
)

env = cdk.Environment(
    account=config.aws_account,
    region=config.aws_region,
)

# 스택 1: VPC(깔끔한 삭제를 위해 별도 구성, Lattice ENI 해제에는 최대 8시간 소요 가능)
vpc_stack = VpcStack(
    app,
    "PrivateIdpVpcStack",
    env=env,
)

# 스택 2: PingFederate IdP(ECS Fargate, 내부 ALB, 퍼블릭 ACM 인증서)
ping_stack = PingFederateStack(
    app,
    "PrivateIdpPingFederateStack",
    vpc=vpc_stack.vpc,
    config=config,
    env=env,
)
ping_stack.add_dependency(vpc_stack)

# 스택 3: Gateway 인프라(MCP Echo Lambda + IAM 역할)
gateway_infra_stack = GatewayInfraStack(
    app,
    "PrivateIdpGatewayInfraStack",
    env=env,
)

# 스택 4: VPC Lattice(선택 사항, --self-managed-lattice 플래그를 지정한 경우에만 사용)
if config.deploy_lattice:
    lattice_stack = LatticeStack(
        app,
        "PrivateIdpLatticeStack",
        vpc=vpc_stack.vpc,
        alb=ping_stack.alb,
        alb_listener=ping_stack.alb_listener,
        suffix=config.suffix,
        env=env,
    )
    lattice_stack.add_dependency(ping_stack)

app.synth()
