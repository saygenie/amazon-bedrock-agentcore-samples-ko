#!/usr/bin/env python3
"""
AgentCore Gateway 통합 예제

이 스크립트에서는 AgentCore Gateway의 전체 수명 주기를 보여 준다.

  1. IAM 실행 역할 생성(공용 도우미 재사용)
  2. IAM 인증과 MCP 프로토콜을 사용하는 Gateway 생성
  3. MCP 대상 추가(원격 MCP 서버 엔드포인트)
  4. 트래픽을 대상으로 전달하는 라우팅 규칙 생성
  5. Gateway에 연결된 Harness 생성
  6. 에이전트 호출: Gateway를 통해 도구를 검색하고 호출
  7. 모든 리소스 정리

AgentCore Gateway는 에이전트와 외부 도구 서버(MCP, HTTP) 사이에 위치하는
관리형 프록시다. 모든 도구 트래픽에 중앙 집중식 인증, 라우팅 규칙,
관측성을 제공한다.

사용법:
    # 기본: 기본 Exa MCP 검색 엔드포인트 사용
    python 02_agentcore_gateway_integration.py

    # 사용자 지정 MCP 엔드포인트
    python 02_agentcore_gateway_integration.py \\
        --mcp-endpoint https://your-mcp-server.example.com/mcp \\
        --target-name my-tools

    # 데모 완료 후 리소스 유지
    python 02_agentcore_gateway_integration.py --skip-cleanup

    # 기존 IAM 역할 사용
    python 02_agentcore_gateway_integration.py --role-arn arn:aws:iam::123456789012:role/MyRole

    # 모든 옵션 확인
    python 02_agentcore_gateway_integration.py --help
"""

import argparse
import json
import os
import sys
import time
import uuid

import boto3
import botocore.exceptions

# 도우미를 가져올 수 있도록 프로젝트 루트를 추가한다.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from helper.iam import create_harness_role
from helper.client import get_agentcore_client, get_agentcore_control_client

REGION = os.getenv("AWS_DEFAULT_REGION")


# ---------------------------------------------------------------------------
# 클라이언트 팩토리
# ---------------------------------------------------------------------------
def _make_session():
    """로컬 서비스 모델을 로드한 boto3 세션을 생성한다."""
    session = boto3.Session(region_name=REGION)
    return session


def get_gateway_control_client():
    """Gateway API용 컨트롤 플레인 클라이언트를 반환한다(GA 엔드포인트, 재정의 없음)."""
    return _make_session().client("bedrock-agentcore-control")


def get_harness_control_client():
    """Harness API용 컨트롤 플레인 클라이언트를 반환한다(베타 엔드포인트)."""
    return get_agentcore_control_client()


def get_data_plane_client():
    """invoke_harness용 데이터 플레인 클라이언트를 반환한다(베타 엔드포인트)."""
    return get_agentcore_client()


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
DEFAULT_MCP_ENDPOINT = "https://mcp.exa.ai/mcp"
DEFAULT_TARGET_NAME = "exa-search"
DEFAULT_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_PROMPT = (
    "Search the web for the top 5 things to do in Tokyo in spring 2025. "
    "For each activity, include a one-sentence description and the best month to visit. "
    "Format the results as a numbered list."
)

GATEWAY_POLL_INTERVAL = 5
GATEWAY_POLL_TIMEOUT = 120
HARNESS_POLL_INTERVAL = 5
HARNESS_POLL_TIMEOUT = 120

# ---------------------------------------------------------------------------
# CLI 실행
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="AgentCore Gateway Integration — create a Gateway, add targets, and invoke via Harness.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument(
    "--mcp-endpoint",
    default=DEFAULT_MCP_ENDPOINT,
    metavar="URL",
    help=f"MCP server endpoint URL (default: {DEFAULT_MCP_ENDPOINT})",
)
parser.add_argument(
    "--target-name",
    default=DEFAULT_TARGET_NAME,
    metavar="NAME",
    help=f"Name for the Gateway target (default: {DEFAULT_TARGET_NAME})",
)
parser.add_argument(
    "--model",
    default=DEFAULT_MODEL,
    metavar="MODEL_ID",
    help=f"Bedrock model ID (default: {DEFAULT_MODEL})",
)
parser.add_argument(
    "--message",
    "-m",
    default=DEFAULT_PROMPT,
    help="Prompt to send to the agent",
)
parser.add_argument(
    "--role-arn",
    default=None,
    metavar="ARN",
    help="Use an existing IAM execution role ARN instead of creating one",
)
parser.add_argument(
    "--skip-cleanup",
    action="store_true",
    help="Keep all resources after the demo",
)
parser.add_argument(
    "--raw-events",
    action="store_true",
    help="Print raw JSON streaming events from invoke",
)


