# AWS Agent Registry를 사용하여 런타임에 도구 및 에이전트 검색

## 개요

이 튜토리얼에서는 하드코딩된 통합 없이 **AWS Agent Registry** 시맨틱 검색을 통해 런타임에 도구와 에이전트를 검색하고 동적으로 호출하는 자율 에이전트를 보여 줍니다.

오케스트레이터 에이전트는 다음과 같은 3단계 검색 패턴을 따릅니다.

1. **검색**: 자연어로 레지스트리를 검색하여 관련 MCP 서버 및 A2A 에이전트를 찾습니다.
2. **인스턴스화**: Amazon Bedrock AgentCore Gateway MCP 서버용 `MCPClient`와 A2A 에이전트용 `@tool` 래퍼를 사용하여 실시간 연결을 생성합니다.
3. **실행**: 동적으로 검색한 기능만 사용하여 사용자의 요청을 실행합니다.

### 레지스트리 기반 검색

기존 에이전트 시스템에서는 빌드할 때 통합을 하드코딩합니다. **AWS Agent Registry**는 이 방식을 뒤집습니다. MCP 서버와 에이전트가 자세한 설명과 함께 카탈로그에 자신을 등록하면, 런타임에 오케스트레이터가 자연어로 카탈로그를 검색하여 필요한 항목을 찾습니다. 재배포하지 않아도 새로운 기능을 즉시 사용할 수 있습니다.

![AWS Agent Registry 사용 여부 비교](images/With_Vs_Without_AWS_Agent_Registry.png)

### 사용 사례: 주문 관리 및 고객 서비스

오케스트레이터 에이전트는 다음 항목을 동적으로 검색하여 고객의 주문 관련 작업을 지원합니다.
- 주문 데이터 검색(상태 확인, 주문 업데이트)을 위한 **MCP 서버**
- 비즈니스 로직 추론(가격/할인, 반품/환불)을 위한 **A2A 에이전트**

### 튜토리얼 세부 정보

| 정보 | 세부 정보 |
|:---|:---|
| 튜토리얼 유형 | 에이전트 기반 검색 및 멀티 에이전트 오케스트레이션 |
| AgentCore 구성 요소 | AWS Agent Registry, Amazon Bedrock AgentCore Gateway, Amazon Bedrock AgentCore Runtime |
| 에이전트 프레임워크 | Strands Agents |
| Gateway 대상 유형 | AWS Lambda |
| 인바운드 인증 | OAuth2(Amazon Cognito를 통한 Custom JWT) |
| 아웃바운드 인증 | Gateway IAM 역할 |
| LLM 모델 | Anthropic Claude Sonnet 4.6 |
| 튜토리얼 구성 요소 | AWS Agent Registry, Amazon Bedrock AgentCore Gateway(MCP/OAuth2), Amazon Bedrock AgentCore Runtime(A2A/SigV4), AWS Lambda, Amazon Cognito |
| 튜토리얼 분야 | 여러 분야에 적용 가능(주문 관리 및 고객 서비스) |
| 예제 난이도 | 고급 |
| 사용 SDK | boto3 |

## 튜토리얼 아키텍처

![주문 관리 AWS Agent Registry 흐름](images/OrderManagement_AWS_Agent_Registry_Flow.png)

오케스트레이터는 요청이 들어올 때마다 레지스트리를 검색하고 결과에서 도구를 인스턴스화한 후 실행합니다. 이 모든 과정은 하드코딩된 통합 없이 런타임에 이루어집니다.

### 오케스트레이터 에이전트 흐름

![오케스트레이터 에이전트 흐름](images/orchestrator_agent_flow_v3.png)

오케스트레이터는 Amazon Bedrock AgentCore Runtime에 배포됩니다. 요청이 들어올 때마다 레지스트리에서 기능을 **검색**하고, 해당 기능에 **연결**한 다음(MCP는 Amazon Bedrock AgentCore Gateway, A2A는 Amazon Bedrock AgentCore Runtime 사용), 검색된 도구만으로 생성한 Strands Agent를 사용하여 **실행**하는 3단계를 진행합니다.

## 튜토리얼 주요 기능

