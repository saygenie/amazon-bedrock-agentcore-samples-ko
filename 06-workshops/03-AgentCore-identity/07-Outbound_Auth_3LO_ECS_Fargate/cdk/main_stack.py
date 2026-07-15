# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""에이전트 애플리케이션용 기본 CDK 스택."""

from aws_cdk import Stack
from constructs import Construct

from cdk.constructs import Agent
from config import CdkConfig


class AgentStack(Stack):
    """Agent construct를 배포하는 기본 스택."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        config: CdkConfig,
        workload_identity_name: str,
        **kwargs,
    ):
        """에이전트 스택을 초기화한다."""
        super().__init__(scope, id, **kwargs)

        Agent(
            self,
            "Agent",
            config=config,
            workload_identity_name=workload_identity_name,
        )
