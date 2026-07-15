# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Gateway 인프라 스택으로, MCP Echo Lambda와 Gateway용 IAM 역할을 구성합니다."""

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class GatewayInfraStack(Stack):
    """AgentCore Gateway 데모에 필요한 인프라를 배포합니다.

    생성하는 리소스:
    - 최소 구성의 MCP Echo Lambda(Gateway 대상)
    - Gateway용 IAM 역할(bedrock-agentcore.amazonaws.com 신뢰)
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # --- MCP Echo Lambda ---
        self.mcp_echo_fn = lambda_.Function(
            self,
            "McpEchoFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/mcp_echo"),
            timeout=Duration.seconds(30),
            memory_size=128,
        )

        # --- Gateway IAM 역할 ---
        # Gateway ID를 알기 전에도 역할을 사용할 수 있도록 조건 블록을 생략함
        # 프로덕션 환경에서는 Gateway 생성 후 SourceAccount 및 SourceArn 조건 추가
        self.gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
        )

        self.mcp_echo_fn.grant_invoke(self.gateway_role)

        # --- 출력 ---
        CfnOutput(
            self,
            "McpEchoLambdaArn",
            value=self.mcp_echo_fn.function_arn,
            description="Lambda ARN for the MCP Echo gateway target",
        )
        CfnOutput(
            self,
            "GatewayRoleArn",
            value=self.gateway_role.role_arn,
            description="IAM role ARN for the AgentCore Gateway",
        )
