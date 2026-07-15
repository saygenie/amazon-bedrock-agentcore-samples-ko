"""공용 테스트 fixture 및 설정."""

import base64
import json

import boto3
import botocore.client
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from backend.session_binding.app.config import get_settings as get_oauth_settings
from backend.runtime.app.config import get_settings

TEST_BUCKET_NAME = "test-bucket"
TEST_AWS_REGION = "us-east-1"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_SUB = "user-123"


def make_oidc_jwt(sub: str = TEST_USER_SUB, email: str = TEST_USER_EMAIL) -> str:
    """테스트용 모의 ALB OIDC JWT를 생성한다."""
    header = base64.urlsafe_b64encode(b'{"alg":"ES256"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.fake-signature"


_orig_api_call = botocore.client.BaseClient._make_api_call


def mock_bedrock_api_call(self, operation_name, kwarg):
    """bedrock 및 bedrock-agentcore API 호출만 모킹한다."""
    if operation_name == "GetWorkloadAccessTokenForUserId":
        return {
            "workloadAccessToken": "test-workload-access-token",
            "expiresAt": "2099-01-01T00:00:00Z",
        }

    if operation_name == "CompleteResourceTokenAuth":
        return {}

    if operation_name == "ConverseStream":

        class MockEventStream:
            def __iter__(self):
                yield {"messageStart": {"role": "assistant"}}
                yield {
                    "contentBlockDelta": {
                        "delta": {"text": "test "},
                        "contentBlockIndex": 0,
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "delta": {"text": "response"},
                        "contentBlockIndex": 0,
                    }
                }
                yield {"contentBlockStop": {"contentBlockIndex": 0}}
                yield {"messageStop": {"stopReason": "end_turn"}}
                yield {
                    "metadata": {
                        "usage": {
                            "inputTokens": 9,
                            "outputTokens": 5,
                            "totalTokens": 14,
                        },
                        "metrics": {"latencyMs": 100},
                    }
                }

        return {"ResponseMetadata": {}, "stream": MockEventStream()}

    if operation_name == "InvokeModelWithResponseStream":
        return {
            "body": iter([b'{"type":"content_block_delta","delta":{"text":"test response"}}']),
            "contentType": "application/json",
        }

    if operation_name == "InvokeModel":
        return {
            "body": b'{"content":[{"text":"test response"}]}',
            "contentType": "application/json",
        }

    return _orig_api_call(self, operation_name, kwarg)


@pytest.fixture
def s3_bucket():
    """전체 테스트에서 mock_aws 컨텍스트가 활성화된 모의 S3 버킷을 생성한다."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=TEST_AWS_REGION)
        bucket = s3.create_bucket(Bucket=TEST_BUCKET_NAME)
        yield bucket


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    """모든 테스트의 환경 변수를 패치한다."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AWS_REGION", TEST_AWS_REGION)
    monkeypatch.setenv("IDENTITY_AWS_REGION", TEST_AWS_REGION)
    monkeypatch.setenv("INFERENCE_PROFILE_ID", "test-profile")
    monkeypatch.setenv("SESSION_BINDING_URL", "http://localhost:8080/oauth2/session-binding")
    monkeypatch.setenv("WORKLOAD_IDENTITY_NAME", "test-workload")
    monkeypatch.setenv("S3_BUCKET_NAME", TEST_BUCKET_NAME)
    get_settings.cache_clear()
    get_oauth_settings.cache_clear()


@pytest.fixture
def agent_client():
    """에이전트 런타임용 테스트 클라이언트를 생성한다."""
    from backend.runtime.app.main import app

    return TestClient(app)


@pytest.fixture
def oauth_client():
    """OAuth 사이드카용 테스트 클라이언트를 생성한다."""
    from backend.session_binding.app.main import app

    return TestClient(app)