# ---------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------
def poll_gateway_status(control, gateway_id, target_status="READY", timeout=GATEWAY_POLL_TIMEOUT):
    """Gateway가 목표 상태에 도달하거나 제한 시간이 끝날 때까지 폴링한다."""
    deadline = time.monotonic() + timeout
    while True:
        resp = control.get_gateway(gatewayIdentifier=gateway_id)
        status = resp["status"]
        print(f"  Gateway status: {status}")
        if status == target_status:
            return resp
        if status == "FAILED":
            reasons = resp.get("statusReasons", [])
            raise RuntimeError(f"Gateway entered FAILED state: {reasons}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Gateway not {target_status} after {timeout}s (current: {status})")
        time.sleep(GATEWAY_POLL_INTERVAL)


def poll_target_status(control, gateway_id, target_id, target_status="READY", timeout=GATEWAY_POLL_TIMEOUT):
    """Gateway 대상이 목표 상태에 도달하거나 제한 시간이 끝날 때까지 폴링한다."""
    deadline = time.monotonic() + timeout
    while True:
        resp = control.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
        status = resp["status"]
        print(f"  Target status: {status}")
        if status == target_status:
            return resp
        if status in ("FAILED", "DELETE_FAILED"):
            reasons = resp.get("statusReasons", [])
            raise RuntimeError(f"Target entered {status}: {reasons}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Target not {target_status} after {timeout}s (current: {status})")
        time.sleep(GATEWAY_POLL_INTERVAL)


def poll_harness_status(control, harness_id, target_status="READY", timeout=HARNESS_POLL_TIMEOUT):
    """Harness가 목표 상태에 도달하거나 제한 시간이 끝날 때까지 폴링한다."""
    deadline = time.monotonic() + timeout
    while True:
        resp = control.get_harness(harnessId=harness_id)
        status = resp["harness"]["status"]
        print(f"  Harness status: {status}")
        if status == target_status:
            return resp
        if status in ("FAILED", "DELETE_FAILED"):
            raise RuntimeError(f"Harness entered {status}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Harness not {target_status} after {timeout}s (current: {status})")
        time.sleep(HARNESS_POLL_INTERVAL)


