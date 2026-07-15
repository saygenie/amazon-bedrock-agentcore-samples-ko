# AWS Agent Registry와 메타데이터 동기화

## 개요

MCP 및 A2A 서버 메타데이터를 AWS Agent Registry와 동기화하는 방법에는 풀 기반 방식과 푸시 기반 방식이 있습니다.

풀 기반 방식에서는 레지스트리가 기반 서버에 연결하여 메타데이터를 직접 가져옵니다. 이 방식에서는 레지스트리가 각 서버의 데이터 계층에 액세스할 수 있는 자격 증명을 보유해야 합니다. 이러한 자격 증명은 만료될 수 있으며, 보안 측면에서 레지스트리와 공유하는 것이 바람직하지 않을 수 있습니다.

푸시 기반 방식에서는 서버가 변경될 때마다 개발자가 메타데이터를 레지스트리로 푸시합니다. 레지스트리가 기반 리소스에 직접 액세스할 필요가 없으므로 자격 증명을 안전하게 보호할 수 있습니다. 또한 게시되는 항목을 더 효과적으로 제어할 수 있는 거버넌스 파이프라인을 사용할 수 있습니다. 다만 일반적으로 CloudTrail 이벤트를 통해 변경 사항을 모니터링해야 하며, 개발자가 이벤트 처리를 놓치면 레지스트리의 동기화가 어긋날 수 있습니다.

이 노트북에서는 메타데이터 동기화의 푸시 기반 방식에 중점을 둡니다. Amazon EventBridge를 통해 `UpdateAgentRuntime` CloudTrail 이벤트를 수신하는 Lambda 함수를 배포합니다. 이 함수는 MCP 서버에 연결하여 현재 도구를 검색하고, 추가되거나 제거되거나 수정된 도구가 있으면 해당 레지스트리 레코드를 업데이트합니다. OAuth 자격 증명은 AgentCore Identity를 통해 안전하게 관리되므로 Lambda 환경 변수에 클라이언트 보안 암호를 저장할 필요가 없습니다.

이 솔루션은 단일 계정 및 교차 계정 아키텍처를 모두 지원합니다.

