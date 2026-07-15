import logging
import os
import traceback

from fastapi import WebSocket, WebSocketDisconnect

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """You are a friendly companion having a casual chat. Be warm, conversational, and natural. Keep responses concise and engaging."""


def get_system_prompt() -> str:
    """Banking Assistant의 기본 system prompt를 가져옵니다."""
    return DEFAULT_SYSTEM_PROMPT


async def handle_websocket_session(websocket: WebSocket, default_gateway_arns: list, send_output=None):
    """
    WebSocket 세션을 처리합니다. 구성 이벤트를 기다리고 Agent를 초기화한 뒤 실행합니다.

    인자:
        websocket: 수락된 WebSocket 연결입니다.
        default_gateway_arns: 환경의 Gateway ARN입니다(대체 값으로 사용).
        send_output: 출력 이벤트를 전송하는 선택적 비동기 callable입니다. 기본값은 websocket.send_json입니다.
    """
    agent = None
    output_fn = send_output or websocket.send_json

    logger.info("New WebSocket connection")
    logger.info("⏳ Waiting for config event from client...")

    try:
        # 초기 구성 이벤트 대기
        config, api_key, system_prompt = await _wait_for_config(websocket)
        if config is None:
            return

        # 구성에서 Agent 초기화
        agent = _create_agent(
            config,
            default_gateway_arns,
            api_key=api_key,
            system_prompt=system_prompt,
        )
        logger.info("✅ Agent initialized successfully")  # 구성 세부 정보는 _wait_for_config에서 기록

        # 클라이언트에 확인 응답 전송
        await websocket.send_json(
            {
                "type": "system",
                "message": "Configuration applied. Agent ready.",
            }
        )

        # 입력 핸들러 정의
        async def handle_websocket_input():
            """클라이언트에서 들어오는 메시지를 처리하고 구성, 텍스트 및 오디오를 필터링합니다."""
            while True:
                message = await websocket.receive_json()

                # 후속 구성 이벤트 처리(초기화 후에는 허용되지 않음)
                if message.get("type") == "config":
                    logger.info("⚠️ Config event received after initialization - ignoring")
                    await websocket.send_json(
                        {
                            "type": "system",
                            "message": "Configuration can only be set once per session. Please reconnect to change settings.",
                        }
                    )
                    continue

                # 클라이언트의 텍스트 메시지인지 확인
                elif message.get("type") == "text_input":
                    text = message.get("text", "")
                    logger.info("Received text input")
                    await agent.send(text)
                    continue

                # 오디오 및 기타 이벤트는 Agent로 전달
                else:
                    return message

        # 입력 핸들러와 함께 Agent 시작
        await agent.run(inputs=[handle_websocket_input], outputs=[output_fn])

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        # 정리 중 발생하는 AWS CRT의 취소된 future 오류 무시
        if "InvalidStateError" in type(e).__name__ or "CANCELLED" in str(e):
            logger.warning("Ignoring CRT cleanup error")
        else:
            logger.error("Session error: %s", type(e).__name__)
            traceback.print_exc()
            try:
                await output_fn({"type": "error", "message": str(e)})
            except Exception:
                pass
    finally:
        logger.info("Connection closed")


async def _wait_for_config(
    websocket: WebSocket,
) -> tuple[dict | None, str | None, str | None]:
    """클라이언트의 초기 구성 이벤트를 기다립니다.

    (config_dict, api_key, system_prompt)를 반환합니다. CodeQL 규정 준수를 위해
    민감한 필드와 사용자가 제공한 텍스트 필드를 분리하여 config dict에
    오염된 데이터가 남지 않도록 합니다.
    """
    while True:
        message = await websocket.receive_json()

        if message.get("type") == "config":
            voice = message.get("voice", "tiffany")
            input_sr = message.get("input_sample_rate", 16000)
            output_sr = message.get("output_sample_rate", 16000)
            model_id = message.get("model_id", "amazon.nova-2-sonic-v1:0")
            region = message.get("region", "us-east-1")
            gateway_arns = message.get("gateway_arns", None)

            logger.info("📥 Received config event")

            config = {
                "voice": voice,
                "input_sample_rate": input_sr,
                "output_sample_rate": output_sr,
                "model_id": model_id,
                "region": region,
                "gateway_arns": gateway_arns,
            }
            return (
                config,
                message.get("api_key", None),
                message.get("system_prompt", None),
            )
        else:
            logger.warning("⚠️ Expected config event, got unexpected message type")
            await websocket.send_json({"type": "system", "message": "Please send config event first"})