- **시맨틱 검색**: 레지스트리 검색은 이름이 아니라 의미로 기능을 찾습니다. 예를 들어 이름에 해당 단어가 정확히 없어도 "return refund"는 Customer Support Agent와 일치합니다.
- **동적 오케스트레이션**: 하드코딩된 통합 없이 에이전트가 런타임에 도구 세트를 구성합니다.
- **혼합 프로토콜**: 하나의 에이전트에서 MCP 서버(Amazon Bedrock AgentCore Gateway 경유)와 A2A 에이전트(Amazon Bedrock AgentCore Runtime 경유)를 사용합니다.
- **OAuth2 + SigV4**: Amazon Bedrock AgentCore Gateway는 Amazon Cognito JWT 인증을 사용하고, Amazon Bedrock AgentCore Runtime은 IAM SigV4 서명을 사용합니다.
- **프로토콜 독립적 검색**: 한 번의 AWS Agent Registry 검색으로 MCP 서버와 A2A 에이전트를 모두 반환합니다.
- **엔드 투 엔드 수명 주기**: 모든 인프라를 생성하고 데모를 실행한 후 정리합니다.

## 사전 요구 사항

- **Amazon SageMaker 노트북 인스턴스**: 권장 구성:
  - 플랫폼: **Amazon Linux 2**
  - 노트북 환경: **JupyterLab 4**(`notebook-al2-v3`)
  - 커널: **conda_python3**
  - 인스턴스 유형: `ml.t3.xlarge` 이상
- Amazon Bedrock 모델(Claude Sonnet 4.6) 액세스 권한이 있는 AWS 계정
- 필수 권한이 있고 노트북 인스턴스에 연결된 IAM 역할(아래 참조)
- Python 3.10+
- boto3 >= 1.42.87

<a id="required-iam-permissions"></a>

### 필수 IAM 권한

