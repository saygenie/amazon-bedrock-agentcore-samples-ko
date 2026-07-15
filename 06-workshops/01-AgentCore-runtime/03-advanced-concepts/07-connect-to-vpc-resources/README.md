# VPC Fargate Agent Runtime CDK 스택

이 CDK stack은 AWS Bedrock AgentCore Runtime과 함께 VPC에 Fargate 컨테이너를 배포합니다. 컨테이너는 두 개의 HTTP 엔드포인트를 제공합니다.

- `POST /invocations` - 요청 처리를 위한 기본 엔드포인트
- `GET /ping` - 상태 확인 엔드포인트

## 아키텍처

Stack은 다음 항목을 생성합니다.

- 2개 Availability Zone에 public 및 private subnet이 있는 **VPC**
- Private subnet의 인터넷 액세스를 위한 **NAT Gateway**
- VPC 내에서 포트 8080의 inbound traffic을 허용하는 **Security Group**
- CDK가 자동으로 빌드하고 ECR에 push하는 **Docker Image**(ARM64/Graviton)
- Private subnet에서 컨테이너를 실행하는 **AgentCore Runtime**
- AgentCore 작업에 필요한 권한이 있는 **IAM Role**

## 사전 요구 사항

1. 적절한 자격 증명으로 구성된 **AWS CLI**
2. **Node.js** 및 **npm** 설치
3. **Docker** 설치 및 실행(컨테이너 이미지 빌드에 필요)
4. 계정/리전에 **AWS CDK** bootstrap:
   ```bash
   npx cdk bootstrap
   ```

## 프로젝트 구조

```
07-connect-to-vpc-resources/
├── bin/
│   └── app.ts              # CDK 앱 진입점
├── lib/
│   └── vpc-fargate-stack.ts # 기본 stack 정의
├── agent-code/
│   ├── app.py              # /ping 및 /invocations가 포함된 Flask 애플리케이션
│   ├── Dockerfile          # 컨테이너 정의
│   └── requirements.txt    # Python 종속성
├── package.json            # NPM 종속성
├── tsconfig.json           # TypeScript 구성
└── cdk.json                # CDK 구성
```

## 설치

1. NPM 종속성 설치:

   ```bash
   npm install
   ```

2. TypeScript 코드 빌드:
   ```bash
   npm run build
   ```

## 배포

### Stack 배포

```bash
npm run deploy
```

이 명령은 다음 작업을 수행합니다.

1. TypeScript CDK 코드 빌드
2. ARM64(Graviton)용 Docker 이미지 빌드
3. 이미지를 ECR에 push
4. VPC, security group, networking 생성
5. 컨테이너와 함께 AgentCore Runtime 배포

### 합성된 CloudFormation Template 보기

```bash
npm run synth
```

### 차이점 표시

배포 전에 적용될 변경 사항을 확인하려면 다음 명령을 실행합니다.

```bash
npx cdk diff
```

## Stack 출력

배포 후 stack은 다음 출력을 제공합니다.

- **VpcId** - 생성된 VPC의 ID
- **SecurityGroupId** - Security group의 ID
- **AgentRuntimeId** - AgentCore Runtime의 ID
- **AgentRuntimeArn** - AgentCore Runtime의 ARN
- **AgentRoleArn** - 실행 역할의 ARN
- **DockerImageUri** - ECR의 Docker 이미지 URI
- **ECRRepositoryName** - ECR repository 이름

## 애플리케이션 테스트

### 로컬 테스트

배포하기 전에 Flask 애플리케이션을 로컬에서 테스트할 수 있습니다.

```bash
cd agent-code
python app.py
```

그런 다음 다른 terminal에서 다음 명령을 실행합니다.

```bash
# Ping 엔드포인트 테스트
curl http://localhost:8080/ping

# Invocations 엔드포인트 테스트
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### AWS에서 테스트

배포 후 컨테이너는 private subnet에서 실행되므로 인터넷에서 직접 액세스할 수 없습니다. 다음 중 하나가 필요합니다.

1. Private subnet에 액세스하도록 VPN 또는 bastion host 설정
2. AWS PrivateLink 또는 API Gateway를 사용하여 서비스 노출
3. Runtime을 호출하도록 AgentCore 구성

## 컨테이너 세부 정보

컨테이너는 다음과 같이 구성됩니다.

- 더 나은 성능과 비용 효율성을 위해 **ARM64** 아키텍처(Graviton)에서 실행
- 포트 **8080** 노출
- Non-root 사용자(`bedrock_agentcore`)로 실행
- `/ping` 엔드포인트에 상태 확인 포함
- Flask와 Python 3.11 사용

## 정리

이 stack에서 생성한 모든 리소스를 삭제하려면 다음 명령을 실행합니다.

```bash
npm run destroy
```

**참고:** VPC, 모든 이미지가 포함된 ECR repository, 관련 리소스가 모두 삭제됩니다.

## 매개변수

Stack은 배포 시 다음 매개변수를 받습니다.

- **AgentName**(기본값: `VpcFargateAgent`) - Agent Runtime 이름

배포 중 매개변수를 설정하려면 다음 명령을 사용합니다.

```bash
npx cdk deploy --parameters AgentName=MyCustomAgent
```

## 사용자 지정

### 애플리케이션 수정

`agent-code/app.py`를 편집하여 애플리케이션 로직을 사용자 지정할 수 있습니다. 현재 구현은 다음 기능을 제공하는 간단한 Flask 앱입니다.

- `GET /ping`에서 상태 반환
- `POST /invocations`에서 수신 데이터 echo

### 인프라 수정

`lib/vpc-fargate-stack.ts`를 편집하여 다음 항목을 변경할 수 있습니다.

- VPC CIDR 범위 변경
- Availability Zone 수 조정
- Security group rule 수정
- 추가 AWS 리소스 생성

### Python 종속성 변경

`agent-code/requirements.txt`를 편집하여 Python package를 추가하거나 업데이트합니다.

## 문제 해결

### Docker 빌드 실패

Docker가 실행 중인지 확인합니다.

```bash
docker ps
```

### CDK Bootstrap 필요

Bootstrapping 관련 오류가 표시되면 다음 명령을 실행합니다.

```bash
npx cdk bootstrap
```

### 권한 오류

AWS 자격 증명에 다음 작업을 수행할 충분한 권한이 있는지 확인합니다.

- VPC 및 networking 리소스 생성
- ECR repository 생성 및 이미지 push
- IAM 역할 및 정책 생성
- BedrockAgentCore 리소스 생성

## 비용 고려 사항

이 stack은 비용이 발생하는 다음 리소스를 생성합니다.

- **NAT Gateway** - 시간당 요금 + 데이터 처리 비용
- **ECR** - Docker 이미지 저장 비용
- **Fargate** - Runtime 활성 상태에서 vCPU 및 memory 비용
- **VPC 리소스** - 데이터 전송 비용

## 보안

- 컨테이너는 인터넷에 직접 액세스할 수 없는 **private subnet**에서 실행
- 종속성 pull을 위해 NAT Gateway를 통한 outbound 인터넷 액세스 사용
- Security group은 VPC 내부에서 포트 8080으로 들어오는 traffic만 허용
- 컨테이너를 non-root 사용자로 실행
- IAM 역할에 최소 권한 원칙 적용

## 추가 리소스

- [AWS CDK 문서](https://docs.aws.amazon.com/cdk/)
- [Amazon Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock/)
- [AWS Fargate 문서](https://docs.aws.amazon.com/fargate/)