def stream_response(client, harness_arn, session_id, message, model_id, gateway_arn, raw=False):
    """Gateway 도구와 함께 Harness를 호출하고 응답을 스트리밍한다."""
    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": message}]}],
        model={"bedrockModelConfig": {"modelId": model_id}},
        tools=[
            {
                "type": "agentcore_gateway",
                "name": "gateway",
                "config": {"agentCoreGateway": {"gatewayArn": gateway_arn}},
            }
        ],
    )

    full_text = ""
    try:
        for event in response["stream"]:
            if raw:
                print(json.dumps(event, default=str))
                continue

            if "contentBlockStart" in event:
                start = event["contentBlockStart"].get("start", {})
                if "toolUse" in start:
                    print(f"\n  [Tool: {start['toolUse'].get('name', '?')}]", flush=True)
            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    print(delta["text"], end="", flush=True)
                    full_text += delta["text"]
            elif "messageStop" in event:
                print()
            elif "internalServerException" in event:
                print(f"\n  Error: {event['internalServerException']}")
    except botocore.exceptions.EventStreamError:
        # 스트림을 닫을 때 빈 오류 이벤트가 전송될 수 있다.
        # 콘텐츠를 이미 받았다면 무시해도 된다.
        if not full_text:
            raise

    return full_text


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main(args=None):
    if args is None:
        args = parser.parse_args()

    # Gateway API는 GA 엔드포인트를, Harness API는 베타 엔드포인트를 사용한다.
    gw_control = get_gateway_control_client()
    harness_control = get_harness_control_client()
    client = get_data_plane_client()

    gateway_id = None
    target_id = None
    harness_id = None

    try:
        # ── 0단계: IAM 역할 ──────────────────────────────────────────
        print("=" * 60)
        print("Step 0: IAM execution role")
        print("=" * 60)
        if args.role_arn:
            role_arn = args.role_arn
            print(f"  Using provided role: {role_arn}")
        else:
            role_arn = create_harness_role()
            # IAM 전파에 필요한 시간을 확보한다.
            print("  Waiting for IAM propagation...")
            time.sleep(10)

        # ── 1단계: Gateway 생성 ──────────────────────────────────────
        print("\n" + "=" * 60)
        print("Step 1: Create Gateway")
        print("=" * 60)
        # Gateway 이름은 ([0-9a-zA-Z][-]?){1,48} 형식이어야 하며 밑줄은 사용할 수 없다.
        gateway_name = f"GatewayDemo-{uuid.uuid4().hex[:8]}"
        resp = gw_control.create_gateway(
            name=gateway_name,
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="NONE",
        )
        gateway_id = resp["gatewayId"]
        gateway_arn = resp["gatewayArn"]
        print(f"  Gateway ID:  {gateway_id}")
        print(f"  Gateway ARN: {gateway_arn}")
        poll_gateway_status(gw_control, gateway_id)

        # ── 2단계: MCP 대상 추가 ─────────────────────────────────────
        print("\n" + "=" * 60)
        print(f"Step 2: Add MCP target ({args.mcp_endpoint})")
        print("=" * 60)
        resp = gw_control.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=args.target_name,
            targetConfiguration={
                "mcp": {
                    "mcpServer": {
                        "endpoint": args.mcp_endpoint,
                    },
                },
            },
        )
        target_id = resp["targetId"]
        print(f"  Target ID: {target_id}")
        poll_target_status(gw_control, gateway_id, target_id)

        # ── 3단계: Harness 생성 ──────────────────────────────────────
        print("\n" + "=" * 60)
        print("Step 3: Create Harness")
        print("=" * 60)
        # Harness 이름은 [a-zA-Z][a-zA-Z0-9_]{0,39} 형식이어야 한다.
        harness_name = f"GatewayHarness_{uuid.uuid4().hex[:8]}"
        resp = harness_control.create_harness(
            harnessName=harness_name,
            executionRoleArn=role_arn,
        )
        harness_id = resp["harness"]["harnessId"]
        harness_arn = resp["harness"]["arn"]
        print(f"  Harness ID:  {harness_id}")
        print(f"  Harness ARN: {harness_arn}")
        poll_harness_status(harness_control, harness_id)

        # ── 4단계: Gateway를 통해 에이전트 호출 ─────────────────────
        print("\n" + "=" * 60)
        print("Step 4: Invoke agent (tools served via Gateway)")
        print("=" * 60)
        session_id = str(uuid.uuid4()).upper()
        print(f"  Session ID: {session_id}")
        print(f"  Model:      {args.model}")
        print(f"  Gateway:    {gateway_arn}")
        print(f"  Message:    {args.message[:80]}{'...' if len(args.message) > 80 else ''}\n")

        stream_response(
            client,
            harness_arn,
            session_id,
            args.message,
            args.model,
            gateway_arn,
            raw=args.raw_events,
        )

        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

        time.sleep(20)

    finally:
        if not args.skip_cleanup:
            print("\nCleaning up...")
            _cleanup(gw_control, harness_control, gateway_id, target_id, harness_id)


def _cleanup(gw_control, harness_control, gateway_id, target_id, harness_id):
    """데모 중 생성된 모든 리소스를 삭제한다."""
    # 베타 엔드포인트를 통해 Harness를 삭제한다.
    if harness_id:
        try:
            harness_control.delete_harness(harnessId=harness_id)
            print(f"  Deleted harness: {harness_id}")
        except Exception as e:
            print(f"  Warning: failed to delete harness: {e}")

    # Gateway보다 먼저 Gateway 대상을 삭제해야 한다.
    if gateway_id and target_id:
        try:
            gw_control.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
            print(f"  Deleted target: {target_id}")
            # 비동기 대상 삭제가 전파될 때까지 기다린다.
            time.sleep(10)
        except Exception as e:
            print(f"  Warning: failed to delete target: {e}")

    # Gateway를 삭제한다(규칙도 Gateway와 함께 자동으로 삭제된다).
    if gateway_id:
        try:
            gw_control.delete_gateway(gatewayIdentifier=gateway_id)
            print(f"  Deleted gateway: {gateway_id}")
        except Exception as e:
            print(f"  Warning: failed to delete gateway: {e}")


if __name__ == "__main__":
    main()
