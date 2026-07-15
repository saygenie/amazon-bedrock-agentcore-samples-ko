# 01 — 여행 가이드 에이전트

여행지를 추천하고, 여행 일정을 렌더링하며, 대화가 바뀌어도 사용자를 기억하는 여행 가이드 페르소나를 중심으로 구성된 완전한 엔드 투 엔드 AgentCore Harness 에이전트입니다. 이 예제에서는 **AgentCore Harness의 모든 기능을 둘러볼 수 있습니다.**

가장 먼저 살펴볼 대표 사용 사례로, 하나의 노트북에서 모든 주요 기능을 다룹니다.

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`01_travel_guide_agent.ipynb`](01_travel_guide_agent.ipynb) | 노트북 | Part 0~8로 구성된 전체 실습 과정으로, 각 Part에서 서로 다른 AgentCore Harness 기능을 보여 줍니다. |

## 구축할 항목

다음 기능을 갖춘 여행 가이드 에이전트를 구축합니다.

- 모든 여행지에 대한 **독립형 HTML 여행 일정**(인라인 CSS/JS 포함) 생성
- `ExecuteCommand`와 iframe을 통해 노트북 안에서 여행 일정을 **인라인 렌더링**
- CloudWatch로 **자동 추적 데이터** 전송(X-Ray 콘솔에서 탐색 가능)
- AgentCore Memory를 사용하여 세션이 바뀌어도 **사용자 기억**
- **Headless Browser**를 사용하여 실시간 날씨 데이터 가져오기
- **Exa MCP 검색과 Code Interpreter**를 결합하여 matplotlib 차트가 포함된 데이터 기반 관광 보고서 생성
- **로컬 채팅 웹 애플리케이션** 구동(FastAPI, SSE 스트리밍, Vanilla JS 프런트엔드)
- **Agent Skills**(Anthropic의 `xlsx` Skill)를 활용하여 실제 Excel 예산 스프레드시트 생성

## 노트북 실습 과정

| Part | 기능 | 수행 내용 |
|---|---|---|
| **0** | 설정 | IAM 실행 역할 생성, Boto3 클라이언트 구성, 베타 서비스 모델 로드 |
| **1** | AgentCore Harness 생성 | 제어 영역: `create_harness` → `READY` 상태가 될 때까지 폴링 |
| **2** | 호출 및 HTML 렌더링 | 데이터 영역: `invoke_harness` → 에이전트가 HTML 작성 → `ExecuteCommand`로 가져오기 → 노트북 안에서 인라인 렌더링 |
| **3** | Observability | Transaction Search 활성화 여부 확인 → CloudWatch X-Ray 콘솔을 열어 전체 에이전트 추적 확인 |
| **4** | Memory | Memory 인스턴스 생성 → AgentCore Harness에 연결 → 여러 호출에 걸쳐 에이전트가 이름과 선호도를 기억하는 멀티턴 대화 |
| **5** | Browser 도구 | `tools=[{"type": "agentcore_browser"}]` → 에이전트가 날씨 사이트 탐색 → 실시간 날씨 HTML 생성 |
| **6** | Exa 및 Code Interpreter | 여러 도구 호출: Exa로 관광 통계 검색 → Code Interpreter로 matplotlib 차트 생성 → 차트를 PNG로 가져오기 |
| **7** | 로컬 채팅 UI | `%%writefile`로 `server.py`(FastAPI + SSE)와 `index.html` 저장 → 서비스 모델 복사 → 로컬 실행 |
| **8** | Agent Skills | `xlsx` Skill을 `npx skills add`로 설치 → `skills=[...]`로 호출 → 생성된 `.xlsx` 다운로드 |

## 사전 요구 사항

- `us-west-2`에서 AgentCore Harness(Private Beta) 허용 목록에 등록된 AWS 계정
- 설치된 `uv`
- `HarnessExecutionRole`은 `helper/iam.py`를 통해 자동 생성

**Part 3(Observability)**을 진행하려면 계정별로 [CloudWatch Transaction Search](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Transaction-Search-getting-started.html)를 한 번 활성화하세요.

**Part 7(채팅 UI)**에서는 `uv`가 인라인 스크립트 메타데이터를 통해 서버 종속성을 처리합니다.

## 실행 방법

```bash
cd 02-use-cases/01-travel-agent
jupyter notebook 01_travel_guide_agent.ipynb
# 또는 VSCode에서 열기
```

셀을 위에서 아래로 실행하세요. 각 Part는 독립적으로 구성되어 있으므로 Part 1에서 AgentCore Harness를 생성한 후에는 원하는 Part만 실행할 수 있습니다.

### Part 7의 채팅 UI 실행

Part 7에서 파일을 저장하면 `travel_chat/` 폴더가 `02-use-cases/` 아래에 생성됩니다. 이 폴더는 생성된 아티팩트이므로 Git에서 추적하지 않습니다. 다음 명령으로 실행하세요.

```bash
cd ../travel_chat
HARNESS_ARN=<from-notebook> REGION=us-west-2 DATA_ENDPOINT=<from-notebook> uv run server.py
# http://localhost:8000 열기
```

## 정리

**Part 9와 Part 10**에서는 AgentCore Harness, Memory 인스턴스, IAM 역할을 삭제합니다. 유휴 AgentCore Harness와 Memory 인스턴스에도 비용이 발생하므로 반드시 실행하세요.

## 다음 실습

- **모델 교체** — `bedrockModelConfig.modelId`를 `us.anthropic.claude-sonnet-4-6-20251101-v1:0` 또는 `us.anthropic.claude-opus-4-5-20251101-v1:0`으로 변경하고 품질 비교
- **공급자 교체** — Bedrock 대신 OpenAI 또는 Gemini 사용(Secrets Manager의 `openAiModelConfig` 및 API 키 필요)
- **자체 도구 추가** — 사용자 지정 MCP 서버를 구축하고 호출에서 `remote_mcp` 도구로 등록
