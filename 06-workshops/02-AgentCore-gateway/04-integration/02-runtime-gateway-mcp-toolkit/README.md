# AgentCore Runtime 및 Gateway MCP Server Toolkit

AgentCore Runtime 및 Gateway 인프라에 Custom MCP Server를 빠르게 설정할 수 있는 구성형 toolkit입니다.

MCP 서버 배포 경험을 간소화하기 위해 [bedrock-agentcore-starter-toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit/)을 기반으로 구축되었습니다.

## 개요

- 코드를 작성하지 않고 custom MCP 서버를 AgentCore에 빠르게 배포하고 싶으신가요?
- 여러 custom MCP 서버 및 도구를 하나의 URL로 통합하여 다양한 MCP Server의 모든 도구를 노출하고 싶으신가요?
- MCP Server에 대한 액세스를 보호하고 싶으신가요?

이 toolkit을 사용하면 간단한 명령줄 인수만으로 이 모든 작업을 수행할 수 있습니다. 다음 리소스의 생성을 자동화합니다.

- 인증용 Cognito User Pool
- 각 MCP Server용 AgentCore Runtime 환경
- MCP 프로토콜을 지원하는 AgentCore Gateway
- OAuth2 인증을 사용하는 Gateway MCP Server 대상

이 toolkit은 완전한 MCP Gateway를 생성하고, 여러 MCP 서버(예: calculator, helloworld)에 적절한 인증과 라우팅을 적용하여 단일 Gateway 엔드포인트를 통해 액세스할 수 있게 합니다.

## 사전 요구 사항

1. AWS 자격 증명 구성
2. Python 3.8 이상 설치
3. Cognito 사용자 구성을 위한 `.env` 파일(선택 사항)

## 설치

### PyPI에서 설치(게시된 경우)
```bash
pip install agentcore-runtime-gw-mcp-toolkit
```

### 소스에서 설치
```bash
git clone <repository-url>
cd agentcore-runtime-gw-mcp-tool-kit
pip install -e .
```

## 구성

### 환경 변수(선택 사항)

프로젝트 디렉터리에 `.env` 파일을 생성하여 Cognito 사용자 자격 증명을 사용자 지정할 수 있습니다.

```bash
# .env 파일
COGNITO_USERNAME=your_username
COGNITO_TEMP_PASSWORD=your_temp_password
COGNITO_PASSWORD=your_permanent_password
```

**기본값**(`.env` 파일을 제공하지 않은 경우 사용):
- `COGNITO_USERNAME`: `testuser`
- `COGNITO_TEMP_PASSWORD`: `Temp123!`
- `COGNITO_PASSWORD`: `MyPassword123!`

**참고**: toolkit은 테스트를 위해 이 자격 증명으로 Cognito 사용자를 자동 생성합니다.

## 사용법

### 시작하기

1. **리포지토리 복제**
   ```bash
   git clone <repository-url>
   cd agentcore-runtime-gw-mcp-tool-kit
   ```

2. **패키지 설치**
   ```bash
   pip install -e .
   ```

3. **MCP Server 코드 준비**
   - MCP 서버 파일은 시스템의 어느 위치에나 둘 수 있습니다.
   - 각 서버에 자체 `server.py`와 `requirements.txt`가 있는지 확인합니다.
   - Runtime 구성에 사용할 수 있도록 이 파일들의 전체 경로를 기록합니다.

   
   **구조 예시(어느 위치에나 배치 가능):**
   ```
   /path/to/my-servers/
   ├── calculator/
   │   ├── server.py
   │   └── requirements.txt
   ├── helloworld/
   │   ├── server.py
   │   └── requirements.txt
   └── my-custom-server/
       ├── server.py
       └── requirements.txt
   ```

4. **명령줄 인수로 배포**
   ```bash
   agentcore-mcp-toolkit \
     --gateway-name "my-gateway" \
     --runtime-configs '[
       {
         "name": "my-custom-runtime",
         "description": "My Custom MCP Server",
         "entrypoint": "/path/to/my-servers/my-custom-server/server.py",
         "requirements_file": "/path/to/my-servers/my-custom-server/requirements.txt"
       }
     ]'
   ```
   **참고:** agentcore-mcp-toolkit은 MCP Server 프로젝트 루트에서 호출해야 합니다. 위 예시에서는 /path/to에서 유틸리티를 호출해야 합니다.

