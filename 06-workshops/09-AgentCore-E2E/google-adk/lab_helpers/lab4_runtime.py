import os
import uuid
import asyncio
import concurrent.futures
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp,
)  #### AGENTCORE RUNTIME - 1번 줄 ####

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import boto3
from bedrock_agentcore.memory import MemoryClient
from lab_helpers.utils import get_ssm_parameter

# boto3 클라이언트 초기화
sts_client = boto3.client("sts")

# AWS 계정 세부 정보 가져오기
REGION = boto3.session.Session().region_name

ACTOR_ID = "customer_001"

# Lab 2 가져오기: Memory
memory_id = os.environ.get("MEMORY_ID")
if not memory_id:
    raise Exception("Environment variable MEMORY_ID is required")

memory_client = MemoryClient(region_name=REGION)

# ============================================================
# 시스템 프롬프트
# ============================================================
SYSTEM_PROMPT = """You are a helpful and professional customer support assistant for an electronics e-commerce company.
Your role is to:
- Provide accurate information using the tools available to you
- Support the customer with technical information and product specifications.
- Be friendly, patient, and understanding with customers
- Always offer additional help after answering questions
- If you can't help with something, direct customers to the appropriate contact

You have access to the following tools:
1. get_return_policy() - For warranty and return policy questions
2. get_product_info() - To get information about a specific product
3. get_technical_support() - To search the technical support knowledge base
4. check_warranty_status() - To check warranty status via serial number (via AgentCore Gateway)
5. web_search() - To access current technical documentation, or for updated information (via AgentCore Gateway)
Always use the appropriate tool to get accurate, up-to-date information rather than making assumptions about electronic products or specifications."""

# ============================================================
# 로컬 도구(Lab 3과 동일)
# ============================================================


def get_return_policy(product_category: str) -> str:
    """Get return policy information for a specific product category.

    Args:
        product_category: Electronics category (e.g., 'smartphones', 'laptops', 'accessories')

    Returns:
        Formatted return policy details including timeframes and conditions
    """
    return_policies = {
        "smartphones": {
            "window": "30 days",
            "condition": "Original packaging, no physical damage, factory reset required",
            "process": "Online RMA portal or technical support",
            "refund_time": "5-7 business days after inspection",
            "shipping": "Free return shipping, prepaid label provided",
            "warranty": "1-year manufacturer warranty included",
        },
        "laptops": {
            "window": "30 days",
            "condition": "Original packaging, all accessories, no software modifications",
            "process": "Technical support verification required before return",
            "refund_time": "7-10 business days after inspection",
            "shipping": "Free return shipping with original packaging",
            "warranty": "1-year manufacturer warranty, extended options available",
        },
        "accessories": {
            "window": "30 days",
            "condition": "Unopened packaging preferred, all components included",
            "process": "Online return portal",
            "refund_time": "3-5 business days after receipt",
            "shipping": "Customer pays return shipping under $50",
            "warranty": "90-day manufacturer warranty",
        },
    }
    default_policy = {
        "window": "30 days",
        "condition": "Original condition with all included components",
        "process": "Contact technical support",
        "refund_time": "5-7 business days after inspection",
        "shipping": "Return shipping policies vary",
        "warranty": "Standard manufacturer warranty applies",
    }
    policy = return_policies.get(product_category.lower(), default_policy)
    return (
        f"Return Policy - {product_category.title()}:\n\n"
        f"\u2022 Return window: {policy['window']} from delivery\n"
        f"\u2022 Condition: {policy['condition']}\n"
        f"\u2022 Process: {policy['process']}\n"
        f"\u2022 Refund timeline: {policy['refund_time']}\n"
        f"\u2022 Shipping: {policy['shipping']}\n"
        f"\u2022 Warranty: {policy['warranty']}"
    )