이 튜토리얼에서는 여러 AWS 서비스의 리소스를 생성하고 관리합니다. 다음 IAM 정책을 SageMaker 노트북 인스턴스의 실행 역할에 연결하세요.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockAgentCoreAccess",
            "Effect": "Allow",
            "Action": "bedrock-agentcore:*",
            "Resource": "*"
        },
        {
            "Sid": "BedrockModelInvocation",
            "Effect": "Allow",
            "Action": "bedrock:InvokeModel",
            "Resource": "*"
        },
        {
            "Sid": "LambdaManagement",
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:DeleteFunction",
                "lambda:GetFunction",
                "lambda:InvokeFunction",
                "lambda:AddPermission"
            ],
            "Resource": "arn:aws:lambda:*:*:function:*"
        },
        {
            "Sid": "CognitoManagement",
            "Effect": "Allow",
            "Action": [
                "cognito-idp:CreateUserPool",
                "cognito-idp:CreateUserPoolClient",
                "cognito-idp:CreateResourceServer",
                "cognito-idp:CreateUserPoolDomain",
                "cognito-idp:DeleteUserPool",
                "cognito-idp:DeleteUserPoolDomain",
                "cognito-idp:DescribeUserPoolClient"
            ],
            "Resource": "*"
        },
        {
            "Sid": "IAMRoleManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies",
                "iam:PassRole"
            ],
            "Resource": "arn:aws:iam::*:role/*"
        },
        {
            "Sid": "ECRManagement",
            "Effect": "Allow",
            "Action": [
                "ecr:CreateRepository",
                "ecr:DeleteRepository",
                "ecr:GetAuthorizationToken",
                "ecr:BatchDeleteImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:BatchCheckLayerAvailability"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CodeBuildManagement",
            "Effect": "Allow",
            "Action": [
                "codebuild:CreateProject",
                "codebuild:UpdateProject",
                "codebuild:StartBuild",
                "codebuild:BatchGetBuilds"
            ],
            "Resource": "arn:aws:codebuild:*:*:project/bedrock-agentcore-*"
        },
        {
            "Sid": "SecretsManagerManagement",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:CreateSecret",
                "secretsmanager:GetSecretValue",
                "secretsmanager:DeleteSecret"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:*"
        },
        {
            "Sid": "S3CodeBuildArtifacts",
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:PutBucketLifecycleConfiguration",
                "s3:PutObject",
                "s3:GetObject",
                "s3:GetBucketLocation"
            ],
            "Resource": "arn:aws:s3:::bedrock-agentcore-*"
        },
        {
            "Sid": "STSAccess",
            "Effect": "Allow",
            "Action": "sts:GetCallerIdentity",
            "Resource": "*"
        },
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/*"
        }
    ]
}
```

> **참고:** 이 정책은 최소 권한 원칙을 따르며 이 튜토리얼에서 생성하는 리소스로 범위가 제한됩니다. 위 JSON을 복사하여 SageMaker 노트북 인스턴스의 실행 역할에 인라인 정책으로 연결하세요.

## 튜토리얼 개요

| 노트북 | 설명 |
|:---|:---|
| [discovery-and-invocation-at-runtime.ipynb](discovery-and-invocation-at-runtime.ipynb) | 인프라 배포, 레지스트리 생성, 레코드 등록, 오케스트레이터 배포, 라이브 데모 3개 실행 및 정리를 다루는 엔드 투 엔드 튜토리얼 |

### 노트북 구성

튜토리얼은 5개의 주요 단계로 구성됩니다.

**1단계: 인프라 배포**: 레지스트리에 등록할 모든 백엔드 리소스를 생성합니다.
- **MCP 서버(Amazon Bedrock AgentCore Gateway 경유):** AWS Lambda에서 지원하고 Amazon Cognito OAuth2를 통해 인증하는 `get_order_status` 및 `update_order` 도구
- **A2A 에이전트(Amazon Bedrock AgentCore Runtime 경유):** IAM SigV4를 통해 인증하고 Docker 컨테이너로 실행하는 Pricing Agent 및 Customer Support Agent

**2단계: 레지스트리 생성 및 레코드 등록**: `autoApproval: False`를 사용하는 AWS Agent Registry를 생성하고 레코드 3개(MCP 1개, A2A 2개)를 등록한 후 2단계 워크플로(DRAFT → PENDING_APPROVAL → APPROVED)를 통해 승인하고 시맨틱 검색을 검증합니다.

**3단계: 오케스트레이터 에이전트 배포**: `discover_and_execute`를 사용하여 레지스트리를 검색하고 메타데이터를 실시간 연결로 파싱한 후 사용자의 요청을 실행하는 오케스트레이터 에이전트를 Amazon Bedrock AgentCore Runtime에 배포합니다.

**4단계: 엔드 투 엔드 데모**: 서로 다른 도구 조합을 보여 주는 세 가지 시나리오입니다.
1. **주문 상태**: MCP 서버만 호출
2. **가격 및 할인**: MCP + A2A 멀티 에이전트 협업
3. **반품 및 환불**: A2A 에이전트를 사용한 Customer Support 의사 결정

**5단계: 정리**: 생성 역순으로 모든 리소스를 삭제합니다.

## 시작하기

1. 위 권장 구성으로 **Amazon SageMaker 노트북 인스턴스를 생성**합니다. [필수 IAM 권한](#required-iam-permissions)에 나열된 정책을 포함하는 IAM 역할을 연결합니다.

2. 인스턴스가 **InService** 상태가 되면 **Open JupyterLab**을 클릭합니다.

3. 다음 **모든 파일을 업로드**하여 노트북의 홈 디렉터리에 저장합니다.
   - `discovery-and-invocation-at-runtime.ipynb`
   - `utils.py`
   - `cleanup.py`
   - `images/` 폴더(모든 PNG 파일)

4. `discovery-and-invocation-at-runtime.ipynb`를 열고 **conda_python3** 커널을 선택합니다.

5. 셀을 순서대로 실행합니다. 노트북에서 모든 종속성(boto3 >= 1.42.87 포함)을 설치하고 인프라를 배포하며, 레지스트리를 생성하고 채운 후 오케스트레이터를 배포하고 세 가지 라이브 데모를 실행한 다음 리소스를 정리합니다.

## 리소스

- [AgentCore 샘플 리포지토리](https://github.com/awslabs/agentcore-samples)
- [Amazon Bedrock AgentCore 설명서](https://docs.aws.amazon.com/bedrock-agentcore/latest/userguide/)
- [Amazon Bedrock AgentCore Gateway 튜토리얼](https://github.com/awslabs/agentcore-samples/tree/main/06-workshops/02-AgentCore-gateway)
- [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