### 기본 사용법

```bash
# 최소 인수로 배포
agentcore-mcp-toolkit \
  --gateway-name "my-gateway" \
  --runtime-configs '[{"name":"runtime1","description":"My Runtime","entrypoint":"/path/to/myserver/server.py","requirements_file":"/path/to/myserver/requirements.txt"}]'

# 모든 옵션을 사용하여 배포
agentcore-mcp-toolkit \
  --region us-east-1 \
  --gateway-name "my-gateway-mcp-server" \
  --gateway-description "My AgentCore Gateway" \
  --runtime-configs '[
    {
      "name": "my-calculator-runtime",
      "description": "Calculator MCP Server", 
      "entrypoint": "/path/to/calculator/server.py",
      "requirements_file": "/path/to/calculator/requirements.txt"
    }
  ]'
```

### 명령줄 옵션

- `--region`: AWS 리전(기본값: us-east-1)
- `--gateway-name`: Gateway 이름(필수)
- `--gateway-description`: Gateway 설명(선택 사항)
- `--runtime-configs`: Runtime 구성의 JSON 배열(필수)

### Runtime 구성 형식

`--runtime-configs` JSON 배열의 각 Runtime 구성에는 다음 항목이 포함되어야 합니다.

```json
{
  "name": "runtime-name",
  "description": "Runtime description",
  "entrypoint": "path/to/server.py",
  "requirements_file": "path/to/requirements.txt",
  "auto_create_execution_role": true,
  "auto_create_ecr": true
}
```

**필수 필드:**
- `name`: 고유한 Runtime 이름
- `entrypoint`: MCP 서버 Python 파일의 전체 경로
- `requirements_file`: requirements.txt 파일의 전체 경로

**선택 필드:**
- `description`: Runtime 설명
- `auto_create_execution_role`: IAM 역할 자동 생성(기본값: true)
- `auto_create_ecr`: ECR 리포지토리 자동 생성(기본값: true)

### 자동으로 파생되는 이름

toolkit은 `gateway-name`과 Runtime `name` 필드에서 리소스 이름을 자동으로 파생합니다.

**Gateway 리소스**(`--gateway-name`에서 파생):
- IAM 역할: `{gateway-name}-role`
- User Pool: `{gateway-name}-pool`
- Resource Server ID: `{gateway-name}-id`
- Resource Server 이름: `{gateway-name}-name`
- Client 이름: `{gateway-name}-client`

**Runtime 리소스**(Runtime `name`에서 파생):
- User Pool: `{runtime-name}-pool`
- Resource Server ID: `{runtime-name}-id`
- Resource Server 이름: `{runtime-name}-name`
- Client 이름: `{runtime-name}-client`
- Agent 이름: `{runtime-name}`(하이픈은 밑줄로 변환)

**대상 리소스**(자동 생성):
- 대상 이름: `{runtime-name}-target`
- Identity Provider: `{runtime-name}-identity`

## Gateway 테스트

배포가 완료되면 toolkit은 MCP Gateway를 테스트하고 사용하는 데 필요한 모든 연결 정보를 자동으로 제공합니다.

### Gateway 연결 정보

배포가 성공하면 toolkit은 연결 세부 정보를 자동으로 표시하고 **자격 증명을 파일에 안전하게 저장**합니다.

#### **안전한 자격 증명 저장**

보안을 위해 민감한 자격 증명은 콘솔 로그에 표시되지 않고 안전한 파일에 저장됩니다.

- **파일 위치**: `.agentcore-credentials-{gateway-name}.json`
- **파일 권한**: 소유자만 액세스 가능(600)
- **콘솔 출력**: 민감한 값을 `<redacted>`로 표시
- **액세스 방법**: `cat .agentcore-credentials-{gateway-name}.json` 사용

**출력 예시:**
```
============================================================
GATEWAY CONNECTION INFORMATION
============================================================
Gateway URL: https://my-gateway-mcp-server-123456789.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
User Pool ID: us-east-1_bt4yEZFOx
Client ID: <redacted>
Client Secret: <redacted>
Access Token: <redacted>
Credentials saved to: .agentcore-credentials-my-gateway.json
File permissions set to owner-only access (600)
Use: cat .agentcore-credentials-my-gateway.json
============================================================

✅ Setup completed successfully!
Gateway ID: my-gateway-mcp-server-123456789
Runtime 1 Agent ARN: arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/my_calculator_runtime-123456789
```

