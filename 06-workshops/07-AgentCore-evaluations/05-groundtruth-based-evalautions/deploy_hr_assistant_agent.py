"""agentcore CLI를 사용하여 HR Assistant 에이전트를 AgentCore Runtime에 배포합니다.

Notebook에서 다음 명령으로 실행합니다: %run -i deploy_hr_assistant_agent.py

호출자의 네임스페이스에 REGION이 설정되어 있어야 합니다(2단계 구성 셀).
호출자의 네임스페이스에 다음 항목을 설정합니다: AGENT_ID, AGENT_ARN, CW_LOG_GROUP, agentcore_client

CodeBuild 이미지 빌드, ECR 푸시, OTel 계측, Runtime 생성을 처리하는
bedrock-agentcore의 agentcore CLI를 사용합니다.
"""

import subprocess
import time
import uuid

import boto3

_REGION = REGION  # noqa: F821
_AGENT_NAME = f"hr_assistant_{uuid.uuid4().hex[:8]}"

# ---- 1. 구성 ----
print(f"Configuring agent '{_AGENT_NAME}' ...")
subprocess.run(
    [
        "agentcore",
        "configure",
        "--entrypoint",
        "hr_assistant_agent.py",
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
print("\nDeploying HR Assistant Agent ...")
print("  This takes ~5 minutes on first run (image build + push + runtime creation).")
subprocess.run(
    ["agentcore", "deploy", "--auto-update-on-conflict"],
    check=True,
)
print("Deploy complete.")

# ---- 3. control plane에서 AGENT_ID와 AGENT_ARN 가져오기 ----
print("\nRetrieving agent info ...")
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
if AGENT_ID:
    cp = boto3.client("bedrock-agentcore-control", region_name=_REGION)
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

CW_LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT"
agentcore_client = boto3.client("bedrock-agentcore", region_name=_REGION)

print(f"\nAGENT_ID     : {AGENT_ID}")
print(f"AGENT_ARN    : {AGENT_ARN}")
print(f"CW_LOG_GROUP : {CW_LOG_GROUP}")
print("Deploy complete.")
