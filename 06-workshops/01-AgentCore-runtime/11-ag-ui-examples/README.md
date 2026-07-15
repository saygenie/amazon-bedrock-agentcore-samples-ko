# AgentCore Runtime의 AG-UI 예제

## 개요

[AG-UI(Agent-User Interface)](https://docs.ag-ui.com)는 AI 에이전트를 사용자용 애플리케이션에 연결하는 개방형 event 기반 프로토콜입니다. 요청-응답 프로토콜과 달리 AG-UI는 에이전트가 작업하는 동안 event를 스트리밍합니다. 도구 호출, 상태 변경, 텍스트 생성이 점진적으로 전달되므로 사용자는 에이전트의 진행 상황을 실시간으로 확인할 수 있습니다.

이 자습서에서는 AG-UI 프로토콜을 사용하여 **Collaborative Document Generator** 에이전트를 Amazon Bedrock AgentCore Runtime에 배포합니다. 에이전트는 대화형 인터페이스를 통해 사용자와 문서를 공동 작성하며 **SSE**와 **WebSocket** 전송 방식을 모두 보여 줍니다.

| 프로토콜 | 용도 | 통신 패턴 |
|:---------|:--------|:----------------------|
| **AG-UI** | Agent → User | Event 스트리밍(SSE + WebSocket) |
| MCP | Agent → Tools | 양방향 JSON-RPC |
| A2A | Agent → Agent | 작업 기반 오케스트레이션 |

## 아키텍처

AG-UI는 AI 에이전트가 사용자용 애플리케이션에 연결되는 방식을 표준화하는 개방형 event 기반 프로토콜입니다. AgentCore Runtime은 SSE와 WebSocket 전송을 모두 사용하여 AG-UI를 기본 지원합니다.

![AG-UI 아키텍처 - Cognito/JWT 인증](images/agui_arch_cognito.png)

![AG-UI 아키텍처 - IAM/SigV4 인증](images/agui_arch_iam.png)

### AG-UI Event 흐름

에이전트가 실행되는 동안 backend는 유형이 지정된 event stream을 내보냅니다.

![AG-UI Event 흐름](images/agui_event_flow.png)

### SSE 전송

**Cognito/JWT:**

![AG-UI SSE - Cognito](images/agui_sse_cognito.png)

**IAM/SigV4:**

![AG-UI SSE - IAM](images/agui_sse_iam.png)

### WebSocket 전송

**Cognito/JWT:**

![AG-UI WebSocket - Cognito](images/agui_ws_cognito.png)

**IAM/SigV4:**

![AG-UI WebSocket - IAM](images/agui_ws_iam.png)

## AG-UI Event 참조

| Event | 용도 |
|:------|:--------|
| `RUN_STARTED` | 에이전트 처리 시작 |
| `RUN_FINISHED` | 에이전트 완료 |
| `RUN_ERROR` | Code와 message가 포함된 오류 |
| `TEXT_MESSAGE_START` | Assistant message 시작 |
| `TEXT_MESSAGE_CONTENT` | 스트리밍 text delta |
| `TEXT_MESSAGE_END` | Message 완료 |
| `TOOL_CALL_START` | Tool 호출(name + ID) |
| `TOOL_CALL_ARGS` | Tool 인수(스트리밍) |
| `TOOL_CALL_END` | 인수 전달 완료 |
| `TOOL_CALL_RESULT` | Tool 출력 |
| `STATE_SNAPSHOT` | 전체 공유 상태 업데이트 |

## 사전 요구 사항

- Python 3.12+
- Bedrock 모델 액세스 권한이 있는 AWS 자격 증명(`us.anthropic.claude-sonnet-4-20250514-v1:0`)
- `bedrock-agentcore-starter-toolkit`(Notebook에서 설치)

## 빠른 시작(Cognito/JWT 인증)

1. `hosting_agui_agent_cognito.ipynb` 열기
2. **Install** 실행 - Python 종속성 및 starter toolkit 설치
3. **Cognito Setup** 실행 - User Pool 생성 및 Bearer token 발급
4. **Configure & Launch** 실행 - `protocol='AGUI'` 및 Cognito JWT authorizer로 에이전트 배포
5. **SSE Demo** 실행 - SSE를 통해 문서 생성 요청 전송
6. **WebSocket Demo** 실행 - WebSocket을 통해 동일한 요청 전송
7. **Interactive Demo** 실행 - 4턴 문서 공동 작성 대화
8. 완료 후 **Cleanup** 실행

## 빠른 시작(IAM/SigV4 인증)

1. `hosting_agui_agent_iam.ipynb` 열기
2. **Install** 실행 - Python 종속성 및 starter toolkit 설치
3. **Configure & Launch** 실행 - `protocol='AGUI'`로 에이전트 배포(IAM이 기본값)
4. **SSE Demo** 실행 - SigV4로 서명된 header와 함께 문서 생성 요청 전송
5. **WebSocket Demo** 실행 - SigV4 presigned URL을 통해 연결
6. **Interactive Demo** 실행 - 4턴 문서 공동 작성 대화
7. 완료 후 **Cleanup** 실행

## 폴더 구조

| 파일 | 설명 |
|:-----|:------------|
| `agui_agent.py` | 문서 공동 작성 AGUI 에이전트(FastAPI + Strands) |
| `requirements.txt` | Python 종속성(`websockets` 포함) |
| `hosting_agui_agent_cognito.ipynb` | SSE + WebSocket 데모가 포함된 Cognito/JWT 인증 Notebook |
| `hosting_agui_agent_iam.ipynb` | SSE + WebSocket 데모가 포함된 IAM/SigV4 인증 Notebook |
| `images/` | 아키텍처 다이어그램(AG-UI 개요, event 흐름, 전송) |
| `README.md` | 이 파일 |

## 전송 방식

### SSE (Server-Sent Events)

- Endpoint: `POST /invocations?qualifier=DEFAULT`
- Auth: `Authorization: Bearer <token>`(Cognito) 또는 SigV4로 서명된 header(IAM)
- 단방향: 클라이언트가 요청을 보내고 서버가 event를 스트리밍
- 대부분의 사용 사례에서 사용하는 기본 전송 방식

### WebSocket

- Endpoint: `GET /ws?qualifier=DEFAULT`(WebSocket으로 upgrade)
- Auth: `Authorization: Bearer <token>` header(Cognito) 또는 SigV4 presigned URL(IAM)
- 양방향: full-duplex 스트리밍
- 장시간 세션 및 실시간 협업에 유용

두 전송 방식 모두 동일한 AG-UI event를 스트리밍합니다. 에이전트 코드는 FastAPI의 `/invocations`(SSE) 및 `/ws`(WebSocket) 엔드포인트를 통해 두 방식을 모두 처리합니다.

## 문제 해결

| 문제 | 해결 방법 |
|:------|:---------|
| 실행 시 `CREATE_FAILED` | IAM permission을 확인하고 CloudWatch log 검토 |
| SSE에서 401/403 | Bearer token(Cognito)을 새로 고치거나 요청(SigV4)을 다시 서명 |
| WebSocket 연결 거부 | 구성 시 `protocol='AGUI'`가 설정되었는지 확인 |
| 에이전트가 빈 응답 반환 | CloudWatch log를 확인하고 Bedrock 모델 액세스 검증 |
| 데모 중 Token 만료 | `refresh_token()`(Cognito)을 실행하거나 SigV4 header를 다시 생성 |
| Runtime 초기화 timeout(30초) | 에이전트가 lazy initialization을 사용하므로 첫 요청은 더 오래 걸릴 수 있음 |

## 정리

각 Notebook에는 다음 항목을 삭제하는 정리 셀이 포함되어 있습니다.
- AgentCore Runtime
- Cognito User Pool(Cognito Notebook만 해당)
