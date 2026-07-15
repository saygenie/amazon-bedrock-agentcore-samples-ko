#!/usr/bin/env python3
"""
AWS Bedrock AgentCore용 WebSocket 도우미 함수

이 모듈은 다양한 인증 방식(SigV4 헤더, SigV4 쿼리 파라미터, OAuth)으로
AWS Bedrock AgentCore에 WebSocket 연결을 생성하는 유틸리티를 제공합니다.
"""

import secrets
import string
import os
from urllib.parse import urlparse
import boto3
from botocore.auth import SigV4Auth, SigV4QueryAuth
from botocore.awsrequest import AWSRequest


def create_signed_headers(url, region=None, service="bedrock-agentcore"):
    """WebSocket 연결용 AWS SigV4 서명 헤더를 생성합니다."""
    if region is None:
        region = os.getenv("AWS_REGION", "us-west-2")
    session = boto3.Session()
    credentials = session.get_credentials()

    parsed_url = urlparse(url)
    request = AWSRequest(method="GET", url=url, headers={"Host": parsed_url.netloc})
    SigV4Auth(credentials, service, region).add_auth(request)
    return dict(request.headers)


def create_presigned_url(url, region=None, service="bedrock-agentcore", expires=300):
    """WebSocket 연결용 AWS SigV4 사전 서명 URL을 생성합니다."""
    if region is None:
        region = os.getenv("AWS_REGION", "us-west-2")
    session = boto3.Session()
    credentials = session.get_credentials()

    https_url = url.replace("wss://", "https://")
    parsed_url = urlparse(https_url)

    request = AWSRequest(method="GET", url=https_url, headers={"Host": parsed_url.netloc})
    SigV4QueryAuth(credentials, service, region, expires=expires).add_auth(request)

    return request.url.replace("https://", "wss://")


def create_websocket_headers(session_id):
    """WebSocket 전용 헤더를 생성합니다."""
    return {
        "Connection": "Upgrade",
        "Upgrade": "websocket",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
        "User-Agent": "AWS-SigV4-WebSocket-Client/1.0",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }


def prepare_connection(runtime_arn, auth_type="headers", session_id=None):
    """연결에 사용할 WebSocket URI와 헤더를 준비합니다."""
    region = os.getenv("AWS_REGION", "us-east-1")

    if session_id is None:
        session_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))

    uri = f"wss://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime_arn}/ws?qualifier=DEFAULT"

    if auth_type == "query":
        uri = create_presigned_url(uri)
        headers = create_websocket_headers(session_id)
    elif auth_type == "oauth":
        token = os.getenv("BEARER_TOKEN")
        if not token:
            raise ValueError("BEARER_TOKEN environment variable required for OAuth")

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
            "Connection": "Upgrade",
            "Upgrade": "websocket",
            "Sec-WebSocket-Version": "13",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            "User-Agent": "OAuth-WebSocket-Client/1.0",
        }
    else:
        signed_headers = create_signed_headers(uri)
        ws_headers = create_websocket_headers(session_id)
        headers = {**signed_headers, **ws_headers}

    return uri, headers