Lambda는 도구 변경 사항을 탐지하고 푸시하는 비즈니스 로직을 처리합니다. 노트북에는 레지스트리를 생성하고 MCP 서버 레코드를 등록하는 단계가 포함되어 있지만, 레지스트리가 이미 설정되어 있으면 이러한 단계를 별도로 수행할 수도 있습니다.
버전 관리 및 승인 동작에 관한 자세한 내용은 [알려진 제한 사항](#known-limitations) 섹션을 참조하세요.

## 사전 요구 사항

- Lambda 함수, IAM 역할 및 EventBridge 규칙을 생성할 권한이 있는 IAM 자격 증명을 갖춘 AWS 계정. 필수 AWS Agent Registry 기능을 허용하는 정책도 필요합니다.
- 인증을 위해 Cognito OAuth가 구성되고 AgentCore Runtime에 배포된 MCP 서버
- 노트북은 Agent Registry와 그 안의 MCP 서버 레코드 생성을 지원합니다. 레지스트리 또는 MCP 레코드가 이미 있으면 해당 셀을 건너뛸 수 있습니다.
- boto3가 설치된 Python 3.10+(노트북에서 `requirements.txt`를 통해 설치 처리)
- 교차 계정 설정의 경우 계정 A와 계정 B 모두에 대해 구성된 AWS CLI 프로파일

## 아키텍처

![아키텍처 다이어그램](architecture.png)

다이어그램은 계정 B의 AgentCore Runtime 업데이트에서 시작하여 EventBridge가 계정 A로 이벤트를 전달하는 엔드 투 엔드 이벤트 흐름을 보여 줍니다. 계정 A에서는 Lambda 함수가 MCP 서버에 도구를 쿼리하고 일치하는 레지스트리 레코드를 업데이트합니다. 단일 계정 배포에서는 교차 계정 전달 단계를 건너뛰고 이벤트가 계정 A 내에서 직접 흐릅니다.

이 솔루션에는 두 가지 유형의 AWS 계정이 사용됩니다.

- **계정 A(레지스트리 계정)**는 AWS Agent Registry, EventBridge 규칙, 푸시 동기화 Lambda 함수 및 CloudWatch Logs를 소유합니다.
- **계정 B(MCP 서버 계정)**는 MCP 서버 Runtime과 인증에 사용되는 Cognito OAuth 공급자를 호스팅합니다.

단일 계정 배포에서는 모든 리소스가 계정 A에 있으며 교차 계정 전달 단계가 필요하지 않습니다.

### 구성 요소

이 솔루션에서는 다음 AWS 서비스를 사용합니다.

- **CloudTrail**은 두 계정에서 `UpdateAgentRuntime` API 호출을 캡처합니다.
- **EventBridge**는 이벤트를 Lambda 함수로 라우팅합니다. 교차 계정 설정에서는 계정 B가 계정 A의 기본 이벤트 버스로 이벤트를 전달합니다.
- **Lambda**는 이벤트를 처리하고 MCP 서버에 도구를 쿼리한 후 레지스트리를 업데이트합니다.
- **AWS Agent Registry**는 도구 스키마와 함께 MCP 서버 레코드를 저장합니다.
- **AgentCore Identity**는 워크로드 자격 증명과 자격 증명 공급자를 통해 OAuth 자격 증명을 안전하게 관리하여 Lambda 환경 변수에 보안 암호를 저장할 필요가 없도록 합니다.
- **Amazon Cognito**는 각 계정에서 MCP 서버 인증을 위한 OAuth 공급자 역할을 합니다.

## 자세한 교차 계정 흐름

다음은 계정 B의 MCP 서버가 업데이트되어 계정 A의 레지스트리를 동기화해야 할 때의 엔드 투 엔드 흐름입니다.

### 1단계: 이벤트 생성(계정 B)
1. 개발자가 `agentcore launch`를 통해 MCP 서버를 배포하거나 업데이트합니다.
2. AgentCore가 `UpdateAgentRuntime` API를 호출합니다.
3. CloudTrail이 API 호출을 관리 이벤트로 기록합니다(전달 지연 약 5분). CloudTrail 데이터 이벤트는 활성화할 필요가 없습니다.
4. 이벤트가 계정 B의 기본 EventBridge 버스로 전달됩니다.

### 2단계: 이벤트 전달(계정 B → 계정 A)
5. EventBridge 규칙 `forward-runtime-updates`가 이벤트와 일치합니다.
6. EventBridge가 계정 B의 `EventBridgeForwardRole`을 수임합니다.
7. 이벤트가 계정 A의 기본 EventBridge 버스로 전달됩니다.
8. 계정 A가 리소스 기반 정책을 통해 이벤트를 수락합니다.

### 3단계: Lambda 트리거(계정 A)
9. 계정 A의 EventBridge 규칙이 이벤트와 일치합니다.
10. `registry-push-sync-lambda`가 호출됩니다.

### 4단계: MCP 서버 쿼리(Lambda → 계정 B)
11. `agentRuntimeArn`을 `detail.responseElements`에서 추출합니다.
12. ARN을 파싱하여 소스 계정을 식별합니다.
13. ARN에서 MCP 서버 호출 URL을 구성합니다.
14. AgentCore Identity에서 워크로드 액세스 토큰을 받습니다.
15. 자격 증명 공급자에서 OAuth Bearer 토큰을 가져옵니다(M2M 흐름).
16. MCP 서버의 `initialize` → `tools/list`를 호출합니다.

### 5단계: 레지스트리 비교 및 업데이트(계정 A)
17. 레지스트리의 모든 레코드를 나열합니다.
18. 각 APPROVED 레코드에 대해 `server.inlineContent`에 Runtime ARN이 포함되어 있는지 확인합니다.
19. 일치하는 레코드의 `tools.inlineContent`에서 기존 도구를 추출합니다.
20. 두 도구 목록을 정규화합니다(이름순 정렬, 이름/설명/inputSchema 비교).
21. 동일하면 업데이트를 건너뜁니다.
22. 다르면 차이점을 기록하고 레지스트리 레코드를 업데이트합니다.

## 설정 가이드

`deploy_lambda_push_sync.ipynb` 노트북을 사용하여 모든 리소스를 배포할 수 있습니다. 각 섹션은 이전 섹션을 기반으로 하므로 셀을 순서대로 실행해야 합니다.

| 노트북 섹션 | 수행 작업 |
|-----------------|--------------|
| 0. 종속성 설치 | requirements.txt에서 boto3와 botocore를 설치합니다. |
| 1. 구성 | AWS 리전, Lambda 이름, 레지스트리 이름, MCP 서버 세부 정보, 계정별 자격 증명 공급자 이름 및 교차 계정 ID를 설정합니다. |
| 2. 레지스트리 생성 | AWS Agent Registry를 생성하고 READY 상태가 될 때까지 기다립니다. |
| 3. 레지스트리 레코드 생성 | 서버 스키마에 Runtime ARN을 포함하여 MCP 서버용 레지스트리 레코드를 생성합니다. |
| 3.1 레코드 승인 | Lambda가 레코드를 동기화할 수 있도록 DRAFT → PENDING_APPROVAL → APPROVED 상태로 전환합니다. |
| 4. AgentCore Identity 자격 증명 공급자 생성 | Lambda의 워크로드 자격 증명과 각 MCP 서버 계정의 OAuth2 자격 증명 공급자를 생성합니다. |
| 5. Lambda용 IAM 역할 생성 | 레지스트리 액세스, AgentCore Identity 및 Secrets Manager 권한을 가진 Lambda 실행 역할을 생성합니다. |
| 6. Lambda 빌드 및 생성 | `handler.py`를 `boto3`, `botocore`, `requests`와 함께 zip으로 패키징한 다음 Lambda 함수를 생성하거나 업데이트합니다. |
| 7. EventBridge 규칙 생성 | `UpdateAgentRuntime` CloudTrail 이벤트와 일치하고 Lambda 함수를 대상으로 하는 EventBridge 규칙을 생성합니다. |
| 8. 교차 계정 설정(선택 사항) | 계정 B에 계정 A의 버스로 이벤트를 전송할 권한을 부여하고, 계정 B에 전달용 IAM 역할과 EventBridge 규칙을 생성합니다. |
| | **섹션 8이 끝나면 배포가 완료됩니다. 아래 섹션은 선택 사항입니다.** |
| 9. Lambda 테스트 | 합성 CloudTrail 이벤트로 Lambda를 수동 호출합니다. |
| 10. Lambda 로그 확인 | Lambda 함수의 최신 CloudWatch 로그 스트림을 표시합니다. |
| 11. 정리 | 레지스트리, 레코드, 계정 A 리소스, 계정 B 리소스 및 AgentCore Identity 리소스를 비롯해 노트북에서 생성한 모든 리소스를 제거합니다. |

## 리소스 세부 정보

### 계정 A(레지스트리 계정)

#### AgentCore Identity

Lambda 함수는 환경 변수에 클라이언트 보안 암호를 저장하지 않고 OAuth 토큰을 받기 위해 AgentCore Identity를 사용합니다. 다음 두 가지 유형의 리소스가 생성됩니다.

| 리소스 | 설명 |
|----------|-------------|
| 워크로드 자격 증명 | AgentCore Identity 내에서 Lambda 함수를 신뢰할 수 있는 호출자로 나타냅니다(예: `registry-push-sync-agent`). |
| 자격 증명 공급자(계정별) | 토큰 엔드포인트, 클라이언트 ID 및 클라이언트 보안 암호를 포함한 Cognito OAuth 구성을 안전하게 저장합니다. |

#### EventBridge 규칙

`UpdateAgentRuntime` CloudTrail 이벤트와 일치하면 Lambda 함수를 호출하는 EventBridge 규칙이 생성됩니다.

| 설정          | 값                                                                    |
|---------------|-----------------------------------------------------------------------|
| 패턴          | `source: aws.bedrock-agentcore`, `detail-type: AWS API Call via CloudTrail`, `detail.eventName: UpdateAgentRuntime` |
| 대상          | Lambda 함수(선택적으로 CloudWatch Logs 포함)                          |

#### Lambda 함수

Lambda 함수는 다음 구성으로 배포됩니다.

| 설정          | 값                                                                    |
|---------------|-----------------------------------------------------------------------|
| 런타임        | Python 3.12                                                           |
| 핸들러        | `handler.handler`                                                     |
| 메모리        | 128 MB                                                                |
| 제한 시간     | 30초                                                                  |

#### Lambda 환경 변수

Lambda 함수에는 다음 환경 변수가 구성됩니다. 클라이언트 보안 암호는 여기에 저장되지 않고 AgentCore Identity에서 관리됩니다.

| 변수                              | 설명                                                     |
|-----------------------------------|----------------------------------------------------------|
| `REGISTRY_ID`                     | 레코드를 검색하고 업데이트할 레지스트리 ID입니다.        |
| `WORKLOAD_IDENTITY_NAME`          | 이 Lambda의 AgentCore 워크로드 자격 증명 이름입니다.     |
| `CREDENTIAL_PROVIDER_{ACCT_ID}`   | 각 MCP 서버 계정의 AgentCore Identity 자격 증명 공급자 이름입니다. |
| `CREDENTIAL_SCOPE_{ACCT_ID}`      | 각 MCP 서버에 필요한 OAuth 범위입니다(선택 사항).        |

#### Lambda IAM 역할 정책

Lambda 실행 역할에는 다음 권한이 필요합니다.

| 정책                                      | 작업                                                                 |
|-------------------------------------------|----------------------------------------------------------------------|
| 레지스트리 액세스                         | `bedrock-agentcore:ListRegistryRecords`, `bedrock-agentcore:GetRegistryRecord`, `bedrock-agentcore:UpdateRegistryRecord` |
| AgentCore Identity                        | `bedrock-agentcore:GetResourceOauth2Token`, `bedrock-agentcore:GetWorkloadAccessToken` |
| Secrets Manager                           | `secretsmanager:GetSecretValue`(AgentCore Identity가 저장된 자격 증명을 읽는 데 필요) |
| CloudWatch Logs                           | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`   |

#### Lambda 리소스 정책

Lambda 함수의 리소스 정책은 EventBridge 규칙 ARN을 조건으로 `events.amazonaws.com`이 함수를 호출하도록 허용합니다.

#### 이벤트 버스 권한(교차 계정만 해당)

교차 계정 설정에서는 계정 A의 기본 EventBridge 버스에 있는 리소스 기반 정책이 각 MCP 서버 계정의 `events:PutEvents` 호출을 허용합니다.

#### 레지스트리 레코드 요구 사항

Lambda가 레지스트리 레코드를 찾아 업데이트하려면 다음 조건을 충족해야 합니다.

| 요구 사항                  | 세부 정보                                                             |
|----------------------------|-----------------------------------------------------------------------|
| `server.inlineContent`     | Lambda가 레코드를 MCP 서버와 일치시킬 수 있도록 Runtime URL 또는 ARN을 포함해야 합니다. |
| 상태                       | `APPROVED`여야 합니다. Lambda는 DRAFT 상태의 레코드를 건너뜁니다.    |
| 도구 스키마 버전           | `protocolVersion: 2025-06-18`                                         |

### 계정 B(MCP 서버 계정 - 교차 계정만 해당)

교차 계정 이벤트 전달을 활성화하기 위해 계정 B에 다음 리소스가 생성됩니다.

#### EventBridge 전달 규칙

| 설정          | 값                                                                    |
|---------------|-----------------------------------------------------------------------|
| 규칙 이름     | `forward-runtime-updates`                                             |
| 패턴          | 계정 A의 규칙과 동일한 패턴(`UpdateAgentRuntime` CloudTrail 이벤트)   |
| 대상          | 계정 A의 기본 이벤트 버스 ARN                                         |
| 역할          | `EventBridgeForwardRole`                                              |

#### IAM 역할: EventBridgeForwardRole

이 IAM 역할은 계정 B의 EventBridge가 계정 A로 이벤트를 전달하도록 허용합니다.

| 설정          | 값                                                                    |
|---------------|-----------------------------------------------------------------------|
| 신뢰          | `events.amazonaws.com`                                                |
| 정책          | 계정 A의 기본 이벤트 버스 ARN에 대한 `events:PutEvents`               |

#### Cognito

각 MCP 서버 계정에는 클라이언트 자격 증명(M2M) 흐름을 위해 앱 클라이언트가 구성된 Cognito 사용자 풀이 필요합니다. Cognito 구성은 계정 A의 AgentCore Identity 자격 증명 공급자에 저장됩니다.

| 설정          | 값                                                                    |
|---------------|-----------------------------------------------------------------------|
| 흐름          | 클라이언트 자격 증명(M2M)                                             |
| 요구 사항     | 앱 클라이언트와 정의된 범위가 있는 리소스 서버를 포함한 Cognito 사용자 풀 |
| 관리 주체     | 계정 A의 AgentCore Identity 자격 증명 공급자                          |


## 테스트

### 수동 Lambda 호출

합성 CloudTrail 이벤트로 Lambda 함수를 수동 호출하여 엔드 투 엔드 흐름을 검증할 수 있습니다.

```bash
aws lambda invoke \
  --function-name registry-push-sync-lambda \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "detail-type": "AWS API Call via CloudTrail",
    "source": "aws.bedrock-agentcore",
    "detail": {
      "eventName": "UpdateAgentRuntime",
      "awsRegion": "us-west-2",
      "responseElements": {
        "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-west-2:<ACCT_ID>:runtime/<RUNTIME_ID>",
        "status": "UPDATING"
      }
    }
  }' \
  --region us-west-2 \
  /tmp/output.json

