# AgentCore 프로젝트

이 프로젝트는 [AgentCore CLI](https://github.com/aws/agentcore-cli)로 생성되었습니다.

## 프로젝트 구조

```
my-project/
├── AGENTS.md               # AI 코딩 어시스턴트 컨텍스트
├── agentcore/
│   ├── agentcore.json      # 프로젝트 구성(agents, memories, credentials, gateways, evaluators)
│   ├── aws-targets.json    # 배포 대상(account + region)
│   ├── .env.local          # 보안 정보 - API 키(gitignored)
│   ├── .llm-context/       # AI 어시스턴트용 TypeScript 타입 정의
│   │   ├── agentcore.ts    # AgentCoreProjectSpec 타입
│   │   ├── aws-targets.ts  # 배포 대상 타입
│   │   └── mcp.ts          # Gateway 및 MCP 도구 타입
│   └── cdk/                # CDK 인프라(@aws/agentcore-cdk)
├── app/                    # 에이전트 애플리케이션 코드
└── evaluators/             # 사용자 지정 evaluator 코드(있는 경우)
```

## 시작하기

### 사전 요구 사항

- **Node.js** 20.x 이상
- Python 에이전트용 **Python 3.10+** 및 **uv**([uv 설치](https://docs.astral.sh/uv/getting-started/installation/))
- 구성된 **AWS 자격 증명**(`aws configure` 또는 환경 변수)
- **Docker**(Container 빌드 에이전트에만 필요)

### 개발

에이전트를 로컬에서 실행합니다.

```bash
agentcore dev
```

### 배포

AWS에 배포합니다.

```bash
agentcore deploy
```

## 명령

| 명령 | 설명 |
| --- | --- |
| `agentcore create` | 새 AgentCore 프로젝트 생성 |
| `agentcore add` | 리소스(agent, memory, credential, gateway, evaluator, policy) 추가 |
| `agentcore remove` | 리소스 제거 |
| `agentcore dev` | hot reload를 사용하여 에이전트를 로컬에서 실행 |
| `agentcore deploy` | CDK를 통해 AWS에 배포 |
| `agentcore status` | 배포 상태 표시 |
| `agentcore invoke` | 로컬 또는 배포된 에이전트 호출 |
| `agentcore logs` | 에이전트 로그 보기 |
| `agentcore traces` | 에이전트 추적 보기 |
| `agentcore eval` | 평가 실행 |
| `agentcore package` | 에이전트 아티팩트 패키징 |
| `agentcore validate` | 구성 검증 |
| `agentcore pause` | 배포된 에이전트 일시 중지 |
| `agentcore resume` | 일시 중지된 에이전트 재개 |
| `agentcore fetch` | 원격 리소스 정의 가져오기 |
| `agentcore import` | 기존 리소스 가져오기 |
| `agentcore update` | CLI 업데이트 확인 |

## 구성

프로젝트를 구성하려면 `agentcore/`의 JSON 파일을 편집합니다. 타입 정의와 검증 제약 조건은 `agentcore/.llm-context/`를 참조하세요.

이 프로젝트는 **플랫 리소스 모델**을 사용합니다. agents, memories, credentials, gateways, evaluators, policies는 `agentcore.json`의 최상위 배열입니다. 리소스는 서로 독립적이며, 에이전트는 런타임에 환경 변수 또는 SDK 호출을 통해 memories와 credentials를 검색합니다.

## 리소스

| 리소스 | 용도 |
| --- | --- |
| Agent(runtime) | AgentCore Runtime에 배포되는 HTTP, MCP 또는 A2A 에이전트 |
| Memory | 구성 가능한 전략을 사용하는 영구 컨텍스트 스토리지 |
| Credential | API key 또는 OAuth credential provider |
| Gateway | 도구 호출을 대상으로 라우팅하는 MCP Gateway |
| Gateway Target | 도구 구현(Lambda, MCP server, OpenAPI, Smithy, API Gateway) |
| Evaluator | 사용자 지정 LLM-as-a-Judge 또는 코드 기반 평가 |
| Online Eval Config | 배포된 에이전트용 연속 평가 파이프라인 |
| Policy | Gateway 도구용 Cedar 권한 부여 정책 |

### 에이전트 유형

- **Template agents**: 프레임워크 템플릿(Strands, LangChain/LangGraph, GoogleADK, OpenAI Agents, Autogen)에서 생성
- **BYO agents**: `agentcore add agent --type byo`를 사용하여 자체 코드 제공
- **Import agents**: `agentcore import`를 사용하여 기존 Bedrock 에이전트 가져오기

### 빌드 유형

- **CodeZip**: Python 소스를 zip으로 패키징하여 AgentCore Runtime에 직접 배포
- **Container**: CodeBuild(ARM64)에서 Docker 이미지를 빌드하고 ECR로 푸시한 후 AgentCore Runtime에 배포

## 문서

- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
