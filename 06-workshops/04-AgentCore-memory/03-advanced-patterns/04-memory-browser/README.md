# AgentCore Memory 대시보드

AWS Bedrock AgentCore Memory 데이터를 탐색하기 위한 경량 React + FastAPI 대시보드입니다.

**📦 저장소 크기**: 약 2MB(종속성 제외, 아래 설정 지침 참조)

## ✨ 주요 기능

- **동적 구성**: UI에서 Memory ID, Actor ID, Session ID 입력
- **단기 메모리**: 대화 이벤트 및 turn 쿼리
- **장기 메모리**: 사실, 선호도, 요약 탐색
- **실시간 검색**: 실시간 결과를 사용한 콘텐츠 필터링



## 📋 사전 요구 사항

- **Node.js** 16+
- **Python** 3.8+
- 자격 증명으로 구성된 **AWS CLI**
- **AWS Bedrock AgentCore Memory** 액세스 권한

## 🔑 AWS 자격 증명 설정

### 1단계: AWS CLI 설치
```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# AWS 웹 사이트에서 AWS CLI MSI installer를 다운로드하여 실행
```

### 2단계: AWS 자격 증명 구성
다음 방법 중 하나를 선택합니다.

#### 옵션 A: AWS Configure(권장)
```bash
aws configure
```
다음 정보를 입력합니다.
- AWS Access Key ID
- AWS Secret Access Key
- 기본 리전(예: `us-east-1`)
- 기본 출력 형식(예: `json`)

#### 옵션 B: 환경 변수
```bash
export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_DEFAULT_REGION=us-east-1
```

#### 옵션 C: AWS 자격 증명 파일
`~/.aws/credentials`를 생성합니다.
```ini
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
```

`~/.aws/config`를 생성합니다.
```ini
[default]
region = us-east-1
output = json
```

### 3단계: AWS 액세스 확인
```bash
# AWS 연결 테스트
aws sts get-caller-identity

# Bedrock 액세스 테스트
aws bedrock list-foundation-models --region us-east-1
```

### 4단계: 필수 IAM 권한
AWS 사용자/role에 다음 권한이 필요합니다.
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

## 🚀 빠른 시작 가이드

### 1단계: 복제 및 설정
```bash
# 리포지토리 복제
git clone <repository-url>
cd 06-workshops/04-AgentCore-memory/03-advanced-patterns/04-memory-browser

# Frontend 종속성 설치(약 200MB의 패키지 다운로드)
npm install
```

**참고**:
- 📦 **종속성 미포함**: `node_modules`와 `backend/venv`는 저장소에서 제외됨
- 🔧 **최초 설정**: `npm install`을 실행하여 모든 frontend 종속성 다운로드
- ✅ **Frontend `.env`**: 기본 설정으로 이미 구성됨
- ❌ **Backend `.env`**: 생성 필요(2단계 참조)

### 2단계: 환경 변수 구성

#### Backend 구성
예제 파일을 복사하여 사용자 지정합니다.
```bash
# 예제 파일 복사
cp backend/.env.example backend/.env

# backend/.env를 편집하고 필요한 경우 AWS profile 설정
# AWS_PROFILE=your-profile-name
```

`backend/.env` 파일에는 다음 내용이 포함되어야 합니다.
```env
# AWS 구성(리전을 설정하지 않으면 AWS CLI/profile에서 자동 감지)
# AWS_REGION=us-east-1

# 서버 구성
# 보안: 로컬 개발에는 127.0.0.1 사용(권장)
# 네트워크의 다른 컴퓨터에서 액세스해야 하는 경우에만 0.0.0.0 사용
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DEBUG=true

# CORS 구성
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# 선택 사항: AWS Profile(여러 profile을 사용하는 경우)
# AWS_PROFILE=your-profile-name
```

**보안 참고 사항**: 보안을 위해 backend는 기본적으로 `127.0.0.1`(localhost 전용)에 바인딩됩니다. 따라서 모든 네트워크 인터페이스에 노출되지 않습니다. 네트워크의 다른 컴퓨터에서 backend에 액세스해야 한다면 `BACKEND_HOST=0.0.0.0`으로 설정한 `.env` 파일을 사용할 수 있지만, 이 경우 서비스가 전체 네트워크에 노출된다는 점에 유의하세요.

**참고**: AWS 리전은 AWS CLI 구성에서 자동으로 감지됩니다. 기본값을 재정의해야 하는 경우에만 `AWS_REGION`을 설정하세요.

#### Frontend 구성
Frontend `.env` 파일은 기본값으로 이미 구성되어 있습니다. 필요한 경우 수정할 수 있습니다.
```env
# 백엔드 API URL
REACT_APP_BACKEND_URL=http://localhost:8000

# 대시보드 설정
REACT_APP_MAX_MEMORY_ENTRIES=50
REACT_APP_REFRESH_INTERVAL=5000
```

### 3단계: Backend 종속성 설치
```bash
# Backend 디렉터리로 이동
cd backend

# Python 가상 환경 생성(Python 패키지 격리)
python3 -m venv venv

# 가상 환경 활성화
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Python 종속성 설치(약 50MB의 패키지)
pip install -r requirements.txt

# 프로젝트 루트로 돌아가기
cd ..
```

**참고**: 저장소를 가볍게 유지하기 위해 가상 환경(`backend/venv/`)은 저장소에서 제외됩니다.

### 4단계: 애플리케이션 시작

#### 옵션 A: 두 서비스를 함께 시작(권장)
```bash
# 프로젝트 루트 디렉터리에서 실행
npm run dev
```
Backend(FastAPI)와 frontend(React)가 동시에 시작됩니다.

#### 옵션 B: 서비스를 개별적으로 시작
```bash
# 터미널 1: Backend 시작
npm run start-backend

# 터미널 2: Frontend 시작
npm start
```



### 5단계: 대시보드 액세스
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

### 6단계: Memory 액세스 구성
1. http://localhost:3000에서 대시보드를 엽니다.
2. 헤더에 **Memory ID**와 **Actor ID**를 입력합니다.
3. 액세스를 검증하려면 **Configure**를 클릭합니다.
4. AgentCore Memory 데이터 쿼리를 시작합니다.

## 📊 대시보드 기능

### 단기 메모리
- 대화 이벤트 및 turn 쿼리
- 콘텐츠, 이벤트 유형, role별 필터링

### 장기 메모리
- **사용자 입력 필요**: Memory ID 및 Namespace(UI에서 입력)
- 콘텐츠 필터링을 사용한 Namespace 기반 쿼리
- 사실, 선호도, 요약 탐색

## 🔧 문제 해결

### 일반적인 문제
- **Backend가 시작되지 않음**: Python 가상 환경이 활성화되어 있는지 확인
- **Frontend에서 연결할 수 없음**: Backend가 8000 포트에서 실행 중인지 확인
- **AWS 권한 오류**: `aws sts get-caller-identity`를 실행해 자격 증명 확인
- **Memory ID를 찾을 수 없음**: Memory ID가 존재하고 적절한 권한이 있는지 확인

---
