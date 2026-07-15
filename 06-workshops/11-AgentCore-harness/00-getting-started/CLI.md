# AgentCore CLI 시작하기

[AgentCore CLI](https://github.com/aws/agentcore-cli/)를 사용하면 최소한의 구성으로 에이전트를 생성하고 로컬에서 개발한 후 AgentCore에 배포할 수 있습니다.

## 사전 요구 사항

시작하려면 다음 항목이 필요합니다.

- Node.js 20.x 이상
- Python 에이전트용 uv([설치](https://docs.astral.sh/uv/getting-started/installation/))

그런 다음 **AgentCore CLI를 설치**합니다.

```Bash
npm i -g @aws/agentcore@preview

# 확인
agentcore --version
```

## Bedrock 모델 공급자로 에이전트 생성 및 호출

이 단계별 튜토리얼에서는 Bedrock 모델 공급자를 사용하는 간단한 에이전트를 생성합니다.

프로젝트를 생성합니다.

```bash
agentcore create --name HarnessBedrock --memory "none" --model-provider bedrock

```

프로젝트를 배포합니다.
```bash
cd HarnessBedrock

agentcore deploy
```

배포 후 `invoke` 명령으로 테스트할 수 있습니다.
```bash
agentcore invoke --harness HarnessBedrock "What is 2+2?"

```

## OpenAI 모델 공급자로 에이전트 생성 및 호출

이 단계별 튜토리얼에서는 OpenAI 모델 공급자를 사용하는 간단한 에이전트를 생성합니다.

먼저 OpenAI API Key를 저장할 Secret을 AWS Secrets Manager에 생성합니다.

```bash
SECRET_ARN=$(aws secretsmanager create-secret \
    --name "openai-api-key" \
    --description "OpenAI API Key" \
    --secret-string "sk-your-api-key-here" \
    --query 'ARN' \
    --output text)


```

프로젝트를 생성합니다.

```bash

agentcore create --name HarnessOpenAI --memory "none" --model-provider OpenAI --api-key-arn $SECRET_ARN

```

프로젝트를 배포합니다.
```bash

cd HarnessOpenAI

agentcore deploy
```

배포 후 `invoke` 명령으로 테스트할 수 있습니다.
```bash

agentcore invoke --harness HarnessOpenAI "Who are you? and what is 2+2?"

```
