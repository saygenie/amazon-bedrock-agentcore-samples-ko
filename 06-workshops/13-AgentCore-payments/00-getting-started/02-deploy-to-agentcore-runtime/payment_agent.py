"""
AgentCore Runtime을 위한 payment-enabled Strands Agent입니다.

이 agent는 AgentCorePaymentsPlugin을 사용하여 x402 payment를 자동으로
처리합니다. AgentCore Runtime에 배포되면 ProcessPaymentRole execution role로
실행되며 application backend에서 설정한 budget 내에서만 payment를
처리할 수 있습니다.

App backend는 invocation payload를 통해 모든 payment context를 전달합니다.
  - payment_manager_arn
  - payment_session_id (payment limit이 있는 새 session)
  - payment_instrument_id
  - user_id

Agent는 environment variable에서 payment config를 읽지 않습니다.
따라서 agent가 stateless 상태로 유지되고 app backend에서 agent의
access 대상을 제어하도록 강제합니다.

배포:
    agentcore create --name PaymentAgent --defaults
    agentcore deploy
"""

import json
import os

from bedrock_agentcore.payments.integrations.strands import (
    AgentCorePaymentsPlugin,
    AgentCorePaymentsPluginConfig,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel
from strands_tools import http_request

# 로컬 테스트를 위해 .env load — Runtime에서는 payload에서 값을 가져옴
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

app = BedrockAgentCoreApp()

# Payment 외 config인 model과 region만 env에서 가져옴
REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")

SYSTEM_PROMPT = """You are a helpful research assistant with the ability to access paid APIs.
Use the http_request tool to access URLs. When you encounter paid content behind x402 paywalls,
the payment is handled automatically within your session budget.
Always report what you found and how much it cost."""


@app.entrypoint
def handle_request(payload, context=None):
    """App backend의 invocation을 처리합니다.

    인수:
        payload: Invoker의 JSON dict. 다음 항목을 포함해야 합니다.
            - prompt: 사용자 request
            - payment_manager_arn: Payment Manager의 ARN
            - user_id: Payment 격리를 위한 user identifier
            - payment_session_id: Budget이 있는 Session(app backend에서 생성)
            - payment_instrument_id: 결제에 사용할 Wallet(app backend에서 생성)
        context: AgentCore Runtime context(session_id 등 제공)

    App backend가 session을 생성하고 모든 payment context를 전달합니다.
    Agent는 ProcessPaymentRole로 실행되며 session budget 내에서만 지출할
    수 있습니다. Session 또는 Instrument는 생성할 수 없습니다.
    """
    # agentcore invoke는 JSON arg를 {"prompt": "<json-string>"}으로 래핑
    raw_prompt = payload.get("prompt", "")
    if isinstance(raw_prompt, str) and raw_prompt.strip().startswith("{"):
        try:
            inner = json.loads(raw_prompt)
            if "payment_manager_arn" in inner:
                payload = inner
        except json.JSONDecodeError:
            pass

    prompt = payload.get("prompt", "Hello")
    payment_manager_arn = payload.get("payment_manager_arn")
    user_id = payload.get("user_id")
    session_id = payload.get("payment_session_id")
    instrument_id = payload.get("payment_instrument_id")

    # 모든 payment field가 app backend에서 전달되었는지 검증
    missing = []
    if not payment_manager_arn:
        missing.append("payment_manager_arn")
    if not user_id:
        missing.append("user_id")
    if not session_id:
        missing.append("payment_session_id")
    if not instrument_id:
        missing.append("payment_instrument_id")
    if missing:
        return {"error": f"Missing required fields in payload: {', '.join(missing)}"}

    # App backend의 context로 request별 plugin 생성
    payment_plugin = AgentCorePaymentsPlugin(
        config=AgentCorePaymentsPluginConfig(
            payment_manager_arn=payment_manager_arn,
            user_id=user_id,
            payment_instrument_id=instrument_id,
            payment_session_id=session_id,
            region=REGION,
            network_preferences_config=["eip155:84532", "base-sepolia"],
        )
    )

    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, streaming=True),
        tools=[http_request],
        plugins=[payment_plugin],
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent(prompt)
    return {"response": result.message.get("content", [{}])[0].get("text", str(result))}


if __name__ == "__main__":
    app.run()
