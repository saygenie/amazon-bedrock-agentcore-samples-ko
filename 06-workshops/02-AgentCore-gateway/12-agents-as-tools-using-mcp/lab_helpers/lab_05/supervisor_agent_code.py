#!/usr/bin/env python3
"""
Lab 5: Supervisor Agent - Multi-Agent 오케스트레이션
MCP를 사용해 세 개의 전문 Agent(Diagnostics, Remediation, Prevention)를 오케스트레이션합니다.

AgentCore Runtime에 배포되며 /invocations 엔드포인트를 노출합니다.
JWT 토큰 전파 사용: Client JWT → Supervisor Runtime → MCP Gateways
"""

import os
import logging
from typing import Dict

# AWS SDK
import boto3
from botocore.config import Config as BotocoreConfig

# Strands 프레임워크
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# MCP 프로토콜
from mcp.client.streamable_http import streamablehttp_client

# 사용자 지정 요청 처리가 포함된 HTTP 서버용 FastAPI
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# AgentCore 배포 시 도구 동의 우회
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# 로깅 구성
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bedrock_agentcore.app")

# 환경 변수(AgentCore Runtime에서 설정)
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-20250514-v1:0")

# Gateway ID 파라미터 경로
DIAGNOSTICS_GATEWAY_PARAM = "/aiml301/lab-02/gateway-id"
REMEDIATION_GATEWAY_PARAM = "/aiml301_sre_agentcore/lab-03/gateway-id"
PREVENTION_GATEWAY_PARAM = "/aiml301_sre_agentcore/lab-04/gateway-id"

# Supervisor 시스템 prompt
SUPERVISOR_SYSTEM_PROMPT = os.environ.get(
    "SUPERVISOR_SYSTEM_PROMPT",
    """
# Supervisor Agent System Prompt

You are an expert SRE Supervisor Agent that orchestrates three specialized sub-agents to provide complete infrastructure troubleshooting solutions.

## Sub-Agent Tools

### 1. Diagnostic Agent (prefix: d_)
- Analyzes AWS infrastructure to identify root causes
- Provides detailed diagnostic information
- Identifies performance bottlenecks and configuration issues

### 2. Remediation Agent (prefix: r_)
- Executes infrastructure fixes and remediation scripts
- Implements corrective actions with approval workflows
- Uses AgentCore Code Interpreter for secure execution

### 3. Prevention Agent (prefix: p_)
- Researches AWS best practices and preventive measures
- Provides proactive recommendations
- Uses AgentCore Browser for real-time documentation

## Orchestration Workflow

For each user request:
1. **Diagnose**: Use diagnostic tools to identify issues
2. **Remediate**: Execute approved remediation steps (with approval)
3. **Prevent**: Provide preventive recommendations

## Response Structure

Always provide:
- **Summary**: Brief overview of the issue
- **Diagnostic Results**: What was found
- **Remediation Actions**: What was fixed (if applicable)
- **Prevention Recommendations**: How to avoid future issues

## Tool Usage Guidelines

- Use diagnostic tools (d_*) to analyze and identify problems
- Use remediation tools (r_*) for fixes (requires approval)
- Use prevention tools (p_*) for best practices and research
- Coordinate across agents for comprehensive solutions

## Safety Rules

- Always validate environment before making changes
- Require explicit approval for remediation actions
- Provide clear explanations of all actions taken
- Include risk assessments for remediation steps
""",
)

# 반복 조회를 방지하기 위한 Gateway URL 캐시
gateway_urls_cache = {}


