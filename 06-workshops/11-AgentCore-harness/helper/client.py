import os
import boto3

REGION = os.environ.get("AWS_DEFAULT_REGION")

# 엔드포인트 재정의
_CP_ENDPOINT = os.environ.get("BEDROCK_AGENTCORE_CP_ENDPOINT")
_DP_ENDPOINT = os.environ.get("BEDROCK_AGENTCORE_DP_ENDPOINT")


def _make_session():
    """boto3 세션을 생성한다."""
    session = boto3.Session(region_name=REGION)
    return session


def get_agentcore_client():
    """Harness 데이터 플레인(invoke, ExecuteCommand)용 boto3 클라이언트를 반환한다."""
    kwargs = {}
    if _DP_ENDPOINT:
        kwargs["endpoint_url"] = _DP_ENDPOINT
    return _make_session().client("bedrock-agentcore", **kwargs)


def get_agentcore_control_client():
    """Harness 컨트롤 플레인(create, get, update, delete)용 boto3 클라이언트를 반환한다."""
    kwargs = {}
    if _CP_ENDPOINT:
        kwargs["endpoint_url"] = _CP_ENDPOINT
    return _make_session().client("bedrock-agentcore-control", **kwargs)
