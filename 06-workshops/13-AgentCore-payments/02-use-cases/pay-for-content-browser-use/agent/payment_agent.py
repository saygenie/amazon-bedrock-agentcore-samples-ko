"""
Pay for Content (Browser Use) - AgentCore Runtime용 Strands agent입니다.

Agent는 AgentCoreBrowser를 사용해 paywall 페이지로 이동하고, DOM에서
x402 요구 사항을 읽고, process_x402_payment를 호출해 proof를 생성한 뒤
paywall UI에 입력하고 잠금 해제된 콘텐츠를 반환합니다.

AgentCore Runtime에 배포하면 컨테이너는 ProcessPaymentRole로 실행됩니다.
Agent의 PaymentManager는 컨테이너의 ambient credential을 사용하며,
agent 내부에서는 sts:AssumeRole을 호출하지 않습니다.

앱 백엔드(Notebook)는 ManagementRole로 payment session을 생성하고
호출 payload를 통해 모든 결제 컨텍스트를 전달합니다.

    payment_manager_arn      - Payment Manager ARN
    payment_session_id       - 예산이 설정된 새 session
    payment_instrument_id    - 결제에 사용할 wallet
    user_id                  - 결제 격리 키
    paywall_url              - 가져올 페이지

브라우저 x402 패턴에서는 HTTP 402 응답이 아니라 DOM의 <script> 요소에서
요구 사항을 읽습니다. 따라서 plugin의 자동 가로채기 hook은 실행되지 않으며,
process_x402_payment가 PaymentManager에서 요구하는 가상의 402 형식을 구성합니다.
"""

import json
import os
import uuid

from bedrock_agentcore.payments.integrations.strands import (
    AgentCorePaymentsPlugin,
    AgentCorePaymentsPluginConfig,
)
from bedrock_agentcore.payments.manager import PaymentManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands_tools.browser import AgentCoreBrowser

app = BedrockAgentCoreApp()

REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")
# AgentCore Payments observability dashboard의 "Agents using Payments" 카운터와
# 각 결제 span의 `payment_agent_name` 속성에 보고되는 식별자입니다.
# PaymentManager를 agent_name=으로 생성하면 모든 data-plane 호출에서
# X-Amzn-Bedrock-AgentCore-Payments-Agent-Name HTTP header를 통해 설정됩니다.
AGENT_NAME = os.environ.get("AGENT_NAME", "PayForContentBrowserAgent")

SYSTEM_PROMPT = """\
You are a content retrieval agent with access to Amazon Bedrock AgentCore payments.
You can autonomously browse paywalled websites and pay for premium content using the
x402 micropayment protocol — without any human involvement in the payment step.

When asked to retrieve content from a URL, follow these steps in order:

1. Use the browser tool to navigate to the URL.
2. Find the <script id="x402-requirement"> element and read its JSON content.
3. Call process_x402_payment with the full JSON text of that element.
4. Use the browser tool to interact with the paywall UI:
   - Discover payment form elements dynamically using button text, input types,
     and aria-labels — do not rely on hardcoded IDs from any particular site.
   - On the reference sample content provider the IDs are: pay-btn, proof-input,
     verify-btn, content — but real x402 sites will differ.
5. Wait for the content to become visible, then extract and return it.
6. Report the content retrieved and the amount paid in USDC.

Always be transparent about what you paid and what content you retrieved.
"""