### Access Token으로 QDev Plugin 구성

QDev plugin에서 MCP Gateway를 사용하려면 다음과 같이 구성합니다.

![QDev MCP 구성](images/qdev_mcp_config.png)

**QDev 구성 단계:**
1. 안전한 파일에서 **자격 증명을 가져옵니다**.
   ```bash
   cat .agentcore-credentials-{gateway-name}.json
   ```
2. JSON 파일에서 **access_token** 값을 복사합니다.
3. QDev plugin 설정에 다음 정보로 새 MCP 서버를 추가합니다.
   - **Server URL**: 자격 증명 파일의 `gateway_url` 사용
   - **Authentication**: Bearer Token
   - **Token**: 2단계에서 복사한 액세스 토큰 붙여넣기
4. 구성을 저장하고 연결을 테스트합니다.

**보안 참고 사항**: 자격 증명 파일을 공유하거나 버전 관리에 커밋하지 마세요.

### 실시간 데모 예시

구성이 완료되면 QDev에서 MCP 도구를 직접 사용할 수 있습니다.

**Calculator MCP Server 데모:**
![Calculator 덧셈 데모](images/calculator_add_demo.png)

**Hello World MCP Server 데모:**
![Hello World 인사 데모](images/greet_hello_world.png)

## 아키텍처

![아키텍처](images/architecture.png)

### 아키텍처 구성 요소

toolkit은 다음 항목을 생성합니다.
1. **단일 Gateway**: 요청을 라우팅하는 여러 MCP Server 대상이 연결된 하나의 AgentCore Gateway
2. **여러 Runtime**: 각 MCP 서버가 자체 AgentCore Runtime에서 실행
3. **인증**: Gateway와 각 Runtime에 별도의 Cognito 리소스 사용
4. **대상**: Gateway를 각 Runtime에 연결하는 Gateway MCP Server 대상

### 인증 흐름

**Inbound Authorization(Client → Gateway):**
- MCP Client(QDev)가 Bearer token과 함께 요청을 전송합니다.
- Gateway JWT Authorizer가 Gateway Cognito User Pool을 기준으로 토큰을 검증합니다.
- 권한이 부여된 요청을 적절한 대상으로 라우팅합니다.

**Outbound Authorization(Gateway → Runtime):**
- 각 대상에는 자체 OAuth2 credential provider가 있습니다.
- Gateway는 각 Runtime Cognito User Pool에서 OAuth 토큰을 가져옵니다.
- 인증된 요청을 개별 MCP 서버 Runtime으로 전송합니다.

## 권한 부여 지원

### 현재 구현
이 toolkit은 현재 인바운드 및 아웃바운드 권한 부여 모두에 **Amazon Cognito OAuth2**를 지원합니다.
- **Inbound Authorization**: Gateway는 클라이언트 인증에 Cognito JWT 토큰을 사용합니다.
- **Outbound Authorization**: Gateway는 Cognito OAuth2 자격 증명을 사용하여 Runtime에 인증합니다.

### 로드맵
- **IAM Role 기반 권한 부여**: 인바운드 및 아웃바운드 인증 모두에 IAM 역할과 정책 지원(할 일 - 다음 릴리스에 계획)

## 보안 기능

### **안전한 자격 증명 관리**
- **파일 기반 저장**: 제한된 권한이 적용된 안전한 파일에 자격 증명 저장
- **콘솔 마스킹**: 로그에서 민감한 값을 `<redacted>`로 표시
- **파일 권한**: 소유자만 액세스할 수 있도록 자동 설정(600)
- **Fallback 보호**: 파일 작업 실패 시 정상적으로 처리

### **입력 검증**
- **Path traversal 보호**: 파일 경로에 `..` 사용 방지
- **파일 확장자 검증**: `.py` 및 `.txt` 확장자 확인
- **JSON 구조 검증**: Runtime 구성 형식 검증
- **필수 필드 확인**: 모든 필수 필드가 있는지 확인

