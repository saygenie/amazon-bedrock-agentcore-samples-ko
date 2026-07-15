"""Nova Sonic 양방향 스트리밍 세션입니다.

Nova Sonic 대화의 전체 수명 주기를 관리합니다.
1. Amazon Bedrock에 연결하고 양방향 스트림 열기
2. 세션 구성(모델 파라미터, 음성, system prompt)
3. 마이크 오디오를 스트리밍하고 음성 응답 수신
"""

import asyncio
import base64
import json
import uuid

from loguru import logger

from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient
from aws_sdk_bedrock_runtime.config import Config
from aws_sdk_bedrock_runtime.models import (
    BidirectionalInputPayloadPart,
    InvokeModelWithBidirectionalStreamInputChunk,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from smithy_aws_core.auth.sigv4 import SigV4AuthScheme
from smithy_aws_core.identity.chain import create_default_chain
from smithy_http.aio.aiohttp import AIOHTTPClient

from audio import convert_to_16khz, INPUT_SAMPLE_RATE, OUTPUT_SAMPLE_RATE

MODEL_ID = "amazon.nova-2-sonic-v1:0"
VOICE_ID = "matthew"
SYSTEM_PROMPT = "You are a helpful AI assistant. Keep responses brief and conversational."

# 입력 및 출력 구성에서 함께 사용하는 오디오 형식
_AUDIO_FORMAT = {
    "mediaType": "audio/lpcm",
    "sampleSizeBits": 16,
    "channelCount": 1,
    "encoding": "base64",
    "audioType": "SPEECH",
}


async def _send(stream, event_dict):
    """Nova Sonic 스트림에 단일 이벤트를 전송합니다."""
    await stream.input_stream.send(
        InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=json.dumps(event_dict).encode("utf-8"))
        )
    )


async def _setup_session(stream, prompt_name):
    """Nova Sonic 세션의 모델 파라미터, system prompt 및 오디오 형식을 구성합니다."""

    # 1. 추론 파라미터로 세션 시작
    await _send(
        stream,
        {
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": 1024,
                        "topP": 0.9,
                        "temperature": 0.7,
                    }
                }
            }
        },
    )

    # 2. 오디오 출력 구성(Nova Sonic -> 브라우저)
    await _send(
        stream,
        {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "audioOutputConfiguration": {
                        **_AUDIO_FORMAT,
                        "sampleRateHertz": OUTPUT_SAMPLE_RATE,
                        "voiceId": VOICE_ID,
                    },
                }
            }
        },
    )

    # 3. system prompt 전송
    system_content = str(uuid.uuid4())
    await _send(
        stream,
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": system_content,
                    "type": "TEXT",
                    "interactive": True,
                    "role": "SYSTEM",
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        },
    )
    await _send(
        stream,
        {
            "event": {
                "textInput": {
                    "promptName": prompt_name,
                    "contentName": system_content,
                    "content": SYSTEM_PROMPT,
                }
            }
        },
    )
    await _send(
        stream,
        {
            "event": {
                "contentEnd": {
                    "promptName": prompt_name,
                    "contentName": system_content,
                }
            }
        },
    )


async def _start_audio_input(stream, prompt_name, audio_content_name):
    """지정 형식의 오디오 입력이 들어올 것을 Nova Sonic에 알립니다."""
    await _send(
        stream,
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        **_AUDIO_FORMAT,
                        "sampleRateHertz": INPUT_SAMPLE_RATE,
                    },
                }
            }
        },
    )


async def run_session(audio_in, audio_out, region, pc_id):
    """전체 Nova Sonic 대화 세션을 실행합니다.

    인자:
        audio_in:  WebRTC MediaStreamTrack(브라우저의 마이크)
        audio_out: OutputTrack(브라우저에서 Nova Sonic 응답 재생)
        region:    Amazon Bedrock용 AWS 리전
        pc_id:     로깅용 Peer Connection ID
    """
    logger.info(f"Starting Nova Sonic session for {pc_id}")

    # --- Amazon Bedrock에 연결 ---
    client = BedrockRuntimeClient(
        Config(
            endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
            region=region,
            aws_credentials_identity_resolver=create_default_chain(AIOHTTPClient()),
            auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")},
        )
    )
    stream = await client.invoke_model_with_bidirectional_stream(
        InvokeModelWithBidirectionalStreamOperationInput(model_id=MODEL_ID)
    )

    # --- 세션 구성 ---
    prompt_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())
    await _setup_session(stream, prompt_name)
    await _start_audio_input(stream, prompt_name, audio_content_name)

    # --- 응답 수신(오디오 전송과 동시에 실행) ---
    # ready 이벤트는 Nova Sonic이 세션을 확인할 때까지 오디오 전송을 차단함
    # 첫 이벤트가 지연될 때를 대비해 0.5초 제한 시간을 대체 수단으로 사용
    ready = asyncio.Event()
    content_roles = {}  # contentId -> 역할

    async def receive_responses():
        try:
            while True:
                output = await stream.await_output()
                result = await output[1].receive()
                if not (result.value and result.value.bytes_):
                    continue

                event = json.loads(result.value.bytes_.decode("utf-8")).get("event", {})

                if not ready.is_set():
                    ready.set()

                if "contentStart" in event:
                    cs = event["contentStart"]
                    if cid := cs.get("contentId"):
                        content_roles[cid] = cs.get("role", "ASSISTANT")
                elif "audioOutput" in event:
                    audio_out.add_audio(base64.b64decode(event["audioOutput"]["content"]))
                elif "textOutput" in event:
                    to = event["textOutput"]
                    content = to["content"]
                    role = content_roles.get(to.get("contentId"), "ASSISTANT")
                    # Barge-in: Nova Sonic이 contentEnd INTERRUPTED보다 먼저 전송함
                    if "interrupted" in content and "true" in content:
                        logger.info("Barge-in detected, clearing audio queue")
                        audio_out.clear()
                    else:
                        label = "User" if role == "USER" else "Nova Sonic"
                        logger.info(f"{label}: {content}")
                elif "contentEnd" in event:
                    ce = event["contentEnd"]
                    if ce.get("stopReason") == "INTERRUPTED":
                        audio_out.clear()
                    content_roles.pop(ce.get("contentId"), None)
        except Exception as e:
            logger.error(f"Receive error: {e}")

    recv_task = asyncio.create_task(receive_responses())

    await asyncio.sleep(0.5)
    if not ready.is_set():
        ready.set()
    await ready.wait()
    logger.info("Session ready, streaming audio")

    # --- 마이크 오디오를 Nova Sonic으로 스트리밍 ---
    try:
        frame_count = 0
        while True:
            pcm = convert_to_16khz(await audio_in.recv())
            if not pcm:
                continue

            frame_count += 1
            if frame_count % 500 == 0:
                logger.info(f"Sent {frame_count} audio frames")

            await _send(
                stream,
                {
                    "event": {
                        "audioInput": {
                            "promptName": prompt_name,
                            "contentName": audio_content_name,
                            "content": base64.b64encode(pcm).decode("utf-8"),
                        }
                    }
                },
            )
    except Exception as e:
        logger.error(f"Audio send error: {e}")
    finally:
        recv_task.cancel()
        try:
            await stream.close()
        except Exception:
            pass
