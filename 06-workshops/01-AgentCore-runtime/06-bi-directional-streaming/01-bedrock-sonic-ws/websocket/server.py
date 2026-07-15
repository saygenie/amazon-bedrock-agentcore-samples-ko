import asyncio
import json
import logging
import os
import uvicorn
import requests
from requests.exceptions import RequestException
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from s2s_session_manager import S2sSessionManager

# 로깅 구성
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


# 자격 증명 갱신 작업을 추적하는 전역 변수
credential_refresh_task = None


def get_imdsv2_token():
    """
    안전한 메타데이터 접근을 위한 IMDSv2 token을 가져옵니다.

    반환:
        str: IMDSv2 token, IMDSv2를 사용할 수 없으면 None
    """
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
    """
    Instance Metadata Service에서 IAM 역할 자격 증명을 직접 가져옵니다.

    이 유틸리티 메서드는 boto3를 사용하지 않고 IMDS에서 직접 자격 증명을
    가져오며, IMDSv1과 IMDSv2 방식을 모두 시도합니다.

    반환:
        dict: 자격 증명 또는 오류 정보를 포함하는 딕셔너리
    """
    result = {
        "success": False,
        "credentials": None,
        "role_name": None,
        "method_used": None,
        "error": None,
    }

    try:
        # IMDSv2를 먼저 시도
        token = get_imdsv2_token()
        headers = {}

        if token:
            headers["X-aws-ec2-metadata-token"] = token
            result["method_used"] = "IMDSv2"
        else:
            result["method_used"] = "IMDSv1"

        # IAM 역할 이름 가져오기
        role_response = requests.get(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers=headers,
            timeout=2,
        )

        if role_response.status_code != 200:
            result["error"] = f"Failed to retrieve IAM role name: HTTP {role_response.status_code}"
            return result

        role_name = role_response.text.strip()
        result["role_name"] = role_name

        # 역할의 자격 증명 가져오기
        creds_response = requests.get(
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{role_name}",
            headers=headers,
            timeout=2,
        )

        if creds_response.status_code != 200:
            result["error"] = f"Failed to retrieve credentials for role {role_name}: HTTP {creds_response.status_code}"
            return result

        # 자격 증명 파싱
        credentials = creds_response.json()

        result["success"] = True
        result["credentials"] = {
            "AccessKeyId": credentials.get("AccessKeyId"),
            "SecretAccessKey": credentials.get("SecretAccessKey"),
            "Token": credentials.get("Token"),
            "Expiration": credentials.get("Expiration"),
            "Code": credentials.get("Code"),
            "Type": credentials.get("Type"),
            "LastUpdated": credentials.get("LastUpdated"),
        }

    except RequestException as e:
        result["error"] = f"Request exception: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result


async def refresh_credentials_from_imds():
    """
    IMDS에서 자격 증명을 주기적으로 갱신하고 환경 변수를 업데이트하는
    백그라운드 작업입니다. EnvironmentCredentialsResolver가 항상 최신
    자격 증명을 사용하도록 합니다.
    """
    logger.info("Starting credential refresh background task")

    while True:
        try:
            # IMDS에서 자격 증명 가져오기
            imds_result = get_credentials_from_imds()

            if imds_result["success"]:
                creds = imds_result["credentials"]

                # 환경 변수 업데이트
                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

                logger.info("✅ Credentials refreshed from IMD.")

                # 만료 시각을 파싱하고 갱신 간격 계산
                # 만료 5분 전에 갱신
                try:
                    expiration = datetime.fromisoformat(creds["Expiration"].replace("Z", "+00:00"))
                    now = datetime.now(expiration.tzinfo)
                    time_until_expiration = (expiration - now).total_seconds()

                    # 만료 5분(300초) 전 또는 만료까지 오래 남았으면 1시간 후 갱신
                    refresh_interval = min(max(time_until_expiration - 300, 60), 3600)
                    logger.info(f"   Next refresh in {refresh_interval:.0f} seconds")
                except Exception as e:
                    logger.warning(f"Could not parse expiration time, using default 1 hour refresh: {e}")
                    refresh_interval = 3600

                # 다음 갱신까지 대기
                await asyncio.sleep(refresh_interval)
            else:
                logger.error(f"Failed to refresh credentials from IMDS: {imds_result['error']}")
                # 실패하면 5분 후 재시도
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Credential refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in credential refresh task: {e}", exc_info=True)
            # 오류가 발생하면 5분 후 재시도
            await asyncio.sleep(300)


