# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Weather REST API Lambda - EntraID 변형입니다.

날씨 데이터를 반환하는 간단한 HTTP 엔드포인트입니다. AgentCore Gateway가
OpenAPI target을 통해 호출합니다. Gateway가 토큰 검증(EntraID 3LO)을 처리하므로
이 Lambda는 사전 승인된 요청을 받습니다.

Gateway는 사용자의 EntraID access token을 Authorization 헤더로 전달합니다.
이 데모에서는 Gateway의 인증을 신뢰하고 모의 날씨 데이터를 반환합니다.
프로덕션에서는 EntraID를 기준으로 토큰을 검증해야 합니다.
"""

import json
import random


def lambda_handler(event, context):
    """GET /weather?location=... 요청을 처리합니다."""
    # 요청 메타데이터만 기록(토큰이 포함될 수 있는 헤더 제외)
    print(f"Method: {event.get('httpMethod', 'unknown')}, Path: {event.get('path', '/')}")

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if method != "GET":
        return json_response(405, {"error": "Method not allowed"})

    params = event.get("queryStringParameters", {}) or {}
    location = params.get("location", "")

    if not location:
        return json_response(400, {"error": "Missing required parameter: location"})

    # 모의 날씨 데이터
    weather = {
        "location": location,
        "temperature": round(random.uniform(20, 95), 1),
        "conditions": random.choice(
            [
                "Sunny",
                "Partly Cloudy",
                "Cloudy",
                "Rainy",
                "Thunderstorms",
                "Snowy",
                "Windy",
            ]
        ),
        "humidity": random.randint(20, 95),
    }

    return json_response(200, weather)


def json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
