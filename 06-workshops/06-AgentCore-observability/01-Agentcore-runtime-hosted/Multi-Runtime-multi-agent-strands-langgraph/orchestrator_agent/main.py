"""
Orchestrator Agent: 하위 에이전트를 조정하는 Strands 기반 에이전트입니다.
트레이스 상관관계를 위해 세션 ID를 전파하며 AgentCore Runtime을 직접 호출합니다.
"""

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from opentelemetry import baggage
import boto3
import json
import logging
import os
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = BedrockAgentCoreApp()

MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")


def get_ssm_parameter(name: str) -> str:
    """SSM에서 파라미터를 가져옵니다."""
    return boto3.client("ssm").get_parameter(Name=name)["Parameter"]["Value"]


def get_region() -> str:
    """AWS 리전을 가져옵니다."""
    return boto3.Session().region_name or os.getenv("AWS_REGION", "us-east-1")


class OrchestratorAgent:
    """직접 호출을 통해 하위 에이전트를 조정하는 오케스트레이터입니다."""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.region = get_region()

        # 하위 에이전트 호출용 AgentCore 클라이언트 생성
        self.agentcore_client = boto3.client("bedrock-agentcore", region_name=self.region)

        # SSM에서 하위 에이전트 ARN 로드
        self.travel_arn = get_ssm_parameter("/agents/travel_agent_arn")
        self.weather_arn = get_ssm_parameter("/agents/weather_agent_arn")

        logger.info(f"Initialized orchestrator with session: {session_id}")
        logger.info(f"Travel agent ARN: {self.travel_arn}")
        logger.info(f"Weather agent ARN: {self.weather_arn}")

        # 도구를 포함한 에이전트 생성
        model = BedrockModel(model_id=MODEL_ID)
        self.agent = Agent(
            name="Orchestrator",
            model=model,
            tools=[self._make_travel_tool(), self._make_weather_tool()],
            system_prompt="""You coordinate between specialized agents to help users.
Use ask_travel_agent for destinations, attractions, and travel tips.
Use ask_weather_agent for weather information.
Always call the appropriate agent tools to get real information, then combine the responses into a helpful answer.""",
        )

    def _call_sub_agent(self, agent_arn: str, query: str) -> str:
        """세션을 전파하며 AgentCore Runtime을 통해 하위 에이전트를 호출합니다."""
        try:
            payload = json.dumps({"prompt": query})

            logger.info(f"Calling sub-agent {agent_arn} with session {self.session_id}")

            # 올바른 API 파라미터 사용
            response = self.agentcore_client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                qualifier="DEFAULT",
                payload=payload,
                runtimeSessionId=self.session_id,  # 트레이스 상관관계에 사용
                runtimeUserId=self.user_id,  # SIGV4 인증에 필요
            )

            # 응답 읽기: 'body'가 아닌 'response' 키 사용
            response_body = response["response"].read().decode("utf-8")
            logger.info(f"Sub-agent response: {response_body[:200]}...")

            # 응답 파싱
            result = json.loads(response_body)

            # 래핑된 응답 형식 처리
            if isinstance(result, dict) and "response" in result:
                resp = result["response"]
                if isinstance(resp, list):
                    return " ".join(str(item) for item in resp)
                return str(resp)
            return str(result)

        except Exception as e:
            logger.error(f"Sub-agent call failed: {e}", exc_info=True)
            return f"Error calling agent: {str(e)}"

    def _make_travel_tool(self):
        @tool
        def ask_travel_agent(query: str) -> str:
            """Ask the travel agent for destinations, attractions, and travel tips."""
            return self._call_sub_agent(self.travel_arn, query)

        return ask_travel_agent

    def _make_weather_tool(self):
        @tool
        def ask_weather_agent(query: str) -> str:
            """Ask the weather agent for current weather information."""
            return self._call_sub_agent(self.weather_arn, query)

        return ask_weather_agent

    def invoke(self, query: str) -> str:
        response = self.agent(query)
        return response.message["content"][0]["text"]


@app.entrypoint
def invoke(payload, context):
    """AgentCore Runtime에서 세션 컨텍스트를 받는 기본 진입점입니다."""
    prompt = payload.get("prompt", "")

    # AgentCore 컨텍스트에서 세션 ID를 가져오거나 새로 생성
    session_id = context.session_id if hasattr(context, "session_id") else str(uuid.uuid4())

    # 전파를 위해 OpenTelemetry baggage에 세션 ID 설정
    baggage.set_baggage("session.id", session_id)

    # 헤더에서 사용자 ID를 가져오거나 기본값 사용
    request_headers = context.request_headers or {}
    user_id = request_headers.get(
        "x-amzn-bedrock-agentcore-runtime-user-id",
        request_headers.get("x-amzn-bedrock-agentcore-runtime-custom-actorid", "orchestrator-user"),
    )

    logger.info(f"Orchestrator received: {prompt}")
    logger.info(f"Session ID: {session_id}, User ID: {user_id}")

    orchestrator = OrchestratorAgent(session_id, user_id)
    return orchestrator.invoke(prompt)


if __name__ == "__main__":
    app.run()
