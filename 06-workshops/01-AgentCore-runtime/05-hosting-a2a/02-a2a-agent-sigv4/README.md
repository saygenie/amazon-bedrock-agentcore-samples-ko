# IAM 인증을 사용하는 AgentCore A2A 샘플

이 샘플은 AWS IAM을 inbound 인증에 사용하여 A2A(Agent-to-Agent) 에이전트를 Amazon Bedrock AgentCore Runtime에 배포하는 방법을 보여 줍니다. A2A 프로토콜과 IAM 기반 인증을 결합하여 AWS 자격 증명으로 통신하는 에이전트를 안전하게 배포합니다.

## 아키텍처

```
┌─────────────┐         IAM Auth          ┌──────────────────┐
│   Client    │ ────────────────────────> │  A2A Agent       │
│  (SigV4)    │                           │  (AgentCore)     │
└─────────────┘                           └──────────────────┘
```

## 주요 기능

* 에이전트 간 통신을 위한 A2A 프로토콜
* AWS IAM(SigV4) 인증
* 에이전트 구현을 위한 Strands 프레임워크
* AgentCore Runtime에 배포

## 사전 요구 사항

* Python 3.10+
* 자격 증명으로 구성된 AWS CLI
* Docker 실행
* pip 설치

## 설치

```bash
pip install -r requirements.txt
```

## 빠른 시작

### 옵션 1: Jupyter Notebook 사용(권장)

```bash
jupyter notebook hosting_a2a_iam_auth.ipynb
```

Notebook의 단계별 지침을 따르세요.

### 옵션 2: 수동 배포

#### 1단계: 로컬 테스트(선택 사항)

```bash
# Terminal 1: 에이전트 시작
python agent.py

# Terminal 2: Agent card 테스트
curl http://localhost:9000/.well-known/agent-card.json | jq .

# Terminal 2: 테스트 message 전송
curl -X POST http://localhost:9000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-001",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{
          "kind": "text",
          "text": "Hello! What can you do?"
        }],
        "messageId": "test-001"
      }
    }
  }' | jq .
```

#### 2단계: AgentCore Runtime에 배포

```bash
python deploy.py
```

스크립트는 다음 작업을 수행합니다.
1. Docker 이미지를 빌드하여 ECR에 push
2. 필요한 권한이 있는 실행 역할 생성
3. 에이전트를 AgentCore Runtime에 배포
4. 에이전트 ARN 출력

#### 3단계: 배포된 에이전트 테스트

```bash
# 배포 출력의 에이전트 ARN 설정
export AGENT_ARN="arn:aws:bedrock-agentcore:us-east-1:..."

# 테스트 클라이언트 실행
python client.py
```

## 예상 출력

```
INFO:__main__:Using AWS region: us-east-1
INFO:__main__:Testing agent: arn:aws:bedrock-agentcore:...
INFO:__main__:Session ID: ...
INFO:__main__:Fetching agent card...
INFO:__main__:Agent: A2A IAM Auth Agent
INFO:__main__:Description: A simple A2A agent demonstrating IAM authentication...

============================================================
INFO:__main__:Sending message: Hello! What can you do?

INFO:__main__:Agent response:
I am an A2A agent deployed on Amazon Bedrock AgentCore Runtime...
```

## 문제 해결

### Docker가 실행되지 않음

```
Error: Cannot connect to the Docker daemon
Solution: Start Docker Desktop or Docker daemon
```

### AWS 자격 증명이 구성되지 않음

```
Error: Unable to locate credentials
Solution: Run 'aws configure' or set AWS_PROFILE
```

### 권한 오류

배포에는 다음 IAM 권한이 필요합니다.
- `bedrock-agentcore:*` - AgentCore 작업
- `ecr:*` - Container registry
- `iam:CreateRole`, `iam:PutRolePolicy` - 실행 역할 생성
- `codebuild:*` - 컨테이너 이미지 빌드
- `logs:*` - CloudWatch log 액세스

실행 역할에는 다음 권한이 필요합니다.
- `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` - ECR 액세스
- `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` - Bedrock 모델 액세스
- `logs:*` - CloudWatch log
- `bedrock-agentcore:GetWorkloadAccessToken*` - Workload identity

전체 실행 역할 정책은 `execution-role-policy.json`을 참조하세요.

## 정리

```python
from bedrock_agentcore_starter_toolkit.operations.runtime import destroy_bedrock_agentcore
from pathlib import Path

destroy_bedrock_agentcore(
    config_path=Path(".bedrock-agentcore-config.yaml"),
    region="us-east-1"
)
```

## 파일

* `agent.py` - 도구가 포함된 A2A 에이전트 구현
* `client.py` - IAM 인증으로 배포된 에이전트를 테스트하는 클라이언트
* `deploy.py` - 배포 스크립트
* `requirements.txt` - Python 종속성
* `execution-role-policy.json` - 실행 역할의 IAM 정책
* `hosting_a2a_iam_auth.ipynb` - 단계별 자습서 Notebook

## 참고 자료

* [AgentCore Runtime 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
* [A2A Protocol 사양](https://a2a-protocol.org/dev/specification/)
* [Strands Agents 프레임워크](https://strandsagents.com/latest/)
