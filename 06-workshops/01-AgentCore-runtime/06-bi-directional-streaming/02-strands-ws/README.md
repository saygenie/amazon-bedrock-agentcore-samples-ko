# Strands 음성 에이전트(멀티 모델 Speech-to-Speech)

세 가지 S2S 모델인 **Amazon Nova Sonic**, **Google Gemini 2.5 Flash Native Audio**, **OpenAI GPT Realtime**을 지원하는 양방향 음성 에이전트입니다. Strands `BidiAgent`로 구축하고 MCP Gateway 도구 액세스와 함께 Amazon Bedrock AgentCore에 배포합니다.

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

# 배포(4개의 MCP Gateway + Agent Runtime 생성)
python utils/deploy.py 02-strands-ws

# 웹 클라이언트 시작
./utils/start_client.sh 02-strands-ws
```

### Knowledge Base 구성(FAQ 도구에 필요)

FAQ KB Gateway에는 Bedrock Knowledge Base가 필요합니다.

1. AWS Bedrock Console → Knowledge Bases → Create로 이동
2. `assets/anybank-faq.md`를 data source로 업로드
3. Knowledge Base ID 기록

그런 다음 Runtime 환경 변수를 업데이트합니다.

```bash
AGENT_RUNTIME_ID=$(python -c "import json; print(json.load(open('02-strands-ws/setup_config.json'))['agent_arn'].split('/')[-1])")

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id $AGENT_RUNTIME_ID \
  --environment-variables KNOWLEDGE_BASE_ID=your-kb-id-here \
  --region us-east-1
```

FAQ 도구(`search_anybank_faq`, `answer_anybank_question`)는 이 구성을 완료한 후에만 작동합니다. 다른 도구(auth, banking, mortgage)는 이 구성 없이도 작동합니다.

### 정리

```bash
python utils/cleanup.py 02-strands-ws
```

## 로컬 테스트

Strands 에이전트가 도구에 액세스하려면 MCP Gateway가 필요합니다. 로컬에서 실행하려면 배포된 Gateway와 AWS 자격 증명이 있어야 합니다.

```bash
# 1. 서버 종속성 설치
pip install -r 02-strands-ws/websocket/requirements.txt

# 2. AWS 자격 증명 설정
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# 3. MCP Gateway 구성 설정(이전에 실행한 `python utils/deploy.py 02-strands-ws` 결과)
export MCP_GATEWAY_ARNS='["arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/gw-1", ...]'
export MCP_GATEWAY_URLS='["https://gateway-1.endpoint.example.com", ...]'

# 4. 서버 시작(port 8080)
cd 02-strands-ws/websocket
python server.py

# 5. 다른 terminal에서 클라이언트 시작(port 8000, 브라우저 열림)
cd 02-strands-ws/client
pip install -r requirements.txt
python client.py --ws-url ws://localhost:8080/ws
```

클라이언트는 `http://localhost:8000`에서 `strands-client.html`을 제공하고 로컬 WebSocket 서버에 직접 연결합니다. SigV4 서명은 필요하지 않습니다.

Gemini 또는 OpenAI 모델에는 관련 API key도 설정합니다.

```bash
export GOOGLE_API_KEY=your-google-api-key    # Gemini용
export OPENAI_API_KEY=your-openai-api-key    # OpenAI용
```

### 사용해 보기

- "Hello, my name is John" → "My account ID is 1234567890 and my birthday is January 15th, 1990"
- "What's my account balance?" / "Show me my recent transactions"
- "What are the current mortgage rates?"
- "How can I avoid monthly fees on my checking account?" (requires Knowledge Base)

## 아키텍처

![Strands S2S Architecture](../assets/strands-s2s-architecture.svg)

`BidiAgent`는 클라이언트와 세션별로 선택된 모델 간의 양방향 stream을 관리합니다. 세 모델 모두 오디오 입력을 처리하고 오디오 출력을 기본 생성하므로 별도의 STT/TTS pipeline이 필요하지 않습니다.

