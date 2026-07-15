#!/usr/bin/env python3
"""
AgentCore Harness의 사용자 지정 컨테이너 및 명령줄 예제

이 스크립트에서는 다음 작업을 보여 준다.
  1. 사용자 지정 컨테이너 이미지로 Harness 생성
  2. 에이전트를 호출하여 해당 런타임에서 코드 작성 및 실행
  3. ExecuteCommand를 통해 에이전트 VM에서 직접 명령 실행
  4. 리소스 정리

사용법:
    # 언어 프리셋 선택(node, go, python)
    python 03_custom_container_cli.py --language node
    python 03_custom_container_cli.py --language go
    python 03_custom_container_cli.py --language python

    # 또는 컨테이너 이미지 직접 지정
    python 03_custom_container_cli.py --container public.ecr.aws/docker/library/rust:slim

    # 기존 IAM 역할 사용
    python 03_custom_container_cli.py --role-arn arn:aws:iam::123456789012:role/MyRole

    # 기타 옵션
    python 03_custom_container_cli.py --model us.anthropic.claude-sonnet-4-6
    python 03_custom_container_cli.py --skip-cleanup
    python 03_custom_container_cli.py --raw-events
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid

# 도우미를 가져올 수 있도록 프로젝트 루트를 추가한다.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from helper.iam import create_harness_role
from helper.client import get_agentcore_client

REGION = os.getenv("AWS_DEFAULT_REGION")

# ---------------------------------------------------------------------------
# 언어 프리셋: 친숙한 이름을 컨테이너 URI와 데모 메시지에 매핑한다.
# ---------------------------------------------------------------------------
LANGUAGE_PRESETS = {
    "node": {
        "container": "public.ecr.aws/docker/library/node:slim",
        "message": (
            "Write a Node.js script that creates a simple HTTP server on port 3000 "
            "that returns JSON with the current time, Node.js version, and platform info. "
            "Save it to /tmp/server.js. Then use curl to test it (start the server in the "
            "background, curl localhost:3000, and kill the server). Show me the output."
        ),
    },
    "go": {
        "container": "public.ecr.aws/docker/library/golang:1.24",
        "message": (
            "Write a Go HTTP server that listens on port 3000 and returns a JSON response "
            "with the current time, Go version, OS, architecture, and number of CPUs. "
            "Initialize a Go module at /tmp/goserver, save the code as main.go, build it "
            "into a binary called 'goserver', then test it: start the binary in the background, "
            "curl localhost:3000, and kill the server. Show me the curl output."
        ),
    },
    "python": {
        "container": "public.ecr.aws/docker/library/python:3.12-slim",
        "message": (
            "Write a Python HTTP server using the http.server module that listens on port 3000 "
            "and returns JSON with the current time, Python version, OS, and platform info. "
            "Save it to /tmp/server.py. Then test it: start the server in the background, "
            "curl localhost:3000, and kill the server. Show me the output."
        ),
    },
}

# ---------------------------------------------------------------------------
# CLI 인자
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

parser = argparse.ArgumentParser(
    description="Harness Custom Container Demo — attach any container image and invoke the agent.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=f"Available language presets: {', '.join(LANGUAGE_PRESETS.keys())}",
)
parser.add_argument(
    "--language",
    "-l",
    choices=LANGUAGE_PRESETS.keys(),
    default="node",
    help="Language preset — sets container + demo message (default: node)",
)
parser.add_argument(
    "--container",
    default=None,
    metavar="URI",
    help="Container image URI (overrides --language preset)",
)
parser.add_argument(
    "--message",
    "-m",
    default=None,
    help="Prompt to send to the agent (overrides --language preset)",
)
parser.add_argument(
    "--model",
    default=DEFAULT_MODEL,
    metavar="MODEL_ID",
    help=f"Bedrock model ID (default: {DEFAULT_MODEL})",
)
parser.add_argument(
    "--role-arn",
    default=None,
    metavar="ARN",
    help="Use an existing IAM execution role ARN instead of creating one",
)
parser.add_argument(
    "--system-prompt",
    default=None,
    metavar="TEXT",
    help="System prompt (default: auto-generated based on container)",
)
parser.add_argument(
    "--commands",
    nargs="*",
    metavar="CMD",
    help="Extra commands to run on the VM after invocation (e.g. 'node --version' 'ls /tmp')",
)
parser.add_argument("--skip-cleanup", action="store_true", help="Keep resources after the demo")
parser.add_argument("--raw-events", action="store_true", help="Print raw streaming events")
args = parser.parse_args()


# ---------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------
def aws_cp(*cli_args: str) -> dict:
    """aws bedrock-agentcore-control 명령을 실행하고 파싱한 JSON을 반환한다."""
    cmd = ["aws", "bedrock-agentcore-control", "--region", REGION]
    cmd.extend(cli_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def wait_ready(harness_id: str, timeout: int = 120):
    """Harness가 READY 상태가 될 때까지 폴링한다."""
    deadline = time.monotonic() + timeout
    while True:
        status = aws_cp("get-harness", "--harness-id", harness_id)["harness"]["status"]
        print(f"  Status: {status}")
        if status == "READY":
            return
        if time.monotonic() > deadline:
            raise TimeoutError(f"Harness not ready after {timeout}s")
        time.sleep(5)


def stream_invoke(client, harness_arn, session_id, message, model_id):
    """Harness를 호출하고 응답을 스트리밍한다."""
    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": message}]}],
        model={"bedrockModelConfig": {"modelId": model_id}},
    )
    for event in response["stream"]:
        if args.raw_events:
            print(json.dumps(event, default=str))
        elif "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                print(f"\n  [Tool: {start['toolUse'].get('name', '?')}]", flush=True)
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                print(delta["text"], end="", flush=True)
        elif "messageStop" in event:
            print()
        elif "internalServerException" in event:
            print(f"\n  Error: {event['internalServerException']}")


def run_command(client, harness_arn, session_id, command):
    """에이전트 VM에서 명령을 실행한다."""
    print(f"  $ {command}")
    resp = client.invoke_agent_runtime_command(
        agentRuntimeArn=harness_arn,
        runtimeSessionId=session_id,
        body={"command": command},
    )
    for event in resp["stream"]:
        if args.raw_events:
            print(json.dumps(event, default=str))
        elif "chunk" in event:
            chunk = event["chunk"]
            if "contentDelta" in chunk:
                d = chunk["contentDelta"]
                if "stdout" in d:
                    print(f"  {d['stdout']}", end="", flush=True)
                if "stderr" in d:
                    print(f"  {d['stderr']}", end="", flush=True)
            elif "contentStop" in chunk:
                print(f"  [exit: {chunk['contentStop']['exitCode']}]")
    print()


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main():
    # 언어 프리셋을 결정한다. 명시적인 --container/--message 값은 프리셋보다 우선한다.
    preset = LANGUAGE_PRESETS[args.language]
    container_uri = args.container or preset["container"]
    message = args.message or preset["message"]
    model_id = args.model

    # 지정하지 않은 경우 컨테이너 이미지 이름으로 system prompt를 자동 생성한다.
    if args.system_prompt:
        system_prompt = args.system_prompt
    else:
        image_name = container_uri.rsplit("/", 1)[-1].split(":")[0]
        system_prompt = (
            f"You are a helpful coding assistant. You have access to a {image_name} runtime. "
            "When asked to write and run code, save it to a file and execute it using the shell."
        )

    harness_id = None
    try:
        # 0단계: IAM 역할
        print("=" * 60)
        print("Step 0: IAM execution role")
        print("=" * 60)
        if args.role_arn:
            role_arn = args.role_arn
            print(f"  Using provided role: {role_arn}")
        else:
            role_arn = create_harness_role()

        # 1단계: Harness 생성
        print("\n" + "=" * 60)
        print("Step 1: Create Harness")
        print("=" * 60)
        name = f"ContainerCLI_{uuid.uuid4().hex[:8]}"
        resp = aws_cp("create-harness", "--harness-name", name, "--execution-role-arn", role_arn)
        harness_id = resp["harness"]["harnessId"]
        harness_arn = resp["harness"]["arn"]
        print(f"  Harness ID:  {harness_id}")
        print(f"  Harness ARN: {harness_arn}")
        wait_ready(harness_id)

        # 2단계: 사용자 지정 컨테이너 연결
        print("\n" + "=" * 60)
        print(f"Step 2: Attach custom container ({container_uri})")
        print("=" * 60)
        aws_cp(
            "update-harness",
            "--harness-id",
            harness_id,
            "--environment-artifact",
            json.dumps({"optionalValue": {"containerConfiguration": {"containerUri": container_uri}}}),
            "--system-prompt",
            json.dumps([{"text": system_prompt}]),
        )
        wait_ready(harness_id)

        # 3단계: 에이전트 호출
        print("\n" + "=" * 60)
        print("Step 3: Invoke agent")
        print("=" * 60)

        client = get_agentcore_client()
        session_id = str(uuid.uuid4()).upper()
        print(f"  Session ID: {session_id}")
        print(f"  Model:      {model_id}")
        print(f"  Message:    {message[:80]}{'...' if len(message) > 80 else ''}\n")
        stream_invoke(client, harness_arn, session_id, message, model_id)

        # 4단계: ExecuteCommand
        print("\n" + "=" * 60)
        print("Step 4: Run commands on the agent's VM (ExecuteCommand)")
        print("=" * 60)
        default_commands = ["cat /etc/os-release | head -3", "ls /tmp/"]
        commands = args.commands if args.commands else default_commands
        for cmd in commands:
            run_command(client, harness_arn, session_id, cmd)

        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

    finally:
        if harness_id and not args.skip_cleanup:
            print("\nCleaning up...")
            try:
                aws_cp("delete-harness", "--harness-id", harness_id)
                print(f"  Deleted harness: {harness_id}")
            except Exception as e:
                print(f"  Warning: cleanup failed: {e}")


if __name__ == "__main__":
    main()
