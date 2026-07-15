"""
테스트 스크립트: JWT로 보호되는 Gateway를 사용하는 AgentCore Runtime 에이전트를 호출합니다.

에이전트는 CLI(--agent-client-id / --agent-client-secret)에서 생성한 관리형 자격 증명을
사용해 Gateway에 자동으로 인증합니다. 호출자 관점에서는 표준 Cognito JWT만 필요합니다.

사용법:
    python invoke.py [prompt]
"""

import warnings

import boto3
import json
import os
import sys

warnings.filterwarnings("ignore", category=Warning, module="requests")
warnings.filterwarnings("ignore", message="urllib3")


def get_bearer_token(config: dict) -> str:
    """테스트 사용자의 새 Cognito 액세스 토큰을 가져옵니다."""
    cognito = boto3.client("cognito-idp", region_name=config["region"])
    auth = cognito.initiate_auth(
        ClientId=config["user_client_id"],
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


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "What tools do you have available?"

    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    region = config["region"]
    client = boto3.client("bedrock-agentcore", region_name=region)

    print("Resolving deployed agent ARN...")
    agent_arn = get_agent_arn()
    print(f"  Agent ARN: {agent_arn}")

    # --- 테스트 1: bearer token 없음 ---
    print("\n[Test 1] Invoking WITHOUT bearer token (expect AccessDeniedException)...")
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeUserId="testuser",
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
        )
        print("  Unexpected success:", resp)
    except client.exceptions.AccessDeniedException as exc:
        print(f"  Correctly rejected: {exc}")
    except Exception as exc:
        print(f"  Error: {type(exc).__name__}: {exc}")

    # --- 테스트 2: 유효한 사용자 bearer token ---
    print("\n[Test 2] Invoking WITH Cognito bearer token (expect success)...")
    bearer_token = get_bearer_token(config)
    print(f"  Token obtained (first 20 chars): {bearer_token[:20]}...")
    print(f"  Prompt: '{prompt}'")

    try:

        def _inject_bearer(request, **kwargs):
            request.headers["Authorization"] = f"Bearer {bearer_token}"

        client.meta.events.register("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer)
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeUserId=config["username"],
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
        )
        client.meta.events.unregister("before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer)
        result = parse_event_stream(resp)
        print(f"\nAgent response:\n{result}")
    except Exception as exc:
        print(f"  Error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