def get_product_info(product_type: str) -> str:
    """Get detailed technical specifications and information for electronics products.

    Args:
        product_type: Electronics product type (e.g., 'laptops', 'smartphones', 'headphones', 'monitors')

    Returns:
        Formatted product information including warranty, features, and policies
    """
    products = {
        "laptops": {
            "warranty": "1-year standard, 3-year extended available",
            "specs": "Intel/AMD processors, 8-64GB RAM, SSD storage",
            "features": "Backlit keyboards, fingerprint readers, Thunderbolt ports",
            "compatibility": "Windows, Linux, macOS (Apple only)",
            "support": "24/7 technical support, on-site repair options",
        },
        "smartphones": {
            "warranty": "1-year manufacturer, 2-year extended",
            "specs": "Latest processors, 6-12GB RAM, 128GB-1TB storage",
            "features": "5G capable, water resistant, wireless charging",
            "compatibility": "iOS or Android ecosystem",
            "support": "In-store and mail-in repair services",
        },
        "headphones": {
            "warranty": "1-year standard warranty",
            "specs": "Bluetooth 5.0+, ANC, 20-40hr battery",
            "features": "Active noise cancellation, transparency mode, multipoint",
            "compatibility": "Universal Bluetooth, some with proprietary apps",
            "support": "Replacement program for defective units",
        },
        "monitors": {
            "warranty": "3-year standard, zero dead pixel guarantee",
            "specs": "4K/1440p resolution, 60-240Hz refresh rate",
            "features": "HDR support, high refresh rates, adjustable stands",
            "compatibility": "HDMI, DisplayPort, USB-C inputs",
            "support": "Color calibration and technical support",
        },
    }
    product = products.get(product_type.lower())
    if not product:
        return f"Technical specifications for {product_type} not available. Please contact our technical support team."
    return (
        f"Technical Information - {product_type.title()}:\n\n"
        f"\u2022 Warranty: {product['warranty']}\n"
        f"\u2022 Specifications: {product['specs']}\n"
        f"\u2022 Key Features: {product['features']}\n"
        f"\u2022 Compatibility: {product['compatibility']}\n"
        f"\u2022 Support: {product['support']}"
    )


def get_technical_support(issue_description: str) -> str:
    """Search the technical support knowledge base for troubleshooting help.

    Args:
        issue_description: Description of the technical issue or question.

    Returns:
        Relevant technical support documentation and troubleshooting steps.
    """
    try:
        ssm = boto3.client("ssm")
        acct = boto3.client("sts").get_caller_identity()["Account"]
        region = boto3.Session().region_name
        kb_id = ssm.get_parameter(Name=f"/{acct}-{region}/kb/knowledge-base-id")["Parameter"]["Value"]
        bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=region)
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": issue_description},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
        )
        results = response.get("retrievalResults", [])
        if not results:
            return "No relevant technical support documentation found for this issue."
        formatted_results = []
        for i, result in enumerate(results, 1):
            text = result.get("content", {}).get("text", "")
            score = result.get("score", 0)
            if score >= 0.4:
                formatted_results.append(f"--- Result {i} (relevance: {score:.2f}) ---\n{text}")
        if not formatted_results:
            return "No sufficiently relevant technical support documentation found."
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Unable to access technical support documentation. Error: {str(e)}"


# ============================================================
# MCP Gateway 도구 래퍼(Lab 3과 동일한 패턴)
# ============================================================


