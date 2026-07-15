# LangChain 음성 에이전트(Sandwich 아키텍처)

"Sandwich" 패턴인 **STT → Agent → TTS**를 사용하는 양방향 음성 에이전트입니다. LangChain + Bedrock Nova 2 Lite로 구축하고 Amazon Bedrock AgentCore에 배포합니다.

## AgentCore에 배포

```bash
# 양방향 스트리밍 자습서 root로 이동
cd 06-workshops/01-AgentCore-runtime/06-bi-directional-streaming

# 가상 환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 배포 종속성 설치
pip install -r utils/requirements.txt

# AWS 계정 ID 설정
export ACCOUNT_ID=123456789012

# AWS 자격 증명 설정(옵션 A: 환경 변수)
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# AWS 자격 증명 설정(옵션 B: 명명된 profile)
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1

# 배포
python utils/deploy.py 03-langchain-transcribe-polly-ws

# 웹 클라이언트 시작
./utils/start_client.sh 03-langchain-transcribe-polly-ws
```

### 정리

```bash
python utils/cleanup.py 03-langchain-transcribe-polly-ws
```

## 로컬 테스트

LangChain 에이전트가 도구에 액세스하려면 Strands 에이전트와 마찬가지로 MCP Gateway가 필요합니다. 로컬에서 실행하려면 배포된 Gateway와 AWS 자격 증명이 있어야 합니다.

```bash
# 1. 서버 종속성 설치
pip install -r 03-langchain-transcribe-polly-ws/websocket/requirements.txt

# 2. AWS 자격 증명 설정
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# 3. MCP Gateway 구성 설정(이전에 실행한 `python utils/deploy.py 03-langchain-transcribe-polly-ws` 결과)
export MCP_GATEWAY_ARNS='["arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/gw-1", ...]'
export MCP_GATEWAY_URLS='["https://gateway-1.endpoint.example.com", ...]'

# 4. 서버 시작(port 8080)
cd 03-langchain-transcribe-polly-ws/websocket
python server.py

# 5. 다른 terminal에서 클라이언트 시작(port 8000, 브라우저 열림)
cd 03-langchain-transcribe-polly-ws/client
pip install -r requirements.txt
python client.py --ws-url ws://localhost:8080/ws
```

클라이언트는 `http://localhost:8000`에서 `langchain-client.html`을 제공하고 로컬 WebSocket 서버에 직접 연결합니다. SigV4 서명은 필요하지 않습니다.

## 아키텍처

![LangChain Sandwich Architecture](../assets/langchain-sandwich-architecture.svg)

Nova Sonic의 native 양방향 오디오 모델을 사용하는 Strands 에이전트와 달리 이 에이전트는 text 기반 LLM 주위에 pipeline을 구성하여 음성을 구현합니다. 클라이언트는 AgentCore의 proxy를 통과하는 WebSocket을 통해 서버로 audio/text를 보내고, 서버는 Amazon Transcribe(STT) → LangChain Agent(Bedrock Nova 2 Lite) → Amazon Polly(TTS) sandwich pipeline을 실행합니다.

## 주요 구성 요소

| 파일 | 용도 |
|------|---------|
| `websocket/server.py` | FastAPI 서버, IMDS 자격 증명, WebSocket 엔드포인트 |
| `websocket/agent.py` | 세션 handler, LangChain 에이전트, STT/TTS pipeline, VAD |
| `client/client.py` | HTML 클라이언트를 제공하는 HTTP 서버 |
| `client/langchain-client.html` | 브라우저 기반 음성/텍스트 클라이언트 |

## Voice Activity Detection(VAD)

LangChain에는 VAD가 기본 제공되지 않습니다. 이 에이전트는 서버 측에서 사용자 지정 energy 기반 무음 감지를 사용합니다.

1. 수신되는 각 audio chunk의 RMS energy를 16-bit PCM sample에서 계산합니다.
2. Energy < `RMS_SILENCE_THRESHOLD`(500)이면 무음 counter가 증가합니다.
3. Energy >= threshold이면 counter가 재설정됩니다.
4. 무음이 `SILENCE_THRESHOLD_SECS`(0.6초) 동안 지속되고 audio buffer > 3200 byte이면 buffer를 Transcribe로 보냅니다.

