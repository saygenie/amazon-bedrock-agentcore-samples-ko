# Amazon Bedrock AgentCore의 TypeScript MCP Server

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime 환경을 사용하여 TypeScript 기반 MCP(Model Context Protocol) 서버를 호스팅하는 방법을 보여 줍니다.


### 자습서 세부 정보

| 정보                | 세부 정보                                                 |
|:--------------------|:----------------------------------------------------------|
| 자습서 유형         | TypeScript MCP 서버 호스팅                                |
| 도구 유형           | MCP 서버                                                  |
| 자습서 구성 요소    | AgentCore Runtime에서 TypeScript MCP 서버 호스팅          |
| 자습서 분야         | 여러 산업 분야                                            |
| 예제 난이도         | 쉬움                                                      |
| 사용 SDK            | Anthropic의 TypeScript SDK for MCP                        |

## 사전 요구 사항

- Node.js v22 이상
- Docker(컨테이너화)
- Docker 이미지를 저장할 Amazon ECR(Elastic Container Registry)
- Amazon Bedrock AgentCore에 액세스할 수 있는 AWS 계정

---

## AgentCore Runtime 서비스 계약

[공식 서비스 계약 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html)를 참조하세요.

**Runtime 구성:**
- **Host:** `0.0.0.0`
- **Port:** `8000`
- **Transport:** Stateless `streamable-http`
- **Endpoint Path:** `POST /mcp`

## 로컬 개발

1. 종속성 설치

```
npm install
```

2. AWS 자격 증명 설정
```
aws configure
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
```

3. 서버 시작
```
npm run start
```

4. [MCP inspector](https://github.com/modelcontextprotocol/inspector)를 사용하여 로컬에서 테스트

```
npx @modelcontextprotocol/inspector
```

## Docker 배포

1. ECR Repository 생성
```
aws ecr create-repository --repository-name mcp-server --region us-east-1
```
2. 이미지를 빌드하여 ECR에 push
```
# 로그인 token 가져오기
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin [account-id].dkr.ecr.us-east-1.amazonaws.com

docker buildx --platform linux/arm64 \
  -t [account-id].dkr.ecr.us-east-1.amazonaws.com/mcp-server:latest --push .
```

3. Bedrock AgentCore에 배포

    - AWS Console에서 Bedrock → AgentCore → Create Agent로 이동
    - Protocol로 MCP 선택
    - Agent Runtime 구성:
        - Image URI: [account-id].dkr.ecr.us-east-1.amazonaws.com/mcp-server:latest
        - Bedrock 모델 액세스를 위한 IAM Permissions 설정
        - Agent Sandbox에서 배포 및 테스트


4. Encoding된 ARN MCP URL 구성

```
echo "agent_arn" | sed 's/:/%3A/g; s/\//%2F/g'
```

```
https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT
```

5. [MCP inspector](https://github.com/modelcontextprotocol/inspector)에서 MCP URL을 사용합니다.

## 참고 자료
- https://aws.amazon.com/bedrock/agentcore/
- https://github.com/modelcontextprotocol/typescript-sdk
- https://github.com/modelcontextprotocol/inspector

