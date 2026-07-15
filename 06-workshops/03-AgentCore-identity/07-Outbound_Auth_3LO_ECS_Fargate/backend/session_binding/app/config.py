# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""OAuth 사이드카 서비스의 설정 관리."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경 변수에서 불러온 애플리케이션 설정."""

    log_level: str = "INFO"
    environment: str = "unknown"
    service_name: str = "session-binding"
    aws_region: str = "eu-central-1"
    identity_aws_region: str | None = None

    @property
    def identity_region(self) -> str:
        """Identity 서비스 리전을 가져오고, 없으면 AWS 리전을 사용한다."""
        return self.identity_aws_region or self.aws_region

    model_config = {"case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    """캐시된 설정 인스턴스를 가져온다."""
    return Settings()
