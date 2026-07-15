# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""AgentCore Workload Identity 스택."""

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from constructs import Construct


class IdentityStack(Stack):
    """자격 증명 리전에 배포되는 AgentCore Workload Identity 스택."""

    def __init__(self, scope: Construct, id: str, suffix: str, **kwargs):
        """자격 증명 스택을 초기화한다."""
        super().__init__(scope, id, **kwargs)

        self.workload_identity = bedrockagentcore.CfnWorkloadIdentity(
            self,
            "WorkloadIdentity",
            name=f"agent-id-{suffix}",
        )

        CfnOutput(
            self,
            "WorkloadIdentityName",
            value=self.workload_identity.name,
            description="AgentCore Workload Identity Name",
            export_name=f"{id}-WorkloadIdentityName",
        )
