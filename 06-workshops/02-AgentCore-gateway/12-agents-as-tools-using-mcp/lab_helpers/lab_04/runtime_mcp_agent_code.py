#!/usr/bin/env python3
"""
Lab 4: AgentCore Browser를 사용하는 Strands Prevention Agent - AgentCore Runtime 배포
Gateway-to-Runtime 통신용 MCP 프로토콜을 FastMCP로 구현합니다.

주요 내용:
- FastMCP를 사용한 MCP 프로토콜 구현
- 예방 중심의 인프라 분석
- AgentCore Browser를 사용한 실시간 AWS 문서 조사
- 문제 예방을 위한 선제적 권장 사항
- 최신 AWS 모범 사례

서버리스 실행을 위해 AgentCore Runtime에 배포됩니다.
"""

import os
import logging

# MCP 프로토콜 구현용 FastMCP
from fastmcp import FastMCP

# Strands 프레임워크
from strands import Agent
from strands.models import BedrockModel
from strands_tools.browser import AgentCoreBrowser

# AgentCore 배포 시 도구 동의 우회
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# CloudWatch 수집을 위한 명시적 StreamHandler로 로깅 구성
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
    force=True,
)

# 올바른 AgentCore 로그 수집을 위해 bedrock_agentcore.app 네임스페이스 사용
logger = logging.getLogger("bedrock_agentcore.app")

# 핸들러가 존재하는지 확인
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# 환경 변수(AgentCore Runtime에서 설정)
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

# 환경 진단 정보 기록
logger.info("=" * 80)
logger.info("AGENT INITIALIZATION DIAGNOSTICS")
logger.info("=" * 80)
logger.info(f"Python Version: {sys.version}")
logger.info(f"AWS_REGION: {AWS_REGION}")
logger.info(f"MODEL_ID: {MODEL_ID}")
logger.info(f"DOCKER_CONTAINER: {os.environ.get('DOCKER_CONTAINER', 'NOT SET')}")
logger.info(f"PYTHONUNBUFFERED: {os.environ.get('PYTHONUNBUFFERED', 'NOT SET')}")
logger.info("=" * 80)

# AgentCore Runtime용 FastMCP 서버 초기화
# host="0.0.0.0" - AgentCore 요구 사항에 따라 모든 인터페이스에서 수신
# stateless_http=True - 엔터프라이즈 보안을 위한 세션 격리 활성화
mcp = FastMCP("SRE Prevention Agent", host="0.0.0.0", stateless_http=True)  # nosec B104

# Browser 및 Agent용 전역 변수
agentcore_browser = None
prevention_agent = None
BROWSER_AVAILABLE = False


def initialize_browser(region=AWS_REGION):
    """웹 조사용 AgentCore Browser를 초기화합니다."""
    global agentcore_browser, BROWSER_AVAILABLE

    try:
        logger.debug(f"[DIAGNOSTIC] Attempting to initialize AgentCoreBrowser in region: {region}")
        agentcore_browser = AgentCoreBrowser(region=region)
        BROWSER_AVAILABLE = True
        logger.info("✅ AgentCore Browser initialized")
        logger.debug(f"[DIAGNOSTIC] Browser type: {type(agentcore_browser)}")
        return True
    except Exception as e:
        BROWSER_AVAILABLE = False
        logger.error("❌ AgentCore Browser initialization failed", exc_info=True)
        logger.warning(f"⚠️ AgentCore Browser not available: {e}")
        return False


# FastMCP 도구 정의
logger.debug("[DIAGNOSTIC] Registering FastMCP tools...")


