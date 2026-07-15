# KVS를 사용하는 최소 WebRTC 음성 에이전트

AWS Nova Sonic을 사용한 WebRTC 오디오 스트리밍을 보여 주는 최소 예제입니다.

## 프로젝트 구조

```
agent/
  bot.py              - FastAPI 서버, WebRTC offer/answer, ICE 처리
  kvs.py              - KVS signaling channel 및 TURN server helper
  audio.py            - 오디오 resampling(av) 및 WebRTC 출력 track(av.AudioFifo)
  nova_sonic.py       - Nova Sonic 양방향 스트리밍 세션
  requirements.txt
  Dockerfile
  .env.example
server/
  index.html          - 브라우저 클라이언트(WebRTC + 선택적 AgentCore Runtime)
  server.py           - 정적 파일 서버
  requirements.txt
kvs-iam-policy.json     - KVS용 최소 IAM 정책
bedrock-iam-policy.json - Nova Sonic용 최소 IAM 정책
```

## 요구 사항

- **Python 3.12+**(aws-sdk-bedrock-runtime에 필요)
- AWS 자격 증명 구성
- AgentCore Runtime 배포용 **인터넷 egress가 있는 VPC**(아래 설정 참조)

## AgentCore Runtime용 VPC 설정

에이전트가 WebRTC 연결을 위해 KVS TURN server에 도달하려면 인터넷 egress가 필요합니다. NAT gateway에 액세스할 수 있는 private subnet이 포함된 VPC가 이미 있다면 [AgentCore Runtime에 배포](#agentcore-runtime에-배포)로 이동하세요.

### 1. Public 및 private subnet이 있는 VPC 생성

1. [VPC console](https://console.aws.amazon.com/vpc/) 열기
2. **Create VPC** 클릭
3. **VPC and more** 선택
4. 이름 설정(예: `webrtc-bot-example`)
5. 기본 CIDR(`10.0.0.0/16`) 유지
6. **Number of Availability Zones**를 **1**로 설정
7. **Number of public subnets**를 **1**로 설정
8. **Number of private subnets**를 **1**로 설정
9. **NAT gateways**를 **In 1 AZ**로 설정
10. **Create VPC** 클릭

### 2. ID 기록

VPC console에서 다음 항목을 복사합니다.
- **Private subnet ID**(예: `subnet-0123456789abcdef0`) - 에이전트가 실행되는 위치
- **Security group ID** - VPC와 함께 생성된 기본 security group(예: `sg-0123456789abcdef0`)

아래 `agentcore configure` 단계에서 이 값을 사용합니다.

## 로컬 설정

### 1. 에이전트

```bash
cd agent
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # AWS 자격 증명으로 편집
python bot.py          # http://localhost:8080
```

### 2. 서버

```bash
cd server
pip install -r requirements.txt
python server.py       # http://localhost:7860
```

### 3. 테스트

`http://localhost:7860`을 열고 "Connect"를 클릭합니다.

## AgentCore Runtime에 배포

### 1. Starter toolkit 설치

```bash
pip install bedrock-agentcore-starter-toolkit
```

### 2. 구성

`agent/` 디렉터리에서 다음 명령을 실행합니다.

```bash
cd agent

export SUBNET_IDS=subnet-0123456789abcdef0  # private subnet(인터넷 egress용 NAT gateway 포함)
export SECURITY_GROUP_ID=sg-0123456789abcdef0

agentcore configure \
  -e bot.py \
  --deployment-type container \
  --disable-memory \
  --vpc \
  --subnets $SUBNET_IDS \
  --security-groups $SECURITY_GROUP_ID \
  --non-interactive
```

PUBLIC network mode는 outbound UDP 연결을 지원하지 않으므로 VPC network mode가 필요합니다.

### 3. 배포

```bash
agentcore deploy --env KVS_CHANNEL_NAME=voice-agent-minimal --env AWS_REGION=us-west-2
```

CodeBuild를 통해 ARM64 컨테이너를 빌드하고 로컬 Docker 없이 AgentCore Runtime에 배포합니다. 출력의 ARN을 기록해 두세요.

### 4. IAM 권한 연결

Toolkit에서 생성한 실행 역할에는 KVS 및 Bedrock 권한이 필요합니다. 먼저 `kvs-iam-policy.json`과 `bedrock-iam-policy.json`의 `ACCOUNT_ID`를 AWS 계정 ID로 업데이트합니다. 그런 다음 `ROLE_NAME`을 배포 출력의 역할 이름으로 교체합니다(예: `AmazonBedrockAgentCoreSDKRuntime-us-west-2-9d74932bdb`).

```bash
ROLE_NAME=ROLE_HERE

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name kvs-access \
  --policy-document file://kvs-iam-policy.json

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name bedrock-nova-sonic \
  --policy-document file://bedrock-iam-policy.json
```

### 5. 테스트

`http://localhost:7860`의 브라우저 클라이언트에 `agentcore deploy`에서 출력된 에이전트 ARN과 AWS 자격 증명을 입력한 다음 Connect를 클릭합니다. 연결된 후 마이크에 말하면 에이전트가 실시간 음성으로 응답합니다.

### 정리

```bash
agentcore destroy
```

## 작동 방식

### 오디오 흐름

**Browser → Nova Sonic:**
1. WebRTC가 마이크 오디오 capture
2. 에이전트의 `aiortc`가 오디오 frame 수신
3. `av.AudioResampler`가 16kHz/16-bit/mono PCM으로 변환
4. Base64로 encoding하여 Nova Sonic에 스트리밍

**Nova Sonic → Browser:**
1. 에이전트가 Nova Sonic에서 오디오 chunk 수신
2. Raw PCM byte를 `av.AudioFifo`에 buffering
3. `OutputTrack`이 고정 크기 20ms frame을 WebRTC에 제공
4. 브라우저가 `<audio>` 요소를 통해 오디오 재생

### 오디오 구성

| 매개변수 | 값 |
|-----------|-------|
| 입력 Sample Rate | 16kHz |
| 출력 Sample Rate | 24kHz |
| 형식 | 16-bit PCM mono |
| Model | amazon.nova-2-sonic-v1:0 |
| Voice | matthew |

## 주요 종속성

| Package | 용도 |
|---------|---------|
| `aws-sdk-bedrock-runtime` | Nova Sonic 스트리밍(Python 3.12+ 필요) |
| `aiortc` | WebRTC peer 연결 |
| `av` | 오디오 resampling 및 frame buffering(FFmpeg) |
| `boto3` | KVS signaling channel 및 TURN server |
| `fastapi` / `uvicorn` | HTTP 서버 |

## IAM 권한

에이전트가 TURN server에 액세스하려면 KVS 권한이 필요합니다. 최소 정책은 `kvs-iam-policy.json`을 참조하고 `ACCOUNT_ID`를 AWS 계정 ID로 교체하세요.

또한 에이전트에는 Nova Sonic 모델을 위한 `bedrock:InvokeModelWithBidirectionalStream` 권한이 필요합니다.

## 문제 해결

**Python version 오류**(`Could not find aws-sdk-bedrock-runtime`):
Python 3.12+를 사용하세요.

**오디오가 작동하지 않음:**
- 브라우저의 마이크 권한 확인
- AWS 자격 증명에 Bedrock 액세스가 있는지 검증
- 상세 logging을 위해 `-v`로 에이전트 실행

**연결 실패:**
- 에이전트와 서버가 모두 실행 중인지 확인
- KVS IAM 권한 확인
- TURN server 연결 검증

## 참고 자료

기반 예제: https://github.com/aws-samples/sample-nova-sonic-speech2speech-webrtc
