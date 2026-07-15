# Amazon Bedrock AgentCore Runtime에서 AgentCore Browser를 사용하는 Embabel GOAP 에이전트 호스팅

## 개요

이 자습서에서는 AgentCore Browser로 웹 기반 주장을 검증하는 Embabel GOAP(Goal-Oriented Action Planning) 에이전트를 Amazon Bedrock AgentCore Runtime에서 호스팅하는 방법을 학습합니다.

이 자습서는 `@Agent`, `@Action`, `@AchievesGoal` annotation을 사용한 type 기반 목표 지향 계획이라는 Java 고유 패턴을 보여 줍니다. GOAP planner는 Blackboard에서 사용할 수 있는 type을 기준으로 action을 자동 연결합니다.

최소 구성의 Spring AI 에이전트는 [01-springai-with-bedrock-model](../01-springai-with-bedrock-model)을 참조하세요.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                                        |
|:--------------------|:-------------------------------------------------------------------------------------------------|
| 자습서 유형         | 여러 단계 pipeline                                                                              |
| 에이전트 유형       | 단일(GOAP 계획)                                                                                  |
| 에이전틱 프레임워크 | Embabel Agent Framework + Spring AI                                                              |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                                       |
| 자습서 구성 요소    | AgentCore Runtime, AgentCore Browser, Embabel GOAP 계획, Spring AI ChatClient                    |
| 자습서 분야         | 여러 산업 분야(사실 확인)                                                                       |
| 예제 난이도         | 중급                                                                                             |
| 사용 SDK            | spring-ai-agentcore-runtime-starter, spring-ai-agentcore-browser, embabel-agent-starter, AWS CDK |

### 라이브러리

이 자습서는 AgentCore Runtime 엔드포인트를 자동 구성하고 `@AgentCoreInvocation` annotation을 제공하며 브라우저 자동화용 `spring-ai-agentcore-browser` 모듈을 포함하는 Spring Boot starter인 [spring-ai-agentcore](https://github.com/spring-ai-community/spring-ai-agentcore) community library를 사용합니다.

### 자습서 주요 기능

* `@Agent`, `@Action`, `@AchievesGoal` annotation을 사용하는 Embabel GOAP 계획
* Typed Blackboard: planner가 자동 연결하는 4개의 POJO(`FactCheckRequest` → `ParsedClaims` → `VerifiedClaims` → `FactCheckReport`)
* 주장 검증 중 실제 웹 탐색을 위한 AgentCore Browser
* 브라우저 도구 호출을 위해 `browserToolCallbackProvider`를 사용하는 내부 `ChatClient`
* Wikipedia 및 공식 문서를 대상으로 하는 기본 데모 주장(bot 친화적이고 항상 검증 가능)

## 사전 요구 사항

* Java 21(Amazon Corretto 권장)
* Maven 3.9+
* Docker
* Node.js 18+ 및 npm(CDK용)
* 적절한 자격 증명으로 구성된 AWS CLI
* AWS CDK CLI (`npm install -g aws-cdk`)

## 프로젝트 구조

```
02-embabel-with-bedrock-model/
├── README.md
├── agent/
│   ├── pom.xml
│   ├── Dockerfile
│   ├── build-and-push.sh
│   └── src/main/
│       ├── java/com/example/agent/
│       │   ├── AgentApplication.java
│       │   ├── model/
│       │   │   ├── FactCheckRequest.java
│       │   │   ├── ParsedClaims.java
│       │   │   ├── VerifiedClaims.java
│       │   │   └── FactCheckReport.java
│       │   └── service/
│       │       └── FactCheckAgent.java
│       └── resources/application.yml
└── infra/
    ├── bin/app.ts
    ├── lib/agentcore-stack.ts
    ├── package.json
    ├── tsconfig.json
    └── cdk.json
```

## GOAP Pipeline 작동 방식

```
FactCheckRequest ──→ parseClaims() ──→ ParsedClaims
                                           │
                     verifyClaims() ◄──────┘
                          │
                     VerifiedClaims
                          │
                     summarize() ──→ FactCheckReport  ← @AchievesGoal
```

1. **parseClaims** - LLM이 사용자 입력에서 개별 검증 가능 주장을 추출
2. **verifyClaims** - 브라우저 도구가 포함된 내부 ChatClient가 실제 웹 페이지를 탐색하여 각 주장을 검증
3. **summarize** - LLM이 사람이 읽을 수 있는 보고서를 생성(최종 목표)

GOAP planner는 `parseClaims`가 `ParsedClaims`를 생성하고, `verifyClaims`가 `ParsedClaims`를 사용하여 `VerifiedClaims`를 생성하며, `summarize`가 `VerifiedClaims`를 사용하여 목표인 `FactCheckReport`를 생성한다는 것을 파악합니다. 그런 다음 이들을 자동으로 연결합니다.

## 단계별 배포

### 1. CDK 종속성 설치

```bash
cd infra
npm install
```

### 2. ECR repository 배포(최초 실행)

```bash
cdk deploy -c firstRun=true
```

### 3. Docker 이미지 빌드 및 push

```bash
cd ../agent
chmod +x build-and-push.sh
./build-and-push.sh -r us-east-1 -u <EcrRepositoryUri>
```

### 4. 전체 stack 배포

```bash
cd ../infra
cdk deploy
```

### 5. 에이전트 호출

```bash
RUNTIME_ARN=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreStack \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeArn`].OutputValue' \
  --output text)

aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "$RUNTIME_ARN" \
  --cli-binary-format raw-in-base64-out \
  --content-type "application/json" \
  --payload '{"claims": ["Amazon S3 was launched in 2006", "Spring Boot requires Java 17 or later"]}' \
  /dev/stdout
```

## 리소스

* [spring-ai-agentcore](https://github.com/spring-ai-community/spring-ai-agentcore) - 이 자습서에서 사용하는 `spring-ai-agentcore-browser` 모듈을 포함한 AgentCore Runtime 통합용 Spring Boot starter
* [Embabel Agent Framework(GitHub)](https://github.com/embabel/embabel-agent) - 빠른 시작 가이드, 구성 참조, 예제가 포함된 source code 및 wiki
* [Embabel Agent Framework(Docs)](https://docs.embabel.com/) - GOAP 계획, annotation, Blackboard 모델 등을 다루는 공식 사용자 가이드

## 정리

```bash
cd infra
cdk destroy
```
