# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""애플리케이션 설정."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정."""

    log_level: str = "INFO"
    environment: str = "development"
    aws_region: str = "eu-west-1"
    identity_aws_region: str = "eu-central-1"
    s3_bucket_name: str
    inference_profile_id: str
    session_binding_url: str
    github_provider_name: str = "github"
    github_api_base: str = "https://api.github.com"
    workload_identity_name: str

    model_config = {"case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    """캐시된 설정 인스턴스를 가져온다."""
    return Settings()
