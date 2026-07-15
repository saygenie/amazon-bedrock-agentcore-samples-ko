import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info("Pre Token Generation Lambda triggered")
    logger.info("Trigger Source: %s", event.get("triggerSource", "Unknown"))

    # ID 및 액세스 토큰 사용자 지정을 위한 V3_0 형식
    event["response"]["claimsAndScopeOverrideDetails"] = {
        "idTokenGeneration": {
            "claimsToAddOrOverride": {
                "custom:role": "agentcore_user",
                "custom:permissions": "read,write",
                "custom:tenant": "default",
                "custom:api_access": "enabled",
            },
            "claimsToSuppress": [],
        },
        "accessTokenGeneration": {
            "claimsToAddOrOverride": {
                "custom:role": "agentcore_user",
                "custom:permissions": "read,write",
                "custom:tenant": "default",
                "custom:api_access": "enabled",
            },
            "claimsToSuppress": [],
            "scopesToAdd": [],
            "scopesToSuppress": [],
        },
    }

    logger.info("Custom claims added to both ID and access tokens")
    return event
