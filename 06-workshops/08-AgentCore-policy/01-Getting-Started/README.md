# AgentCore Policy - 시작하기 데모

Amazon Bedrock AgentCore Policy를 사용하여 AI 에이전트에 정책 기반 제어를 구현하는 종합 실습 데모입니다.

## 🚀 빠른 시작

1. **종속성 설치**: `pip install -r requirements.txt`
2. **노트북 열기**: `jupyter notebook AgentCore-Policy-Demo.ipynb`
3. 노트북의 **단계별 안내 따르기**

> **참고**: 네이티브 policy-registry API를 사용하려면 boto3 1.42.0 이상이 필요합니다.

## 개요

이 데모에서는 AgentCore Gateway를 통해 AI 에이전트가 도구와 상호 작용할 때 적용할 정책 기반 제어를 구현하는 전체 과정을 안내합니다.

## 학습 내용

- ✅ Lambda 함수를 에이전트 도구로 배포
- ✅ 여러 Lambda 대상이 연결된 AgentCore Gateway 설정
- ✅ Policy Engine 생성 및 구성
- ✅ 세분화된 액세스 제어를 위한 Cedar 정책 작성
- ✅ 실제 AI 에이전트 요청으로 정책 적용 테스트
- ✅ ALLOW 및 DENY 시나리오 이해

## 데모 시나리오

정책 제어가 적용된 **보험 인수 처리 시스템**을 구축합니다.

- **도구**:
  - **ApplicationTool** - 지역 및 자격 요건을 검증하여 보험 신청을 생성합니다.
    - 매개변수: `applicant_region` (string), `coverage_amount` (integer)
  - **RiskModelTool** - 거버넌스 제어에 따라 외부 위험 점수 산정 모델을 호출합니다.
    - 매개변수: `API_classification` (string), `data_governance_approval` (boolean)
  - **ApprovalTool** - 고액 또는 고위험 보험 인수 결정을 승인합니다.
    - 매개변수: `claim_amount` (integer), `risk_level` (string)

- **정책 규칙**: 보장 금액이 $1M 미만인 보험 신청만 허용
- **테스트 사례**:
  - ✅ $750K 보험 신청 (ALLOWED)
  - ❌ $1.5M 보험 신청 (DENIED)

> **중요**: 정책에서는 Gateway 대상 스키마에 정의된 매개변수만 참조할 수 있습니다. 각 도구에는 정책 조건에서 사용할 수 있는 특정 매개변수가 정의된 자체 스키마가 있습니다.

## 사전 요구 사항

시작하기 전에 다음 사항을 준비했는지 확인하세요.

- 적절한 자격 증명으로 구성된 AWS CLI
- boto3 1.42.0 이상이 설치된 Python 3.10 이상
- 설치된 `bedrock_agentcore_starter_toolkit` 패키지
- 설치된 `strands` 패키지(AI 에이전트 기능에 사용)
- AWS Lambda 액세스 권한(대상 함수 생성에 사용)
- Amazon Bedrock 액세스 권한(AI 에이전트 모델에 사용)
- **us-east-1 (N.Virginia)** 리전에서 작업

> **참고**: Gateway 설정 스크립트는 AgentCore 서비스에 필요한 신뢰 정책이 포함된 IAM 역할을 자동으로 생성합니다.

## 설정 지침

### 1. 종속성 설치

```bash
pip install -r requirements.txt
```

**중요**: boto3 1.42.0 이상이 설치되어 있는지 확인하세요.

```bash
pip install --upgrade boto3
```

### 2. 데모 노트북 열기

```bash
jupyter notebook AgentCore-Policy-Demo.ipynb
```

### 3. 노트북 따라 하기

노트북에서는 다음 단계를 안내합니다.

1. **환경 설정** - 자격 증명 및 종속성 확인
2. **Lambda 배포** - Lambda 함수 3개(ApplicationTool, RiskModelTool, ApprovalTool) 배포
3. **Gateway 설정** - OAuth로 AgentCore Gateway를 구성하고 Lambda 대상 연결
4. **에이전트 테스트** - 모든 도구에 액세스할 수 있는 AI 에이전트 테스트(아직 정책 없음)
5. **Policy Engine** - Policy Engine을 생성하고 Gateway에 연결
6. **Cedar 정책** - 액세스 제어를 위한 Cedar 정책 작성 및 배포
7. **정책 테스트** - 실제 AI 에이전트 요청으로 ALLOW 및 DENY 시나리오 테스트
8. **정리** - 생성된 모든 리소스 제거

