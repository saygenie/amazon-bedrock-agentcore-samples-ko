# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""GitHub 도구 설정."""

from pydantic import BaseModel, Field


class GitHubConfig(BaseModel):
    """GitHub 도구 설정."""

    session_binding_url: str = Field(..., description="Session Binding URL for the customer-managed service")
    github_api_base: str = Field(..., description="GitHub API base URL")
    provider_name: str = Field(..., description="Provider name in AgentCore Identity")
    workload_access_token: str = Field(..., description="AgentCore workload access token")
    aws_region: str = Field(default="eu-central-1", description="AWS region")