@mcp.tool()
def research_agent(research_topic_query: str):
    """Research AWS best practices and prevention strategies using AgentCore Browser

    Analyzes infrastructure for proactive improvements by accessing real-time AWS documentation. Provides prevention recommendations, implementation roadmaps, and monitoring best practices.

    Args:
        research_topic_query: Topic to research (e.g., "DynamoDB performance optimization", "EC2 cost reduction strategies", "S3 security hardening")

    Returns:
        Analysis with prevention opportunities, AWS best practices, and implementation guidance
    """

    global prevention_agent, agentcore_browser, BROWSER_AVAILABLE

    try:
        logger.debug("[DIAGNOSTIC] setup_prevention_agent() called")
        logger.info("=" * 80)
        logger.info("📥 INCOMING REQUEST")
        logger.info(f"research_topic_query: {research_topic_query}")
        logger.info("=" * 80)

        logger.debug("[DIAGNOSTIC] setup_prevention_agent() called")

        if not BROWSER_AVAILABLE:
            logger.debug("[DIAGNOSTIC] Browser not available, initializing...")
            initialize_browser(AWS_REGION)

        if not BROWSER_AVAILABLE:
            logger.debug("[DIAGNOSTIC] Browser initialization failed, returning None")
            return None

        # 이미 초기화된 전역 Browser 인스턴스 재사용
        logger.debug("[DIAGNOSTIC] Using existing AgentCoreBrowser instance...")
        if not agentcore_browser:
            logger.error("[DIAGNOSTIC] Browser flag is True but instance is None!")
            return None

        # Bedrock 모델 설정
        logger.debug(f"[DIAGNOSTIC] Setting up BedrockModel with model_id: {MODEL_ID}")
        model = BedrockModel(
            model_id=MODEL_ID,
            streaming=True,
        )

        # 기존 Browser 인스턴스를 재사용하여 Browser 도구가 포함된 Agent 생성
        logger.debug("[DIAGNOSTIC] Creating Strands Agent with browser tool...")
        system_prompt = """ I need you to analyze our CRM infrastructure for prevention opportunities using the available tool to access AWS documentation. 

    
    Please use the browser tool to access these specific AWS documentation pages and provide analysis:
    
    1. First, use the browser tool to visit: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html
    2. Then visit: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-best-practices.html  
    3. Finally visit: https://docs.aws.amazon.com/wellarchitected/latest/framework/
    
    Based on what you find in the AWS documentation, provide analysis focusing on:
    
    1. **Proactive Infrastructure Management**: Best practices we should implement
    4. **Monitoring and Alerting**: Best practices for proactive monitoring
    
    Provide your analysis with:
    - Executive summary of prevention opportunities
    - Implementation roadmap with AWS best practices
    - Success metrics for measuring prevention effectiveness
    
    """
        prevention_agent = Agent(system_prompt=system_prompt, model=model, tools=[agentcore_browser.browser])

        logger.info("✅ Prevention agent with browser tool initialized")
        logger.debug(f"[DIAGNOSTIC] Agent type: {type(prevention_agent)}")
        # logger.debug(f"System prompt length: {len(system_prompt)}")
        # logger.debug(f"Tools: {[tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in prevention_agent.tools]}")

    except Exception as e:
        logger.error("❌ Failed to setup prevention agent", exc_info=True)
        logger.error(f"Exception: {e}")
        return f"Error: Failed to initialize agent - {str(e)}"

    return_text = ""
    response = prevention_agent(research_topic_query)
    # 3. 원시 응답 객체 기록
    logger.info("=" * 80)
    logger.info("📤 RAW AGENT RESPONSE")
    logger.info(f"Response type: {type(response)}")
    logger.info(f"Response attributes: {dir(response)}")
    logger.debug(f"Full response object: {response}")
    logger.debug(f"Response.message: {response.message}")
    logger.info("=" * 80)
    response_content = response.message.get("content", [])
    if response_content:
        for content in response_content:
            if isinstance(content, dict) and "text" in content:
                return_text = content["text"]

    return return_text


# 참고: Browser는 첫 번째 도구 호출 시 지연 초기화됨
# 모듈 가져오기 및 FastMCP 서버 시작 중 차단을 방지함

logger.info("=" * 80)
logger.info("🚀 Module loaded - Browser will initialize on first tool call (lazy)")
logger.info("=" * 80)


# FastMCP 서버 실행
if __name__ == "__main__":
    # AgentCore Runtime에는 상태 비저장 streamable-HTTP 전송이 필요함(stdio 아님)
    # AWS 문서 참조: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
    # - 전송: streamable-http(상태 비저장, HTTP 기반)
    # - 포트: 8000(MCP 프로토콜 요구 사항)
    # - 호스트: 0.0.0.0(모든 인터페이스에서 수신)

    logger.info("=" * 80)
    logger.info("🚀 PHASE 2: FastMCP Server Startup")
    logger.info("=" * 80)
    logger.info("Starting FastMCP server with streamable-http transport on port 8000")
    logger.debug(f"[DIAGNOSTIC] FastMCP instance: {mcp}")
    logger.debug(
        f"[DIAGNOSTIC] FastMCP tools: {mcp.list_tools() if hasattr(mcp, 'list_tools') else 'method not available'}"
    )
    logger.info("=" * 80)

    try:
        logger.info("🔌 Calling mcp.run(transport='streamable-http')...")
        mcp.run(transport="streamable-http")
    except Exception as e:
        logger.error("❌ FastMCP server failed to start", exc_info=True)
        logger.error(f"Exception: {e}")
        raise
