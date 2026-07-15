"""
LangChain Voice Agent의 세션 및 Agent 로직입니다.

Voice Agent용 "sandwich" 아키텍처(STT → Agent → TTS)를 구현합니다.
STT에는 Amazon Transcribe Streaming, 추론에는 Amazon Bedrock Nova 2 Lite
(extended thinking)를 사용하는 LangChain Agent, TTS에는 Amazon Polly를 사용합니다.

Strands 패턴에 따라 server.py에서 분리했습니다. server.py는 FastAPI, IMDS 및
엔드포인트를 담당하고 agent.py는 WebSocket 세션과 Agent 구성을 담당합니다.
"""

import logging
import os
import json
import asyncio
import base64
import struct
import traceback
from uuid import uuid4
from typing import AsyncIterator

import boto3
from fastapi import WebSocket, WebSocketDisconnect

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice Agent 이벤트 유형(sandwich 파이프라인 이벤트)
# ---------------------------------------------------------------------------


class VoiceAgentEvent:
    """STT > Agent > TTS 파이프라인을 통과하는 기본 이벤트입니다."""

    def __init__(self, event_type: str, **kwargs):
        self.type = event_type
        self.__dict__.update(kwargs)


class STTChunkEvent(VoiceAgentEvent):
    """STT의 부분 Transcript입니다."""

    def __init__(self, transcript: str):
        super().__init__("stt_chunk", transcript=transcript)


class STTOutputEvent(VoiceAgentEvent):
    """STT의 최종 Transcript입니다."""

    def __init__(self, transcript: str):
        super().__init__("stt_output", transcript=transcript)


class AgentChunkEvent(VoiceAgentEvent):
    """LangChain Agent의 스트리밍 텍스트 청크입니다."""

    def __init__(self, text: str):
        super().__init__("agent_chunk", text=text)


class TTSChunkEvent(VoiceAgentEvent):
    """TTS의 오디오 청크입니다."""

    def __init__(self, audio: bytes):
        super().__init__("tts_chunk", audio=audio)


# ---------------------------------------------------------------------------
# system prompt
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly banking assistant for AnyBank. "
    "Help customers with account inquiries, transactions, mortgages, and general questions. "
    "Be warm, conversational, and concise. Keep responses to two or three sentences. "
    "Do NOT use emojis, special characters, or markdown. "
    "Your responses will be read aloud by a text-to-speech engine."
)


def get_system_prompt() -> str:
    """기본 system prompt를 가져옵니다."""
    return DEFAULT_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# LangChain Agent 설정
# ---------------------------------------------------------------------------


def build_agent(system_prompt: str | None = None, region: str = "us-east-1"):
    """Amazon Bedrock Nova 2 Lite의 extended thinking과 Memory를 사용하는 LangChain Agent를 생성합니다."""
    from langchain_aws import ChatBedrockConverse

    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    # 자리 표시자 도구 - 프로덕션에서는 MCP Gateway 엔드포인트를 호출함
    @tool
    def get_account_balance(account_id: str) -> str:
        """Get the balance for a customer account."""
        return f"Account {account_id} has a balance of $4,231.56."

    @tool
    def get_recent_transactions(account_id: str, count: int = 5) -> str:
        """Get recent transactions for a customer account."""
        return (
            f"Last {count} transactions for account {account_id}: "
            "Coffee Shop $4.50, Grocery Store $62.30, Gas Station $45.00, "
            "Online Transfer -$200.00, Direct Deposit +$3,200.00."
        )

    @tool
    def get_mortgage_rates() -> str:
        """Get current mortgage rates."""
        return "Current rates: 30-year fixed 6.75%, 15-year fixed 5.99%, 5/1 ARM 6.25%."

    # Amazon Bedrock Converse API를 통한 Nova 2 Lite extended thinking
    llm = ChatBedrockConverse(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name=region,
        additional_model_request_fields={
            "reasoningConfig": {
                "type": "enabled",
                "maxReasoningEffort": "low",
            }
        },
    )

    agent = create_react_agent(
        model=llm,
        tools=[get_account_balance, get_recent_transactions, get_mortgage_rates],
        prompt=prompt,
        checkpointer=MemorySaver(),
    )
    return agent