def get_gateway_urls_from_parameter_store() -> Dict[str, str]:
    """
    다음 방식으로 Gateway URL을 가져옵니다.
    1. Parameter Store에서 Gateway ID 조회
    2. AgentCore API를 사용해 ID를 URL로 변환

    반환:
        'diagnostics', 'remediation', 'prevention' 키가 포함된 딕셔너리
    """
    # 캐시된 URL이 있으면 반환
    if gateway_urls_cache:
        return gateway_urls_cache

    try:
        ssm_client = boto3.client("ssm", region_name=AWS_REGION)
        agentcore_client = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION)

        # Gateway ID 파라미터 경로
        gateway_id_params = {
            "diagnostics": DIAGNOSTICS_GATEWAY_PARAM,
            "remediation": REMEDIATION_GATEWAY_PARAM,
            "prevention": PREVENTION_GATEWAY_PARAM,
        }

        urls = {}
        for name, param_path in gateway_id_params.items():
            try:
                # Parameter Store에서 Gateway ID 조회
                response = ssm_client.get_parameter(Name=param_path, WithDecryption=True)
                gateway_id = response["Parameter"]["Value"]
                logger.info(f"✅ Fetched {name} gateway ID from SSM: {gateway_id}")

                # AgentCore API를 사용해 Gateway ID를 URL로 변환
                gateway_response = agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
                gateway_url = gateway_response["gatewayUrl"]
                urls[name] = gateway_url
                logger.info(f"✅ Converted to {name} gateway URL: {gateway_url}")

            except ssm_client.exceptions.ParameterNotFound:
                logger.warning(f"⚠️  SSM parameter not found: {param_path}")
                urls[name] = ""
            except Exception as e:
                logger.error(f"Error fetching {name} gateway: {e}")
                urls[name] = ""

        # URL 캐시
        gateway_urls_cache.update(urls)
        return urls

    except Exception as e:
        logger.error(f"Error connecting to Parameter Store or AgentCore: {e}")
        return {"diagnostics": "", "remediation": "", "prevention": ""}


def create_supervisor_agent(auth_headers: Dict[str, str]) -> Agent:
    """
    모든 하위 Agent 도구가 포함된 Strands supervisor agent를 생성합니다.

    인자:
        auth_headers: MCP 클라이언트에 전달할 인증 헤더(JWT Authorization 헤더 포함)

    반환:
        모든 하위 Agent 도구가 포함된 초기화된 Strands Agent
    """
    logger.info("🤖 Creating Supervisor Agent...")

    # Gateway URL 조회
    logger.info("📦 Fetching gateway URLs from Parameter Store...")
    gateway_urls = get_gateway_urls_from_parameter_store()

    # 64자 제한 이내의 짧은 접두사로 MCP 클라이언트 초기화
    gateway_configs = [
        ("Diagnostics", gateway_urls["diagnostics"], "d"),
        ("Remediation", gateway_urls["remediation"], "r"),
        ("Prevention", gateway_urls["prevention"], "p"),
    ]

    mcp_clients = []
    all_tools = []

    logger.info("🔧 Connecting to specialized agent gateways...")

    import time

    for name, url, prefix in gateway_configs:
        if url:
            logger.info(f"   • Connecting to {name} Gateway: {url}")
            try:
                # 사용자 요청의 JWT 토큰이 포함된 인증 헤더로 MCPClient 생성
                # Lambda가 Authorization 헤더를 포함한 auth_headers를 캡처함
                connect_start = time.time()
                client = MCPClient(
                    lambda u=url, h=auth_headers: streamablehttp_client(u, headers=h),
                    prefix=prefix,
                )
                # 클라이언트 연결을 즉시 열기
                client.__enter__()
                connect_duration = time.time() - connect_start
                mcp_clients.append((name, client, prefix))
                logger.info(f"   ✅ {name} MCP client created ({connect_duration:.2f}s) (prefix: {prefix}_)")

                # 사용 가능한 도구 나열
                tools_start = time.time()
                tools = client.list_tools_sync()
                tools_duration = time.time() - tools_start
                all_tools.extend(tools)
                logger.info(f"   • {name} Agent: {len(tools)} tools ({tools_duration:.2f}s)")

            except Exception as e:
                elapsed = time.time() - connect_start if "connect_start" in locals() else 0
                logger.error(f"   ❌ Failed to create {name} MCP client after {elapsed:.2f}s: {e}")
        else:
            logger.warning(f"   ⚠️  {name} Gateway URL not configured - skipping")

    if len(all_tools) == 0:
        logger.error("❌ No tools available - agent cannot be created")
        return None

    logger.info(f"✅ Total tools available: {len(all_tools)}")

    try:
        # 하위 Agent의 모든 도구가 포함된 Strands agent 생성
        # Multi-Agent Orchestration을 위해 더 긴 제한 시간으로 botocore 구성
        bedrock_config = BotocoreConfig(
            connect_timeout=300,
            read_timeout=3600,  # 복잡한 오케스트레이션 작업을 위한 60분 제한 시간
            retries={"total_max_attempts": 1, "mode": "standard"},
        )

        model = BedrockModel(
            model_id=MODEL_ID,
            region_name=AWS_REGION,  # region이 아닌 region_name 파라미터 사용
            boto_client_config=bedrock_config,  # 제한 시간 설정용 botocore 구성 전달
        )

        agent = Agent(model=model, tools=all_tools, system_prompt=SUPERVISOR_SYSTEM_PROMPT)

        logger.info("✅ Supervisor agent created successfully")
        logger.info(f"   Model: {MODEL_ID}")
        logger.info(f"   Region: {AWS_REGION}")
        logger.info(f"   Total tools: {len(all_tools)}")

        # 참조를 저장하여 MCP 클라이언트 유지
        agent._mcp_clients = mcp_clients

        return agent

    except Exception as e:
        logger.error(f"❌ Failed to create supervisor agent: {e}")
        return None


