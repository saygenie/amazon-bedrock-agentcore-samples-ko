import logging
import uvicorn
import os
import json
import asyncio
import requests
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from agent import handle_websocket_session


# ---------------------------------------------------------------------------
# 대용량 이벤트 분할(Strands 이벤트 형식에 맞게 Sonic Server에서 수정)
# ---------------------------------------------------------------------------
MAX_WS_MESSAGE_SIZE = 10000


def split_large_event(event_dict, max_size=MAX_WS_MESSAGE_SIZE):
    """audio 필드를 나눠 큰 이벤트를 더 작은 청크로 분할합니다.

    손상을 방지하도록 오디오 이벤트를 base64 경계에서 분할하고,
    전송할 이벤트 딕셔너리 목록을 반환합니다.
    """
    event_json = json.dumps(event_dict)
    event_size = len(event_json.encode("utf-8"))

    if event_size <= max_size:
        return [event_dict]

    event_type = event_dict.get("type", "unknown")

    # 'audio' 필드가 있는 이벤트만 분할
    if "audio" not in event_dict or not isinstance(event_dict["audio"], str):
        logger.warning(f"Event {event_type} is large ({event_size} bytes) but has no audio field to split")
        return [event_dict]

    audio_content = event_dict["audio"]

    # 오버헤드 측정(오디오 콘텐츠를 제외한 모든 항목)
    template = {k: v for k, v in event_dict.items() if k != "audio"}
    template["audio"] = ""
    overhead = len(json.dumps(template).encode("utf-8"))

    # 청크당 최대 오디오 콘텐츠 크기(여유 공간 포함)
    max_content_size = max_size - overhead - 100

    # 유효한 base64를 위해 4자 경계로 정렬(base64 4자 = 3바이트)
    alignment = 4
    max_content_size = (max_content_size // alignment) * alignment

    if max_content_size <= 0:
        logger.warning(f"Cannot split {event_type}: overhead too large")
        return [event_dict]

    chunks = []
    for i in range(0, len(audio_content), max_content_size):
        chunk_audio = audio_content[i : i + max_content_size]

        # 필요한 경우 적절한 base64 패딩 보장
        remainder = len(chunk_audio) % 4
        if remainder != 0:
            chunk_audio += "=" * (4 - remainder)

        chunk_event = {k: v for k, v in event_dict.items() if k != "audio"}
        chunk_event["audio"] = chunk_audio
        chunks.append(chunk_event)

    logger.info(f"Split {event_type} event ({event_size} bytes) into {len(chunks)} chunks")
    return chunks


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gateway 구성을 사용할 수 있는지 확인
MCP_GATEWAY_ARNS = os.getenv("MCP_GATEWAY_ARNS")
MCP_GATEWAY_URLS = os.getenv("MCP_GATEWAY_URLS")

if not MCP_GATEWAY_ARNS or not MCP_GATEWAY_URLS:
    logger.error("❌ MCP Gateway configuration is required!")
    logger.error("   Set MCP_GATEWAY_ARNS and MCP_GATEWAY_URLS environment variables")
    raise RuntimeError("MCP Gateway not configured")

try:
    gateway_arns = json.loads(MCP_GATEWAY_ARNS)
    gateway_urls = json.loads(MCP_GATEWAY_URLS)
    logger.info(f"✅ Loaded {len(gateway_arns)} MCP Gateways")
except json.JSONDecodeError:
    logger.error("❌ Failed to parse MCP Gateway configuration")
    raise RuntimeError("Invalid MCP Gateway configuration")

_credential_refresh_task = None


def get_imdsv2_token():
    """안전한 메타데이터 접근을 위한 IMDSv2 token을 가져옵니다."""
    try:
        response = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2,
        )
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None


def get_credentials_from_imds():
    """EC2 IMDS에서 IAM 역할 자격 증명을 가져옵니다(IMDSv2 우선, 실패 시 IMDSv1)."""
    result = {
        "success": False,
        "credentials": None,
        "role_name": None,
        "method_used": None,
        "error": None,
    }

    try:
        token = get_imdsv2_token()
        headers = {"X-aws-ec2-metadata-token": token} if token else {}
        result["method_used"] = "IMDSv2" if token else "IMDSv1"

        role_response = requests.get(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers=headers,
            timeout=2,
        )

        if role_response.status_code != 200:
            result["error"] = f"Failed to retrieve IAM role: HTTP {role_response.status_code}"
            return result

        role_name = role_response.text.strip()
        result["role_name"] = role_name

        creds_response = requests.get(
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{role_name}",
            headers=headers,
            timeout=2,
        )

        if creds_response.status_code != 200:
            result["error"] = f"Failed to retrieve credentials: HTTP {creds_response.status_code}"
            return result

        credentials = creds_response.json()
        result["success"] = True
        result["credentials"] = {
            "AccessKeyId": credentials.get("AccessKeyId"),
            "SecretAccessKey": credentials.get("SecretAccessKey"),
            "Token": credentials.get("Token"),
            "Expiration": credentials.get("Expiration"),
        }

    except Exception as e:
        result["error"] = str(e)

    return result