`agent.py`에서 조정할 수 있는 매개변수:

| 매개변수 | 기본값 | 효과 |
|-----------|---------|--------|
| `SILENCE_THRESHOLD_SECS` | 0.6 | STT가 시작되기 전 무음 시간. 값이 낮으면 응답이 빨라지고 높으면 잘못된 trigger가 줄어듦 |
| `RMS_SILENCE_THRESHOLD` | 500 | 오디오를 무음으로 간주하는 energy 기준. 값이 낮으면 작은 음성에 덜 민감 |
| `CHUNK_INTERVAL_SECS` | 0.085 | 클라이언트에서 전송되는 audio chunk 사이의 예상 간격 |

## AgentCore WebSocket Proxy 고려 사항

AgentCore에 배포하면 WebSocket 연결은 직접 localhost 연결과 다르게 작동하는 proxy 계층을 통과합니다.

- **Message echo**: Proxy가 서버에서 보낸 message를 서버로 다시 echo합니다. 에이전트는 자신이 보내는 message type(`tts_audio`, `agent_chunk`, `transcript`, `system`, `error`)을 무시하여 이를 걸러냅니다.
- **TTS feedback loop**: Proxy로 인한 추가 지연이 브라우저의 기본 echo cancellation을 무력화할 수 있습니다. 클라이언트는 TTS 오디오 재생 중에 마이크를 음소거하여 에이전트 음성이 수집되고 transcribe되어 새 입력으로 돌아오는 것을 방지합니다.

Localhost에서는 FastAPI의 WebSocket이 message echo가 없는 직접 point-to-point 연결이므로 이러한 문제가 발생하지 않습니다.

## Strands와 LangChain 비교

| 항목 | Strands(Nova Sonic) | LangChain(Sandwich) |
|--------|---------------------|---------------------|
| Audio 모델 | Native 양방향(Nova Sonic) | Text LLM + STT/TTS pipeline |
| VAD | Nova Sonic 모델에서 처리 | 사용자 지정 RMS energy 감지 |
| Proxy echo 처리 | BidiAgent에 기본 제공(분리된 I/O channel) | 명시적인 message type filtering |
| 지연 시간 | 낮음(단일 모델 호출) | 높음(STT + LLM + TTS 순차 실행) |
| 음성 품질 | Neural(model-native) | Amazon Polly |

## 음성 에이전트 Event 정의

이 에이전트는 sandwich pipeline용 사용자 지정 event 시스템을 정의합니다. Event는 STT → Agent → TTS 단계를 거칩니다.

### Pipeline Event(서버 측, `agent.py`에 정의)

서버의 비동기 pipeline 단계에서 사용하는 내부 Python event입니다.

| Event Class | Type String | Payload | 설명 |
|-------------|-------------|---------|-------------|
| `VoiceAgentEvent` | (base class) | `type: str` | Pipeline의 기본 event |
| `STTChunkEvent` | `stt_chunk` | `transcript: str` | STT의 partial/interim transcript |
| `STTOutputEvent` | `stt_output` | `transcript: str` | 에이전트 처리를 시작하는 최종 transcript |
| `AgentChunkEvent` | `agent_chunk` | `text: str` | LangChain 에이전트에서 스트리밍된 text chunk |
| `TTSChunkEvent` | `tts_chunk` | `audio: bytes` | TTS의 raw PCM audio chunk |

### WebSocket Message(클라이언트 ↔ 서버)

WebSocket을 통해 JSON으로 전송되는 message:

#### 클라이언트 → 서버

| Type | Field | 설명 |
|------|--------|-------------|
| `config` | `voice`, `region`, `input_sample_rate`, `output_sample_rate`, `system_prompt`, `gateway_arns` | 초기 세션 구성(첫 번째 message여야 함) |
| `text_input` | `text` | 에이전트에 보낼 text message |
| `audio_input` | `audio`(base64), `format`, `sample_rate`, `channels` | 마이크에서 전송된 PCM audio chunk |

#### 서버 → 클라이언트

