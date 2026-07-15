"""
Actor ID 추출용 JWT 헬퍼 함수

Cognito JWT 토큰에서 actor_id를 추출하는 유틸리티를 제공합니다.
Lab 2~5에서 에이전트 호출을 특정 사용자/actor까지 추적하는 데 사용합니다.
"""

import jwt
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def get_jwt_claims(access_token: str, region: str, user_pool_id: str, skip_verification: bool = True) -> Dict[str, str]:
    """
    Cognito JWT 토큰에서 claim을 추출합니다.

    인자:
        access_token: Cognito 인증의 JWT 토큰
        region: Cognito Pool이 생성된 AWS 리전
        user_pool_id: Cognito User Pool ID
        skip_verification: True이면 서명 검증 없이 디코딩(Lab 기본값: True)

    반환:
        actor_id, sub, email, username, token_use, aud 키가 포함된 딕셔너리

    예:
        >>> claims = get_jwt_claims(token, "us-west-2", "us-west-2_abc123xyz")
        >>> actor_id = claims['actor_id']  # Cognito 사용자 이름
    """
    try:
        # Workshop Lab에서는 검증을 건너뛰고 JWT 디코딩
        claims = jwt.decode(access_token, options={"verify_signature": False})

        # 사용자 이름 claim에서 actor_id 추출
        # Cognito는 사용자 이름을 'cognito:username'에 저장
        actor_id = claims.get("cognito:username", claims.get("sub", "unknown-user"))

        return {
            "actor_id": actor_id,
            "sub": claims.get("sub"),
            "email": claims.get("email"),
            "token_use": claims.get("token_use"),
            "aud": claims.get("aud"),
            "username": claims.get("cognito:username"),
        }

    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        raise
    except Exception as e:
        logger.error(f"Error extracting JWT claims: {e}")
        raise


def extract_actor_id_from_jwt(access_token: str) -> str:
    """
    JWT 토큰에서 actor_id만 빠르게 추출하는 유틸리티입니다.

    인자:
        access_token: Cognito의 JWT 토큰

    반환:
        토큰의 actor_id(사용자 이름)
    """
    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
        return claims.get("cognito:username", claims.get("sub", "unknown-user"))
    except Exception as e:
        logger.error(f"Error extracting actor_id from JWT: {e}")
        raise