# ---------------------------------------------------------------------------
# 파이프라인 단계(sandwich 아키텍처 참조 구현)
# ---------------------------------------------------------------------------


async def stt_stream(
    audio_stream: AsyncIterator[bytes],
) -> AsyncIterator[VoiceAgentEvent]:
    """STT 단계: 오디오 바이트 → VoiceAgentEvent(stt_chunk/stt_output)."""
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")  # noqa: F841

    audio_buffer = bytearray()
    SILENCE_THRESHOLD = 0.5
    CHUNK_DURATION = 0.1
    silence_chunks = 0
    silence_limit = int(SILENCE_THRESHOLD / CHUNK_DURATION)

    async for chunk in audio_stream:
        audio_buffer.extend(chunk)
        if len(chunk) > 0:
            energy = sum(abs(b - 128) for b in chunk) / len(chunk)
            if energy < 5:
                silence_chunks += 1
            else:
                silence_chunks = 0
        if silence_chunks >= silence_limit and len(audio_buffer) > 3200:
            yield STTOutputEvent(transcript=f"[audio:{len(audio_buffer)} bytes]")
            audio_buffer.clear()
            silence_chunks = 0


async def agent_stream(
    event_stream: AsyncIterator[VoiceAgentEvent],
    agent,
    thread_id: str,
) -> AsyncIterator[VoiceAgentEvent]:
    """Agent 단계: 상위 이벤트를 전달하고 stt_output에 agent_chunk를 추가합니다."""
    async for event in event_stream:
        yield event
        if event.type == "stt_output":
            stream = agent.astream(
                {"messages": [HumanMessage(content=event.transcript)]},
                {"configurable": {"thread_id": thread_id}},
                stream_mode="messages",
            )
            async for message, _ in stream:
                if hasattr(message, "text") and message.text:
                    yield AgentChunkEvent(text=message.text)


async def tts_stream(
    event_stream: AsyncIterator[VoiceAgentEvent],
) -> AsyncIterator[VoiceAgentEvent]:
    """TTS 단계: Amazon Polly를 통해 Agent 텍스트를 오디오로 합성합니다."""
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    voice_id = os.getenv("POLLY_VOICE_ID", "Joanna")
    polly = boto3.client("polly", region_name=region)
    text_buffer = []

    async for event in event_stream:
        yield event
        if event.type == "agent_chunk":
            text_buffer.append(event.text)
            combined = "".join(text_buffer)
            if any(combined.rstrip().endswith(p) for p in (".", "!", "?", ":")):
                try:
                    response = polly.synthesize_speech(
                        Text=combined,
                        OutputFormat="pcm",
                        SampleRate="16000",
                        VoiceId=voice_id,
                    )
                    audio_bytes = response["AudioStream"].read()
                    if audio_bytes:
                        yield TTSChunkEvent(audio=audio_bytes)
                except Exception as e:
                    logger.error(f"Polly TTS error: {e}")
                text_buffer.clear()

    if text_buffer:
        combined = "".join(text_buffer)
        if combined.strip():
            try:
                response = polly.synthesize_speech(
                    Text=combined,
                    OutputFormat="pcm",
                    SampleRate="16000",
                    VoiceId=voice_id,
                )
                audio_bytes = response["AudioStream"].read()
                if audio_bytes:
                    yield TTSChunkEvent(audio=audio_bytes)
            except Exception as e:
                logger.error(f"Polly TTS error: {e}")


# ---------------------------------------------------------------------------
# Amazon Transcribe Streaming 헬퍼
# ---------------------------------------------------------------------------


