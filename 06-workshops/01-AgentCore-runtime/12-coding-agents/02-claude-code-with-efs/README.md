# EFS를 사용하는 AgentCore Runtime의 Claude Code

Claude Code를 AWS Bedrock AgentCore Runtime에 HTTP 에이전트로 배포하고, 세션 간 공유 영구 저장소를 위해 `/mnt/efs`에 EFS 파일 시스템을 mount합니다.

## 아키텍처

```
  ┌─────────────────────────┐         ┌─────────────────────────┐
  │  AgentCore Runtime      │         │  AgentCore Runtime      │
  │  Session A              │         │  Session B              │
  │  (Claude Code)          │         │  (Claude Code)          │
  │                         │         │                         │
  │  /mnt/efs ─────-────────┼────┐    │  /mnt/efs ─────-────────┼────┐
  └─────────────────────────┘    │    └─────────────────────────┘    │
                                 │                                   │
                                 ▼                                   ▼
                    ┌──────────────────────────────────────────────────┐
                    │  EFS File System (encrypted, generalPurpose)     │
                    │                                                  │
                    │  ┌────────────────────────┐                      │
                    │  │  EFS Access Point      │                      │
                    │  │  (uid/gid 1000,        │                      │
                    │  │   root /shared)        │                      │
                    │  └────────────────────────┘                      │
                    └──────────────────────────────────────────────────┘
```

여러 Runtime 세션이 동일한 EFS 파일 시스템을 mount하므로 에이전트는 독립적인 호출 간에 skill, 결과, 데이터를 공유할 수 있습니다.

```
CloudFormation 스택(cfn-vpc.yaml):
  VPC, subnet, NAT Gateway, Security Group
  EFS 파일 시스템, access point, mount target

deploy.py 생성 항목:
  IAM 실행 역할
  AgentCore Runtime(ECR의 컨테이너, /mnt/efs에 EFS mount)
```

## 사전 요구 사항

### Python 환경

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install boto3 awscli --force-reinstall --no-cache-dir
```

## 단계별 가이드

### 1단계 - 인프라 설정(CloudFormation)

설정 스크립트를 실행하여 CloudFormation stack(VPC, subnet, NAT Gateway, Security Group, EFS)을 배포한 다음 arm64 Docker 이미지를 빌드하여 ECR에 push합니다.

```bash
./setup.sh us-west-2
```

모든 출력은 `envvars.config`에 저장되며 다음 단계에서 자동으로 사용됩니다.

### 2단계 - 에이전트 배포

IAM 실행 역할과 AgentCore Runtime을 생성합니다.

```bash
python deploy.py
```

스크립트는 Runtime 상태가 `READY`가 될 때까지 기다린 다음 Runtime 구성을 `runtime_config.json`에 저장합니다.

Docker 이미지를 다시 빌드한 후처럼 기존 Runtime을 업데이트해야 하는 경우 다음을 실행합니다.

```bash
python update.py
```

### 3단계 - 에이전트 호출

배포된 에이전트에 prompt를 보냅니다. 첫 호출은 새 세션을 생성하며 이후 호출은 대화 연속성을 위해 세션 ID를 재사용할 수 있습니다.

**세션 A** - 영구 파일 시스템에 공유 skill 생성:

```bash
python invoke.py "can u create a new skill, to review python code? This skill should be created into /mnt/efs/skills/"
```

동일한 세션에서 대화를 계속합니다.

```bash
python invoke.py --session <session-a-id> "now add unit tests for that skill"
```

**세션 B** - 완전히 새로운 세션이 동일한 파일 시스템에 액세스하고 세션 A가 생성한 skill을 사용:

```bash
python invoke.py "list the skills available in /mnt/efs/skills/ and use the python review skill to review this code: def add(a,b): return a+b"
```

두 세션이 `/mnt/efs`를 공유하므로 한 세션에서 기록한 모든 내용을 다른 세션에서 즉시 사용할 수 있습니다.

### 4단계 - 실행 중인 세션에서 명령 실행

이전 단계의 세션 ID를 사용하여 컨테이너에서 shell 명령을 직접 실행합니다.

```bash
python exec_cmd.py --session <session-id> "ls -l /mnt/efs"
```

### 5단계 - 정리

모든 AgentCore 리소스(Runtime, IAM 역할)와 CloudFormation stack을 삭제합니다.

```bash
python cleanup.py
```

또는 shell wrapper를 사용합니다.

```bash
./cleanup.sh
```
