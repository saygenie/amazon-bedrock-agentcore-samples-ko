#!/usr/bin/env python3
"""AWS AgentCore Registry용 Auth0 OAuth 유틸리티: 생성, 시드 및 검색.

이 스크립트는 Auth0 CUSTOM_JWT 권한 부여를 사용하는 AWS AgentCore Registry를
설정하고 채우기 위한 엔드 투 엔드 도구를 제공합니다.

주요 기능:
    - Auth0 클라이언트 자격 증명 OAuth 흐름을 통한 인증
    - Auth0 기반 CUSTOM_JWT 권한 부여자를 사용하여 새 레지스트리 생성
    - 샘플 에이전트 레코드(weather, order-status, customer-support,
      inventory-lookup)를 레지스트리에 시드하고 자동 승인
    - OAuth Bearer 토큰을 사용하여 레지스트리 레코드 검색

설정은 .env 파일에서 로드되며(.env.example 참조), 다음 값이 필요합니다.
    AWS_REGION, AWS_ACCOUNT_ID,
    AUTH0_DOMAIN, AUTH0_AUDIENCE.

사용법:
    # 모듈로 사용
    from seed_records import create_registry, seed, search, get_token

    # 스크립트로 사용 - REGISTRY_ID로 지정한 레지스트리에 레코드 시드
    python seed_records.py
"""

import boto3
import json
import logging
import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-west-2")
ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUDIENCE = os.getenv("AUTH0_AUDIENCE")


def _registry_arn(registry_id):
    return f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT_ID}:registry/{registry_id}"


def _cp_client():
    return boto3.client("bedrock-agentcore-control", region_name=REGION)


def _dp_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


# ── Registry 설정 ─────────────────────────────────────────────────────────────


def create_registry(
    name="auth0-oauth-registry",
    description="Registry with Auth0 OAuth authentication",
    poll_interval=5,
    max_wait=150,
):
    """Auth0 CUSTOM_JWT 권한 부여자를 사용하는 AgentCore Registry를 생성합니다.

    registryId, registryArn, status가 포함된 딕셔너리를 반환합니다.
    """
    cp = _cp_client()
    discovery_url = f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration"

    logger.info("Creating registry '%s' with CUSTOM_JWT authorizer...", name)
    resp = cp.create_registry(
        name=name,
        description=description,
        authorizerType="CUSTOM_JWT",
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": discovery_url,
                "allowedAudience": [AUDIENCE],
            }
        },
    )
    registry_arn = resp["registryArn"]
    registry_id = registry_arn.split("/")[-1]
    logger.info("Created registry %s (%s)", registry_id, registry_arn)

    status = "UNKNOWN"
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        info = cp.get_registry(registryId=registry_id)
        status = info.get("status", "UNKNOWN")
        logger.info("[%ds] status=%s", elapsed, status)
        if status == "READY":
            break
    else:
        logger.warning("Registry not READY after %ds — continuing anyway", max_wait)

    update_registry_audience_with_mcp_url(registry_id)
    logger.info("Added MCP URL to allowedAudience")

    result = {"registryId": registry_id, "registryArn": registry_arn, "status": status}
    logger.info("Done: %s", result)
    return result


def update_registry_audience_with_mcp_url(registry_id):
    """레지스트리의 allowedAudience에 MCP 엔드포인트 URL을 추가합니다."""
    cp = _cp_client()
    dp = _dp_client()
    registry = cp.get_registry(registryId=registry_id)
    jwt_config = registry["authorizerConfiguration"]["customJWTAuthorizer"]
    mcp_url = f"{dp.meta.endpoint_url}/registry/{registry_id}/mcp"
    audience = list(set(jwt_config.get("allowedAudience", []) + [mcp_url]))
    cp.update_registry(
        registryId=registry_id,
        authorizerConfiguration={
            "optionalValue": {
                "customJWTAuthorizer": {
                    "discoveryUrl": jwt_config["discoveryUrl"],
                    "allowedAudience": audience,
                }
            }
        },
    )
    while True:
        status = cp.get_registry(registryId=registry_id)["status"]
        if status != "UPDATING":
            break
        time.sleep(2)
    return cp.get_registry(registryId=registry_id)


# ── 시드 ──────────────────────────────────────────────────────────────────────

