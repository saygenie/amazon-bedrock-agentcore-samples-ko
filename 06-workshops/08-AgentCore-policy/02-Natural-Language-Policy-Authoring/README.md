# AgentCore Policy - 자연어 정책 작성(NL2Cedar)

Amazon Bedrock AgentCore Policy의 NL2Cedar 기능을 사용하여 자연어로 Cedar 정책을 생성하는 실습 데모입니다.

## 🚀 빠른 시작

1. **종속성 설치**: `pip install -r requirements.txt`
2. **노트북 열기**: `jupyter notebook NL-Authoring-Policy.ipynb`
3. 노트북의 **단계별 안내 따르기**

> **참고**: 이 데모는 시작하기 튜토리얼을 기반으로 합니다. 해당 튜토리얼을 완료하지 않았더라도 노트북에서 필요한 인프라를 자동으로 설정합니다.

## 개요

이 데모에서는 권한 부여 요구 사항을 자연어로 작성하고 Cedar 구문으로 자동 변환하는 방법을 보여 줍니다. NL2Cedar 기능을 사용하면 다음 작업을 수행할 수 있습니다.

- Cedar 구문 대신 일반적인 영어 문장으로 정책 작성
- 여러 줄로 작성한 문장에서 여러 정책 생성
- 자격 증명 속성을 사용하는 principal 기반 정책 생성
- 생성된 정책이 요구 사항과 일치하는지 확인

## 학습 내용

- ✅ 자연어 설명으로 Cedar 정책 생성
- ✅ 간단한 단일 문장 정책 생성
- ✅ 여러 줄로 작성한 문장에서 여러 정책 생성
- ✅ 자격 증명 속성을 사용하는 principal 범위 정책 작성
- ✅ 다양한 정책 구조와 패턴 이해

## 사전 요구 사항

시작하기 전에 다음 사항을 준비했는지 확인하세요.

- 적절한 자격 증명으로 구성된 AWS CLI
- boto3 1.42.0 이상이 설치된 Python 3.10 이상
- 설치된 `bedrock_agentcore_starter_toolkit` 패키지
- AWS Lambda 액세스 권한(대상 함수에 사용)
- **01-Getting-Started** 튜토리얼 완료(또는 노트북에서 자동으로 설정)

## 데모 시나리오

이 데모에서는 시작하기 튜토리얼의 **보험 인수 시스템**과 3개의 Lambda 도구를 사용합니다.

1. **ApplicationTool** - 보험 신청 생성
   - 매개변수: `applicant_region`, `coverage_amount`

2. **RiskModelTool** - 위험 점수 산정 모델 호출
   - 매개변수: `API_classification`, `data_governance_approval`

3. **ApprovalTool** - 보험 인수 결정 승인
   - 매개변수: `claim_amount`, `risk_level`

## 자연어 정책 예제

### 1. 간단한 단일 문장 정책

**자연어:**
```
Allow all users to invoke the application tool when the coverage amount 
is under 1 million and the application region is US or CAN
```

**생성된 Cedar 정책:**
```cedar
permit(
  principal,
  action == AgentCore::Action::"ApplicationToolTarget___create_application",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  (context.input.coverage_amount < 1000000) && 
  ((context.input.applicant_region == "US") || 
   (context.input.applicant_region == "CAN"))
};
```

### 2. 여러 줄 문장

**자연어:**
```
Allow all users to invoke the risk model tool when data governance approval is true.
Block users from calling the application tool unless coverage amount is present.
```

**결과:** permit 정책 하나와 forbid 정책 하나, 총 **2개의 개별 정책**을 생성합니다.

### 3. Principal 기반 정책

**자연어:**
```
Allow principals with username "test-user" to invoke the risk model tool
```

**생성된 Cedar 정책:**
```cedar
permit(
  principal,
  action == AgentCore::Action::"RiskModelToolTarget___invoke_risk_model",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  (principal.hasTag("username")) && 
  (principal.getTag("username") == "test-user")
};
```

**자연어:**
```
Forbid principals to access the approval tool unless they have 
the scope group:Controller
```