## 지원 모델

| 모델 | ID | API Key | MCP Gateway |
|-------|----|---------|--------------|
| Amazon Nova Sonic | `amazon.nova-2-sonic-v1:0` | 없음(AWS 자격 증명) | 사용 |
| Google Gemini 2.5 Flash | `gemini-2.5-flash-native-audio-preview-12-2025` | `GOOGLE_API_KEY` | 사용 |
| OpenAI GPT Realtime | `gpt-realtime` | `OPENAI_API_KEY` | 사용 |

클라이언트의 구성 modal을 통해 세션별로 모델을 선택합니다. 선택한 모델에 따라 sample rate가 자동으로 구성됩니다.

## 주요 구성 요소

| 파일 | 용도 |
|------|---------|
| `websocket/server.py` | FastAPI 서버, IMDS 자격 증명, WebSocket 엔드포인트, 대용량 event 분할 |
| `websocket/agent.py` | 세션 handler, 멀티 모델 BidiAgent 설정(Nova Sonic / Gemini / OpenAI) |
| `client/client.py` | HTML 클라이언트를 제공하는 HTTP 서버 |
| `client/strands-client.html` | 모델 selector 및 구성 modal이 있는 브라우저 기반 음성/텍스트 클라이언트 |
| `client/profiles.json` | 사전 구성된 에이전트 profile(Finance, General, Tech Support) |
| `mcp/auth_mcp.py` | 인증 MCP 서버(authenticate_user, verify_identity) |
| `mcp/banking_mcp.py` | Banking MCP 서버(balance, transactions, transfers, summary) |
| `mcp/mortgage_mcp.py` | Mortgage MCP 서버(rates, calculator, eligibility, status) |
| `mcp/faq_kb_mcp.py` | FAQ Knowledge Base MCP 서버(search, citation 포함 answer) |

## BidiAgent 작동 방식

에이전트의 핵심은 I/O channel이 분리된 `BidiAgent`입니다.

```python
model = _create_model(config, gateway_arns)  # Nova Sonic, Gemini 또는 OpenAI

agent = BidiAgent(
    model=model,
    tools=[],
    system_prompt=system_prompt,
)

await agent.run(inputs=[handle_websocket_input], outputs=[chunked_send_json])
```

- `inputs` - 클라이언트의 message(audio chunk, text input)를 yield하는 비동기 함수입니다. `handle_websocket_input` 함수는 config event를 걸러내고 text/audio를 적절하게 전달합니다.
- `outputs` - `server.py`의 `chunked_send_json` wrapper는 WebSocket으로 전송하기 전에 대용량 audio event를 분할합니다.

이러한 분리를 통해 에이전트는 AgentCore의 WebSocket proxy echo에 영향을 받지 않습니다.

## 멀티 모델 설정

`agent.py`의 `_create_model` 함수는 클라이언트 구성의 `model_id`를 기준으로 적절한 모델을 생성합니다.

```python
# Nova Sonic - AWS 자격 증명 사용, MCP Gateway 지원
BidiNovaSonicModel(region=..., model_id=..., provider_config={...}, mcp_gateway_arn=[...])

# Gemini - GOOGLE_API_KEY 필요(config 또는 환경 변수)
BidiGeminiLiveModel(model_id=..., provider_config={...}, client_config={"api_key": key})

# OpenAI - OPENAI_API_KEY 필요(config 또는 환경 변수)
BidiOpenAIRealtimeModel(model_id=..., provider_config={...}, client_config={"api_key": key})
```

API key는 클라이언트 구성 modal에서 세션별로 제공하거나 서버의 환경 변수로 설정할 수 있습니다.

### 종속성

Gemini 및 OpenAI 모델에는 기본 `strands-agents` 외에 추가 package가 필요합니다.

```
google-genai>=1.32.0    # Gemini Live용
openai>=1.0.0           # OpenAI Realtime용
websockets>=14.0        # OpenAI Realtime SDK에 필요
```