async def _call_mcp_tool(tool_name: str, arguments: dict, gateway_url: str, auth_header: str) -> str:
    """AgentCore Gateway의 MCP 도구를 호출하는 헬퍼."""
    async with streamablehttp_client(
        gateway_url,
        headers={"Authorization": auth_header},
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                return "\n".join(part.text for part in result.content if hasattr(part, "text"))
            return "No result returned."


def _run_async_in_thread(coro):
    """'event loop already running' 오류를 방지하도록 별도 스레드에서 비동기 코루틴을 실행한다."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


# 진입점에서 요청마다 설정됨
_gateway_url = None
_auth_header = None


def check_warranty_status(serial_number: str, customer_email: str) -> str:
    """Check the warranty status of a product using its serial number.

    Args:
        serial_number: The product serial number to look up.
        customer_email: Customer email for verification. Pass empty string if not available.

    Returns:
        Warranty status information for the product.
    """
    args = {"serial_number": serial_number}
    if customer_email:
        args["customer_email"] = customer_email
    return _run_async_in_thread(
        _call_mcp_tool("LambdaUsingSDK___check_warranty_status", args, _gateway_url, _auth_header)
    )


def web_search(keywords: str, region: str, max_results: int) -> str:
    """Search the web for updated information using DuckDuckGo.

    Args:
        keywords: The search query keywords.
        region: The search region (e.g., us-en, uk-en, ru-ru).
        max_results: The maximum number of results to return.

    Returns:
        Search results from the web.
    """
    args = {"keywords": keywords, "region": region, "max_results": max_results}
    return _run_async_in_thread(_call_mcp_tool("LambdaUsingSDK___web_search", args, _gateway_url, _auth_header))


# AgentCore Runtime 앱 초기화
app = BedrockAgentCoreApp()  #### AGENTCORE RUNTIME - 2번 줄 ####


@app.entrypoint  #### AGENTCORE RUNTIME - 3번 줄 ####
async def invoke(payload, context=None):
    """AgentCore Runtime 진입점 함수"""
    global _gateway_url, _auth_header

    user_input = payload.get("prompt", "")
    session_id = context.session_id  # 컨텍스트에서 session_id 가져오기
    actor_id = payload.get("actor_id", ACTOR_ID)
    # 요청 헤더에 접근하고 None인 경우 처리
    request_headers = context.request_headers or {}

    # 클라이언트 JWT 토큰 가져오기
    auth_header = request_headers.get("Authorization", "")
    print(f"Authorization header: {auth_header}")

    # Gateway ID 가져오기
    existing_gateway_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")

    # Bedrock AgentCore Control 클라이언트 초기화
    gateway_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=REGION,
    )
    # 기존 Gateway 세부 정보 가져오기
    gateway_response = gateway_client.get_gateway(gatewayIdentifier=existing_gateway_id)
    gateway_url = gateway_response["gatewayUrl"]

    if gateway_url and auth_header:
        try:
            # MCP 도구 래퍼용 모듈 수준 변수 설정
            _gateway_url = gateway_url
            _auth_header = auth_header

            # 모든 도구: 로컬 도구 + MCP Gateway 래퍼
            all_tools = [
                get_product_info,
                get_return_policy,
                get_technical_support,
                check_warranty_status,
                web_search,
            ]

            # --- 1. Memory에서 고객 컨텍스트 검색 ---
            all_context = []
            namespaces = {
                "preferences": f"support/customer/{actor_id}/preferences/",
                "semantic": f"support/customer/{actor_id}/semantic/",
            }
            for context_type, namespace in namespaces.items():
                try:
                    memories = memory_client.retrieve_memories(
                        memory_id=memory_id,
                        namespace=namespace,
                        query=user_input,
                        top_k=3,
                    )
                    for mem in memories:
                        if isinstance(mem, dict):
                            text = mem.get("content", {}).get("text", "").strip()
                            if text:
                                all_context.append(f"[{context_type.upper()}] {text}")
                except Exception as e:
                    print(f"Warning: Could not retrieve {context_type} memories: {e}")

            # --- 2. 컨텍스트가 포함된 보강 쿼리 구성 ---
            if all_context:
                context_text = "\n".join(all_context)
                enriched_query = f"Customer Context:\n{context_text}\n\n{user_input}"
            else:
                enriched_query = user_input

            # --- 3. ADK 에이전트 생성 및 실행 ---
            agent = LlmAgent(
                name="customer_support_agent",
                model=LiteLlm(model="bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0"),
                instruction=SYSTEM_PROMPT,
                tools=all_tools,
            )

            adk_session_id = str(uuid.uuid4())
            session_service = InMemorySessionService()
            adk_session = await session_service.create_session(  # noqa: F841
                app_name="customer_support_app",
                user_id="user_001",
                session_id=adk_session_id,
            )
            runner = Runner(
                agent=agent,
                app_name="customer_support_app",
                session_service=session_service,
            )
            content = types.Content(role="user", parts=[types.Part(text=enriched_query)])

            final_response = ""
            async for event in runner.run_async(user_id="user_001", session_id=adk_session_id, new_message=content):
                if event.is_final_response():
                    final_response = event.content.parts[0].text

            # --- 4. Memory에 상호 작용 저장 ---
            if final_response:
                try:
                    memory_client.create_event(
                        memory_id=memory_id,
                        actor_id=actor_id,
                        session_id=str(session_id),
                        messages=[
                            (user_input, "USER"),
                            (final_response, "ASSISTANT"),
                        ],
                    )
                except Exception as e:
                    print(f"Warning: Could not save to memory: {e}")

            return final_response
        except Exception as e:
            print(f"Agent error: {str(e)}")
            return f"Error: {str(e)}"
    else:
        return "Error: Missing gateway URL or authorization header"


if __name__ == "__main__":
    app.run()  #### AGENTCORE RUNTIME - 4번 줄 ####
