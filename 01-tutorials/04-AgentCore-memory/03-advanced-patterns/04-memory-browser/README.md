# AgentCore 메모리 대시보드

AWS Bedrock AgentCore 메모리 데이터를 탐색하기 위한 경량 React + FastAPI 대시보드입니다.

**저장소 크기**: ~2MB (종속성 제외 - 아래 설정 안내 참조)

## 주요 기능

- **동적 구성**: UI를 통해 메모리 ID, 액터 ID, 세션 ID 입력
- **단기 메모리**: 대화 이벤트 및 턴 쿼리
- **장기 메모리**: 사실, 선호도, 요약 탐색
- **실시간 검색**: 실시간 결과를 포함한 콘텐츠 필터링



## 사전 요구사항

- **Node.js** 16+
- **Python** 3.8+
- **AWS CLI** 자격 증명 구성 완료
- **AWS Bedrock AgentCore 메모리** 접근 권한

## AWS 자격 증명 설정

### 1단계: AWS CLI 설치
```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# AWS 웹사이트에서 AWS CLI MSI 설치 프로그램을 다운로드하고 실행하세요
```

### 2단계: AWS 자격 증명 구성
다음 방법 중 하나를 선택하세요:

#### 옵션 A: AWS Configure (권장)
```bash
aws configure
```
다음 정보를 입력하세요:
- AWS 액세스 키 ID
- AWS 시크릿 액세스 키
- 기본 리전 (예: `us-east-1`)
- 기본 출력 형식 (예: `json`)

#### 옵션 B: 환경 변수
```bash
export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_DEFAULT_REGION=us-east-1
```

#### 옵션 C: AWS 자격 증명 파일
`~/.aws/credentials` 생성:
```ini
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
```

`~/.aws/config` 생성:
```ini
[default]
region = us-east-1
output = json
```

### 3단계: AWS 접근 확인
```bash
# AWS 연결 테스트
aws sts get-caller-identity

# Bedrock 접근 테스트
aws bedrock list-foundation-models --region us-east-1
```

### 4단계: 필수 IAM 권한
AWS 사용자/역할에 다음 권한이 필요합니다:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:ListMemoryRecords",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:GetLastKTurns",
                "bedrock-agentcore:RetrieveMemories",
                "bedrock-agentcore:GetMemoryStrategies"
            ],
            "Resource": "*"
        }
    ]
}
```

## 빠른 시작 가이드

### 1단계: 클론 및 설정
```bash
# 저장소 클론
git clone <repository-url>
cd 01-tutorials/04-AgentCore-memory/03-advanced-patterns/04-memory-browser

# 프론트엔드 종속성 설치 (약 200MB의 패키지 다운로드)
npm install
```

**참고**:
- **종속성 미포함**: `node_modules` 및 `backend/venv`는 저장소에서 제외됩니다
- **최초 설정**: `npm install`을 실행하여 모든 프론트엔드 종속성을 다운로드하세요
- **프론트엔드 `.env`**: 기본 설정으로 이미 구성되어 있습니다
- **백엔드 `.env`**: 생성이 필요합니다 (2단계 참조)

### 2단계: 환경 변수 구성

#### 백엔드 구성
예제 파일을 복사하고 사용자 정의하세요:
```bash
# 예제 파일 복사
cp backend/.env.example backend/.env

# backend/.env를 편집하고 AWS 프로필을 설정하세요 (필요한 경우)
# AWS_PROFILE=your-profile-name
```

`backend/.env` 파일에는 다음 내용이 포함되어야 합니다:
```env
# AWS 구성 (리전은 설정하지 않으면 AWS CLI/프로필에서 자동 감지됩니다)
# AWS_REGION=us-east-1

# 서버 구성
# 보안: 로컬 개발에는 127.0.0.1 사용 (권장)
# 네트워크의 다른 머신에서 접근해야 하는 경우에만 0.0.0.0 사용
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DEBUG=true

# CORS 구성
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# 선택사항: AWS 프로필 (여러 프로필을 사용하는 경우)
# AWS_PROFILE=your-profile-name
```

**보안 참고**: 백엔드는 보안을 위해 기본적으로 `127.0.0.1` (로컬호스트 전용)에 바인딩됩니다. 이는 모든 네트워크 인터페이스에 대한 노출을 방지합니다. 네트워크의 다른 머신에서 백엔드에 접근해야 하는 경우 `.env` 파일에서 `BACKEND_HOST=0.0.0.0`으로 설정하되, 이렇게 하면 전체 네트워크에 서비스가 노출된다는 점에 유의하세요.

**참고**: AWS 리전은 AWS CLI 구성에서 자동으로 감지됩니다. 기본값을 재정의해야 하는 경우에만 `AWS_REGION`을 설정하세요.

#### 프론트엔드 구성
프론트엔드 `.env` 파일은 이미 기본값으로 구성되어 있습니다. 필요한 경우 수정할 수 있습니다:
```env
# 백엔드 API URL
REACT_APP_BACKEND_URL=http://localhost:8000

# 대시보드 설정
REACT_APP_MAX_MEMORY_ENTRIES=50
REACT_APP_REFRESH_INTERVAL=5000
```

### 3단계: 백엔드 종속성 설치
```bash
# 백엔드 디렉토리로 이동
cd backend

# Python 가상 환경 생성 (격리된 Python 패키지)
python3 -m venv venv

# 가상 환경 활성화
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Python 종속성 설치 (약 50MB의 패키지)
pip install -r requirements.txt

# 프로젝트 루트로 돌아가기
cd ..
```

**참고**: 가상 환경 (`backend/venv/`)은 경량 유지를 위해 저장소에서 제외됩니다.

### 4단계: 애플리케이션 시작

#### 옵션 A: 두 서비스를 함께 시작 (권장)
```bash
# 프로젝트 루트 디렉토리에서
npm run dev
```
이렇게 하면 백엔드(FastAPI)와 프론트엔드(React)가 동시에 시작됩니다.

#### 옵션 B: 서비스를 개별적으로 시작
```bash
# 터미널 1: 백엔드 시작
npm run start-backend

# 터미널 2: 프론트엔드 시작
npm start
```



### 5단계: 대시보드 접근
- **프론트엔드**: http://localhost:3000
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

### 6단계: 메모리 접근 구성
1. http://localhost:3000 에서 대시보드를 엽니다
2. 헤더에 **메모리 ID**와 **액터 ID**를 입력합니다
3. **Configure**를 클릭하여 접근을 검증합니다
4. AgentCore 메모리 데이터 쿼리를 시작하세요!

## 대시보드 기능

### 단기 메모리
- 대화 이벤트 및 턴 쿼리
- 콘텐츠, 이벤트 유형, 역할별 필터링

### 장기 메모리
- **사용자 입력 필요**: 메모리 ID 및 네임스페이스 (UI를 통해 입력)
- 콘텐츠 필터링을 포함한 네임스페이스 기반 쿼리
- 사실, 선호도, 요약 탐색

## 문제 해결

### 일반적인 문제
- **백엔드가 시작되지 않음**: Python 가상 환경이 활성화되었는지 확인
- **프론트엔드가 연결되지 않음**: 백엔드가 포트 8000에서 실행 중인지 확인
- **AWS 권한 오류**: `aws sts get-caller-identity`를 실행하여 자격 증명 확인
- **메모리 ID를 찾을 수 없음**: 메모리 ID가 존재하고 적절한 권한이 있는지 확인

---