def agent_function(prompt: str, auth_headers: Dict[str, str]) -> str:
    """
    /invocations 엔드포인트에서 호출하는 메인 Agent 함수입니다.

    인자:
        prompt: 사용자의 입력 prompt
        auth_headers: 요청의 인증 헤더(JWT 토큰 포함)

    반환:
        문자열 형식의 Agent 응답
    """
    import time

    start_time = time.time()
    logger.info(f"🎯 Supervisor invocation: {prompt[:100]}...")

    # 올바른 인증 헤더를 사용해 이 요청용 Agent 생성
    logger.info("⏳ Creating supervisor agent...")
    agent_start = time.time()
    agent = create_supervisor_agent(auth_headers)
    agent_duration = time.time() - agent_start
    logger.info(f"✅ Agent creation took {agent_duration:.2f}s")

    if not agent:
        logger.error("❌ Supervisor agent not initialized")
        return "Error: Supervisor agent not initialized. Check Runtime logs."

    try:
        # 사용자 prompt로 Supervisor Agent 호출
        # Agent가 적절한 하위 Agent로 지능적으로 라우팅함
        logger.info("⏳ Executing supervisor orchestration...")
        exec_start = time.time()
        response = agent(prompt)
        exec_duration = time.time() - exec_start
        logger.info(f"✅ Orchestration execution took {exec_duration:.2f}s")

        # 응답 텍스트 추출
        response_text = ""
        if hasattr(response, "message") and "content" in response.message:
            for content in response.message["content"]:
                if isinstance(content, dict) and "text" in content:
                    response_text += content["text"]
        else:
            response_text = str(response)

        total_duration = time.time() - start_time
        logger.info(f"✅ Supervisor orchestration complete (total: {total_duration:.2f}s)")

        return response_text

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Supervisor orchestration error after {elapsed:.2f}s: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return f"Error during orchestration: {str(e)}"


# HTTP 서버용 FastAPI 앱 생성
app = FastAPI()


@app.get("/ping")
async def ping():
    """
    Health check endpoint required by AgentCore Runtime.
    Returns status and timestamp to indicate the runtime is healthy.
    """
    import time

    logger.info("🏥 Health check ping")
    return {
        "status": "Healthy",
        "time_of_last_update": int(time.time() * 1000),  # 밀리초 단위 Unix 타임스탬프
    }


@app.post("/invocations")
async def invoke(request: Request):
    """
    Entrypoint for AgentCore Runtime invocations.
    Called via POST /invocations endpoint.

    Args:
        request: HTTP request object with headers and body

    Returns:
        JSON response with agent output
    """
    try:
        # 요청 본문에서 페이로드 추출
        payload = await request.json()

        # 다양한 페이로드 형식을 처리하며 prompt 추출
        if isinstance(payload, dict):
            prompt = payload.get("input", {}).get("prompt", "") or payload.get("prompt", "")
        else:
            prompt = str(payload)

        # HTTP 요청에서 Authorization 헤더 추출
        # 이 JWT 토큰은 Gateway 연결로 전파됨
        auth_header = request.headers.get("Authorization", "")

        logger.info(f"✅ Received request with Authorization header: {auth_header[:50] if auth_header else 'NONE'}...")

        # MCP 클라이언트용 인증 헤더 구성(사용자 JWT 토큰 전달)
        auth_headers = {}
        if auth_header:
            auth_headers["Authorization"] = auth_header
        else:
            logger.warning("⚠️  No Authorization header found in request - gateway auth may fail")

        # 인증 헤더와 함께 Agent 함수 호출
        response_text = agent_function(prompt, auth_headers)

        return JSONResponse({"response": response_text, "status": "success"})

    except Exception as e:
        logger.error(f"❌ Error processing request: {e}")
        import traceback

        logger.error(traceback.format_exc())

        return JSONResponse(
            {
                "response": "Error processing request. Check server logs for details.",
                "status": "error",
            },
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Supervisor Agent Runtime...")
    logger.info(f"   Model: {MODEL_ID}")
    logger.info(f"   Region: {AWS_REGION}")
    logger.info("   Listening on 0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)  # nosec B104
