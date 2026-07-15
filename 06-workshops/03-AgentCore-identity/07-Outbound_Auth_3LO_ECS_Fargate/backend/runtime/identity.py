# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""워크로드 액세스 토큰을 위한 AgentCore Identity 통합."""

import logging

from bedrock_agentcore.services.identity import IdentityClient

logger = logging.getLogger(__name__)


def get_workload_access_token(user_id: str, workload_identity_name: str | None, aws_region: str | None) -> str | None:
    """현재 호출에 사용할 워크로드 액세스 토큰을 AgentCore Identity에서 가져온다.

    인수:
        user_id: 토큰 요청에 사용할 사용자 식별자
        workload_identity_name: AgentCore 워크로드 자격 증명 이름(설정되지 않은 경우 None)
        aws_region: IdentityClient의 AWS 리전

    반환값:
        워크로드 액세스 토큰 문자열. 자격 증명이 설정되지 않은 경우 None

    """
    if not workload_identity_name or not aws_region:
        logger.info("Identity not configured, skipping token acquisition")
        return None

    client = IdentityClient(aws_region)
    response = client.get_workload_access_token(workload_identity_name, user_id=user_id)
    return str(response["workloadAccessToken"])
