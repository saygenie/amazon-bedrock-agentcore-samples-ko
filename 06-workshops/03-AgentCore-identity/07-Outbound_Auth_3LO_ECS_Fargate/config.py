# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""CDK 배포 설정."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OidcConfig(BaseSettings):
    """ALB 인증용 OIDC 설정. 환경 변수 또는 .env 파일에서 불러온다."""

    model_config = SettingsConfigDict(env_prefix="OIDC_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    issuer: str = Field(description="OIDC issuer URL")
    authorization_endpoint: str = Field(description="Authorization endpoint URL")
    token_endpoint: str = Field(description="Token endpoint URL")
    user_info_endpoint: str = Field(
        default="https://graph.microsoft.com/oidc/userinfo",
        description="UserInfo endpoint URL",
    )
    secret_name: str = Field(
        default="agent-oauth/credentials",
        description="Secrets Manager secret name for client credential",
    )
    scope: str = Field(default="openid email profile", description="OAuth scopes")


class DnsConfig(BaseSettings):
    """Route 53용 DNS 설정. 환경 변수 또는 .env 파일에서 불러온다."""

    model_config = SettingsConfigDict(env_prefix="DNS_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    domain_name: str = Field(description="Domain name for the application")
    hosted_zone_id: str = Field(description="Route53 hosted zone ID")


class CdkConfig(BaseModel):
    """CDK 배포 설정."""

    aws_region: str = Field(default="eu-west-1", description="AWS region for main stack deployment")
    identity_aws_region: str = Field(default="eu-central-1", description="AWS region for identity stack deployment")
    aws_account: str | None = Field(default=None, description="AWS account ID")
    suffix: str = Field(default="sample", description="Suffix for resource naming")

    inference_profile_id: str = Field(
        default="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        description="Bedrock inference profile ID",
    )

    @property
    def model_id(self) -> str:
        """추론 프로파일에서 리전 접두사를 제거하여 모델 ID를 추출한다."""
        parts = self.inference_profile_id.split(".", 1)
        return parts[1] if len(parts) > 1 else parts[0]

    dns_config: DnsConfig = Field(
        default_factory=DnsConfig,
        description="DNS configuration for Route 53",
    )
    github_provider_name: str = Field(
        default="github-oauth-client-i5yd5",
        description="AgentCore Identity OAuth provider name for GitHub (registered in AgentCore Identity)",
    )
    github_api_base: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL",
    )
    oidc_config: OidcConfig = Field(
        default=OidcConfig(),
        description="Entra ID OIDC configuration for ALB authentication",
    )