# FastAPI 앱 생성
app = FastAPI(title="Nova Sonic S2S WebSocket Server")

# CORS Middleware 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global credential_refresh_task

    logger.info("🚀 Application starting up...")
    logger.info(f"📍 AWS Region: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}")

    # 환경에 자격 증명이 이미 있는지 확인(로컬 모드)
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.info("✅ Using credentials from environment variables (local mode)")
        logger.info("   Credential refresh task will not be started")
    else:
        # IMDS에서 자격 증명을 가져오고 갱신 작업 시작
        logger.info("🔄 Attempting to fetch credentials from ENV IMDS...")

        imds_result = get_credentials_from_imds()

        if imds_result["success"]:
            creds = imds_result["credentials"]

            # 환경에 초기 자격 증명 설정
            os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
            os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

            logger.info("✅ Initial credentials loaded from IMDS.")

            # 자격 증명 갱신 백그라운드 작업 시작
            credential_refresh_task = asyncio.create_task(refresh_credentials_from_imds())
            logger.info("🔄 Credential refresh background task started")
        else:
            logger.error(f"❌ Failed to fetch credentials from IMDS: {imds_result['error']}")
            logger.error("   Application may not function correctly without credentials")


@app.on_event("shutdown")
async def shutdown_event():
    global credential_refresh_task

    logger.info("🛑 Application shutting down...")

    # 실행 중인 자격 증명 갱신 작업 취소
    if credential_refresh_task and not credential_refresh_task.done():
        logger.info("Stopping credential refresh task...")
        credential_refresh_task.cancel()
        try:
            await credential_refresh_task
        except asyncio.CancelledError:
            pass
        logger.info("Credential refresh task stopped")


@app.get("/health")
@app.get("/")
async def health_check():
    logger.info("Health check request received")
    return JSONResponse({"status": "healthy"})


@app.get("/ping")
async def ping():
    logger.debug("Ping endpoint called")
    return JSONResponse({"status": "ok"})


