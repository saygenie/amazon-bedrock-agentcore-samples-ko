import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

RESOURCE_SERVER_ID = os.environ.get("RESOURCE_SERVER_ID", "")


def lambda_handler(event, context):
    """
    Cognito Pre-Token Generation Lambda Trigger입니다.
    사용자의 이메일을 기반으로 ID token에 사용자 지정 claim을 추가합니다.
    """

    logger.info(f"Pre-token generation event: {json.dumps(event)}")

    try:
        # 이벤트에서 사용자 속성 추출
        user_attributes = event["request"]["userAttributes"]
        email = user_attributes.get("email", "")

        logger.info(f"Processing token for user with email: {email}")

        # 이메일 도메인 또는 특정 규칙에 따라 사용자 지정 claim 추가
        # 예: 이메일 도메인을 기반으로 사용자 지정 태그 추가
        custom_tag = "default_user"

        if email == "vscode-admin@example.com":
        # 예: 이메일을 기반으로 사용자 지정 태그 설정
            custom_tag = "admin_user"
        elif email == "vscode-readonly@example.com":
            # 제한된 scope를 가진 테스트 사용자: mcp.read만 있고 mcp.write는 없음
            # scope가 부족한 요청을 gateway가 거부하는지 확인하는 데 사용
            custom_tag = "readonly_user"
        else:
            custom_tag = "regular_user"

        # ID token에 사용자 지정 claim 추가
        # 참고: ID token의 claimsOverrideDetails에 추가할 수 있음
        if "claimsOverrideDetails" not in event["response"] or event["response"]["claimsOverrideDetails"] is None:
            event["response"]["claimsOverrideDetails"] = {}

        if "claimsToAddOrOverride" not in event["response"]["claimsOverrideDetails"]:
            event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] = {}

        # ID token에 사용자 지정 claim 추가
        event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]["user_tag"] = custom_tag
        event["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"]["email"] = email

        # Access token에 사용자 지정 claim 추가(V2 trigger)
        if (
            "claimsAndScopeOverrideDetails" not in event["response"]
            or event["response"]["claimsAndScopeOverrideDetails"] is None
        ):
            event["response"]["claimsAndScopeOverrideDetails"] = {}

        if "accessTokenGeneration" not in event["response"]["claimsAndScopeOverrideDetails"]:
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"] = {}

        if "claimsToAddOrOverride" not in event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]:
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["claimsToAddOrOverride"] = {}

            # access token에 email, user_tag, aud 추가
        event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["claimsToAddOrOverride"][
            "email"
        ] = email
        event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["claimsToAddOrOverride"][
            "user_tag"
        ] = custom_tag
            # 프록시 Lambda와 AgentCore Gateway가 토큰의 적용 범위가 이 resource server인지
            # 확인할 수 있도록 audience claim을 삽입
            # Cognito에서는 aud가 현재 세션의 app client ID와 일치해야 함
        client_id = event.get("callerContext", {}).get("clientId", "")
        if client_id:
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["claimsToAddOrOverride"][
                "aud"
            ] = client_id

            # 읽기 전용 테스트 사용자의 mcp.write 및 mcp.read scope를 제외하여
            # gateway가 쓰기 작업을 insufficient_scope로 거부하도록 함
        if custom_tag == "readonly_user":
            event["response"]["claimsAndScopeOverrideDetails"]["accessTokenGeneration"]["scopesToSuppress"] = [
                f"{RESOURCE_SERVER_ID}/mcp.write",
                f"{RESOURCE_SERVER_ID}/mcp.read",
            ]
            logger.info("Suppressed mcp.write and mcp.read scopes for readonly test user")

        logger.info(f"Added custom claims to ID token and Access token: user_tag={custom_tag}, email={email}")

    except Exception as e:
        logger.error(f"Error in pre-token generation: {str(e)}", exc_info=True)
        # 인증을 실패시키지 않고 오류만 기록
        pass

    return event
