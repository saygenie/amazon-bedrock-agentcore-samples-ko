"""Pay for API - AgentCore Runtime buyer agent입니다.

AgentCore Runtime contract를 준수하도록 FastAPI ``/invocations`` endpoint로
감싼 최소 구성의 Strands Agent입니다. Agent에는 ``strands-agents-tools``의
``http_request`` tool 하나만 있으며, ``bedrock-agentcore``의
``AgentCorePaymentsPlugin``을 사용해 HTTP 402 -> ``ProcessPayment`` -> 재시도를
투명하게 처리합니다.

Private key나 수동 x402 조립은 사용하지 않습니다. 호출자는
``agentcore-payments/payment-agent`` 패턴과 마찬가지로 호출할 때마다 결제
컨텍스트(manager ARN, instrument ID, session ID, vendor 수준 user ID)를 제공합니다.

Runtime 호출 contract:

    POST /invocations
    {
        "prompt":          "Tell me one fact about space",
        "sellerUrl":       "https://example.com/",
        "managerArn":      "arn:aws:bedrock-agentcore:…:payment-manager/…",
        "instrumentId":    "payment-instrument-…",
        "sessionId":       "payment-session-…",
        "paymentUserId":   "<CDP UUID | Privy DID>",
        "region":          "us-west-2"          # optional, defaults to AWS_REGION
    }

상태 확인 endpoint:

    GET /ping  ->  {"status": "ok"}
"""

from __future__ import annotations

# ── ADOT 자동 계측(다른 import보다 먼저 실행해야 함) ──
# 이 환경 변수는 AgentCore Runtime이 컨테이너에 주입하는 ADOT collector를 통해
# trace와 log를 CloudWatch로 내보내는 방법을 AWS Distro for OpenTelemetry에
# 알려 줍니다. 일부 OTEL library가 import 시점에 환경 변수를 읽으므로 module
# 맨 위에서 설정해야 합니다.
import os

os.environ.setdefault("AGENT_OBSERVABILITY_ENABLED", "true")
os.environ.setdefault("OTEL_PYTHON_DISTRO", "aws_distro")
os.environ.setdefault("OTEL_PYTHON_CONFIGURATOR", "aws_configurator")
os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
os.environ.setdefault("OTEL_TRACES_EXPORTER", "otlp")
os.environ.setdefault("OTEL_LOGS_EXPORTER", "otlp")
# 관심 있는 observability 영역(결제 호출, tool 사용, HTTP request)은 trace와 log로
# 확인할 수 있으므로 metric을 비활성화합니다. 필요하면 활성화하세요.
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")

try:
    from opentelemetry.instrumentation.auto_instrumentation._load import (
        _load_configurators,
        _load_distro,
        _load_instrumentors,
    )

    _distro = _load_distro()
    _distro.configure()
    _load_configurators()
    _load_instrumentors(_distro)
except Exception as _otel_err:  # noqa: BLE001 — ADOT optional for local dev
    import sys

    print(f"[WARN] ADOT auto-instrumentation skipped: {_otel_err}", file=sys.stderr)

# ── 표준 import ──
import logging