@app.entrypoint
def handle_request(payload, context=None):
    """앱 백엔드에서 전달된 paywall 조회 요청을 처리합니다.

    Args:
        payload: 다음 항목을 포함하는 dict:
            prompt                 - 자연어 작업(URL 포함 가능)
            paywall_url            - 대상 paywall 페이지
            payment_manager_arn    - Payment Manager ARN
            user_id                - 결제 격리 키
            payment_session_id     - 예산이 설정된 새 session
            payment_instrument_id  - 결제에 사용할 wallet
        context: AgentCore Runtime 컨텍스트(session_id 등을 제공)
    """
    # `agentcore invoke`는 JSON 인수를 {"prompt": "<json-string>"}으로 감싸므로 이를 해제합니다.
    raw_prompt = payload.get("prompt", "")
    if isinstance(raw_prompt, str) and raw_prompt.strip().startswith("{"):
        try:
            inner = json.loads(raw_prompt)
            if "payment_manager_arn" in inner:
                payload = inner
        except json.JSONDecodeError:
            pass

    payment_manager_arn = payload.get("payment_manager_arn")
    user_id = payload.get("user_id")
    session_id = payload.get("payment_session_id")
    instrument_id = payload.get("payment_instrument_id")
    paywall_url = payload.get("paywall_url")
    prompt = payload.get("prompt") or (
        f"Please retrieve the premium article from {paywall_url}. "
        f"Pay for it using x402 and give me a summary of what it contains."
    )

    missing = [
        name
        for name, value in [
            ("payment_manager_arn", payment_manager_arn),
            ("user_id", user_id),
            ("payment_session_id", session_id),
            ("payment_instrument_id", instrument_id),
            ("paywall_url", paywall_url),
        ]
        if not value
    ]
    if missing:
        return {"error": f"Missing required fields in payload: {', '.join(missing)}"}

    # PaymentManager는 컨테이너의 ambient credential을 사용합니다(배포 시에는
    # ProcessPaymentRole, 로컬 개발 실행 시에는 현재 활성화된 role).
    # agent_name은 모든 data-plane 호출의
    # X-Amzn-Bedrock-AgentCore-Payments-Agent-Name header를 채워
    # AgentCore Payments observability가 span/metric을 이 agent에 연결할 수 있게 합니다.
    payment_manager = PaymentManager(
        payment_manager_arn=payment_manager_arn,
        region_name=REGION,
        agent_name=AGENT_NAME,
    )

    @tool
    def process_x402_payment(requirement_json: str) -> dict:
        """Process an x402 v2 payment requirement and return a signed proof.

        Args:
            requirement_json: JSON string of the x402 requirement read from
                              the <script id="x402-requirement"> DOM element.

        Returns:
            dict with proof_b64, amount, and status.
        """
        requirement = json.loads(requirement_json)

        first_accept = requirement["accepts"][0]
        amount_units = int(first_accept.get("maxAmountRequired") or first_accept.get("amount", 0))
        # Token의 최소 단위입니다(예: 소수점 6자리인 USDC의 경우 1_000_000).
        # 이 값은 표시를 위해 호출자에게 반환되며 routing이나 settlement에는
        # 사용되지 않습니다.
        amount = amount_units / 1_000_000

        # generate_payment_header는 HTTP 402 형식의 envelope을 요구합니다.
        # 브라우저 패턴에서는 HTTP 402 응답이 아닌 DOM script tag에서 요구 사항을
        # 가져오므로 SDK의 입력 contract에 맞게 감쌉니다.
        payment_required_request = {
            "statusCode": 402,
            "headers": {},
            "body": requirement,
        }

        header_dict = payment_manager.generate_payment_header(
            user_id=user_id,
            payment_instrument_id=instrument_id,
            payment_session_id=session_id,
            payment_required_request=payment_required_request,
            client_token=str(uuid.uuid4()),
        )
        proof_b64 = list(header_dict.values())[0]

        return {
            "proof_b64": proof_b64,
            "amount": amount,
            "status": "PROOF_GENERATED",
        }

    payments_plugin = AgentCorePaymentsPlugin(
        config=AgentCorePaymentsPluginConfig(
            payment_manager_arn=payment_manager_arn,
            user_id=user_id,
            payment_instrument_id=instrument_id,
            payment_session_id=session_id,
            region=REGION,
            agent_name=AGENT_NAME,
        )
    )

    agent_core_browser = AgentCoreBrowser(region=REGION)

    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[agent_core_browser.browser, process_x402_payment],
        plugins=[payments_plugin],
        model=MODEL_ID,
    )

    result = agent(prompt)
    text = result.message.get("content", [{}])[0].get("text", str(result))
    return {"response": text}


if __name__ == "__main__":
    app.run()
