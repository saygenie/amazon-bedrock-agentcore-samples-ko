"""
AWS re:Invent 2025 AIML301 Workshop 구성 모듈
AgentCore SRE 사용 사례 - 중앙 집중식 구성

정적 구성 값을 모듈 수준 변수로 제공합니다.
사용자는 값을 직접 가져오고 출처를 확인할 수 있습니다.

사용법:
    from lab_helpers.config import AWS_REGION, MODEL_ID, WORKSHOP_NAME
    from lab_helpers import config

    print(config.AWS_REGION)
    print(config.MODEL_ID)
"""

# ============================================================================
# AWS 구성
# ============================================================================
AWS_REGION = "us-west-2"  # 정상 동작하는 배포에 맞게 us-west-2로 변경
AWS_PROFILE = None

# ============================================================================
# Bedrock 모델 구성
# ============================================================================
# Global CRIS(Cross-Region Inference Server)를 통한 Claude Sonnet 4
# 모델 ID: global.anthropic.claude-sonnet-4-20250514-v1:0
# - 20만 토큰 컨텍스트 창
# - 출시일: 2025년 5월 22일
# MODEL_ID = "global.anthropic.claude-sonnet-4-20250514-v1:0"
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
# ============================================================================
# Workshop 구성
# ============================================================================
WORKSHOP_NAME = "aiml301_sre_agentcore"