import boto3
import botocore.exceptions
import fastapi
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("pay-for-api-agent")

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
# Claude Sonnet 4.5 cross-region inference profile(US)입니다.
MODEL_ID = os.environ.get(
    "MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)

# AgentCore Memory - 설정되어 있으면 모든 호출이
# (memory_id, actor_id=paymentUserId, 호출별 session_id)를 키로 사용하는
# AgentCoreMemorySessionManager를 거칩니다. CDK stack이 컨테이너 환경에 이 값을
# 설정하며, 변수가 없으면 agent는 Memory 없이 실행됩니다.
MEMORY_ID = os.environ.get("BEDROCK_AGENTCORE_MEMORY_ID", "")

# AgentCorePaymentsPlugin 활성화 설정입니다. 격리된 runtime을 Notebook이
# 호출하므로 컨테이너에서는 기본적으로 활성화됩니다. 디버깅 시 결제 없는
# agent로 전환하려면 "0" 또는 "false"로 설정하세요.
ENABLE_PAYMENTS_PLUGIN = os.environ.get("ENABLE_PAYMENTS_PLUGIN", "1").lower() in (
    "1",
    "true",
    "yes",
)

# AgentCore Payments vended log delivery 활성화 설정입니다. 활성화 상태에서
# 첫 호출에 `managerArn`이 제공되면 agent가 해당 Manager의 CloudWatch Logs
# vended delivery를 구성합니다. 멱등성이 있어 재실행해도 아무 작업을 하지 않으며
# 기본적으로 활성화됩니다.
ENABLE_VENDED_LOG_DELIVERY = os.environ.get("ENABLE_VENDED_LOG_DELIVERY", "1").lower() in ("1", "true", "yes")

# agent가 호출할 때마다 control plane을 다시 호출하지 않도록 vended delivery를
# 이미 구성한 Manager ARN을 추적합니다.
_VENDED_LOG_DELIVERY_CONFIGURED: set[str] = set()

SYSTEM_PROMPT = (
    "You are a research agent powered by Amazon Bedrock AgentCore Payments.\n"
    "\n"
    "Your only tool is `http_request`. Use it to fetch paid facts from the\n"
    "Fun Facts API. Each `GET` returns exactly one fact and costs $0.01 in\n"
    "USDC. The AgentCore Payments plugin pays on your behalf — you never\n"
    "handle private keys, assemble payment headers, or retry failed calls.\n"
    "\n"
    "SELLER CONTRACT\n"
    "  Endpoint:          GET <seller>/facts?topic=<topic>\n"
    "  Supported topics:  space, oceans, ai, payments\n"
    "                     (any other value falls back to a random general fact)\n"
    '  Success body:      {"x402_content": {"data": "<JSON string>", ...},\n'
    '                      "x402_meta":    {"seller": ..., "generated_at": ...}}\n'
    "                     `x402_content.data` is a JSON string — parse it to\n"
    '                     read `{"topic": ..., "fact": ...}`.\n'
    "  Price per call:    $0.01 USDC.\n"
    "\n"
    "RULES\n"
    "  1. One `http_request` GET per topic the user asks about.\n"
    "     If the user asks for two topics, make two calls.\n"
    "  2. If the user's topic is not in the supported list, pick the closest\n"
    "     supported topic rather than letting the seller fall back silently —\n"
    "     e.g. 'volcanoes' → 'space', 'whales' → 'oceans'.\n"
    "  3. Parse `x402_content.data` to get the `fact` and answer concisely,\n"
    "     citing each fact verbatim.\n"
    "  4. End every response with the total amount spent in USD — $0.01 per\n"
    "     successful call.\n"
)


def _ensure_vended_log_delivery(manager_arn: str, region: str) -> None:
    """PaymentManager의 CloudWatch Logs vended delivery를 멱등 방식으로 연결합니다.

    다음 control plane 작업은 재실행 시 아무 작업도 하지 않습니다.

      1. ``CreateLogGroup`` - 없으면 대상 Log Group을 생성합니다.
      2. ``PutDeliverySource`` - Payments -> log pipeline을 구성합니다.
      3. ``PutDeliveryDestination`` - Log Group을 대상으로 지정합니다.
      4. ``CreateDelivery`` - source를 destination에 연결합니다.

    Manager의 log 전송 권한은 호출 principal의 다음 IAM 권한으로 부여됩니다.
    ``bedrock-agentcore:PaymentsAllowVendedLogDeliveryForResource`` and
    ``bedrock-agentcore:AllowVendedLogDeliveryForResource``. 이 권한은 CDK
    stack에서 agent runtime execution role에 이미 연결되며, CloudWatch는 두
    권한을 product 및 service 수준 gate로 확인합니다. Vended delivery를
    활성화하는 별도의 SDK 호출은 없습니다. Payment Manager ARN을 대상으로
    ``put_delivery_source``를 실행할 때 CloudWatch가 두 권한을 암묵적으로
    확인합니다. 자세한 내용은
    ``docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AWS-logs-infrastructure-V2-service-specific.html``을
    참조하세요.

    ``ConflictException`` 및 이미 존재함을 나타내는 응답은 무시하므로 agent가
    확인하는 모든 Manager에서 부작용 없이 실행할 수 있습니다.
    """
    if not ENABLE_VENDED_LOG_DELIVERY or not manager_arn:
        return
    if manager_arn in _VENDED_LOG_DELIVERY_CONFIGURED:
        return

    # 동일한 Manager를 재실행할 때 중복 생성하지 않고 같은 log group을 사용하도록
    # Manager ID에서 안정적인 Manager 범위 log group 이름을 만듭니다. Manager ID는
    # ARN의 마지막 path segment입니다.
    manager_id = manager_arn.rsplit("/", 1)[-1]
    log_group_name = f"/bedrock-agentcore/payments/{manager_id}"
    source_name = f"pay-for-api-payments-src-{manager_id}"
    destination_name = f"pay-for-api-payments-dest-{manager_id}"

    logs_client = boto3.client("logs", region_name=region)

    # 아래에서 destination ARN을 구성할 수 있도록 STS에서 account를 조회합니다.
    account_id = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    destination_arn = f"arn:aws:logs:{region}:{account_id}:delivery-destination:{destination_name}"
    log_group_arn = f"arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}"

    def _swallow(code_set: set[str], fn, **kwargs):
        """fn(**kwargs)를 호출하고 지정된 error code는 무시합니다."""
        try:
            return fn(**kwargs)
        except botocore.exceptions.ClientError as exc:
            err_code = exc.response["Error"].get("Code", "")
            if err_code in code_set:
                return None
            raise

    # 1. Delivery 대상으로 지정하기 전에 log group이 있는지 확인합니다.
    _swallow(
        {"ResourceAlreadyExistsException"},
        logs_client.create_log_group,
        logGroupName=log_group_name,
    )

    # 2. Delivery source - Payments resource가 APPLICATION_LOGS를 내보냅니다.
    # 이 시점에 CloudWatch는 resourceArn을 대상으로 호출자의
    # bedrock-agentcore:PaymentsAllowVendedLogDeliveryForResource and
    # bedrock-agentcore:AllowVendedLogDeliveryForResource permissions
    # 권한을 검증합니다. 둘 중 하나라도 없으면 이 호출은
    # AccessDeniedException을 반환합니다.
    _swallow(
        {"ConflictException", "ResourceAlreadyExistsException"},
        logs_client.put_delivery_source,
        name=source_name,
        resourceArn=manager_arn,
        logType="APPLICATION_LOGS",
    )

    # 3. Delivery destination - 방금 확인한 Log Group입니다.
    _swallow(
        {"ConflictException", "ResourceAlreadyExistsException"},
        logs_client.put_delivery_destination,
        name=destination_name,
        deliveryDestinationConfiguration={
            "destinationResourceArn": log_group_arn,
        },
    )

    # 4. Source를 destination에 연결합니다. CreateDelivery는 (source, destination)
    # 쌍에 대해 멱등성을 가지므로 재실행 시 ConflictException을 반환합니다.
    _swallow(
        {"ConflictException", "ResourceAlreadyExistsException"},
        logs_client.create_delivery,
        deliverySourceName=source_name,
        deliveryDestinationArn=destination_arn,
    )

    _VENDED_LOG_DELIVERY_CONFIGURED.add(manager_arn)
    logger.info(
        "Vended log delivery ensured for Manager %s → %s",
        manager_id,
        log_group_name,
    )


def _build_agent(payment_config: dict | None):
    """http_request tool 하나로 Strands Agent를 구성하고, 결제 컨텍스트가 제공되면
    x402 자동 처리를 위한 AgentCorePaymentsPlugin을 연결합니다.

    ``payment_config`` 키:
      - manager_arn, instrument_id, session_id, payment_user_id, region
    """
    from strands import Agent
    from strands.models.bedrock import BedrockModel
    from strands_tools import http_request

    model = BedrockModel(
        model_id=MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.7,
    )

    # ── AgentCoreMemorySessionManager ──
    # Memory는 (memory_id, actor_id, session_id)를 키로 사용합니다. 어떤 Notebook
    # kernel 또는 process가 runtime을 구동하더라도 한 사용자의 모든 호출이 동일한
    # actor로 집계되도록 vendor가 할당한 paymentUserId를 actor로 사용합니다.
    # Memory를 사용할 수 없으면(SDK version 문제, resource 누락 등) log를 남기고
    # Memory 없이 계속하며 plugin은 그대로 동작합니다.
    session_manager = None
    actor_id = (payment_config or {}).get("payment_user_id") or ""
    if MEMORY_ID and actor_id:
        try:
            import uuid as _uuid

            from bedrock_agentcore.memory.integrations.strands.config import (
                AgentCoreMemoryConfig,
            )
            from bedrock_agentcore.memory.integrations.strands.session_manager import (
                AgentCoreMemorySessionManager,
            )

            session_id = f"{actor_id}-{_uuid.uuid4().hex[:8]}"
            memory_config = AgentCoreMemoryConfig(
                memory_id=MEMORY_ID,
                session_id=session_id,
                actor_id=actor_id,
            )
            session_manager = AgentCoreMemorySessionManager(
                agentcore_memory_config=memory_config,
                region_name=AWS_REGION,
            )
            logger.info(
                "AgentCoreMemorySessionManager attached memory=%s actor=%s session=%s",
                MEMORY_ID,
                actor_id,
                session_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Memory session manager unavailable, continuing without: %s",
                exc,
            )

    plugins: list = []
    if ENABLE_PAYMENTS_PLUGIN and payment_config:
        missing = [
            k for k in ("manager_arn", "instrument_id", "session_id", "payment_user_id") if not payment_config.get(k)
        ]
        if missing:
            logger.info(
                "AgentCorePaymentsPlugin skipped — missing fields on this invocation: %s",
                missing,
            )
        else:
            try:
                from bedrock_agentcore.payments.integrations.config import (
                    AgentCorePaymentsPluginConfig,
                )
                from bedrock_agentcore.payments.integrations.strands.plugin import (
                    AgentCorePaymentsPlugin,
                )

                plugin_cfg = AgentCorePaymentsPluginConfig(
                    payment_manager_arn=payment_config["manager_arn"],
                    user_id=payment_config["payment_user_id"],
                    payment_instrument_id=payment_config["instrument_id"],
                    payment_session_id=payment_config["session_id"],
                    region=payment_config.get("region") or AWS_REGION,
                    agent_name="pay-for-api-agent",
                    network_preferences_config=payment_config.get("network_preferences"),
                )
                plugins.append(AgentCorePaymentsPlugin(config=plugin_cfg))
                logger.info(
                    "AgentCorePaymentsPlugin attached — manager=%s instrument=%s session=%s user=%s",
                    payment_config["manager_arn"],
                    payment_config["instrument_id"],
                    payment_config["session_id"],
                    payment_config["payment_user_id"],
                )
            except Exception as exc:  # noqa: BLE001 — plugin optional at edit time
                logger.warning(
                    "AgentCorePaymentsPlugin init failed, continuing without: %s",
                    exc,
                )

    kwargs: dict = {
        "model": model,
        "tools": [http_request],
        "system_prompt": SYSTEM_PROMPT,
    }
    if plugins:
        kwargs["plugins"] = plugins
    if session_manager is not None:
        kwargs["session_manager"] = session_manager

    # 손상된 Memory session 때문에 호출이 실패하지 않도록 agent 생성을
    # try/retry로 감쌉니다. 실패하면 Memory를 제외하고 새 agent로 재시도하며
    # plugin의 결제 기능은 그대로 유지됩니다.
    try:
        return Agent(**kwargs)
    except Exception as exc:  # noqa: BLE001
        if session_manager is None:
            raise
        logger.warning(
            "Agent init with memory failed (%s) — retrying without memory",
            exc,
        )
        kwargs.pop("session_manager", None)
        return Agent(**kwargs)


# ── FastAPI app ──

app = FastAPI(title="Pay for API — Buyer Agent", version="1.0.0")


@app.get("/ping")
async def ping():
    return JSONResponse(content={"status": "ok"}, status_code=200)


# /invocations endpoint가 허용하는 최대 prompt 길이입니다. 호출별 Bedrock token
# 비용을 제한하고 수 MB 크기의 prompt가 한꺼번에 들어와 runtime memory를 채우는
# 일을 방지합니다. Use case에서 더 긴 prompt가 필요하면 늘릴 수 있으며, 이는
# 제품 제약이 아닌 방어적 상한입니다.
MAX_PROMPT_LEN = 5000


@app.post("/invocations")
async def invocations(request: fastapi.Request):
    try:
        data = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid JSON body on /invocations: %s", exc)
        return JSONResponse(
            content={"error": "Invalid JSON body"},
            status_code=400,
        )

    prompt = data.get("prompt") or data.get("text") or data.get("message") or ""
    seller_url = data.get("sellerUrl") or data.get("seller_url")
    if not prompt:
        return JSONResponse(content={"error": "prompt is required"}, status_code=400)
    if not seller_url:
        return JSONResponse(content={"error": "sellerUrl is required"}, status_code=400)

    # ── 방어적 입력 검증 ──
    # Prompt는 Bedrock으로 전달되고 seller URL은 http_request tool이 가져옵니다.
    # AgentCore Runtime이 자체 auth 및 payload validation으로 이 endpoint를
    # 보호하지만, 두 입력을 제한하면 악의적인 입력에도 runtime이 안정적으로
    # 동작합니다.
    if len(prompt) > MAX_PROMPT_LEN:
        return JSONResponse(
            content={"error": f"prompt exceeds {MAX_PROMPT_LEN} characters"},
            status_code=400,
        )
    if not (seller_url.startswith("https://") or seller_url.startswith("http://")):
        return JSONResponse(
            content={"error": "sellerUrl must be an http(s) URL"},
            status_code=400,
        )

    payment_config = {
        "manager_arn": data.get("managerArn") or data.get("manager_arn", ""),
        "instrument_id": data.get("instrumentId") or data.get("instrument_id", ""),
        "session_id": data.get("sessionId") or data.get("session_id", ""),
        "payment_user_id": data.get("paymentUserId") or data.get("payment_user_id", ""),
        "region": data.get("region", AWS_REGION),
        "network_preferences": (data.get("networkPreferences") or data.get("network_preferences")),
    }

    # Manager를 처음 확인할 때 vended log delivery를 연결합니다. 이후 동일
    # process에서 같은 Manager를 만나면 아무 작업도 하지 않습니다. Observability는
    # 최선형 부가 기능이므로 오류는 log에 기록하되 호출을 실패시키지 않습니다.
    try:
        _ensure_vended_log_delivery(
            manager_arn=payment_config["manager_arn"],
            region=payment_config["region"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vended log delivery setup failed, continuing: %s", exc)

    # Agent가 GET할 정확한 URL을 알 수 있도록 user prompt 앞에 seller URL을
    # 추가합니다. System prompt에 넣지 않으므로 Notebook에서 다시 build하지 않고도
    # 동일한 agent가 여러 seller를 가리키게 할 수 있습니다.
    enriched_prompt = f"Seller URL: {seller_url.rstrip('/')}/facts\n\n{prompt}"

    try:
        agent = _build_agent(payment_config=payment_config)
        result = agent(enriched_prompt)
        return JSONResponse(content={"response": str(result)})
    except Exception as exc:  # noqa: BLE001
        logger.error("Invocation error: %s", exc, exc_info=True)
        return JSONResponse(
            content={"error": "Agent invocation failed. See runtime logs for details."},
            status_code=500,
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    # AgentCore Runtime은 모든 interface에서 컨테이너로 traffic을 route하므로
    # 기본적으로 컨테이너 내부의 0.0.0.0에 bind합니다. 개발자 장비에서 컨테이너를
    # 직접 실행할 때는 HOST=127.0.0.1로 재정의하세요.
    host = os.environ.get("HOST", "0.0.0.0")  # nosec B104 — required by AgentCore Runtime
    logger.info("Starting pay-for-api agent on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
