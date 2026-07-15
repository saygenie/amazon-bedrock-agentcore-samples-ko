"""
테스트 스크립트: Cognito bearer token으로 M2M + Auth Code 에이전트를 호출합니다.

테스트:
  1. M2M 흐름: 에이전트가 사용자 상호 작용 없이 client credentials로 내부 API 호출
  2. Auth Code: 에이전트가 사용자를 대신해 Google Calendar에 액세스(3LO 동의 흐름)

3LO 테스트에서 이 스크립트가 수행하는 작업:
  - OAuth2 콜백 서버 시작(localhost:9090)
  - 세션 바인딩에서 신원을 검증할 수 있도록 사용자의 bearer token 저장
  - 에이전트 호출(첫 호출에서 Google 동의 URL 반환)
  - 사용자가 동의를 완료할 때까지 기다린 후 다시 호출하여 Calendar 이벤트 조회

사용법:
    # M2M 흐름 테스트
    python invoke.py --flow m2m

    # Auth Code(3LO) 흐름 테스트
    python invoke.py --flow authcode
"""

import warnings

import argparse
import json
import os
import subprocess
import sys
import webbrowser

import boto3

from oauth2_callback_server import (
    store_token_in_oauth2_callback_server,
    wait_for_oauth2_server_to_be_ready,
    get_oauth2_callback_url,
)

warnings.filterwarnings("ignore", category=Warning, module="requests")
warnings.filterwarnings("ignore", message="urllib3")


def get_bearer_token(config: dict) -> str:
    """새 Cognito 액세스 토큰을 가져옵니다."""
    cognito = boto3.client("cognito-idp", region_name=config["region"])
    auth = cognito.initiate_auth(
        ClientId=config["client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": config["username"],
            "PASSWORD": config["password"],
        },
    )
    return auth["AuthenticationResult"]["AccessToken"]


def _find_project_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    for entry in os.listdir(base):
        candidate = os.path.join(base, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "agentcore")):
            return candidate
    raise FileNotFoundError("No agentcore project directory found. Run 'agentcore create' first.")


