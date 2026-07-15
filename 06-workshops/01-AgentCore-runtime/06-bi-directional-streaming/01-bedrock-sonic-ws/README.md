# Nova Sonic Direct Agent(하위 수준 S2S)

AWS Bedrock Runtime SDK를 통해 **Nova Sonic S2S API를 직접** 사용하는 양방향 음성 에이전트입니다. `BidiAgent` 추상화를 사용하는 Strands 에이전트나 sandwich pipeline을 사용하는 LangChain 에이전트와 달리, 이 에이전트는 raw 양방향 stream, event 프로토콜, 세션 수명 주기를 수동으로 관리합니다.

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
python utils/deploy.py 01-bedrock-sonic-ws

# 웹 클라이언트 시작
./utils/start_client.sh 01-bedrock-sonic-ws
```

### 사용해 보기

- 자연스럽게 말하면 에이전트가 실시간으로 응답합니다.
- 에이전트 응답 도중 끼어듭니다(barge-in).
- 테스트에는 텍스트 입력을 사용합니다.
- 도구 통합을 테스트하려면 "What's the date today?"라고 질문합니다.

### 정리

```bash
python ./utils/cleanup.py 01-bedrock-sonic-ws
```

## 로컬 테스트

AWS 자격 증명 외에 외부 종속성은 없습니다. Sonic 에이전트는 MCP Gateway 없이 Bedrock과 직접 통신합니다.

```bash
# 1. 서버 종속성 설치
pip install -r 01-bedrock-sonic-ws/websocket/requirements.txt

# 2. AWS 자격 증명 설정
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# 3. 서버 시작(port 8080)
cd 01-bedrock-sonic-ws/websocket
python server.py

# 4. 다른 terminal에서 클라이언트 시작(port 8000, 브라우저 열림)
cd 01-bedrock-sonic-ws/client
pip install -r requirements.txt
python client.py --ws-url ws://localhost:8080/ws
```

클라이언트는 `http://localhost:8000`에서 `sonic-client.html`을 제공하고 로컬 WebSocket 서버에 직접 연결합니다. SigV4 서명은 필요하지 않습니다.

## 아키텍처

![Sonic Direct Architecture](../assets/sonic-direct-architecture.svg)

클라이언트는 Nova Sonic 프로토콜 event(sessionStart, promptStart, audioInput 등)를 WebSocket을 통해 직접 전송합니다. 서버는 얇은 relay로 동작하며 Bedrock에 양방향 stream을 열고 클라이언트 event를 전달한 다음 Bedrock 응답을 내보냅니다. 에이전트 프레임워크는 사용하지 않습니다.

## 주요 구성 요소

| 파일 | 용도 |
|------|---------|
| `websocket/server.py` | FastAPI 서버, IMDS 자격 증명, WebSocket 엔드포인트, 대용량 event 분할, 응답 전달 |
| `websocket/s2s_session_manager.py` | Bedrock으로 연결되는 raw 양방향 stream 관리. Event 전송, 응답 처리, 도구 사용 처리 |
| `websocket/s2s_events.py` | Nova Sonic 프로토콜용 event factory(sessionStart, promptStart, audioInput, toolResult 등) |
| `client/client.py` | 선택적 SigV4 presigned URL 생성과 함께 HTML 클라이언트를 제공하는 HTTP 서버 |
| `client/sonic-client.html` | Nova Sonic event 프로토콜을 직접 사용하는 브라우저 기반 음성 클라이언트 |

## 작동 방식

### 세션 수명 주기

1. 클라이언트가 WebSocket을 통해 연결하고 `sessionStart` event를 전송합니다.
2. 서버가 `S2sSessionManager`를 생성하고 `BedrockRuntimeClient`를 통해 `amazon.nova-2-sonic-v1:0`으로 양방향 stream을 엽니다.
3. 클라이언트가 전체 event 순서를 전송합니다: `promptStart` → `contentStart`(system prompt) → `textInput` → `contentEnd` → `contentStart`(audio) → 스트리밍 `audioInput` chunk
4. 서버가 모든 event를 Bedrock에 전달하고 응답을 클라이언트로 relay합니다.
5. 클라이언트가 `sessionEnd`를 전송하여 세션을 닫습니다.

