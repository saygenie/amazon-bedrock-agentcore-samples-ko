"""agentcore CLI를 사용하여 Shopping Concierge 에이전트를 AgentCore Runtime에 배포합니다.

Notebook에서 다음 명령으로 실행합니다: %run -i deploy_shopping_concierge_agent.py

호출자의 네임스페이스에 REGION이 설정되어 있어야 합니다(2단계 구성 셀).
호출자의 네임스페이스에 다음 항목을 설정합니다: AGENT_ID, AGENT_ARN, RUNTIME_ARN,
    SERVICE_NAME, LOG_GROUP, SPANS_LOG_GROUP

CodeBuild 이미지 빌드, ECR 푸시, OTel 계측, Runtime 생성을 처리하는
bedrock-agentcore의 agentcore CLI를 사용합니다.
"""

import subprocess
import time
import uuid

import boto3

_REGION = REGION  # noqa: F821
_AGENT_NAME = f"shopping_concierge_{uuid.uuid4().hex[:8]}"

# ---- 1. 구성 ----
print(f"Configuring agent '{_AGENT_NAME}' ...")
subprocess.run(
    [
        "agentcore",
        "configure",
        "--entrypoint",
        "shopping_concierge_agent.py",
        "--name",
        _AGENT_NAME,
        "--region",
        _REGION,
        "--requirements-file",
        "requirements.txt",
        "--non-interactive",
    ],
    check=True,
)
print("Configuration complete.")

# ---- 2. 배포 ----
print("\nDeploying Shopping Concierge Agent ...")
print("  This takes ~5 minutes on first run (image build + push + runtime creation).")
subprocess.run(
    ["agentcore", "deploy", "--auto-update-on-conflict"],
    check=True,
)
print("Deploy complete.")

# ---- 3. 에이전트 ID 가져오기 ----
cp = boto3.client("bedrock-agentcore-control", region_name=_REGION)
AGENT_ID = ""
AGENT_ARN = ""
paginator = cp.get_paginator("list_agent_runtimes")
for page in paginator.paginate():
    for rt in page.get("agentRuntimes", []):
        if rt.get("agentRuntimeName") == _AGENT_NAME:
            AGENT_ID = rt["agentRuntimeId"]
            AGENT_ARN = rt["agentRuntimeArn"]
            break
    if AGENT_ID:
        break

if not AGENT_ID:
    raise RuntimeError(f"Could not find {_AGENT_NAME} runtime after deploy")

# ---- 4. READY 상태 대기 ----
print("Waiting for READY ...")
for elapsed in range(0, 600, 15):
    status = cp.get_agent_runtime(agentRuntimeId=AGENT_ID).get("status", "UNKNOWN")
    print(f"  [{elapsed:>3}s] {status}")
    if status in ("READY", "ACTIVE"):
        break
    if status in ("FAILED", "CREATE_FAILED", "UPDATE_FAILED"):
        raise RuntimeError(f"Deploy failed: {status}")
    time.sleep(15)
else:
    raise TimeoutError("Agent did not reach READY in 600s")

# ---- Notebook용 변수 설정 ----
RUNTIME_ARN = AGENT_ARN
SERVICE_NAME = f"{_AGENT_NAME}.DEFAULT"
LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT"
SPANS_LOG_GROUP = "aws/spans"

print(f"\nAGENT_ID     : {AGENT_ID}")
print(f"AGENT_ARN    : {AGENT_ARN}")
print(f"RUNTIME_ARN  : {RUNTIME_ARN}")
print(f"SERVICE_NAME : {SERVICE_NAME}")
print(f"LOG_GROUP    : {LOG_GROUP}")
print("Deploy complete.")
