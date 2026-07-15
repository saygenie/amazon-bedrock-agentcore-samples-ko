"""
A2A Client와 IAM 인증

이 클라이언트는 AWS IAM(SigV4) 인증을 사용해 AgentCore Runtime에 배포된
A2A Agent에 연결하는 방법을 보여 줍니다.
"""

import asyncio
import logging
import sys
from uuid import uuid4
from urllib.parse import quote

import boto3
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5분


class SigV4HTTPXAuth(httpx.Auth):
    """AWS SigV4로 요청에 서명하는 HTTPX Auth 클래스입니다."""

    def __init__(self, credentials, service: str, region: str):
        self.credentials = credentials
        self.service = service
        self.region = region
        self.signer = SigV4Auth(credentials, service, region)

    def auth_flow(self, request: httpx.Request):
        """SigV4로 요청에 서명하고 요청 헤더에 서명을 추가합니다."""
        headers = dict(request.headers)
        headers.pop("connection", None)  # 서명을 위해 connection 헤더 제거

        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )

        self.signer.add_auth(aws_request)
        request.headers.update(dict(aws_request.headers))

        yield request


def create_message(*, role: Role = Role.user, text: str) -> Message:
    """A2A 메시지를 생성합니다."""
    return Message(
        kind="message",
        role=role,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
    )


def format_agent_response(event):
    """Agent 응답을 추출하고 읽기 쉬운 형식으로 지정합니다."""
    # 튜플 응답 처리(event가 (response, metadata)일 수 있음)
    response = event[0] if isinstance(event, tuple) else event

    if hasattr(response, "artifacts") and response.artifacts and len(response.artifacts) > 0:
        artifact = response.artifacts[0]
        if artifact.parts and len(artifact.parts) > 0:
            return artifact.parts[0].root.text

    # 대체 방식: 기록의 모든 Agent 메시지 연결
    if hasattr(response, "history"):
        agent_messages = [msg.parts[0].root.text for msg in response.history if msg.role.value == "agent" and msg.parts]
        return "".join(agent_messages)

    # 마지막 수단으로 문자열 표현 반환
    return str(response)


async def test_agent(agent_arn: str, message: str):
    """IAM 인증을 사용해 A2A Agent를 테스트합니다."""

    # AWS 세션 및 자격 증명 가져오기
    boto_session = boto3.Session()
    region = boto_session.region_name
    credentials = boto_session.get_credentials()

    logger.info(f"Using AWS region: {region}")
    logger.info(f"Testing agent: {agent_arn}")

    # Runtime URL 구성
    escaped_agent_arn = quote(agent_arn, safe="")
    runtime_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations/"

    # 세션 ID 생성
    session_id = str(uuid4())
    logger.info(f"Session ID: {session_id}")

    # SigV4 인증 생성
    auth = SigV4HTTPXAuth(credentials, "bedrock-agentcore", region)

    # AgentCore용 추가 헤더
    headers = {
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, auth=auth, headers=headers) as httpx_client:
            # Agent Card 가져오기
            logger.info("Fetching agent card...")
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=runtime_url)
            agent_card = await resolver.get_agent_card()

            logger.info(f"Agent: {agent_card.name}")
            logger.info(f"Description: {agent_card.description}")

            # A2A Client 생성
            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=False,
            )
            factory = ClientFactory(config)
            client = factory.create(agent_card)

            # 메시지 전송
            logger.info(f"\nSending message: {message}")
            msg = create_message(text=message)

            async for event in client.send_message(msg):
                response_text = format_agent_response(event)
                logger.info(f"\nAgent response:\n{response_text}")
                return response_text

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def main():
    """Agent를 테스트하는 메인 함수입니다."""

    # 환경 또는 명령줄에서 Agent ARN 가져오기
    import os

    agent_arn = os.environ.get("AGENT_ARN")

    if not agent_arn:
        if len(sys.argv) > 1:
            agent_arn = sys.argv[1]
        else:
            logger.error("Please provide AGENT_ARN environment variable or as command line argument")
            sys.exit(1)

    # 테스트 메시지
    test_messages = [
        "Hello! What can you do?",
        "Please greet me. My name is Alice.",
        "Tell me about yourself.",
    ]

    for message in test_messages:
        logger.info("\n" + "=" * 60)
        await test_agent(agent_arn, message)
        await asyncio.sleep(1)  # 요청 사이에 잠시 대기


if __name__ == "__main__":
    asyncio.run(main())