RECORDS = [
    {
        "name": "weather_agent",
        "description": "Retrieves current weather conditions and 5-day forecasts for any city worldwide. Provides temperature, humidity, wind speed, and precipitation data.",
        "descriptorType": "CUSTOM",
        "descriptors": {
            "custom": {
                "inlineContent": json.dumps(
                    {
                        "type": "http-agent",
                        "team": "Platform",
                        "capabilities": [
                            "current weather",
                            "5-day forecast",
                            "severe weather alerts",
                        ],
                        "endpoint": "https://api.example.com/weather",
                    }
                )
            }
        },
    },
    {
        "name": "order_status_agent",
        "description": "Tracks order status, shipping updates, and estimated delivery times for e-commerce orders. Integrates with major carriers like UPS, FedEx, and USPS.",
        "descriptorType": "CUSTOM",
        "descriptors": {
            "custom": {
                "inlineContent": json.dumps(
                    {
                        "type": "http-agent",
                        "team": "Commerce",
                        "capabilities": [
                            "order tracking",
                            "shipping status",
                            "delivery estimates",
                            "return status",
                        ],
                        "endpoint": "https://api.example.com/orders",
                    }
                )
            }
        },
    },
    {
        "name": "customer_support_agent",
        "description": "Handles customer inquiries, processes refunds, and escalates issues. Uses knowledge base for FAQ resolution and sentiment analysis for prioritization.",
        "descriptorType": "CUSTOM",
        "descriptors": {
            "custom": {
                "inlineContent": json.dumps(
                    {
                        "type": "http-agent",
                        "team": "Support",
                        "capabilities": [
                            "FAQ resolution",
                            "refund processing",
                            "ticket escalation",
                            "sentiment analysis",
                        ],
                        "endpoint": "https://api.example.com/support",
                    }
                )
            }
        },
    },
    {
        "name": "inventory_lookup_agent",
        "description": "Checks real-time product inventory across warehouses and stores. Supports SKU lookup, stock level alerts, and reorder recommendations.",
        "descriptorType": "CUSTOM",
        "descriptors": {
            "custom": {
                "inlineContent": json.dumps(
                    {
                        "type": "http-agent",
                        "team": "Supply Chain",
                        "capabilities": [
                            "stock levels",
                            "warehouse lookup",
                            "reorder alerts",
                            "SKU search",
                        ],
                        "endpoint": "https://api.example.com/inventory",
                    }
                )
            }
        },
    },
]


def seed(registry_id):
    """레코드를 생성하고 승인 요청을 제출한 후 승인합니다.

    생성된 레코드 딕셔너리의 목록을 반환합니다.
    """
    cp = _cp_client()
    created = []
    for rec in RECORDS:
        logger.info("Creating record '%s' (%s)...", rec["name"], rec["descriptorType"])
        try:
            resp = cp.create_registry_record(registryId=registry_id, **rec)
            record_id = resp["recordArn"].split("/")[-1]
            logger.info("  Created %s", record_id)
            created.append({"name": rec["name"], "recordId": record_id})
        except cp.exceptions.ConflictException:
            logger.info("  Already exists — skipping")
        except Exception as e:
            logger.error("  Failed: %s", e)

    if created:
        logger.info("Approving %d record(s)...", len(created))
        time.sleep(2)
        for rec in created:
            try:
                cp.submit_registry_record_for_approval(
                    registryId=registry_id,
                    recordId=rec["recordId"],
                )
                cp.update_registry_record_status(
                    registryId=registry_id,
                    recordId=rec["recordId"],
                    status="APPROVED",
                    statusReason="Auto-seed",
                )
                logger.info("  ✓ %s approved", rec["name"])
            except Exception as e:
                logger.error("  ✗ %s: %s", rec["name"], e)

    logger.info("Done — seeded %d record(s)", len(created))
    return created


def delete_registry(registry_id):
    """레지스트리의 모든 레코드를 삭제한 후 레지스트리 자체를 삭제합니다."""
    cp = _cp_client()
    records = cp.list_registry_records(registryId=registry_id).get("registryRecords", [])
    for rec in records:
        rid = rec["recordId"]
        logger.info("Deleting record %s...", rid)
        cp.delete_registry_record(registryId=registry_id, recordId=rid)
    logger.info("Deleting registry %s...", registry_id)
    resp = cp.delete_registry(registryId=registry_id)
    logger.info("Registry %s status: %s", registry_id, resp.get("status"))
    return resp


if __name__ == "__main__":
    seed()
