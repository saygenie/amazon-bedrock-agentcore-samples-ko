# 시작하기 - Amazon Bedrock AgentCore의 TypeScript 에이전트

Node.js 22의 Direct Code Deploy를 사용하여 TypeScript 에이전트를 AgentCore Runtime에 배포합니다.

## 사전 요구 사항

| 요구 사항 | 버전 | 설치 |
|---|---|---|
| Node.js | 22.x | [nodejs.org](https://nodejs.org/) |
| AWS CLI | 2.x | [AWS CLI 설치 가이드](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| jq | latest | `brew install jq` / `apt install jq` |

### AWS 자격 증명 구성

```bash
aws configure
# 또는 환경 변수 설정:
# export AWS_ACCESS_KEY_ID=<your-key>
# export AWS_SECRET_ACCESS_KEY=<your-secret>
# export AWS_DEFAULT_REGION=us-west-2
```

자격 증명을 확인합니다.

```bash
aws sts get-caller-identity
```

---

## 프로젝트 구조

```
typescript/
├── app.ts               # 에이전트 진입점(Express 서버)
├── package.json          # Node.js 종속성
├── tsconfig.json         # TypeScript 구성
├── iam.sh                # IAM 역할 생성/삭제(bash + AWS CLI)
├── runtime.sh            # Runtime 생성, 조회, 목록, 대기, 호출, 삭제(bash + AWS CLI)
└── README.md
```

---

## 1단계: IAM 실행 역할 생성

AgentCore Runtime에서 에이전트를 실행하려면 IAM 역할이 필요합니다. `iam.sh` 스크립트는 필요한 권한(Bedrock 모델 호출, ECR pull, CloudWatch Logs, X-Ray, AgentCore 서비스)을 가진 `TypescriptExecutionRole` 역할을 생성합니다.

```bash
./iam.sh create
```

이 작업은 idempotent합니다. 역할이 이미 있으면 기존 ARN을 반환합니다. 출력을 저장하고 export합니다.

```bash
export ROLE_ARN=$(./iam.sh create)
echo $ROLE_ARN
```

---

## 2단계: 에이전트 Package 빌드

종속성을 설치하고 TypeScript와 모든 종속성을 단일 파일로 bundle한 다음 배포용 zip 파일을 생성합니다.

```bash
npm install

npm run build

cd dist
zip deployment_package.zip app.js
cd ..

```

`esbuild`를 사용하여 `app.ts`와 모든 종속성(Express, Strands Agents SDK, Zod, AWS SDK)을 단일 `dist/app.js`로 bundle합니다. Zip에는 `node_modules`가 필요하지 않습니다.

---

## 3단계: S3에 업로드

계정 ID와 리전을 설정한 다음 업로드합니다.

```bash
export BUCKET=$(your-bucket)

aws s3 cp dist/deployment_package.zip \
  s3://$BUCKET/typescript_deploy/deployment_package.zip
```

---

## 4단계: Direct Code Deploy로 배포

1단계에서 `ROLE_ARN`을 export했는지 확인한 다음 Runtime을 생성합니다.

```bash
export AWS_REGION="us-east-1"
# ROLE_ARN은 1단계에서 이미 export됨

./runtime.sh create
```

출력 예:

```json
{
  "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my_typescript_agent-XXXXXXX",
  "agentRuntimeId": "my_typescript_agent-XXXXXXX",
  "status": "CREATING"
}
```

다음 예제에서 참조할 에이전트 ARN을 export합니다.

```bash
export AGENT_ARN="arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my_typescript_agent-XXXXXXX"
export AGENT_ID="my_typescript_agent-XXXXXXX"
```


Runtime이 `READY` 상태가 될 때까지 기다립니다(10초마다 polling).

```bash
./runtime.sh wait $AGENT_ID
```

---

## 5단계: 검증 및 호출

### Runtime 목록 조회

```bash
./runtime.sh list
```

### Runtime 세부 정보 조회

```bash
./runtime.sh get $AGENT_ID
```

### 에이전트 호출

Runtime 상태가 `READY`가 되면 다음 명령을 실행합니다.

```bash
./runtime.sh invoke $AGENT_ARN

# 사용자 지정 prompt 사용:
./runtime.sh invoke $AGENT_ARN "what is your status?"
```

---

## 6단계: 정리

작업이 끝나면 Runtime, IAM 역할, S3 artifact를 삭제합니다.

```bash
# Runtime 삭제
./runtime.sh delete <agentRuntimeId>

# IAM 역할 삭제
./iam.sh delete

# S3 artifact 제거
aws s3 rm s3://bedrock-agentcore-code-${ACCOUNT_ID}-${REGION}/typescript_deploy/deployment_package.zip
```

---

## 작동 방식

### 에이전트 코드(`app.ts`)

에이전트는 **calculator tool**과 [Strands Agents SDK](https://strandsagents.com/)를 사용하는 Express 서버입니다. Strands 에이전트는 Amazon Bedrock(Claude Haiku 4.5)을 LLM으로 사용하며 native tool-calling을 통해 도구를 호출할 수 있습니다.

| Endpoint | Method | 용도 |
|---|---|---|
| `/ping` | GET | 상태 확인. AgentCore가 에이전트 실행 여부를 검증할 때 사용 |
| `/invocations` | POST | Prompt를 받고 도구를 사용하는 Strands 에이전트를 실행한 뒤 응답 반환 |

AgentCore Runtime은 서버가 포트 **8080**에서 수신할 것으로 예상합니다.

#### Calculator Tool

에이전트에는 `add`, `subtract`, `multiply`, `divide`를 지원하는 `calculator` 도구가 있습니다. 수학 질문을 보내면 LLM이 도구 호출 여부를 판단하고 결과를 반환합니다.

```bash
./runtime.sh invoke $AGENT_ARN "What is 25 * 4 + 10?"
```

### Direct Code Deploy

Direct Code Deploy를 사용하면 컨테이너 이미지를 빌드하는 대신 source code를 zip으로 S3에 업로드할 수 있습니다. AgentCore가 빌드 및 Runtime 환경을 처리합니다. 배포 payload는 다음과 같이 지정합니다.

```json
{
  "agentRuntimeArtifact": {
    "codeConfiguration": {
      "code": {
        "s3": {
          "bucket": "bedrock-agentcore-code-<ACCOUNT_ID>-<REGION>",
          "prefix": "typescript_deploy/deployment_package.zip"
        }
      },
      "runtime": "NODE_22",
      "entryPoint": ["app.js"]
    }
  }
}
```

### IAM 역할

실행 역할은 에이전트에 다음 권한을 부여합니다.
- Bedrock 모델 호출(`bedrock:InvokeModel`)
- ECR에서 컨테이너 이미지 pull
- CloudWatch에 log 기록
- X-Ray로 trace 전송
- AgentCore 서비스 액세스(Memory, Browser, Gateway, CodeInterpreter)
