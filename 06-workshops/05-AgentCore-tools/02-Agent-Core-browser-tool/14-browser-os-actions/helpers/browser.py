import json

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession
import requests


SERVICE = "bedrock-agentcore"
SESSION_HEADER = "x-amzn-browser-session-id"


def get_credentials(profile=None):
    session = BotocoreSession()
    if profile:
        session.set_config_variable("profile", profile)
    return (
        session.get_credentials().get_frozen_credentials(),
        session.get_config_variable("region") or "us-west-2",
    )


def signed_request(method, url, *, headers=None, body=None, region, credentials):
    """SigV4로 서명한 요청을 보내고 응답을 반환한다."""
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    data = json.dumps(body) if body else ""
    req = AWSRequest(method=method, url=url, headers=hdrs, data=data)
    SigV4Auth(credentials, SERVICE, region).add_auth(req)
    resp = requests.request(method, url, headers=dict(req.headers), data=data)
    return resp


def invoke(
    base_url,
    session_id,
    action,
    *,
    region,
    credentials,
    browser_id="aws.browser.v1",
    extra_headers=None,
):
    """주어진 작업 페이로드로 InvokeBrowser를 호출한다."""
    url = f"{base_url}/browsers/{browser_id}/sessions/invoke"
    hdrs = {SESSION_HEADER: session_id}
    if extra_headers:
        hdrs.update(extra_headers)
    return signed_request(
        "POST",
        url,
        headers=hdrs,
        body={"action": action},
        region=region,
        credentials=credentials,
    )


def start_session(base_url, browser_id, *, region, credentials):
    """관리형 브라우저 세션을 시작하고 세션 ID를 반환한다."""
    url = f"{base_url}/browsers/{browser_id}/sessions/start"
    body = {
        "name": "bugbash-invoke-test",
        "sessionTimeoutSeconds": 3600,
        "viewPort": {"width": 1920, "height": 1080},
    }
    resp = signed_request("PUT", url, body=body, region=region, credentials=credentials)
    resp.raise_for_status()
    data = resp.json()
    print(f"  ✓ Session started: {data['sessionId']}")
    return data["sessionId"]


def stop_session(base_url, session_id, browser_id, *, region, credentials):
    """브라우저 세션을 중지한다."""
    url = f"{base_url}/browsers/{browser_id}/sessions/stop?sessionId={session_id}"
    resp = signed_request("PUT", url, body="", region=region, credentials=credentials)
    print(f"  → Session stop status: {resp.status_code}")