> **참고**: 이 데모는 boto3 1.42.0 이상에서 사용할 수 있는 boto3의 네이티브 policy-registry 클라이언트와 AI 에이전트 기능을 위한 Strands 프레임워크를 사용합니다.

## 프로젝트 구조

```
Getting-Started/
├── AgentCore-Policy-Demo.ipynb    # 기본 demo Notebook
├── README.md                       # 이 파일
├── requirements.txt                # Python 의존성
├── config.json                     # 생성된 구성 파일
└── scripts/                        # 지원 script
    ├── setup_gateway.py            # IAM role을 자동 생성하는 Gateway 설정
    ├── agent_with_tools.py         # AI agent 세션 관리자
    ├── get_client_secret.py        # Cognito client secret 조회
    ├── policy_generator.py         # NL에서 Cedar 생성
    └── lambda-target-setup/        # Lambda 배포 script
        ├── deploy_lambdas.py       # Lambda 함수 3개 모두 배포
        ├── application_tool.js     # ApplicationTool Lambda 코드
        ├── risk_model_tool.js      # RiskModelTool Lambda 코드
        └── approval_tool.js        # ApprovalTool Lambda 코드
```

## 핵심 개념

### AgentCore Gateway

에이전트가 도구에 액세스할 수 있게 해 주는 MCP와 유사한 클라이언트입니다.

### Policy Engine

정의된 규칙에 따라 요청을 실시간으로 평가하는 Cedar 정책 모음입니다.

### Cedar 정책 언어

다음 구조를 사용하는 선언적 정책 언어입니다.

```cedar
permit(
  principal,              // Who can access
  action,                 // What action they can perform  
  resource                // What resource they can access
) when {
  conditions              // Under what conditions
};
```

### 정책 모드

- **LOG_ONLY**: 정책을 평가하지만 요청을 차단하지 않습니다(테스트용).
- **ENFORCE**: 정책을 위반하는 요청을 차단합니다(프로덕션용).

## 정책 예제

```cedar
permit(
  principal,
  action == AgentCore::Action::"ApplicationToolTarget___create_application",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.coverage_amount <= 1000000
};
```

이 정책은 다음과 같이 작동합니다.
- 보장 금액이 $1M 미만인 보험 신청 생성을 허용합니다.
- 보장 금액이 $1M 이상인 보험 신청을 거부합니다.
- ApplicationTool 대상에 적용됩니다.
- `coverage_amount` 매개변수를 실시간으로 평가합니다.

> **핵심 사항**: Policy Engine을 ENFORCE 모드로 Gateway에 연결하면 기본 동작은 DENY입니다. 액세스를 허용할 각 도구에 대해 permit 정책을 명시적으로 생성해야 합니다.

## 아키텍처

```
┌─────────────┐
│   AI Agent  │
└──────┬──────┘
       │ Tool Call Request
       ▼
┌─────────────────────┐
│  AgentCore Gateway  │
│  + OAuth Auth       │
└──────┬──────────────┘
       │ Policy Check
       ▼
┌─────────────────────┐
│   Policy Engine     │
│   (Cedar Policies)  │
└──────┬──────────────┘
       │ ALLOW / DENY
       ▼
┌─────────────────────┐
│   Lambda Target     │
│   (RefundTool)      │
└─────────────────────┘
```

## 테스트

이 데모에는 실제 AI 에이전트를 사용한 종합 테스트가 포함되어 있습니다.

### Policy Engine 연결 전
- 에이전트가 3개 도구를 모두 나열할 수 있습니다.
- 에이전트가 제한 없이 모든 도구를 호출할 수 있습니다.
- 정책이 적용되지 않습니다.

### 비어 있는 Policy Engine 연결 후
- 에이전트가 어떤 도구도 나열할 수 없습니다(기본값 DENY).
- 에이전트가 어떤 도구도 호출할 수 없습니다.
- 모든 요청이 차단됩니다.