async def refresh_credentials_from_imds():
    """IMDS에서 자격 증명을 갱신하는 백그라운드 작업입니다."""
    logger.info("Starting credential refresh task")

    while True:
        try:
            imds_result = get_credentials_from_imds()

            if imds_result["success"]:
                creds = imds_result["credentials"]

                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

                logger.info(f"✅ Credentials refreshed ({imds_result['method_used']})")

                try:
                    expiration = datetime.fromisoformat(creds["Expiration"].replace("Z", "+00:00"))
                    now = datetime.now(expiration.tzinfo)
                    time_until_expiration = (expiration - now).total_seconds()
                    refresh_interval = min(max(time_until_expiration - 300, 60), 3600)
                    logger.info(f"   Next refresh in {refresh_interval:.0f}s")
                except Exception:
                    refresh_interval = 3600

                await asyncio.sleep(refresh_interval)
            else:
                logger.error(f"Failed to refresh credentials: {imds_result['error']}")
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Credential refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in credential refresh: {e}")
            await asyncio.sleep(300)


app = FastAPI(title="Strands BidiAgent WebSocket Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global _credential_refresh_task

    logger.info("🚀 Starting server...")
    logger.info(
        f"📍 Default Region: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')} (can be overridden per session via client config)"
    )
    logger.info(f"✅ {len(gateway_arns)} Gateway(s) configured:")
    for i, (arn, url) in enumerate(zip(gateway_arns, gateway_urls), 1):
        logger.info(f"   {i}. {url}")
        logger.info(f"      ARN: {arn}")
    logger.info("   Tools will be accessed via AgentCore Gateway")

    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.info("✅ Using credentials from environment (local mode)")
    else:
        logger.info("🔄 Fetching credentials from EC2 IMDS...")
        imds_result = get_credentials_from_imds()

        if imds_result["success"]:
            creds = imds_result["credentials"]
            os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
            os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

            logger.info(f"✅ Credentials loaded ({imds_result['method_used']})")

            _credential_refresh_task = asyncio.create_task(refresh_credentials_from_imds())
            logger.info("🔄 Credential refresh task started")
        else:
            logger.error(f"❌ Failed to fetch credentials: {imds_result['error']}")


@app.on_event("shutdown")
async def shutdown_event():
    global _credential_refresh_task

    logger.info("🛑 Shutting down...")

    if _credential_refresh_task and not _credential_refresh_task.done():
        _credential_refresh_task.cancel()
        try:
            await _credential_refresh_task
        except asyncio.CancelledError:
            pass


@app.get("/ping")
async def ping():
    """
    Health check endpoint required by AgentCore Runtime.
    Returns agent status and timestamp per AgentCore protocol contract.
    """
    import time

    return JSONResponse({"status": "Healthy", "time_of_last_update": int(time.time())})


@app.post("/invocations")
async def invocations(request: dict):
    """
    Traditional request/response endpoint required by AgentCore Runtime protocol.

    This agent is WebSocket-first and requires bidirectional streaming for audio.
    This endpoint provides information about how to connect properly.
    """
    return JSONResponse(
        {
            "message": "This agent requires WebSocket connection for bidirectional audio streaming.",
            "websocket_endpoint": "/ws",
            "instructions": "Connect to /ws endpoint and send a 'config' event with voice settings.",
            "config_event_format": {
                "type": "config",
                "voice": "tiffany",
                "input_sample_rate": 16000,
                "output_sample_rate": 16000,
            },
            "available_voices": ["tiffany", "matthew", "ruth", "gregory", "joanna"],
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def chunked_send_json(event_dict):
        """큰 오디오 페이로드를 작은 청크로 나눠 출력 이벤트를 전송합니다."""
        chunks = split_large_event(event_dict)
        for idx, chunk in enumerate(chunks):
            await websocket.send_json(chunk)
            if len(chunks) > 1:
                chunk_size = len(json.dumps(chunk).encode("utf-8"))
                logger.info(f"Forwarded chunk {idx + 1}/{len(chunks)} to client ({chunk_size} bytes)")

    await handle_websocket_session(websocket, default_gateway_arns=gateway_arns, send_output=chunked_send_json)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")  # nosec B104
    port = int(os.getenv("PORT", "8080"))

    uvicorn.run(app, host=host, port=port)
