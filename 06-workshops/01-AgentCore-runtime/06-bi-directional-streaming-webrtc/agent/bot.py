"""Nova Sonic을 사용하는 최소 WebRTC Voice Agent입니다.

KVS TURN Server를 통해 브라우저의 WebRTC 오디오를 Nova Sonic에 연결하는
FastAPI Server입니다. ICE 구성, WebRTC offer/answer 및 ICE candidate 교환을
처리하는 단일 /invocations 엔드포인트를 노출합니다.
"""

import argparse
import os
import sys
import time
from contextlib import asynccontextmanager

import uvicorn
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

import kvs
from audio import OutputTrack
from nova_sonic import run_session

load_dotenv(override=True)

CHANNEL_NAME = os.getenv("KVS_CHANNEL_NAME", "voice-agent-minimal")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# pc_id를 키로 사용하는 활성 Peer Connection
peer_connections = {}


# ---------------------------------------------------------------------------
# 앱 수명 주기
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    kvs.init(CHANNEL_NAME, AWS_REGION)
    yield
    for pc in peer_connections.values():
        await pc.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@app.get("/ping")
async def ping():
    """Health check for AgentCore Runtime."""
    return {"status": "Healthy", "time_of_last_update": int(time.time())}


@app.post("/invocations")
async def invocations(request: dict, background_tasks: BackgroundTasks):
    """Main endpoint — routes ICE config, offer/answer, and ICE candidate actions."""
    action = request.get("action")

    if action == "ice_config":
        return _handle_ice_config()
    elif action == "offer":
        return await _handle_offer(request.get("data", {}), background_tasks)
    elif action == "ice_candidate":
        return await _handle_ice_candidate(request.get("data", {}))
    elif action == "disconnect":
        return await _handle_disconnect(request.get("data", {}))

    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# 작업 핸들러
# ---------------------------------------------------------------------------


def _handle_ice_config():
    """브라우저용 KVS TURN/STUN Server 자격 증명을 반환합니다."""
    return {
        "iceServers": [
            {
                "urls": server["Uris"],
                "username": server.get("Username"),
                "credential": server.get("Password"),
            }
            for server in kvs.get_ice_servers(AWS_REGION, client_id="web-client")
        ]
    }


async def _handle_offer(data, background_tasks):
    """WebRTC offer를 수락하고 Peer Connection을 생성한 뒤 answer를 반환합니다."""
    ice_servers = kvs.get_rtc_ice_servers(AWS_REGION, client_id="server", turn_only=data.get("turnOnly", False))

    # 출력 오디오 트랙이 포함된 Peer Connection 생성
    pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
    audio_out = OutputTrack()
    pc.addTrack(audio_out)

    pc_id = f"pc_{len(peer_connections)}"
    peer_connections[pc_id] = pc

    # 브라우저의 오디오 트랙이 도착하면 Nova Sonic 세션 시작
    @pc.on("track")
    async def on_track(track):
        if track.kind == "audio":
            background_tasks.add_task(run_session, track, audio_out, AWS_REGION, pc_id)

    @pc.on("iceconnectionstatechange")
    async def on_ice_state():
        logger.info(f"ICE state: {pc.iceConnectionState}")

    # SDP offer/answer 교환
    await pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type=data["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "pc_id": pc_id,
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }


async def _handle_disconnect(data):
    """Peer Connection을 닫고 제거합니다."""
    pc = peer_connections.pop(data.get("pc_id"), None)
    if pc:
        await pc.close()
    return {"status": "success"}


async def _handle_ice_candidate(data):
    """기존 Peer Connection에 trickle ICE candidate를 추가합니다."""
    pc = peer_connections.get(data.get("pc_id"))
    if not pc:
        return {"status": "success"}

    for candidate_data in data.get("candidates", []):
        try:
            # 브라우저가 포함하는 "candidate:" 접두사 제거
            raw = candidate_data.get("candidate", "")
            if raw.startswith("candidate:"):
                raw = raw.split(":", 1)[1]

            candidate = candidate_from_sdp(raw)
            candidate.sdpMid = candidate_data.get("sdp_mid")
            candidate.sdpMLineIndex = candidate_data.get("sdp_mline_index")
            await pc.addIceCandidate(candidate)
        except Exception as e:
            logger.error(f"ICE candidate error: {e}")

    return {"status": "success"}


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("-v", "--verbose", action="count")
    args = parser.parse_args()

    logger.remove(0)
    logger.add(sys.stderr, level="TRACE" if args.verbose else "DEBUG")
    uvicorn.run(app, host=args.host, port=args.port)
