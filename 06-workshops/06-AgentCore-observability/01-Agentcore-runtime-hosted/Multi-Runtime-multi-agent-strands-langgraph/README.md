# 관측성을 갖춘 다중 에이전트 시스템

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime 및 Observability를 사용하여 완전한 관측성을 갖춘 **다중 에이전트 시스템**을 구축하는 방법을 살펴봅니다. CloudWatch GenAI Observability를 통해 엔드 투 엔드 트레이싱을 유지하면서 여러 에이전트를 조정하는 두 가지 패턴을 학습합니다.

### 패턴

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         MULTI-AGENT Patterns                              │
├─────────────────────────────────┬─────────────────────────────────────────┤
│     PART 1: SINGLE RUNTIME      │      PART 2: MULTI-RUNTIME              │
│                                 │                                         │
│  ┌───────────────────────────┐  │  ┌───────────────────────────────────┐  │
│  │   AgentCore Runtime       │  │  │      ORCHESTRATOR (Strands)       │  │
│  │                           │  │  │      AgentCore Runtime #1         │  │
│  │  ┌─────────────────────┐  │  │  └──────────────┬────────────────────┘  │
│  │  │    ORCHESTRATOR     │  │  │                 │                       │
│  │  │      (Strands)      │  │  │         ┌──────┴──────┐                 │
│  │  │         │           │  │  │         ▼             ▼                 │
│  │  │    ┌────┴────┐      │  │  │  ┌────────────┐ ┌────────────┐          │
│  │  │    ▼         ▼      │  │  │  │  TRAVEL    │ │  WEATHER   │          │
│  │  │ TRAVEL    WEATHER   │  │  │  │  (Strands) │ │ (LangGraph)│          │
│  │  │(Strands)  (Strands) │  │  │  │ Runtime #2 │ │ Runtime #3 │          │
│  │  └─────────────────────┘  │  │  └────────────┘ └────────────┘          │
│  └───────────────────────────┘  │                                         │
│                                 │                                         │
│  - Single unified trace         │  - Linked traces via session ID         │
│  - Simple deployment            │  - Mix frameworks (Strands + LangGraph  │
└─────────────────────────────────┴─────────────────────────────────────────┘
```


## 사전 요구 사항

1. 필요한 권한으로 구성된 AWS CLI(`aws configure`)
2. `global.anthropic.claude-haiku-4-5-20251001-v1:0`에 대한 Amazon Bedrock 모델 액세스 활성화
3. CloudWatch Transaction Search 활성화([설정 가이드](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Transaction-Search-getting-started.html))

## 프로젝트 구조

```
03-multi-runtimes-with-observability/
├── multi_agent_observability.ipynb   # 기본 튜토리얼 노트북
├── utils.py                          # Helper 함수
├── requirements.txt                  # 종속성
│
├── single_runtime/                   # Part 1: 하나의 Runtime에 모든 에이전트 배치
│   ├── multi_agent.py               # Orchestrator + Travel + Weather 에이전트
│   └── requirements.txt
│
├── travel_agent/                     # Part 2: Strands 기반 travel 에이전트
│   ├── main.py                      # 웹 검색 기능
│   └── requirements.txt
│
├── weather_agent/                    # Part 2: LangGraph 기반 weather 에이전트
│   ├── main.py                      # 날씨 조회 기능
│   └── requirements.txt
│
└── orchestrator_agent/               # Part 2: Coordinator 에이전트
    ├── main.py                      # Query를 하위 에이전트로 라우팅
    └── requirements.txt
```

## 빠른 시작

```bash
# 종속성 설치
pip install -r requirements.txt

# 튜토리얼 노트북 실행
jupyter notebook multi_agent_observability.ipynb
```

## 1부: 단일 Runtime 아키텍처

모든 에이전트가 단일 AgentCore Runtime에서 실행되며 직접 함수 호출로 서로 통신합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                   AgentCore Runtime                          │
│                                                             │
│    User Query ──► ORCHESTRATOR                              │
│                        │                                    │
│                   ┌────┴────┐                               │
│                   ▼         ▼                               │
│              TRAVEL      WEATHER                            │
│              AGENT       AGENT                              │
│                │           │                                │
│                ▼           ▼                                │
│           web_search   get_weather                          │
│                                                             │
│    Telemetry:  CloudWatch GenAI Observability Dashboard     │
└─────────────────────────────────────────────────────────────┘
```

**핵심 사항:**
- 단일 배포, 단일 IAM 역할
- CloudWatch의 통합 트레이스 트리
- 적합한 경우: 긴밀하게 결합된 에이전트, 단일 팀 소유

## 2부: 다중 Runtime 아키텍처

각 에이전트가 자체 AgentCore Runtime에서 실행되며, 세션 ID를 전파하는 직접 호출을 통해 통신합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                              │
│                 AgentCore Runtime #1                         │
│                   (Strands Agent)                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
            invoke_agent_runtime() + session_id
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│     TRAVEL AGENT        │     │     WEATHER AGENT       │
│  AgentCore Runtime #2   │     │  AgentCore Runtime #3   │
│     (Strands)           │     │     (LangGraph)         │
│                         │     │                         │
│  Tool: web_search       │     │  Tool: get_weather      │
│  (DuckDuckGo)           │     │  (Mock data)            │
└─────────────────────────┘     └─────────────────────────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
              CloudWatch GenAI Observability
                   (Linked Traces)
```

**핵심 사항:**
- 에이전트별로 서로 다른 프레임워크 사용(Strands Agents + LangGraph)
- 트레이스 연결


## 트레이스 확인

에이전트를 실행한 후 CloudWatch 대시보드에서 트레이스, 세션, 로그, 제공 로그 및 지표를 확인하고 로그와 지표를 모니터링합니다.


## 다음 단계

이 자습서를 완료한 후 [A2A를 사용하는 다중 Runtime](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/02-use-cases/A2A-multi-agent-incident-response)을 살펴보세요.
