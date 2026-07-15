# AgentCore Runtime에 결제 에이전트 배포하기

## 개요

역할 분리와 관찰 가능성을 적용한 결제 지원 Strands 에이전트를 AgentCore Runtime에 배포합니다. 에이전트는 전용 실행 역할로 실행되며, 플러그인이 앱 백엔드에서 설정한 예산 범위 내에서 에이전트를 대신해 `ProcessPayment`를 호출합니다. 에이전트(LLM)는 `ProcessPayment`를 직접 호출하지 않습니다.

에이전트 코드는 상태 비저장이며 특정 지갑에 종속되지 않습니다. 모든 결제 컨텍스트(manager ARN, session ID, instrument ID)는 호출 페이로드에서 가져옵니다. 따라서 코드 변경 없이 동일한 배포 에이전트가 Coinbase CDP와 Stripe (Privy) 사용자를 모두 지원합니다.

### 학습 내용

| AgentCore payments 기능 | 이 튜토리얼에서 다루는 내용 |
|---------------------------|-------------------------------|
| 결제 처리 | 에이전트가 x402 엔드포인트를 호출하면 `AgentCorePaymentsPlugin`이 402를 자동 처리 |
| 결제 한도 | 앱 백엔드가 예산이 설정된 세션을 생성하고 서비스가 세션별 지출을 제한 |
| 결제 연결 | Tutorial 00의 PaymentManager + Connector 및 AgentCore Identity의 자격 증명 사용 |
| 결제 수단 | 호출 페이로드를 통해 에이전트에 embedded wallet 전달 |
| 관찰 가능성 | GenAI Observability Dashboard에서 Runtime trace 확인 |

### 튜토리얼 세부 정보

| 정보                 | 세부 정보                                                                    |
|:--------------------|:-----------------------------------------------------------------------------|
| 튜토리얼 유형        | 작업 기반                                                                    |
| 에이전트 유형        | 단일                                                                         |
| 에이전트 프레임워크  | Strands Agents                                                               |
| LLM 모델             | Anthropic Claude Sonnet                                                      |
| 튜토리얼 구성 요소   | AgentCore Runtime, AgentCorePaymentsPlugin, AgentCore CLI                    |
| 예제 난이도          | 중급                                                                         |
| 사용 SDK             | bedrock-agentcore SDK, Strands Agents SDK, AgentCore CLI (`@aws/agentcore`)  |

## 사전 요구 사항

* Tutorial 00 완료(`.env`에 manager ARN, connector, instrument가 있어야 함)
* Tutorial 01 완료(로컬 에이전트 + 플러그인 흐름 이해)
* https://faucet.circle.com/ 에서 테스트넷 USDC를 받아 지갑에 충전
* Python 3.10+
* Node.js 20+(AgentCore CLI용)
* [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) 설치
* AWS CLI 구성(`aws configure`)

이 튜토리얼은 Coinbase CDP 또는 Stripe (Privy) 중 어느 지갑 공급자에서도 동작합니다. 에이전트 코드는 동일하며 Tutorial 00에서 설정한 `.env` 값만 다릅니다.

> **테스트넷 전용.** 모든 코드는 [faucet.circle.com](https://faucet.circle.com/)에서 무료로 받은 USDC를 사용해 Base Sepolia에서 실행됩니다. 테스트넷 USDC는 실제 가치가 없습니다.

## 배포 흐름

```
agentcore create → agentcore dev → agentcore deploy → agentcore invoke
```

| 단계 | 명령어 | 수행 작업 |
|------|---------|-------------|
| CLI 설치 | `npm install -g @aws/agentcore` | AgentCore CLI 설치 |
| 프로젝트 생성 | `agentcore create --name PaymentAgent` | 프로젝트 구조 생성 |
| 로컬 테스트 | `agentcore dev` | :8080에서 로컬 개발 서버 시작 |
| 배포 | `agentcore deploy` | CDK를 통해 패키징하고 AWS에 배포 |
| 호출 | `agentcore invoke '{...}'` | 배포된 에이전트 호출 |
| 정리 | `agentcore remove all -y` | 모든 리소스 제거 |

## 아키텍처

```
App Backend (ManagementRole)              AgentCore Runtime (Execution Role)
  │                                        ┌──────────────────────────────┐
  │ create_session(budget=$0.50)           │  payment_agent.py            │
  │                                        │  BedrockAgentCoreApp         │
  │── invoke(manager_arn, session_id, ──►  │  + AgentCorePaymentsPlugin   │
  │         instrument_id, prompt)         │                              │
  │                                        │  Plugin calls: ProcessPayment│
  │◄── result ────────────────────────     │  Cannot: CreateSession       │
  │                                        │  Cannot: Override budget     │
  │ get_session(check spend)               └──────────────────────────────┘
```

## 파일 구조

```
02-deploy-to-agentcore-runtime/
├── deploy_payment_agent.ipynb    # 단계별 실습
├── payment_agent.py              # Agent 코드(BedrockAgentCoreApp + plugin)
├── requirements.txt              # Dependency(공유 wheel 참조)
├── README.md
└── images/
```

## 빠른 시작(Notebook을 사용하지 않는 경우)

```bash
# CLI 설치(Node.js 20+ 필요)
npm install -g @aws/agentcore

# 프로젝트 생성
agentcore create --name PaymentAgent --framework Strands --protocol HTTP --model-provider Bedrock --memory none

# 에이전트 코드와 종속성을 프로젝트에 복사
cp payment_agent.py PaymentAgent/app/PaymentAgent/main.py
cp -r deps PaymentAgent/app/PaymentAgent/deps/

# 로컬 테스트
cd PaymentAgent
agentcore dev
# 다른 터미널에서 실행: agentcore dev "Hello, what can you do?"

# AWS에 배포
agentcore deploy

# 호출
agentcore invoke '{"prompt": "...", "payment_manager_arn": "...", "user_id": "...", "payment_session_id": "...", "payment_instrument_id": "..."}'

# 정리
agentcore remove all -y
```

## 정리

> **비용 안내:** AgentCore Runtime 배포, 결제 세션 및 CloudWatch 관찰 가능성 기능을 사용하면 AWS 요금이 발생합니다.

AgentCore Runtime 배포에는 컴퓨팅 및 스토리지 요금이 발생합니다. 실습을 마치면 다음과 같이 제거하세요.

```bash
cd PaymentAgent && agentcore remove all -y
```

이 명령은 Runtime 배포, CloudWatch log group 및 관련 리소스를 제거합니다.

**결제 세션**: 이 튜토리얼에서 생성한 세션은 구성된 `expiryTimeInMinutes`(60분)가 지나면 자동으로 만료됩니다. 수동으로 정리할 필요가 없습니다.

## 마무리

이 튜토리얼에서는 역할을 적절히 분리해 결제 지원 Strands 에이전트를 AgentCore Runtime에 배포했습니다. 배포된 에이전트는 ProcessPaymentRole로 실행되며 앱 백엔드(ManagementRole)에서 설정한 예산 범위 내에서만 지출할 수 있습니다.
