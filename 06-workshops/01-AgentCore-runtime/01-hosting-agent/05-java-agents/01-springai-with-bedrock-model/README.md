# Amazon Bedrock AgentCore Runtime에서 Amazon Bedrock 모델을 사용하는 Spring AI 에이전트 호스팅

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime에서 Java/Spring AI 에이전트를 호스팅하는 방법을 학습합니다.

Python [Strands with Bedrock model](../../01-strands-with-bedrock-model) 자습서의 Java 버전입니다.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                                |
|:--------------------|:-----------------------------------------------------------------------------------------|
| 자습서 유형         | 도구 호스팅                                                                              |
| 에이전트 유형       | 단일                                                                                     |
| 에이전틱 프레임워크 | Spring AI                                                                                |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                               |
| 자습서 구성 요소    | AgentCore Runtime에서 에이전트 호스팅, Spring AI ChatClient 및 Amazon Bedrock 모델 사용 |
| 자습서 분야         | 여러 산업 분야                                                                           |
| 예제 난이도         | 쉬움                                                                                     |
| 사용 SDK            | spring-ai-agentcore-runtime-starter(Java) 및 AWS CDK                                     |

### 라이브러리

이 자습서는 AgentCore Runtime 엔드포인트를 자동 구성하고 `@AgentCoreInvocation` annotation을 제공하는 Spring Boot starter인 [spring-ai-agentcore](https://github.com/spring-ai-community/spring-ai-agentcore) community library를 사용합니다.

### 자습서 주요 기능

* AgentCore samples repository의 첫 Java 기반 자습서
* Amazon Bedrock AgentCore Runtime에서 Spring Boot 에이전트 호스팅
* Amazon Bedrock 모델과 Spring AI `ChatClient` 사용
* Python의 `@app.entrypoint`에 해당하는 Java `@AgentCoreInvocation` annotation
* Corretto 21 Docker 이미지
* `CfnRuntime` L1 construct를 사용하는 CDK 인프라

## 사전 요구 사항

* Java 21(Amazon Corretto 권장)
* Maven 3.9+
* Docker
* Node.js 18+ 및 npm(CDK용)
* 적절한 자격 증명으로 구성된 AWS CLI
* AWS CDK CLI (`npm install -g aws-cdk`)

## 프로젝트 구조

```
01-springai-with-bedrock-model/
├── README.md
├── agent/
│   ├── pom.xml
│   ├── Dockerfile
│   ├── build-and-push.sh
│   └── src/main/
│       ├── java/com/example/agent/AgentApplication.java
│       └── resources/application.yml
└── infra/
    ├── bin/app.ts
    ├── lib/agentcore-stack.ts
    ├── package.json
    ├── tsconfig.json
    └── cdk.json
```

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

출력의 `EcrRepositoryUri`를 기록해 두세요.

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
  --payload '{"message": "What is Amazon Bedrock AgentCore?"}' \
  /dev/stdout
```

## 작동 방식

에이전트는 하나의 class로 구성된 단일 Spring Boot 애플리케이션입니다.

1. `AgentApplication` - Spring을 시작하고 `ConversationalAgent` 내부 서비스를 정의
2. `@AgentCoreInvocation` - `chat()` method를 AgentCore Runtime 진입점으로 표시
3. `spring-ai-agentcore-runtime-starter` - `/invoke` 및 `/ping` 엔드포인트 자동 구성

CDK stack은 다음 항목을 프로비저닝합니다.
- 컨테이너 이미지용 ECR repository
- Bedrock InvokeModel 및 CloudWatch Logs 권한이 있는 IAM 역할
- ECR 이미지를 가리키는 `CfnRuntime` 리소스

## 정리

```bash
cd infra
cdk destroy
```
