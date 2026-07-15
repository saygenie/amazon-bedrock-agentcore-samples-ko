#!/usr/bin/env python3
"""Pay for API - Fun Facts seller stack용 CDK app 진입점입니다."""

import os

import aws_cdk as cdk

from seller_stack import AgentCorePaymentsFunFactsSellerStack

app = cdk.App()

# Region은 일반적인 CDK 확인 순서를 따릅니다.
#   CDK_DEFAULT_REGION -> AWS_REGION -> AWS CLI profile region.
# 기본 AgentCore Payments region과 일치하도록 us-west-2를 기본값으로 사용합니다.
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-west-2")),
)

AgentCorePaymentsFunFactsSellerStack(
    app,
    "AgentCorePaymentsFunFactsSellerStack",
    env=env,
    description="AgentCore Payments sample — Fun Facts x402 seller (pay per API call)",
)

app.synth()
