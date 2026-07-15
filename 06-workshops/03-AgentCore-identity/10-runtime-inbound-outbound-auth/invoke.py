"""
테스트 스크립트: Cognito JWT bearer token으로 배포된 AgentCore Runtime을 호출합니다.

확인할 내용:
  1. bearer token 없이 호출 -> AccessDeniedException(예상 결과)
  2. 유효한 Cognito bearer token으로 호출 -> 성공

사용법:
    python invoke.py [prompt]

    prompt 기본값은 "What is the weather in Seattle?"입니다.
"""

import warnings

import boto3
import json
import os
import sys

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
    """agentcore/를 포함하는 하위 디렉터리에서 agentcore 프로젝트를 찾습니다."""
    base = os.path.dirname(os.path.abspath(__file__))
    for entry in os.listdir(base):
        candidate = os.path.join(base, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "agentcore")):
            return candidate
    raise FileNotFoundError("No agentcore project directory found. Run 'agentcore create' first.")


def get_agent_arn(region: str) -> str:
    """deployed-state.json에서 배포된 에이전트 ARN을 읽습니다.

    CLI 버전에 관계없이 동작하도록 runtimeArn을 재귀적으로 검색합니다.
    0.3.x는 'agents'를 사용하고 0.4.x는 'runtimes'를 사용할 수 있습니다.
    """
    project_dir = _find_project_dir()
    state_file = os.path.join(project_dir, "agentcore", ".cli", "deployed-state.json")
    if not os.path.exists(state_file):
        raise FileNotFoundError("No deployed-state.json found. Run 'agentcore deploy -y' first.")
    with open(state_file) as f:
        state = json.load(f)

    # 상태 JSON에서 runtimeArn을 재귀적으로 검색
    def _find_arn(obj):
        if isinstance(obj, dict):
            if "runtimeArn" in obj:
                return obj["runtimeArn"]
            for v in obj.values():
                result = _find_arn(v)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = _find_arn(item)
                if result:
                    return result
        return None

    arn = _find_arn(state)
    if arn:
        return arn
    raise ValueError("No deployed agent found in deployed-state.json. Run 'agentcore deploy -y' first.")


def parse_event_stream(response: dict) -> str:
    """boto3 EventStream 응답에서 텍스트를 추출합니다."""
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
    prompt = sys.argv[1] if len(sys.argv) > 1 else "What is the weather in Seattle?"

    # Cognito 구성 불러오기
    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found.")
        print("Run 'python setup_cognito.py' first.")
        sys.exit(1)

    region = config["region"]
    client = boto3.client("bedrock-agentcore", region_name=region)

    print("Resolving deployed agent ARN...")
    agent_arn = get_agent_arn(region)
    print(f"  Agent ARN: {agent_arn}")

    print(f"\nPrompt: '{prompt}'")

    # --- 테스트 1: bearer token 없음(거부되어야 함) ---
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

    # --- 테스트 2: 유효한 Cognito bearer token ---
    print("\n[Test 2] Invoking WITH valid Cognito bearer token...")
    bearer_token = get_bearer_token(config)
    print(f"  Token obtained (first 20 chars): {bearer_token[:20]}...")

    try:
        # boto3에는 bearerToken 매개변수가 없으므로 요청 헤더를 통해 주입
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