## 대용량 Event 분할

`server.py`의 `split_large_event` 함수는 크기가 큰 audio output event를 처리합니다.

- 10KB보다 큰 event는 `audio` field를 작은 chunk로 나누어 분할
- Decoding 손상을 방지하도록 4자 base64 경계에 맞춰 분할
- 각 chunk가 원래 event 구조를 유지
- `chunked_send_json` 출력 wrapper가 모든 outbound event에 이를 자동 적용

## Voice Activity Detection(VAD)

Nova Sonic은 모델 내부에서 VAD를 처리하므로 사용자 지정 무음 감지가 필요하지 않습니다. 모델이 음성 경계를 기본 감지하고 barge-in을 지원합니다.

Gemini와 OpenAI도 각 Realtime API 내부에서 VAD를 처리합니다.

## MCP Gateway 통합

AgentCore MCP Gateway를 통해 도구에 액세스합니다. 4개의 Gateway가 배포됩니다.

| Gateway | MCP Server | 도구 |
|---------|-----------|-------|
| auth-tools | auth-tools-mcp | `authenticate_user`, `verify_identity` |
| banking-tools | banking-tools-mcp | `get_account_balance`, `get_recent_transactions`, `transfer_funds`, `get_account_summary` |
| mortgage-tools | mortgage-tools-mcp | `get_mortgage_rates`, `calculate_mortgage_payment`, `check_mortgage_eligibility`, `get_mortgage_application_status` |
| faq-kb-tools | anybank-faq-kb | `search_anybank_faq`, `answer_anybank_question` |

Gateway ARN은 `mcp_gateway_arn` 매개변수를 통해 모델에 전달되고 서버 측에서 `MCP_GATEWAY_ARNS` 환경 변수로 구성됩니다.

## WebSocket Message(클라이언트 ↔ 서버)

### 클라이언트 → 서버

| Type | Field | 설명 |
|------|--------|-------------|
| `config` | `voice`, `model_id`, `region`, `input_sample_rate`, `output_sample_rate`, `system_prompt`, `api_key` | 초기 세션 구성(첫 번째 message여야 함) |
| `text_input` | `text` | 에이전트에 보낼 text message |
| `bidi_audio_input` | `audio`(base64), `format`, `sample_rate`, `channels` | 마이크에서 전송된 PCM audio chunk |

### 서버 → 클라이언트

| Type | Field | 설명 |
|------|--------|-------------|
| `bidi_audio_stream` | `audio`(base64) | 모델의 audio output |
| `bidi_transcript_stream` | `text`, `role`, `delta` | 사용자 음성 또는 에이전트 응답의 transcript |
| `bidi_interruption` | - | 사용자가 에이전트 응답에 끼어듦(barge-in) |
| `bidi_response_complete` | - | 에이전트 응답 완료 |
| `bidi_usage` | `inputTokens`, `outputTokens`, `totalTokens` | Token 사용 통계 |
| `tool_use_stream` | `current_tool_use` | 도구 호출 진행 중 |
| `tool_result` | `tool_result` | 도구 실행 결과 |
| `system` | `message` | 상태/정보 message |

## 모델 비교

| 항목 | Nova Sonic | Gemini 2.5 Flash | OpenAI GPT Realtime |
|--------|-----------|------------------|---------------------|
| Audio rate | 16kHz in/out | 24kHz in/out | 24kHz in/out |
| 인증 | AWS 자격 증명 | Google API key | OpenAI API key |
| 음성 선택 | 지원(tiffany, matthew 등) | 미지원 | 미지원 |
| MCP Gateway | 기본 지원 | BidiAgent 경유 | BidiAgent 경유 |
| Barge-in | 기본 지원 | 기본 지원 | 기본 지원 |
| Transcript 처리 | 즉시 표시 | Buffering(grouped) | Buffering(grouped) |