### 오디오 처리

- 입력: 16kHz PCM, 16-bit, mono(클라이언트가 브라우저의 native rate로 capture한 뒤 downsampling)
- 출력: 24kHz PCM, 16-bit, mono(Nova Sonic의 neural voice 출력)
- Backpressure를 처리하도록 오디오 입력을 queue에 저장(`asyncio.Queue`, 최대 100개 chunk). Queue가 가득 차면 chunk를 버립니다.
- 대용량 오디오 출력 event(>10KB)는 클라이언트에 전달하기 전에 base64 경계에서 더 작은 chunk로 분할합니다.

### 도구 사용

에이전트에는 현재 UTC 날짜/시간을 반환하는 간단한 `getDateTool`이 포함되어 있습니다. 도구 처리 흐름은 다음과 같습니다.

1. Bedrock이 도구 이름과 ID가 포함된 `toolUse` event를 전송합니다.
2. `S2sSessionManager`가 background `asyncio.Task`에서 non-blocking 방식으로 도구를 처리합니다.
3. 결과를 `contentStart`(TOOL) → `toolResult` → `contentEnd` 순서로 다시 전송합니다.
4. Tool event도 표시를 위해 클라이언트에 전달합니다.

### 대용량 Event 분할

`server.py`의 `split_large_event` 함수가 크기가 큰 Bedrock 응답을 처리합니다.

- 10KB보다 큰 event는 `content` field를 chunk로 나누어 분할합니다.
- Audio event(`audioOutput`)는 decoding 손상을 방지하도록 4자 base64 경계에 맞춥니다.
- 각 chunk는 content field만 변경하고 원래 event 구조를 유지합니다.

## Nova Sonic Event 프로토콜

이 에이전트는 raw Nova Sonic 양방향 스트리밍 프로토콜을 사용합니다. Event는 `event` wrapper가 있는 JSON 객체입니다.

### 클라이언트 → Bedrock(서버 relay 경유)

| Event | 용도 |
|-------|---------|
| `sessionStart` | 추론 구성(maxTokens, temperature, topP)으로 세션 초기화 |
| `promptStart` | 오디오/텍스트 출력 구성 및 도구 정의와 함께 prompt 시작 |
| `contentStart` | Content block 시작(system prompt는 TEXT, 사용자 음성은 AUDIO) |
| `textInput` | System prompt 텍스트 콘텐츠 |
| `audioInput` | 마이크에서 전송된 Base64 encoding PCM 오디오 chunk |
| `contentEnd` | Content block 종료 |
| `promptEnd` | Prompt 종료 |
| `sessionEnd` | 세션 종료 |

### Bedrock → 클라이언트(서버 relay 경유)

| Event | 용도 |
|-------|---------|
| `audioOutput` | Nova Sonic의 Base64 encoding PCM 오디오 응답 |
| `textOutput` | 에이전트 음성의 텍스트 transcript |
| `toolUse` | 도구 이름, ID, 매개변수가 포함된 도구 호출 요청 |
| `contentStart` / `contentEnd` | Type 및 role metadata가 포함된 content block 경계 |

## 자격 증명 관리

서버는 두 가지 mode를 지원합니다.

- **Local mode**: 환경 변수의 `AWS_ACCESS_KEY_ID` 및 `AWS_SECRET_ACCESS_KEY` 사용
- **EC2 mode**: IMDS에서 자격 증명을 가져오며(IMDSv2 우선, IMDSv1 fallback), 만료 전 background에서 자동 갱신

`S2sSessionManager`는 AWS SDK의 `EnvironmentCredentialsResolver`를 사용합니다. 이 resolver는 서버가 최신 상태로 유지하는 환경 변수에서 자격 증명을 읽습니다.