| Type | Field | 설명 |
|------|--------|-------------|
| `system` | `message` | 상태/정보 message(예: "agent ready") |
| `transcript` | `text` | 사용자 음성의 최종 STT transcript |
| `agent_chunk` | `text` | 에이전트의 text 응답 |
| `tts_audio` | `audio`(base64), `sample_rate` | 합성 음성 audio chunk |
| `error` | `message` | 오류 세부 정보 |

## LangChain 공식 문서

LangChain은 sandwich 아키텍처를 사용하는 음성 에이전트 구축 공식 가이드를 제공합니다.

- [LangChain으로 음성 에이전트 구축](https://docs.langchain.com/oss/python/langchain/voice-agent) - STT → Agent → TTS pipeline 패턴, `RunnableGenerator`를 사용한 비동기 스트리밍, pipeline 단계 구성 방법을 다룹니다. 공식 가이드는 STT에 AssemblyAI, TTS에 Cartesia를 사용하지만 이 구현은 각각 Amazon Transcribe와 Amazon Polly로 대체합니다.

공식 문서의 핵심 event 모델(`stt_chunk`, `stt_output`, `agent_chunk`, `tts_chunk`)은 이 에이전트의 `VoiceAgentEvent` class에 정의된 event type과 일치합니다.

## 제한 사항

### Barge-In 미지원

이 에이전트는 발화 중인 에이전트에 끼어드는 barge-in을 지원하지 않습니다. Feedback loop를 방지하도록 TTS 재생 중에 마이크를 음소거하며, 서버는 응답을 순차적으로 처리합니다. `run_agent_and_respond`는 message loop로 돌아가기 전에 전체 Agent → TTS cycle을 완료합니다.

반면 Nova Sonic(Strands 에이전트)은 모델 내에서 입력 및 출력 오디오가 단일 양방향 stream을 공유하므로 barge-in을 기본 처리합니다.

### Barge-In 추가 방법

Sandwich 아키텍처에 barge-in을 추가하려면 클라이언트와 서버를 모두 변경해야 합니다.

**클라이언트:**
1. TTS 재생 중 마이크 활성 상태 유지(음소거 방식을 acoustic echo cancellation으로 교체하거나 일부 echo 위험 감수)
2. 오디오 재생 중 음성을 감지하도록 클라이언트 측에서 VAD 실행
3. 재생 중 음성이 감지되면 WebSocket을 통해 `barge_in` event를 보내고 즉시 오디오 재생 중지(`source.stop()`, `nextPlayTime` queue 비우기)

**서버:**
1. 기본 loop에서 `barge_in` message type 처리
2. `asyncio.Event` 또는 cancellation token을 사용하여 진행 중인 `run_agent_and_respond` 중단. 에이전트 stream(`agent.astream`)을 취소하고 대기 중인 Polly TTS 호출을 건너뛰어야 함
3. 서버 측 audio buffer 및 무음 counter 비우기
4. Barge-in을 시작한 새 오디오 입력 처리

주요 과제는 순차 pipeline 전체에 cancellation을 전달하는 것입니다. 각 단계(에이전트 스트리밍, Polly 합성, WebSocket 전송)는 진행하기 전에 cancellation flag를 확인해야 합니다. 다음과 같은 패턴을 사용할 수 있습니다.

```python
cancel_event = asyncio.Event()

async def run_agent_and_respond(text: str):
    # ... 에이전트 스트리밍 ...
    async for msg, metadata in stream:
        if cancel_event.is_set():
            break  # 응답 중단
        # Chunk 처리...

    if cancel_event.is_set():
        return  # TTS 건너뛰기

    # ... TTS 합성 및 전송 ...
    for i in range(0, len(audio_bytes), TTS_CHUNK_SIZE):
        if cancel_event.is_set():
            break
        # Chunk 전송...
```

### S2S보다 높은 지연 시간

Sandwich 아키텍처는 STT → LLM → TTS라는 세 단계를 순차적으로 실행하므로 speech-to-speech 모델보다 기본적으로 지연 시간이 깁니다. 각 단계에서 자체 처리 시간과 network round-trip이 추가됩니다. VAD 무음 threshold(현재 0.6초)로 인해 처리가 시작되기 전 추가 지연도 발생합니다. Nova Sonic은 단일 모델 호출에서 오디오를 end-to-end로 처리하여 이러한 overhead를 피합니다.