@app.get("/credentials/info")
async def credential_info():
    """Get information about credential configuration (for debugging)"""
    # 자격 증명 소스 결정
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        credential_source = "Environment Variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)"
        mode = "local"
        note = "Using static credentials from environment variables"
    else:
        credential_source = "ENV IMDS (IMDSv2 preferred, falls back to IMDSv1)"
        mode = "ec2"
        note = "Credentials are automatically refreshed from IMDS by background task"

    return JSONResponse(
        {
            "status": "ok",
            "mode": mode,
            "credential_source": credential_source,
            "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            "note": note,
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info(f"WebSocket connection attempt from: {websocket.client}")
    logger.debug(f"Headers: {websocket.headers}")

    # WebSocket 연결 수락
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    stream_manager = None
    forward_task = None

    try:
        # 기본 메시지 처리 루프
        while True:
            try:
                message = await websocket.receive_text()
                logger.debug("Received message from client")

                try:
                    data = json.loads(message)

                    # 래핑된 본문 형식 처리
                    if "body" in data:
                        data = json.loads(data["body"])

                    if "event" not in data:
                        logger.warning("Received message without event field")
                        continue

                    event_type = list(data["event"].keys())[0]

                    # 세션 시작 처리 - 새 Stream Manager 생성
                    if event_type == "sessionStart":
                        logger.info("Starting new session")

                        # 기존 세션이 있으면 정리
                        if stream_manager:
                            logger.info("Cleaning up existing session")
                            await stream_manager.close()
                        if forward_task and not forward_task.done():
                            forward_task.cancel()
                            try:
                                await forward_task
                            except asyncio.CancelledError:
                                pass

                        # 이 연결의 새 Stream Manager 생성
                        stream_manager = S2sSessionManager(model_id="amazon.nova-2-sonic-v1:0", region=aws_region)

                        # Amazon Bedrock 스트림 초기화
                        await stream_manager.initialize_stream()
                        logger.info("Stream initialized successfully")

                        # Amazon Bedrock 응답을 WebSocket으로 전달하는 작업 시작
                        forward_task = asyncio.create_task(forward_responses(websocket, stream_manager))

                        # sessionStart 이벤트를 Amazon Bedrock으로 전송
                        await stream_manager.send_raw_event(data)
                        logger.info(f"SessionStart event sent to Bedrock {json.dumps(data)}")

                        # 다음 이벤트를 처리하도록 다음 반복으로 이동
                        continue

                    # 세션 종료 처리 - 리소스 정리
                    elif event_type == "sessionEnd":
                        logger.info("Ending session")

                        if stream_manager:
                            await stream_manager.close()
                            stream_manager = None
                        if forward_task and not forward_task.done():
                            forward_task.cancel()
                            try:
                                await forward_task
                            except asyncio.CancelledError:
                                pass
                            forward_task = None

                        # 다음 반복으로 이동
                        continue

                    # 활성 Stream Manager가 있으면 이벤트 처리
                    if stream_manager and stream_manager.is_active:
                        # 제공된 경우 prompt 이름과 콘텐츠 이름 저장
                        if event_type == "promptStart":
                            stream_manager.prompt_name = data["event"]["promptStart"]["promptName"]
                        elif event_type == "contentStart" and data["event"]["contentStart"].get("type") == "AUDIO":
                            stream_manager.audio_content_name = data["event"]["contentStart"]["contentName"]

                        # 오디오 입력을 별도로 처리(큐 기반 처리)
                        if event_type == "audioInput":
                            prompt_name = data["event"]["audioInput"]["promptName"]
                            content_name = data["event"]["audioInput"]["contentName"]
                            audio_base64 = data["event"]["audioInput"]["content"]

                            # 비동기 처리를 위해 오디오 큐에 추가
                            stream_manager.add_audio_chunk(prompt_name, content_name, audio_base64)
                        else:
                            # 다른 이벤트는 Amazon Bedrock으로 직접 전송
                            await stream_manager.send_raw_event(data)
                    elif event_type not in ["sessionStart", "sessionEnd"]:
                        logger.warning(f"Received event {event_type} but no active stream manager")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received from WebSocket: {e}")
                    try:
                        await websocket.send_json({"type": "error", "message": "Invalid JSON format"})
                    except Exception:
                        pass
                except Exception as exp:
                    logger.error(f"Error processing WebSocket message: {exp}", exc_info=True)
                    try:
                        await websocket.send_json({"type": "error", "message": str(exp)})
                    except Exception:
                        pass

            except WebSocketDisconnect as e:
                logger.info(f"WebSocket disconnected: {websocket.client}")
                logger.info(
                    f"Disconnect details: code={getattr(e, 'code', 'N/A')}, reason={getattr(e, 'reason', 'N/A')}"
                )
                if stream_manager and stream_manager.is_active:
                    logger.info("Bedrock stream was still active when WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                break

    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "WebSocket handler error"})
        except Exception:
            pass
    finally:
        # 리소스 정리
        logger.info("Cleaning up WebSocket connection resources")

        if stream_manager:
            await stream_manager.close()
        if forward_task and not forward_task.done():
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass

        try:
            await websocket.close()
        except Exception as e:
            logger.error(f"Error closing websocket: {e}")

        logger.info("Connection closed")


def split_large_event(response, max_size=16000):
    """
    content 필드를 나눠 큰 이벤트를 더 작은 청크로 분할합니다.
    오디오 이벤트는 잡음을 방지하도록 샘플 경계에서 분할합니다.
    전송할 이벤트 목록을 반환합니다.
    """
    event = json.dumps(response)
    event_size = len(event.encode("utf-8"))

    # 이벤트가 충분히 작으면 그대로 반환
    if event_size <= max_size:
        return [response]

    # 이벤트 유형과 데이터 가져오기
    if "event" not in response:
        return [response]

    event_type = list(response["event"].keys())[0]
    event_data = response["event"][event_type]

    # 'content' 필드가 있는 이벤트만 분할(audioOutput, textOutput 등)
    if "content" not in event_data:
        logger.warning(f"Event {event_type} is large ({event_size} bytes) but has no content field to split")
        return [response]

    content = event_data["content"]

    # 청크마다 담을 수 있는 콘텐츠 양 계산
    # 오버헤드를 측정할 템플릿 이벤트 생성
    template_event = response.copy()
    template_event["event"] = {event_type: event_data.copy()}
    template_event["event"][event_type]["content"] = ""
    overhead = len(json.dumps(template_event).encode("utf-8"))

    # 청크당 최대 콘텐츠 크기 계산(일부 여유 공간 유지)
    max_content_size = max_size - overhead - 100

    # 오디오 이벤트는 샘플 경계에 정렬
    # Base64 인코딩: 4자 = 바이너리 데이터 3바이트
    # PCM 16-bit: 샘플당 2바이트
    # 유효한 base64를 위해 4자의 배수로 정렬해야 함(패딩 문제 방지)
    if event_type == "audioOutput":
        # 완전한 base64 그룹을 위해 4자 경계로 정렬
        # 각 청크가 패딩 문제 없는 유효한 base64가 되도록 함
        alignment = 4
        max_content_size = (max_content_size // alignment) * alignment
        logger.debug(f"Audio splitting: aligned chunk size to {max_content_size} chars (base64 boundary)")

    # 콘텐츠를 청크로 분할
    chunks = []
    for i in range(0, len(content), max_content_size):
        chunk_content = content[i : i + max_content_size]

        # base64 콘텐츠에 필요한 경우 적절한 패딩 보장
        if event_type == "audioOutput":
            # 각 청크는 4자의 배수여야 함(위에서 이미 정렬)
            # 그래도 확인하고 필요한 경우 패딩 추가
            remainder = len(chunk_content) % 4
            if remainder != 0:
                # 정렬 덕분에 발생하지 않아야 하지만 만약을 대비함
                padding_needed = 4 - remainder
                chunk_content += "=" * padding_needed
                logger.warning(f"Added {padding_needed} padding chars to audio chunk")

        # 분할된 콘텐츠로 새 이벤트 생성
        chunk_event = response.copy()
        chunk_event["event"] = {event_type: event_data.copy()}
        chunk_event["event"][event_type]["content"] = chunk_content

        chunks.append(chunk_event)

    logger.info(f"Split {event_type} event ({event_size} bytes) into {len(chunks)} chunks")
    return chunks


async def forward_responses(websocket: WebSocket, stream_manager):
    """Amazon Bedrock의 응답을 WebSocket Client로 전달합니다."""
    try:
        while True:
            # 출력 큐에서 다음 응답 가져오기
            response = await stream_manager.output_queue.get()

            # WebSocket으로 전송
            try:
                # 이벤트 분할이 필요한지 확인
                event = json.dumps(response)
                event_size = len(event.encode("utf-8"))

                    # 로깅할 이벤트 유형 가져오기
                event_type = list(response.get("event", {}).keys())[0] if "event" in response else "unknown"

                    # 큰 이벤트 분할
                if event_size > 10000:
                    logger.warning(f"!!!! Large {event_type} event detected (size: {event_size} bytes) - splitting...")
                    events_to_send = split_large_event(response, max_size=10000)
                else:
                    events_to_send = [response]

                    # 모든 청크 전송
                for idx, event_chunk in enumerate(events_to_send):
                    chunk_json = json.dumps(event_chunk)
                    chunk_size = len(chunk_json.encode("utf-8"))

                    await websocket.send_text(chunk_json)

                    if len(events_to_send) > 1:
                        logger.info(
                            f"Forwarded {event_type} chunk {idx + 1}/{len(events_to_send)} to client (size: {chunk_size} bytes)"
                        )
                    else:
                        logger.info(f"Forwarded {event_type} to client (size: {chunk_size} bytes)")

            except Exception as e:
                logger.error(f"Error sending response to client: {e}", exc_info=True)
            # 루프를 중단해야 하는 연결 오류인지 확인
                error_str = str(e).lower()
                if "closed" in error_str or "disconnect" in error_str:
                    logger.info("WebSocket connection closed, stopping forward task")
                    break
            # 기타 오류는 기록하고 계속 시도
                logger.warning("Continuing to forward responses despite error")
    except asyncio.CancelledError:
        logger.debug("Forward responses task cancelled")
    except Exception as e:
        logger.error(f"Error forwarding responses: {e}", exc_info=True)
    finally:
        logger.info("Forward responses task ended")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nova Sonic S2S WebSocket Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if args.debug:
        DEBUG = True
        logging.getLogger().setLevel(logging.DEBUG)

    host = os.getenv("HOST", "0.0.0.0")  # nosec B104
    port = int(os.getenv("PORT", "8080"))

    logger.info(f"Starting Nova Sonic S2S WebSocket Server on {host}:{port}")

    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