async def transcribe_audio(pcm_bytes: bytes, region: str, sample_rate: int) -> str | None:
    """Amazon Transcribe Streaming API를 사용해 PCM 오디오 바이트를 전사합니다."""
    if len(pcm_bytes) < 1600:
        return None

    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    final_transcripts: list[str] = []

    class CollectorHandler(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, transcript_event: TranscriptEvent):
            results = transcript_event.transcript.results
            for result in results:
                if not result.is_partial:
                    for alt in result.alternatives:
                        if alt.transcript.strip():
                            final_transcripts.append(alt.transcript.strip())

    try:
        client = TranscribeStreamingClient(region=region)
        stream = await client.start_stream_transcription(
            language_code="en-US",
            media_sample_rate_hz=sample_rate,
            media_encoding="pcm",
        )

        CHUNK_SIZE = 1024 * 8

        async def write_chunks():
            for i in range(0, len(pcm_bytes), CHUNK_SIZE):
                chunk = pcm_bytes[i : i + CHUNK_SIZE]
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
            await stream.input_stream.end_stream()

        handler = CollectorHandler(stream.output_stream)
        await asyncio.gather(write_chunks(), handler.handle_events())

        transcript = " ".join(final_transcripts).strip()
        logger.info(f'   📝 Transcribe streaming result: "{transcript}"')
        return transcript if transcript else None

    except Exception as e:
        logger.error(f"   ❌ Transcribe streaming error: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# WebSocket 세션 핸들러
# ---------------------------------------------------------------------------


async def handle_websocket_session(websocket: WebSocket, default_gateway_arns: list):
    """단일 WebSocket 음성 세션을 처리합니다.

    text_input과 audio_input 메시지가 서로를 차단하지 않도록 전체 sandwich
    파이프라인 대신 단순한 메시지 루프를 사용합니다. 개념적으로 sandwich
    파이프라인(STT → Agent → TTS)은 유지됩니다. 오디오는 STT, Agent, TTS를
    차례로 거치고 텍스트는 STT를 건너뛰어 바로 Agent → TTS로 이동합니다.
    """
    logger.info(f"🔌 New WebSocket connection from {websocket.client}")
    logger.info("⏳ Waiting for config event from client...")

    msg_count = 0
    audio_chunk_count = 0

    try:
        # 구성 대기
        config = await _wait_for_config(websocket)
        if config is None:
            logger.warning("❌ No config received, closing connection")
            return

        system_prompt = config.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
        region = config.get("region") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        voice_id = config.get("voice", "Joanna")
        output_sr = config.get("output_sample_rate", 16000)

        logger.info(f"📝 System prompt length: {len(system_prompt)} chars")
        logger.info(f"🤖 Building LangChain agent (Bedrock Nova 2 Lite, region={region})...")

        agent = build_agent(system_prompt, region=region)
        thread_id = str(uuid4())

        logger.info("✅ LangChain voice agent initialized")
        logger.info(f"   🎤 Voice: {voice_id}")
        logger.info(f"   🌍 Region: {region}")
        logger.info(f"   📊 Audio: {config['input_sample_rate']}Hz input, {output_sr}Hz output")
        logger.info(f"   🧵 Thread ID: {thread_id}")

        await websocket.send_json(
            {
                "type": "system",
                "message": f"LangChain sandwich agent ready: voice={voice_id}, region={region}",
            }
        )
        logger.info("📤 Sent system ready message to client")

        # --- 헬퍼 ----------------------------------------------------------

        async def run_agent_and_respond(text: str):
            """텍스트를 Agent에 전달하고 청크를 스트리밍한 뒤 TTS를 합성합니다."""
            logger.info(f"{'=' * 60}")
            logger.info(f'🧠 Agent processing input: "{text[:120]}"')

            raw_response: list[str] = []
            clean_full = ""
            try:
                logger.info(f"   📡 Calling agent.astream() with thread_id={thread_id}")
                stream = agent.astream(
                    {"messages": [HumanMessage(content=text)]},
                    {"configurable": {"thread_id": thread_id}},
                    stream_mode="messages",
                )
                async for msg, metadata in stream:
                    # Nova 2 extended thinking의 reasoning_content 블록 필터링
                    if hasattr(msg, "content") and isinstance(msg.content, list):
                        for block in msg.content:
                            if isinstance(block, dict):
                                if block.get("type") == "reasoning_content":
                                    logger.debug("   🧠 Skipping reasoning_content block")
                                    continue
                                if block.get("type") == "text" and block.get("text"):
                                    raw_response.append(block["text"])
                    elif hasattr(msg, "text") and msg.text:
                        raw_response.append(msg.text)
                    elif hasattr(msg, "content") and isinstance(msg.content, str) and msg.content:
                        raw_response.append(msg.content)

                raw_full = "".join(raw_response)
                clean_full = raw_full.strip()
                logger.info(f"   ✅ Agent finished: {len(raw_response)} raw chunks")
                logger.info(f'   📝 Response: "{clean_full[:150]}"')

                if clean_full:
                    await websocket.send_json(
                        {
                            "type": "agent_chunk",
                            "text": clean_full,
                        }
                    )
            except Exception as e:
                logger.error(f"   ❌ Agent error: {type(e).__name__}: {e}")
                traceback.print_exc()
                await websocket.send_json({"type": "error", "message": str(e)})
                return

            # TTS - 전체 응답을 Amazon Polly로 합성
            # AgentCore WebSocket Proxy에는 프레임당 32KB 제한이 있으므로
            # 오디오를 이 제한보다 충분히 작은 조각으로 분할함
            # 16KB 원시 PCM → 약 21KB base64 + JSON 오버헤드 ≈ 프레임당 약 22KB
            TTS_CHUNK_SIZE = 16000  # 프레임당 원시 PCM 바이트
            if clean_full.strip():
                logger.info(f"   🔊 Synthesizing TTS with Polly (voice={voice_id}, rate={output_sr}Hz)")
                logger.info(f'   📝 TTS text ({len(clean_full)} chars): "{clean_full[:120]}..."')
                try:
                    polly = boto3.client("polly", region_name=region)
                    resp = polly.synthesize_speech(
                        Text=clean_full,
                        OutputFormat="pcm",
                        SampleRate=str(output_sr),
                        VoiceId=voice_id,
                    )
                    audio_bytes = resp["AudioStream"].read()
                    total_chunks = (len(audio_bytes) + TTS_CHUNK_SIZE - 1) // TTS_CHUNK_SIZE
                    logger.info(f"   ✅ Polly returned {len(audio_bytes)} bytes, sending in {total_chunks} chunks")
                    for i in range(0, len(audio_bytes), TTS_CHUNK_SIZE):
                        chunk = audio_bytes[i : i + TTS_CHUNK_SIZE]
                        chunk_b64 = base64.b64encode(chunk).decode("utf-8")
                        await websocket.send_json(
                            {
                                "type": "tts_audio",
                                "audio": chunk_b64,
                                "sample_rate": output_sr,
                            }
                        )
                    logger.info(f"   📤 Sent {total_chunks} tts_audio chunks to client")
                except Exception as e:
                    logger.error(f"   ❌ Polly TTS error: {type(e).__name__}: {e}")
                    traceback.print_exc()
            else:
                logger.warning("   ⚠️ Agent returned empty response, skipping TTS")
            logger.info("=" * 60)

        # --- 기본 메시지 루프 ----------------------------------------------

        audio_buffer = bytearray()
        silence_chunks = 0
        SILENCE_THRESHOLD_SECS = 0.6
        CHUNK_INTERVAL_SECS = 0.085
        silence_limit = int(SILENCE_THRESHOLD_SECS / CHUNK_INTERVAL_SECS)
        RMS_SILENCE_THRESHOLD = 500
        rms_energy = 0

        logger.info("🔄 Entering main message loop...")

        while True:
            try:
                raw = await websocket.receive()
                logger.info(
                    f"📥 Raw WS frame: type={raw.get('type')}, text_len={len(raw.get('text', ''))}, bytes_len={len(raw.get('bytes', b''))}"
                )
                if raw.get("text"):
                    message = json.loads(raw["text"])
                elif raw.get("bytes"):
                    message = json.loads(raw["bytes"].decode("utf-8"))
                else:
                    logger.warning(f"📥 Unexpected frame with no text or bytes: {raw}")
                    continue
            except json.JSONDecodeError as e:
                logger.error(f"📥 Failed to parse WS message as JSON: {e}")
                continue
            msg_count += 1
            msg_type = message.get("type")

            if msg_type != "audio_input":
                logger.info(f"📥 Message #{msg_count}: type={msg_type}, keys={list(message.keys())}")

            # AgentCore WebSocket Proxy는 서버가 보낸 메시지를 다시 전송함
            # 자체 출력을 처리하지 않도록 이 서버가 보내는 메시지 유형은 건너뜀
            SERVER_SENT_TYPES = {
                "tts_audio",
                "agent_chunk",
                "transcript",
                "system",
                "error",
            }
            if msg_type in SERVER_SENT_TYPES:
                logger.debug(f"   🔁 Ignoring echoed server message: {msg_type}")
                continue

            if msg_type == "config":
                logger.info("   ⚠️ Duplicate config event, ignoring")
                await websocket.send_json(
                    {
                        "type": "system",
                        "message": "Configuration can only be set once per session. Reconnect to change.",
                    }
                )

            elif msg_type == "text_input":
                text = message.get("text", "").strip()
                logger.info(f'   💬 Text input received: "{text}"')
                if text:
                    await run_agent_and_respond(text)
                else:
                    logger.warning("   ⚠️ Empty text input, ignoring")

            elif msg_type == "audio_input":
                audio_b64 = message.get("audio", "")
                if not audio_b64:
                    continue
                chunk = base64.b64decode(audio_b64)
                audio_chunk_count += 1
                audio_buffer.extend(chunk)

                # 16-bit signed PCM의 에너지 기반 무음 감지
                num_samples = len(chunk) // 2
                if num_samples > 0:
                    samples = struct.unpack(f"<{num_samples}h", chunk[: num_samples * 2])
                    rms_energy = (sum(s * s for s in samples) / num_samples) ** 0.5
                    if rms_energy < RMS_SILENCE_THRESHOLD:
                        silence_chunks += 1
                    else:
                        silence_chunks = 0

                if audio_chunk_count % 50 == 0:
                    logger.info(
                        f"   🎤 Audio: {audio_chunk_count} chunks received, "
                        f"buffer={len(audio_buffer)} bytes, "
                        f"silence={silence_chunks}/{silence_limit}, "
                        f"rms={rms_energy:.0f}"
                    )

                if silence_chunks >= silence_limit and len(audio_buffer) > 3200:
                    logger.info(f"   🔇 Silence detected after {len(audio_buffer)} bytes of audio")
                    transcript = await transcribe_audio(bytes(audio_buffer), region, config["input_sample_rate"])
                    audio_buffer.clear()
                    silence_chunks = 0

                    if transcript:
                        logger.info(f'   🗣️ Transcript: "{transcript}"')
                        await websocket.send_json({"type": "transcript", "text": transcript})
                        await run_agent_and_respond(transcript)
                    else:
                        logger.info("   🔇 No speech detected in audio, skipping")

            else:
                logger.warning(f"   ❓ Unknown message type: {msg_type}, data: {json.dumps(message)[:200]}")

    except WebSocketDisconnect:
        logger.info("🔌 Client disconnected")
    except Exception as e:
        if "InvalidStateError" in type(e).__name__ or "CANCELLED" in str(e):
            logger.warning(f"Ignoring cleanup error: {e}")
        else:
            logger.error(f"💥 Unhandled error: {type(e).__name__}: {e}")
            traceback.print_exc()
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
    finally:
        logger.info(f"🔌 Connection closed (processed {msg_count} messages, {audio_chunk_count} audio chunks)")


async def _wait_for_config(websocket: WebSocket) -> dict | None:
    """클라이언트의 초기 구성 이벤트를 기다립니다."""
    while True:
        message = await websocket.receive_json()
        if message.get("type") == "config":
            voice = message.get("voice", "Joanna")
            input_sr = message.get("input_sample_rate", 16000)
            output_sr = message.get("output_sample_rate", 16000)
            region = message.get("region", "us-east-1")
            system_prompt = message.get("system_prompt", None)
            gateway_arns = message.get("gateway_arns", None)

            logger.info(f"📥 Received config: voice={voice}, region={region}, audio={input_sr}Hz/{output_sr}Hz")
            return {
                "voice": voice,
                "input_sample_rate": input_sr,
                "output_sample_rate": output_sr,
                "region": region,
                "system_prompt": system_prompt,
                "gateway_arns": gateway_arns,
            }
        else:
            logger.warning(f"⚠️ Expected config event, got {message.get('type')}")
            await websocket.send_json({"type": "system", "message": "Please send config event first"})