cat /tmp/output.json | python3 -m json.tool
```

### Lambda 로그 확인

최신 Lambda 실행 로그를 확인하려면 다음 명령을 실행합니다.

```bash
aws logs tail /aws/lambda/registry-push-sync-lambda --region us-west-2 --since 10m --format short
```

### 빌드 및 배포

`handler.py` 또는 서비스 모델을 변경한 후 Lambda 함수를 다시 배포합니다.

```bash
cd registry-push-sync-lambda
zip -r handler.zip handler.py models/
aws lambda update-function-code \
  --function-name registry-push-sync-lambda \
  --zip-file fileb://handler.zip \
  --region us-west-2
```

<a id="known-limitations"></a>

## 알려진 제한 사항

Lambda 함수는 기존 레지스트리 레코드를 업데이트하지만 새 레코드를 생성하지는 않습니다. MCP 서버의 Runtime ARN이 `server.inlineContent` 필드에 포함된 일치하는 레지스트리 레코드가 레지스트리에 이미 있어야 합니다. 노트북의 섹션 2와 3에서 이를 처리하지만, 해당 단계를 건너뛴 경우 레코드를 수동으로 생성해야 합니다. 일치하는 레코드를 찾지 못하면 동기화를 건너뜁니다.

현재 레코드 버전 관리는 구현되어 있지 않습니다. 도구가 변경되면 Lambda는 변경 특성과 관계없이 기존 레코드를 직접 업데이트합니다. 따라서 도구 설명 업데이트와 같은 사소한 변경이 새 도구 추가, 도구 제거 또는 입력 스키마 변경과 같은 주요 변경과 동일하게 처리됩니다. 향후에는 사소한 버전 변경과 주요 버전 변경을 구분하도록 개선할 수 있습니다. 예를 들어 호환성을 손상하는 변경에는 새 레코드 버전을 생성하고 이전 버전을 사용 중단 처리할 수 있습니다.

Lambda가 레코드를 업데이트하면 레지스트리는 레코드 상태를 자동으로 DRAFT로 되돌립니다. 업데이트된 도구가 소비자에게 표시되기 전에 DRAFT → PENDING_APPROVAL → APPROVED 워크플로를 통한 공식 검토를 거치도록 하기 위한 것입니다. 이 동작은 모든 변경 사항이 거버넌스 검토를 거치도록 설계되었지만, 관리자가 승인할 때까지 도구 업데이트를 즉시 사용할 수 없다는 의미이기도 합니다.

## 문제 해결

다음 표에는 일반적인 문제와 해결 방법이 나와 있습니다.

| 증상                                 | 원인                                     | 해결 방법                                                  |
|--------------------------------------|------------------------------------------|------------------------------------------------------------|
| Lambda가 트리거되지 않음             | CloudTrail 전달 지연(5~15분)             | 기다린 후 EventBridge 지표를 확인합니다.                   |
| Lambda가 트리거되지 않음             | 계정 B 전달 규칙 누락                    | 계정 B에 규칙이 있고 ENABLED 상태인지 확인합니다.          |
| Lambda가 트리거되지 않음             | 계정 A 버스가 계정 B를 허용하지 않음     | 계정 B에 대해 `aws events put-permission`을 실행합니다.    |
| 도구 0개 반환                        | MCP 서버 콜드 스타트                     | 서버를 워밍업하고 다시 시도합니다.                         |
| 일치하는 레코드 없음                 | 서버 스키마에 Runtime ARN 누락            | `server.inlineContent`에 올바른 URL을 포함하여 레코드를 다시 생성합니다. |
| 일치하는 레코드 없음                 | 레코드가 DRAFT 상태                      | DRAFT → PENDING_APPROVAL → APPROVED 워크플로를 통해 레코드를 승인합니다. |
| 인증 오류(secretsmanager)            | Lambda 역할에 Secrets Manager 권한 누락  | Lambda 역할에 `secretsmanager:GetSecretValue`를 추가합니다. |
| 인증 오류(워크로드 토큰)             | Lambda 역할에 Identity 권한 누락         | Lambda 역할에 `bedrock-agentcore:GetWorkloadAccessToken`을 추가합니다. |
| 인증 오류(자격 증명 공급자)          | 계정의 공급자 이름이 잘못됨              | Lambda의 `CREDENTIAL_PROVIDER_{ACCT_ID}` 환경 변수를 확인합니다. |
| 레지스트리 업데이트 실패             | Lambda 역할에 권한 누락                  | Lambda 역할에 `bedrock-agentcore:UpdateRegistryRecord`를 추가합니다. |
| 업데이트가 예상되지만 `no_change` 발생 | 도구가 동일함                          | 도구 이름, 설명 또는 inputSchemas가 실제로 다른지 확인합니다. |
