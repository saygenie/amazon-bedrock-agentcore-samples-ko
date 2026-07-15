# Pipecat 음성 에이전트(Nova Sonic)

Native speech-to-speech를 위해 Amazon Nova Sonic과 [Pipecat](https://github.com/pipecat-ai/pipecat) 프레임워크를 사용하는 양방향 음성 에이전트입니다. `bedrock-agentcore` SDK를 사용하여 Amazon Bedrock AgentCore Runtime에 배포합니다.

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

# AgentCore에 배포
python utils/deploy.py 04-pipecat-sonic-ws

# 웹 클라이언트 시작
./utils/start_client.sh 04-pipecat-sonic-ws
```

### 정리

```bash
python utils/cleanup.py 04-pipecat-sonic-ws
```

## 로컬 테스트

MCP Gateway는 필요하지 않습니다. Pipecat 도구는 서버 코드에 inline으로 정의되어 있습니다.

```bash
# 1. 서버 종속성 설치
pip install -r 04-pipecat-sonic-ws/websocket/requirements.txt

# 2. AWS 자격 증명 설정
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# 3. 서버 시작(port 8081)
cd 04-pipecat-sonic-ws/websocket
python server.py

# 4. 다른 terminal에서 클라이언트 설치 및 시작
cd 04-pipecat-sonic-ws/client
npm install
npm run dev
```

Vite가 표시한 URL(일반적으로 `http://localhost:5173`)을 열고 Connect를 클릭합니다.

## 아키텍처

![Pipecat S2S Architecture](../assets/pipecat-s2s-architecture.svg)

Sandwich 아키텍처(STT → LLM → TTS)와 달리 Nova Sonic은 단일 모델 호출에서 오디오 입력과 출력을 기본 처리합니다.

## 주요 구성 요소

| 파일 | 용도 |
|------|---------|
| `websocket/server.py` | `AWSNovaSonicLLMService`, FastAPI + IMDS 자격 증명을 사용하는 Pipecat pipeline |
| `client/index.html` | Vite 앱 진입점 |
| `client/src/app.js` | `@pipecat-ai/client-js` + `WebSocketTransport`를 사용하는 브라우저 클라이언트 |
| `client/client.py` | AgentCore용 SigV4 presigned URL을 생성하는 경량 signing server |


## AgentCore 인증

AgentCore에 배포하면 브라우저는 SigV4 서명을 수행할 수 없습니다. 경량 Python signing server(`client.py`)가 presigned `wss://` URL을 생성합니다. Vite dev server는 `/start`를 이 서버로 proxy합니다.

`start_client.sh 04-pipecat-sonic-ws`는 이를 자동으로 처리하며 signing server와 Vite를 모두 시작합니다.

수동으로 실행하려면 다음 명령을 사용합니다.

```bash
# 터미널 1: signing server(포트 8081)
cd 04-pipecat-sonic-ws/client
python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/your-runtime-id

# 터미널 2: Vite 개발 서버
cd 04-pipecat-sonic-ws/client
npm run dev
```

클라이언트가 `/start`를 가져오면 Vite가 signing server로 proxy하고 presigned `wss://` URL을 반환합니다. 그런 다음 클라이언트가 AgentCore에 직접 연결합니다.