### 보험 신청 정책 추가 후
- 에이전트가 ApplicationTool만 나열할 수 있습니다.
- 에이전트가 보장 금액이 $1M 미만인 보험 신청을 생성할 수 있습니다. ✅
- 에이전트가 보장 금액이 $1M을 초과하는 보험 신청을 생성할 수 없습니다. ❌
- 다른 도구는 계속 차단됩니다.

### 테스트 1: ALLOW 시나리오 ✅
- 요청: Create application with $750K coverage
- 예상 결과: ALLOWED
- 이유: $750K <= $1M
- 결과: Lambda가 실행되고 보험 신청이 생성됩니다.

### 테스트 2: DENY 시나리오 ❌
- 요청: Create application with $1.5M coverage
- 예상 결과: DENIED
- 이유: $1.5M > $1M
- 결과: 정책이 요청을 차단하며 Lambda는 실행되지 않습니다.

## 고급 기능

### 여러 조건

```cedar
permit(...) when {
  context.input.coverage_amount <= 1000000 &&
  has(context.input.applicant_region) &&
  context.input.applicant_region == "US"
};
```

### 지역 기반 조건

```cedar
permit(...) when {
  context.input.applicant_region in ["US", "CA", "UK"]
};
```

### 위험 모델 거버넌스

```cedar
permit(
  principal,
  action == AgentCore::Action::"RiskModelToolTarget___invoke_risk_model",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.API_classification == "public" &&
  context.input.data_governance_approval == true
};
```

### 승인 임계값

```cedar
permit(
  principal,
  action == AgentCore::Action::"ApprovalToolTarget___approve_underwriting",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.claim_amount <= 100000 &&
  context.input.risk_level in ["low", "medium"]
};
```

### 거부 정책

```cedar
forbid(...) when {
  context.input.coverage_amount > 10000000
};
```

## 모니터링 및 디버깅

### CloudWatch Logs

정책 결정은 CloudWatch에 기록됩니다.

- **Gateway 로그**: 요청/응답 세부 정보
- **Policy Engine 로그**: 정책 평가 결과
- **Lambda 로그**: 도구 실행 세부 정보

### 일반적인 문제

1. **정책이 적용되지 않음**
   - LOG_ONLY가 아닌 ENFORCE 모드인지 확인합니다.
   - 정책 상태가 ACTIVE인지 확인합니다.
   - Gateway 연결 여부를 확인합니다.

2. **모든 요청이 거부됨**
   - 정책 조건을 검토합니다.
   - 작업 이름이 대상과 일치하는지 확인합니다.
   - 리소스 ARN이 Gateway와 일치하는지 확인합니다.

3. **인증 실패**
   - OAuth 자격 증명을 확인합니다.
   - 토큰 엔드포인트에 액세스할 수 있는지 확인합니다.
   - client_id와 client_secret이 올바른지 확인합니다.

4. **모듈 가져오기 오류**
   - boto3 1.42.0 이상이 설치되어 있는지 확인합니다: `pip install --upgrade boto3`
   - strands가 설치되어 있는지 확인합니다: `pip install strands`
   - 종속성을 업데이트한 후 Jupyter 커널을 다시 시작합니다.
   - Python 캐시를 삭제합니다: `rm -rf scripts/__pycache__`

5. **에이전트 세션 오류**
   - `MCPClientInitializationError`가 표시되면 노트북 커널을 다시 시작합니다.
   - config.json의 client_secret 필드에 값이 입력되어 있는지 확인합니다.
   - 보안 암호가 없으면 `scripts/get_client_secret.py`를 실행하여 가져옵니다.

6. **AWS 토큰 만료**
   - AWS 자격 증명을 갱신합니다: `aws sso login` 또는 `aws configure`
   - 새 자격 증명을 적용하려면 노트북 커널을 다시 시작합니다.
   - 처음부터 셀을 다시 실행합니다.


## 추가 자료

- **Cedar 정책 언어**: [Cedar 문서](https://docs.cedarpolicy.com/)
- **Amazon Bedrock AgentCore Policy**: [AWS AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)

---

**즐겁게 만들어 보세요!** 🚀
