# AWS Agent Registry Kiro Power - 게시자 워크플로

## 개요

Kiro Powers는 MCP 도구, steering 파일 및 훅을 하나의 설치 패키지로 묶어 과도한 컨텍스트 없이 에이전트에 전문 지식을 제공합니다. 자세한 내용은 [Kiro Powers 설명서](https://kiro.dev/docs/powers/)를 참조하세요.

이 Kiro Power를 사용하면 **게시자 페르소나**가 AWS Agent Registry에서 에이전트/MCP 레코드를 생성하고 관리하며 제출할 수 있습니다.

> 게시자 워크플로에서는 관리자가 생성한 레지스트리가 이미 있다고 가정합니다.

### 튜토리얼 세부 정보

| 정보                | 세부 정보                                                               |
|:--------------------|:------------------------------------------------------------------------|
| 튜토리얼 유형       | 워크플로                                                                |
| 페르소나            | 게시자                                                                  |
| Power 유형          | Knowledge(steering만 사용, MCP 도구 없음)                               |
| 구성 요소           | `POWER.md`, 워크플로 지침과 코드 조각이 포함된 steering 파일            |
| 레지스트리 작업     | 레지스트리 레코드 생성, 나열, 제출, 삭제(MCP 및 A2A)                    |
| 예제 난이도         | 중급                                                                    |
| 사용 SDK            | boto3                                                                   |

### Power의 구성 요소

- `POWER.md`: 진입점 steering 파일은 Kiro 에이전트의 온보딩 설명서 역할을 하며 사용 가능한 도구와 사용 컨텍스트를 정의합니다. 또한 사용 가능한 API 집합을 정의하고 문제 해결 지침을 포함합니다.
- `Steering`: 작업 및 워크플로별 지침과 함께 Power가 실행할 참조 문서와 예제 코드 조각을 자동화합니다. Knowledge Power이므로 지침만 포함됩니다.

이 두 파일은 함께 패키징되며 사용자 쿼리에 따라 동적으로 로드됩니다.

### 게시자 워크플로 아키텍처

<div style="text-align:left">
    <img src="images/publisher-workflow.png" width="100%"/>
</div>

### 주요 기능

* AWS Agent Registry의 게시자 페르소나 작업
* MCP 서버 레코드 생성 및 관리
* A2A 에이전트 카드 레코드 생성 및 관리
* 관리자 승인을 위한 레코드 제출
* Kiro steering 파일을 통한 워크플로 지침 제공

---

## Power 활성화

아래 GitHub URL을 사용하여 Kiro에 이 Power를 직접 설치합니다.

[AWS Agent Registry 게시자용 Kiro Power(GitHub)](https://github.com/awslabs/agentcore-samples/tree/main/06-workshops/10-Agent-Registry/01-advanced/kiro/kiro-power-publisher-workflow/aws-agent-registry)

Kiro에서 Powers 패널을 열고 "Add Custom Power -> Import Power from Github"을 선택한 다음 위 링크를 붙여 넣습니다.

<div style="text-align:left">
    <img src="images/activate-kiro-power.png" width="100%"/>
</div>

<div style="text-align:left">
    <img src="images/import-from-github.png" width="100%"/>
</div>

<div style="text-align:left">
    <img src="images/aws-agent-registry-power.png" width="100%"/>
</div>

---

## 사전 요구 사항

### 1. AWS CLI 설치

```bash
aws --version
# 예상 결과: aws-cli/2.x.x ...
```

[AWS CLI 설치](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)

---

### 2. boto3 설치

```bash
pip install boto3
```

---

### 3. 게시자 페르소나 권한으로 구성된 AWS Identity

AWS Identity에는 레지스트리 작업을 수행할 권한이 필요합니다. 환경에 맞는 방법을 사용하세요.

옵션 A - 명명된 프로파일:
```bash
aws configure --profile <YOUR_PROFILE>
```

옵션 B - IAM 사용자 액세스 키(환경 변수):
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=your_region
```

옵션 C - IAM 역할 - 자격 증명이 자동으로 선택됩니다.

자격 증명이 올바르게 확인되는지 검증합니다.
```bash
aws sts get-caller-identity
# 예상 결과: AccountId, Arn, UserId 반환
```

---

### 4. 게시자 페르소나 정책

게시자 워크플로의 AWS Agent Registry 작업을 수행하려면 다음 정책을 포함하는 IAM 역할을 생성합니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RegistryPublisherPermission",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:ListRegistries",
        "bedrock-agentcore:GetRegistry",
        "bedrock-agentcore:CreateRegistryRecord",
        "bedrock-agentcore:ListRegistryRecords",
        "bedrock-agentcore:GetRegistryRecord",
        "bedrock-agentcore:DeleteRegistryRecord",
        "bedrock-agentcore:UpdateRegistryRecord",
        "bedrock-agentcore:SubmitRegistryRecordForApproval"
      ],
      "Resource": ["*"]
    }
  ]
}
```

> 참고: 게시자는 `CreateRegistry`, `DeleteRegistry`를 수행하거나 레코드를 승인/거부할 수 없습니다. 이러한 작업은 관리자만 수행할 수 있습니다.

---

### 5. 게시자 역할을 수임하기 위한 IAM 신뢰 정책

게시자 IAM 역할을 수임하려면 IAM 사용자에게 `sts:AssumeRole` 권한이 부여되어야 하며, 대상 역할의 신뢰 정책에서 사용자를 보안 주체로 허용해야 합니다. 설정 지침은 AWS 설명서의 [신뢰 정책 구성 방법](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user.html) 및 [역할 수임 방법](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use.html)을 참조하세요.

---

## 다음 단계

사전 요구 사항을 충족하면 게시자 워크플로용 **AWS Agent Registry** Kiro Power를 사용할 준비가 된 것입니다.

---

## 샘플 프롬프트

> 팁: 하나의 Kiro IDE 세션에서 작업하는 경우 매번 레지스트리 이름을 언급할 필요가 없습니다. Kiro가 컨텍스트를 통해 이름을 기억합니다.

1. "List all registries in my account in the us-west-2 region"
2. "Show me the list of records in registry `<REGISTRY-NAME>`"
3. "Create a new MCP server record in registry `<REGISTRY-NAME>` for my `<YOUR-TOOL>`"
4. "Create an A2A agent card record for my `<YOUR-AGENT>` in registry `<REGISTRY-NAME>`"
5. "Show all records in `PENDING_APPROVAL` state"
6. "Submit all records in `DRAFT` status for approval in registry `<REGISTRY-NAME>`"
7. "Show me the details of record `<RECORD-ID>`"
8. "Update the description of record `<RECORD-ID>` in registry `<REGISTRY-NAME>`"
9. "Delete all records in registry `<REGISTRY-NAME>`"