**생성된 Cedar 정책:**
```cedar
forbid(
  principal,
  action == AgentCore::Action::"ApprovalToolTarget",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  !((principal.hasTag("scope")) && 
    (principal.getTag("scope") like "*group:Controller*"))
};
```

**자연어:**
```
Block principals from using risk model tool and approval tool 
unless the principal has role "senior-adjuster"
```

**생성된 Cedar 정책:**
```cedar
forbid(
  principal,
  action in [AgentCore::Action::"RiskModelToolTarget",
             AgentCore::Action::"ApprovalToolTarget"],
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  !((principal.hasTag("role")) && 
    (principal.getTag("role") == "senior-adjuster"))
};
```

## NL2Cedar 작동 방식

1. **스키마 인식**: Foundation Model이 도구 이름과 매개변수를 이해할 수 있도록 Gateway 대상 스키마가 NL2Cedar에 제공됩니다.

2. **자연어 입력**: 일반적인 영어 문장으로 권한 부여 요구 사항을 제공합니다.

3. **Cedar 생성**: 시스템이 구문상 올바른 Cedar 정책을 생성합니다.

4. **정책 생성**: 생성된 정책을 Policy Engine에 바로 생성할 수 있습니다.

## 워크플로

노트북에서는 다음 단계를 안내합니다.

1. **환경 설정** - 자격 증명 및 종속성 확인
2. **인프라 확인** - 필요한 경우 Gateway를 자동으로 설정(시작하기 튜토리얼의 구성 사용)
3. **Policy Engine 생성** - NL2Cedar 정책을 위한 Policy Engine 생성
4. **간단한 정책 생성** - 자연어로 단일 정책 생성
5. **정책 생성** - 생성된 정책을 Policy Engine에 생성
6. **여러 줄 입력으로 생성** - 여러 줄로 작성한 문장에서 여러 정책 생성
7. **Principal 기반 정책** - 자격 증명을 인식하는 정책 생성
8. **정리** - 생성된 모든 리소스 제거

## 주요 기능

### 자동 인프라 설정

시작하기 튜토리얼을 완료하지 않았다면 노트북에서 다음 작업을 수행합니다.
- Lambda 함수 3개(ApplicationTool, RiskModelTool, ApprovalTool) 배포
- OAuth 인증을 사용하는 AgentCore Gateway 생성
- 올바른 스키마로 Lambda 대상 구성
- 구성을 `config.json`에 저장

### 여러 정책 생성

일관된 구분 기호(쉼표, 마침표, 세미콜론)를 사용해 여러 줄로 문장을 제공하면 NL2Cedar가 다음 작업을 자동으로 수행합니다.
- 개별 정책 문장 감지
- 각 문장에 대해 별도의 Cedar 정책 생성
- 모든 정책을 `generatedPolicies` 배열로 반환

### Principal 범위 지원

자격 증명 기반 정책에서는 다음 항목을 참조할 수 있습니다.
- **사용자 이름**: `principal.getTag("username")`
- **역할**: `principal.getTag("role")`
- **범위**: `principal.getTag("scope")`
- **사용자 지정 클레임**: OAuth 토큰의 모든 속성

> **💡 팁**: 자연어 문장에 정확한 태그 이름을 지정하면 NL2Cedar가 올바른 Cedar 정책을 생성하는 데 도움이 됩니다.


## 모범 사례

1. **구체적으로 작성**: 도구 이름, 매개변수 및 조건을 명확하게 기술합니다.
2. **정확한 매개변수 이름 사용**: Gateway 스키마에 표시된 이름으로 매개변수를 참조합니다.
3. **Principal 속성 지정**: 자격 증명 기반 정책에는 정확한 태그 이름을 명시합니다.
4. **한 줄에 하나의 개념 작성**: 여러 줄 입력으로 정책을 생성할 때 일관된 구분 기호로 서로 다른 정책을 구분합니다.
5. **생성된 정책 테스트**: 배포하기 전에 생성된 Cedar 구문을 항상 검토합니다.



## 추가 자료

- **정책 예제**: [지원되는 Cedar 정책](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/example-policies.html)
- **시작하기 튜토리얼**: `../01-Getting-Started/README.md`

---

**즐겁게 만들어 보세요!** 🚀
