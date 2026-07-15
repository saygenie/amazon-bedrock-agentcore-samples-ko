# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""ALB JWT 검증 및 사용자 추출 유틸리티."""

import logging
from functools import lru_cache

import httpx
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import HTTPException
from jwt import decode as jwt_decode
from jwt import get_unverified_header
from jwt.exceptions import PyJWTError

logger = logging.getLogger(__name__)


@lru_cache
def get_alb_public_key(key_url: str) -> ec.EllipticCurvePublicKey:
    """JWT 검증용 ALB 공개 키를 가져와 캐시한다."""
    response = httpx.get(key_url)
    response.raise_for_status()
    return load_pem_public_key(response.content)


def verify_alb_jwt(token: str, region: str) -> dict:
    """ALB JWT 서명을 검증하고 claim을 반환한다."""
    kid = get_unverified_header(token)["kid"]
    key_url = f"https://public-keys.auth.elb.{region}.amazonaws.com/{kid}"
    public_key = get_alb_public_key(key_url)
    return jwt_decode(token, public_key, algorithms=["ES256"])


def get_user_email_from_jwt(token: str, aws_region: str) -> str:
    """ALB OIDC JWT에서 사용자 식별자를 추출한다."""
    try:
        claims = verify_alb_jwt(token, aws_region)
        return claims["sub"]
    except (PyJWTError, KeyError, httpx.HTTPError) as e:
        logger.exception("Failed to verify ALB JWT")
        raise HTTPException(status_code=401, detail="Invalid ALB token") from e
