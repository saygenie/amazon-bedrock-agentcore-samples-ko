<div align="center">

# 🧪 실습 5 — 평가 데이터 생성기

### Strands Agents 기반 에이전트 · 격리된 리소스 · 워크숍 실습과 충돌 없음

<br>

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   ⚡  setup  →  test  →  generate  →  cleanup  ⚡      │
│                                                         │
│   Creates a full Strands agent stack (Labs 1-4)         │
│   then generates 30 min of evaluation traffic           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

</div>

---

## 🎯 주요 기능

이 도우미 스크립트는 **Google ADK가 아닌 Strands Agents**를 사용해 워크숍의 **실습 1부터 실습 4까지**를 재현합니다. 기본 워크숍 실습과 충돌하지 않도록 **완전히 다른 리소스 이름**을 사용합니다.

전체 에이전트 스택을 프로비저닝하고 정상 작동을 확인한 다음, 30분 동안 다양한 고객 지원 프롬프트를 반복해서 보내 평가 데이터를 생성합니다.

---

## 🏗️ 리소스 격리

이 스크립트가 생성하는 모든 리소스는 별도의 네임스페이스를 사용합니다.

| 리소스 | 워크숍 실습(Google ADK) | 이 스크립트(Strands Agents) |
|:---------|:--------------------------|:----------------------|
| Memory | `CustomerSupportMemory` | `EvalSupportMemory` |
| Gateway | `customersupport-gw` | `evalsupport-gw` |
| Runtime 에이전트 | `customer_support_agent` | `eval_support_agent` |
| SSM 접두사 | `/app/customersupport/agentcore/` | `/app/evalsupport/agentcore/` |
| IAM 역할 | `CustomerSupportAssistant...` | `EvalSupportAgentCoreRole-{region}` |
| Actor ID | `customer_001` | `eval_customer_001` |

> 💡 이 스크립트는 워크숍 사전 요구 사항에서 생성한 기존 Cognito 풀과 Lambda 함수를 **재사용**합니다. 이 리소스를 읽기만 하며 수정하지는 않습니다.

---

## 🚀 빠른 시작

```bash
# scripts 디렉터리로 이동
cd lab_helpers/lab5_evaluation/scripts/

# 1️⃣  모든 리소스 생성(Memory → Gateway → Runtime)
python lab5_evaluation_helper.py setup

# 2️⃣  단일 테스트 호출로 확인
python lab5_evaluation_helper.py test

# 3️⃣  평가 데이터 생성(기본값: 30분)
python lab5_evaluation_helper.py generate

# 4️⃣  완료 후 모든 평가 리소스 제거
python lab5_evaluation_helper.py cleanup
```

---

## 📋 명령어

### `setup`
다음 순서로 전체 스택을 프로비저닝합니다.
1. **에이전트 도구** — Strands Agents의 `@tool` 데코레이터(반품 정책, 제품 정보, KB 검색)
2. **AgentCore Memory** — 선호도 및 의미 체계 전략으로 `EvalSupportMemory` 생성
3. **AgentCore Gateway** — Lambda 대상을 사용하는 `evalsupport-gw` 생성
4. **AgentCore Runtime** — 컨테이너를 빌드하고 `eval_support_agent`를 배포한 후 READY 상태가 될 때까지 대기

⏱️ 약 10~15분 소요(컨테이너 빌드 및 배포)

### `test`
배포된 평가 에이전트에 단일 질의(`"What is the return policy for laptops?"`)를 보내고 응답을 출력합니다. 데이터를 생성하기 전에 이 명령어로 스택이 정상인지 확인하세요.

### `generate`
**서로 다른 고객 지원 프롬프트 30개**로 평가 에이전트를 30분 동안 반복 호출합니다(시간 변경 가능). 인증 오류가 발생하면 토큰을 자동으로 갱신합니다.

```bash
# 사용자 지정 기간
python lab5_evaluation_helper.py generate --duration 60   # 1시간
python lab5_evaluation_helper.py generate --duration 10   # 10분
```

### `cleanup`
평가 전용 리소스를 역순으로 모두 삭제합니다.
- Runtime 에이전트 → Gateway 대상 → Gateway → Memory → IAM 역할/정책 → SSM 파라미터
- 생성된 `eval_runtime_entrypoint.py` 파일도 삭제

---

## 📁 파일

```
lab5_evaluation/scripts/
├── lab5_evaluation_helper.py      # 기본 script(이 helper)
├── requirements.txt               # Python 의존성
├── README.md                      # 현재 파일
└── eval_runtime_entrypoint.py     # `setup`에서 자동 생성(gitignore 대상)
```

---

## ⚙️ 사전 요구 사항

- 워크숍 **사전 요구 사항 스택**이 배포되어 있어야 함(CloudFormation)
- 실습 **1~3**을 한 번 이상 실행한 상태여야 함(Cognito 풀, Lambda, KB가 존재)
- `requirements.txt`의 Python 패키지가 설치되어 있어야 함:

```bash
pip install -r requirements.txt
```

---

## 🔧 아키텍처

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│                  │     │                  │     │                  │
│  Eval Helper     │────▶│  AgentCore       │────▶│  Strands Agent   │
│  (this script)   │     │  Runtime         │     │  + MCP Gateway   │
│                  │     │                  │     │  + Memory        │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────────┐
                                                  │  Lambda Tools    │
                                                  │  (warranty,      │
                                                  │   web search)    │
                                                  └──────────────────┘
```

---

<div align="center">

*Amazon Bedrock AgentCore 워크숍의 실습 5 평가를 위해 제작*

</div>
