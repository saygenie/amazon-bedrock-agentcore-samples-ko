# AgentCore Runtime의 양방향 스트리밍 음성 에이전트

[Amazon Nova Sonic](https://docs.aws.amazon.com/bedrock/latest/userguide/nova-sonic.html)을 사용하여 실시간 음성 에이전트를 구축하고 [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-toolkit.html)에 배포합니다.

![AgentCore Bidirectional Runtime](assets/agentcore-bidi-runtime.png)

## 음성 에이전트에 AgentCore를 사용하는 이유

음성 에이전트에는 지속적인 저지연 연결이 필요합니다. 브라우저가 오디오를 스트리밍하면 에이전트가 모델을 통해 처리하고 음성 응답을 다시 스트리밍합니다. [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/)은 이를 프로덕션에서 실행하기 위한 관리형 인프라를 제공합니다.

- **SigV4 인증을 사용하는 WebSocket proxy** - 클라이언트가 AgentCore의 인증된 엔드포인트를 통해 연결되므로 에이전트가 인증을 처리할 필요가 없습니다.
- **CodeBuild를 통한 컨테이너 배포** - 에이전트를 Docker 컨테이너로 packaging하고 인프라를 관리하지 않고 배포합니다. 로컬 Docker는 필요하지 않습니다.
- **IAM 역할 관리** - AgentCore가 Bedrock 모델 액세스 권한이 있는 실행 역할을 프로비저닝합니다.
- **MCP Gateway 통합** - [Model Context Protocol](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/mcp-gateway.html)을 통해 에이전트를 외부 도구(database, API, knowledge base)에 연결합니다.
- **Auto Scaling 및 수명 주기 관리** - AgentCore가 scaling과 상태 확인을 처리합니다.

## 아키텍처 패턴

이 샘플은 음성 에이전트를 위한 두 가지 아키텍처 패턴을 보여 줍니다.

**Native Speech-to-Speech(S2S)** - 오디오가 음성을 이해하고 음성으로 응답하는 모델에 직접 전달됩니다. Nova Sonic, Gemini, OpenAI Realtime이 모두 이를 기본 지원합니다. 지연 시간이 짧고 pipeline이 단순하며 VAD와 barge-in이 기본 제공됩니다.

**Sandwich(STT → LLM → TTS)** - 오디오를 텍스트로 변환하고 text LLM으로 처리한 다음 다시 음성으로 합성합니다. 모든 text LLM을 사용할 수 있어 더 유연하지만 순차 pipeline으로 인해 지연 시간이 더 깁니다.

## 샘플

| # | 샘플 | 아키텍처 | 프레임워크 | 주요 기능 |
|---|--------|-------------|-----------|-------------|
| 01 | [Bedrock Sonic](01-bedrock-sonic-ws/) | Native S2S | Raw Bedrock SDK | 전체 프로토콜 제어, 하위 수준 event 처리 |
| 02 | [Strands](02-strands-ws/) | Native S2S(멀티 모델) | Strands BidiAgent | MCP Gateway, 멀티 모델(Nova Sonic / Gemini / OpenAI) |
| 03 | [LangChain + Transcribe + Polly](03-langchain-transcribe-polly-ws/) | Sandwich(STT→LLM→TTS) | LangChain + Transcribe + Polly | 음성 I/O pipeline을 사용하는 text LLM, 사용자 지정 VAD |
| 04 | [Pipecat Sonic](04-pipecat-sonic-ws/) | Native S2S | Pipecat pipeline | Open source 프레임워크, RTVI/Protobuf, Silero VAD |

### [01 - Bedrock Sonic](01-bedrock-sonic-ws/README.md)

Raw Bedrock Runtime SDK를 사용하는 직접 구현입니다. 양방향 stream, event 프로토콜, 세션 수명 주기를 수동으로 관리합니다. Nova Sonic 프로토콜을 이해하거나 세밀한 제어가 필요한 사용자 지정 통합을 구축하는 데 적합합니다.

### [02 - Strands](02-strands-ws/README.md)

Strands `BidiAgent` SDK를 통해 세 가지 S2S 모델(Nova Sonic, Gemini, OpenAI)을 지원하는 banking assistant입니다. 4개의 MCP Gateway가 인증, banking, mortgage, FAQ 서비스를 위한 모듈식 도구 액세스를 제공합니다. 기능이 가장 풍부한 샘플입니다.

### [03 - LangChain + Transcribe + Polly](03-langchain-transcribe-polly-ws/README.md)

음성 인식에는 Amazon Transcribe, 추론에는 Bedrock Nova 2 Lite와 LangChain, 음성 합성에는 Amazon Polly를 사용하여 STT → Agent → TTS "sandwich" 패턴을 보여 줍니다. Text 기반 LLM pipeline과 native S2S 모델 간의 trade-off를 이해하는 데 유용합니다.

### [04 - Pipecat Sonic](04-pipecat-sonic-ws/README.md)

Native speech-to-speech를 위해 `AWSNovaSonicLLMService`와 [Pipecat](https://github.com/pipecat-ai/pipecat) open source 프레임워크를 사용합니다. Silero VAD, Protobuf serialization을 사용하는 RTVI 프로토콜, Vite 기반 브라우저 클라이언트를 포함합니다.

## 시작하기

각 샘플에는 설정, 배포, 로컬 테스트 지침이 포함된 README가 있습니다. 샘플을 선택하고 해당 가이드를 따르세요.

- [01-bedrock-sonic-ws/README.md](01-bedrock-sonic-ws/README.md) - raw 프로토콜을 이해하려면 여기에서 시작
- [02-strands-ws/README.md](02-strands-ws/README.md) - 도구를 갖춘 전체 기능 에이전트는 여기에서 시작
- [03-langchain-transcribe-polly-ws/README.md](03-langchain-transcribe-polly-ws/README.md) - sandwich 아키텍처는 여기에서 시작
- [04-pipecat-sonic-ws/README.md](04-pipecat-sonic-ws/README.md) - Pipecat 프레임워크는 여기에서 시작

## 프로젝트 구조

```
├── utils/                             # 공유 배포/정리 스크립트
├── 01-bedrock-sonic-ws/               # Native Nova Sonic(raw SDK)
│   ├── websocket/                     #   서버 + Dockerfile
│   └── client/                        #   브라우저 클라이언트
├── 02-strands-ws/                     # Strands BidiAgent(멀티 모델)
│   ├── websocket/                     #   서버 + Dockerfile
│   ├── client/                        #   브라우저 클라이언트
│   └── mcp/                           #   MCP 서버 구현
├── 03-langchain-transcribe-polly-ws/  # LangChain sandwich(STT→LLM→TTS)
│   ├── websocket/                     #   서버 + Dockerfile
│   └── client/                        #   브라우저 클라이언트
├── 04-pipecat-sonic-ws/               # Pipecat 프레임워크(Nova Sonic)
│   ├── websocket/                     #   서버 + Dockerfile
│   └── client/                        #   Vite 앱 + signing server
└── assets/                            # 아키텍처 다이어그램
```

## 리소스

- [AgentCore Runtime 문서](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AgentCore Starter Toolkit](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-toolkit.html)
- [AgentCore MCP Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/mcp-gateway.html)
- [Amazon Nova Sonic](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html)
- [Strands Agents SDK](https://strandsagents.com/docs/user-guide/concepts/bidirectional-streaming/quickstart)
- [Pipecat 프레임워크](https://github.com/pipecat-ai/pipecat)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