def _find_in_json(obj, key):
    """중첩된 JSON에서 키를 재귀적으로 검색합니다."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _find_in_json(v, key)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_in_json(item, key)
            if result:
                return result
    return None


def get_agent_arn() -> str:
    """deployed-state.json에서 배포된 에이전트 ARN을 읽습니다.

    CLI 버전에 관계없이 동작하도록 runtimeArn을 재귀적으로 검색합니다.
    """
    project_dir = _find_project_dir()
    state_file = os.path.join(project_dir, "agentcore", ".cli", "deployed-state.json")
    if not os.path.exists(state_file):
        raise FileNotFoundError("No deployed-state.json found. Run 'agentcore deploy -y' first.")
    with open(state_file) as f:
        state = json.load(f)
    arn = _find_in_json(state, "runtimeArn")
    if arn:
        return arn
    raise ValueError("No deployed agent found. Run 'agentcore deploy -y' first.")


def parse_event_stream(response: dict) -> str:
    parts = []
    for event in response.get("response", []):
        raw = event if isinstance(event, bytes) else event.get("chunk", {}).get("bytes", b"")
        if raw:
            try:
                decoded = json.loads(raw.decode("utf-8"))
                if isinstance(decoded, str):
                    parts.append(decoded)
                elif isinstance(decoded, dict):
                    content = decoded.get("content", [])
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c["text"])
                        elif isinstance(c, str):
                            parts.append(c)
                    if not content and "message" in decoded:
                        msg = decoded["message"]
                        if isinstance(msg, dict):
                            for c in msg.get("content", []):
                                if isinstance(c, dict) and c.get("type") == "text":
                                    parts.append(c["text"])
            except Exception:
                parts.append(raw.decode("utf-8"))
    return "\n".join(parts) if parts else "(no response)"


def invoke(client, agent_arn: str, prompt: str, bearer_token: str, user_id: str, region: str) -> str:
    def _inject_bearer(request, **kwargs):
        request.headers["Authorization"] = f"Bearer {bearer_token}"

    client.meta.events.register("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeUserId=user_id,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
    )
    client.meta.events.unregister("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer)
    return parse_event_stream(resp)


def test_m2m(client, agent_arn: str, bearer_token: str, config: dict):
    print("\n=== M2M Flow Test ===")
    print("The agent will get weather data using M2M client credentials (no user consent needed).")
    prompt = "What is the weather in Seattle?"
    print(f"Prompt: '{prompt}'")

    result = invoke(client, agent_arn, prompt, bearer_token, config["username"], config["region"])
    print(f"\nAgent response:\n{result}")


def test_authcode(client, agent_arn: str, bearer_token: str, config: dict, provider: str = "google"):
    provider_config = {
        "github": {
            "prompt": "List my GitHub repositories.",
            "consent_keywords": ["github", "oauth", "http"],
            "wait_message": "Waiting for you to complete the GitHub consent flow...",
            "reinvoke_message": "Re-invoking agent to retrieve GitHub repositories...",
        },
        "google": {
            "prompt": "What is on my Google Calendar today?",
            "consent_keywords": ["google", "oauth", "http"],
            "wait_message": "Waiting for you to complete the Google consent flow...",
            "reinvoke_message": "Re-invoking agent to retrieve calendar events...",
        },
    }
    cfg = provider_config[provider]

    print(f"\n=== Auth Code (3LO) Flow Test — {provider.capitalize()} ===")
    print("Starting OAuth2 callback server...")

    server_proc = subprocess.Popen(
        [sys.executable, "oauth2_callback_server.py", "--region", config["region"]],
    )

    try:
        if not wait_for_oauth2_server_to_be_ready():
            print("ERROR: OAuth2 callback server did not start in time.")
            return

        # 세션 바인딩을 위해 사용자의 bearer token 저장
        store_token_in_oauth2_callback_server(bearer_token)
        print(f"  Callback URL: {get_oauth2_callback_url()}")  # codeql[py/clear-text-logging-sensitive-data]

        prompt = cfg["prompt"]
        print(f"\nPrompt: '{prompt}'")
        print("Invoking agent (first call — expect consent URL)...")

        result = invoke(
            client,
            agent_arn,
            prompt,
            bearer_token,
            config["username"],
            config["region"],
        )
        print(f"\nAgent response:\n{result}")

        # 응답에 인증 URL이 있으면 사용자가 동의를 완료할 때까지 대기
        result_lower = result.lower()
        if "http" in result_lower and any(kw in result_lower for kw in cfg["consent_keywords"]):
            # 동의 URL을 추출하여 자동으로 열기
            import re

            urls = re.findall(r'https?://[^\s\'")*\]]+', str(result))
            if urls:
                consent_url = urls[0]
                print(f"\nConsent URL: {consent_url}")
                print("Opening in your browser automatically...")
                webbrowser.open(consent_url)
            print(f"\n{cfg['wait_message']}")
            print("After authorizing in your browser, press Enter to re-invoke the agent.")
            input()

            print(cfg["reinvoke_message"])
            result2 = invoke(
                client,
                agent_arn,
                prompt,
                bearer_token,
                config["username"],
                config["region"],
            )
            print(f"\nAgent response:\n{result2}")

    finally:
        server_proc.terminate()
        server_proc.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flow",
        choices=["m2m", "authcode", "both"],
        default="both",
        help="Which flow to test (default: both)",
    )
    parser.add_argument(
        "--provider",
        choices=["github", "google"],
        default="google",
        help="3LO provider for authcode flow: github or google (default: google)",
    )
    args = parser.parse_args()

    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    print("Getting Cognito bearer token...")
    bearer_token = get_bearer_token(config)
    print(f"  Token obtained (first 20 chars): {bearer_token[:20]}...")

    print("Resolving deployed agent ARN...")
    agent_arn = get_agent_arn()
    print(f"  Agent ARN: {agent_arn}")

    boto_client = boto3.client("bedrock-agentcore", region_name=config["region"])

    if args.flow in ("m2m", "both"):
        test_m2m(boto_client, agent_arn, bearer_token, config)

    if args.flow in ("authcode", "both"):
        test_authcode(boto_client, agent_arn, bearer_token, config, provider=args.provider)


if __name__ == "__main__":
    main()