### **오류 처리**
- **구체적인 예외 처리**: 적절한 예외 유형 사용
- **정제된 오류 메시지**: 정보 노출 방지
- **Graceful degradation**: 가능한 경우 작업 계속
- **올바른 종료 코드**: 자동화에 적절한 상태 반환

## 정리

### 리소스 제거

toolkit이 생성한 모든 리소스를 정리하려면 cleanup 스크립트를 사용합니다.

```bash
# 특정 Gateway 및 Runtime 정리
python -m cleanup \
  --gateway-name "my-gateway" \
  --runtime-names '["runtime1", "runtime2"]' \
  --region us-east-1

# 확인 메시지 건너뛰기
python -m cleanup \
  --gateway-name "my-gateway" \
  --runtime-names '["runtime1", "runtime2"]' \
  --confirm
```

### 정리 옵션

- `--gateway-name`: 정리할 Gateway 이름(필수)
- `--runtime-names`: 정리할 Runtime 이름의 JSON 배열(필수)
- `--region`: AWS 리전(기본값: us-east-1)
- `--confirm`: 확인 메시지 건너뛰기

### 정리되는 리소스

cleanup 스크립트는 다음을 제거합니다.
- AgentCore Gateway 및 모든 대상
- AgentCore Runtime 인스턴스
- Cognito User Pool 및 도메인
- IAM 역할 및 정책
- OAuth2 credential provider

**참고**: cleanup 스크립트는 로컬 자격 증명 파일을 제거하지 않습니다. 제거하려면 다음 명령을 실행합니다.
```bash
# 자격 증명 파일 수동 제거
rm .agentcore-credentials-*.json
```

**경고**: 이 작업은 실행 취소할 수 없습니다. 계속하기 전에 항상 리소스를 확인하세요.

## 문제 해결

1. AWS 자격 증명이 올바르게 구성되었는지 확인합니다.
2. 필요한 MCP 서버 파일이 각각의 디렉터리에 있는지 확인합니다.
3. AWS 리전 권한을 확인합니다.
4. 자세한 오류 정보는 CloudWatch 로그에서 확인합니다.
5. 테스트할 때 Gateway URL 형식이 올바른지 확인합니다.
6. Cognito User Pool과 Client가 정상적으로 생성되었는지 확인합니다.
7. **Access Token 문제**: 액세스 토큰이 만료되면 toolkit을 다시 실행하여 새 토큰을 받습니다.
8. **QDev 연결 문제**: Gateway URL이 `/mcp`로 끝나고 bearer token이 올바르게 복사되었는지 확인합니다.
9. **도구 탐색**: 도구를 찾지 못하면 다른 쿼리 용어를 사용합니다("calculator", "greet" 또는 "tools" 시도).
10. **권한 부여 문제**: 현재는 Cognito OAuth2만 지원하므로 모든 인증에 Cognito 토큰을 사용하는지 확인합니다.
11. **Cognito 사용자 문제**: 사용자 생성 오류가 발생하면 `.env` 파일 구성을 확인하거나 기본 자격 증명을 사용합니다.
12. **정리 문제**: 정리에 실패하면 AWS 콘솔에서 리소스를 직접 확인하고 구체적인 리소스 이름으로 다시 시도합니다.
13. **자격 증명 파일 문제**: 자격 증명 파일을 생성할 수 없다면 디렉터리 권한과 디스크 공간을 확인합니다.
14. **파일 권한 문제**: Windows에서는 파일 권한이 올바르게 설정되지 않을 수 있으므로 자격 증명 파일을 수동으로 보호합니다.
15. **경로 검증 오류**: 파일 경로에 `..`가 없고 올바른 확장자(`.py`, `.txt`)를 사용하는지 확인합니다.
16. **JSON 검증 오류**: runtime-configs가 필수 필드를 포함한 유효한 JSON 배열인지 확인합니다.

## MCP Server 예시

toolkit에는 다음 MCP 서버 예시가 포함되어 있습니다.
- **Calculator**: 덧셈 및 곱셈 함수 제공
- **HelloWorld**: 인사 기능 제공

두 서버 모두 MCP 프로토콜 구현 방식을 보여주며 custom MCP 서버를 생성하기 위한 템플릿으로 사용할 수 있습니다.