def _create_agent(
    config: dict,
    default_gateway_arns: list,
    api_key: str = None,
    system_prompt: str = None,
) -> BidiAgent:
    """주어진 구성에서 BidiAgent를 생성해 반환합니다."""
    # 구성에 Gateway ARN이 있으면 사용하고, 없으면 환경 기본값 사용
    effective_gateway_arns = config["gateway_arns"] if config["gateway_arns"] else default_gateway_arns
    effective_system_prompt = system_prompt if system_prompt else get_system_prompt()

    if config["gateway_arns"]:
        num_gateways = len(config["gateway_arns"])
        logger.info("   Gateways: %d from config event", num_gateways)
    else:
        logger.info("   Gateways: %d from environment", len(default_gateway_arns))

    logger.info("🎤 Initializing agent...")

    model = _create_model(config, effective_gateway_arns, api_key=api_key)

    return BidiAgent(
        model=model,
        tools=[],
        system_prompt=effective_system_prompt,
    )


def _create_model(config: dict, effective_gateway_arns: list, api_key: str = None):
    """model_id에 따라 적절한 BidiModel을 생성합니다."""
    model_id = config["model_id"]

    # Nova Sonic
    if model_id.startswith("amazon.nova"):
        return BidiNovaSonicModel(
            client_config={"region": config.get("region", "us-east-1")},
            model_id=model_id,
            provider_config={
                "audio": {
                    "input_rate": config["input_sample_rate"],
                    "output_rate": config["output_sample_rate"],
                    "voice": config["voice"],
                }
            },
            mcp_gateway_arn=effective_gateway_arns,
        )

    # OpenAI Realtime
    elif model_id.startswith("gpt-"):
        logger.info("Using OpenAI RealTime Model")
        try:
            from strands.experimental.bidi.models.openai_realtime import (
                BidiOpenAIRealtimeModel,
            )
        except ImportError:
            raise RuntimeError("OpenAI Realtime support not installed. Run: pip install 'strands-agents[bidi-openai]'")

        openai_key = api_key or os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise RuntimeError("OpenAI API key is required. Provide it via config or OPENAI_API_KEY env var.")

        return BidiOpenAIRealtimeModel(
            model_id=model_id,
            provider_config={
                "audio": {
                    "voice": config["voice"],
                }
            },
            client_config={"api_key": openai_key},
            mcp_gateway_arn=effective_gateway_arns,
        )

    # Gemini Live
    elif model_id.startswith("gemini"):
        logger.info("Using Gemini Live Model")
        try:
            from strands.experimental.bidi.models.gemini_live import BidiGeminiLiveModel
        except ImportError:
            raise RuntimeError("Gemini Live support not installed. Run: pip install 'strands-agents[bidi-gemini]'")

        google_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not google_key:
            raise RuntimeError("Google API key is required. Provide it via config or GOOGLE_API_KEY env var.")

        return BidiGeminiLiveModel(
            model_id=model_id,
            provider_config={
                "audio": {
                    "input_rate": config["input_sample_rate"],
                    "output_rate": config["output_sample_rate"],
                }
            },
            client_config={"api_key": google_key},
            mcp_gateway_arn=effective_gateway_arns,
        )

    else:
        raise RuntimeError(f"Unsupported model_id: {model_id}")
