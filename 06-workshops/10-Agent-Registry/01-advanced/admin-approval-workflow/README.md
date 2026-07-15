# AWS Agent Registry 관리자 CI/CD 및 승인 워크플로

> [!CAUTION]
> 이 리포지토리에서 제공하는 예제는 실험 및 교육 목적으로만 사용됩니다. 개념과 기법을 보여 주기 위한 것이며 프로덕션 환경에서 직접 사용하도록 설계되지 않았습니다.

## 개요

엔터프라이즈 AI 에이전트 플랫폼에는 검증된 안전한 에이전트와 도구만 프로덕션에 배포되도록 보장하는 거버넌스 제어가 필요합니다. 여러 팀이 공유 레지스트리에 A2A 에이전트, MCP 서버 및 사용자 지정 스킬을 게시하는 경우, 관리자는 제출된 항목이 검색 가능해지기 전에 이를 검토하고 스캔하여 승인하거나 거부할 수 있는 자동화 파이프라인이 필요합니다.

AWS Agent Registry는 레코드가 `DRAFT → PENDING_APPROVAL → APPROVED / REJECTED` 상태로 전환되는 거버넌스 우선 승인 워크플로를 지원합니다. 이 튜토리얼에서는 Amazon EventBridge, AWS Lambda, Amazon DynamoDB, Amazon S3 및 Slack 알림을 사용하여 이 워크플로를 중심으로 자동화된 CI/CD 파이프라인을 구축하고, 관리자에게 간소화된 검토 및 승인 환경을 제공합니다.

![관리자 승인 워크플로 아키텍처](images/admin-flow-architecture.png)

### 작동 방식

게시자가 레지스트리 레코드의 승인을 요청하면 EventBridge 규칙이 CI/CD Lambda 함수를 트리거하여 다음 작업을 수행합니다.

1. Agent Registry 제어 영역에서 **레코드 세부 정보를 가져옵니다**.
2. Agent Registry의 시맨틱 검색 API를 사용하여 **중복 항목을 검색합니다**.
3. Cisco AI Defense A2A Scanner를 사용하여 A2A 에이전트 카드에 **AI 보안 스캔을 실행**하고, 결과를 DynamoDB에 저장하며, HTML 보고서를 S3에 업로드합니다. 이 단계는 A2A 레코드에만 적용됩니다. 스캐너는 A2A 에이전트 카드 분석 전용이므로 MCP 및 CUSTOM 레코드는 이 단계를 건너뜁니다.
4. 레코드 메타데이터, 중복 탐지 결과, 스캔 요약(해당하는 경우) 및 승인/거부 또는 세부 정보 확인용 CLI 명령이 포함된 **Slack 알림을 관리자에게 전송합니다**.

관리자는 알림에 포함된 **AWS CLI** 명령을 사용하여 레코드를 처리할 수 있습니다. AWS CLI 설치 및 구성에 관한 자세한 지침은 [AWS CLI 설명서](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html)를 참조하세요. 또는 [AWS CloudShell](https://aws.amazon.com/cloudshell/)을 사용하면 별도의 설치나 구성 없이 브라우저에서 직접 AWS CLI 명령을 실행할 수 있습니다.


### Slack 알림 예시

![Slack 메시지](images/slack-message.png)

### 페르소나

| 페르소나      | 가능한 작업                                                   | 불가능한 작업                                      |
|:--------------|:--------------------------------------------------------------|:---------------------------------------------------|
| 관리자        | 레지스트리 생성/삭제, 레코드 승인/거부                        | 없음                                               |
| 게시자        | 레코드 생성, 승인 요청, DRAFT 레코드 업데이트                 | 레코드 승인/거부, 레지스트리 생성/삭제             |

### 지원되는 레코드 유형

| 유형     | 설명                                              | 설명자                   |
|:---------|:-------------------------------------------------|:-------------------------|
| MCP      | Model Context Protocol 서버(도구)                 | `server` + `tools`       |
| A2A      | Agent-to-Agent 프로토콜 에이전트                  | `agentCard`              |
| CUSTOM   | 스킬, 사용자 지정 API 리소스 및 기타 항목         | `custom`                 |

## 튜토리얼 세부 정보

| 정보                     | 세부 정보                                                                                         |
|:-------------------------|:-------------------------------------------------------------------------------------------------|
| 튜토리얼 유형            | 대화형                                                                                           |
| AgentCore 구성 요소      | AWS Agent Registry                                                                |
| 레코드 유형              | A2A, MCP, CUSTOM                                                                                 |
| 승인 모드                | 수동(`autoApproval: false`)                                                                      |
| 튜토리얼 구성 요소       | AWS Agent Registry, Amazon EventBridge, AWS Lambda, Amazon API Gateway, Amazon DynamoDB, Amazon S3, Slack Webhooks |
| 보안 스캔                | Cisco AI Defense A2A Scanner(A2A 레코드용)                                                       |
| 튜토리얼 분야            | 여러 분야에 적용 가능(모든 엔터프라이즈 에이전트 거버넌스 워크플로에 적용 가능)                   |
| 예제 난이도              | 중급                                                                                             |
| 사용 SDK                 | boto3                                                                                            |

## 튜토리얼 주요 기능

* 수동 승인 워크플로(`DRAFT → PENDING_APPROVAL → APPROVED / REJECTED`)를 사용하는 거버넌스 우선 Agent Registry
* Agent Registry 레코드 상태가 변경될 때 EventBridge가 트리거하는 자동화된 CI/CD 파이프라인
* Agent Registry 시맨틱 검색을 사용한 중복 탐지
* HTML 보고서 생성 기능을 포함한 A2A 에이전트 카드 AI 보안 스캔
* API Gateway를 통한 원클릭 승인/거부 작업이 포함된 Slack 알림
* CloudFormation을 사용한 전체 코드형 인프라(IaC) 배포

## 사전 요구 사항

- 적절한 권한이 있는 IAM 자격 증명([`IAM_PERMISSIONS.md`](./IAM_PERMISSIONS.md) 참조). Agent Registry 관련 작업 외에 다음 권한이 사용됩니다.

  | 서비스 | 권한 |
  |:--------|:------------|
  | **Amazon S3** | `CreateBucket`, `HeadBucket`, `PutPublicAccessBlock`, `DeleteBucket`, `ListBucket`, `PutObject`, `GetObject`, `DeleteObject` |
  | **AWS CloudFormation** | `CreateStack`, `UpdateStack`, `DeleteStack`, `DescribeStacks`, `CreateChangeSet`, `ExecuteChangeSet`, `DescribeChangeSet`, `DeleteChangeSet` |
  | **AWS Lambda** | `CreateFunction`, `UpdateFunctionCode`, `UpdateFunctionConfiguration`, `GetFunction`, `DeleteFunction`, `PublishLayerVersion`, `DeleteLayerVersion`, `AddPermission`, `RemovePermission` |
  | **AWS IAM** | `CreateRole`, `GetRole`, `DeleteRole`, `PassRole`, `AttachRolePolicy`, `DetachRolePolicy`, `PutRolePolicy`, `DeleteRolePolicy` |
  | **AWS EventBridge** | `PutRule`, `DescribeRule`, `DeleteRule`, `PutTargets`, `RemoveTargets` |
  | **Amazon DynamoDB** | `CreateTable`, `DeleteTable`, `DescribeTable` |
  | **AWS CloudWatch Logs** | `CreateLogGroup`, `CreateLogStream`, `PutLogEvents`, `DeleteLogGroup` |

- `boto3`가 설치된 Python 3.9+
- Python 종속성 설치를 위한 [uv](https://docs.astral.sh/uv/getting-started/installation/) 패키지 관리자
- [수신 웹후크](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)가 구성된 Slack 워크스페이스. 웹후크 URL과 채널 이름을 기록해 두세요.
- 기본 리전(`us-west-2`)이 구성된 AWS CLI

## 생성되는 AWS 리소스

CloudFormation 스택(`cfn_eventbridge.yaml`)은 다음 리소스를 배포합니다.

| 리소스                          | 유형                              | 용도                                                       |
|:--------------------------------|:----------------------------------|:-----------------------------------------------------------|
| CI/CD Lambda                    | `AWS::Lambda::Function`           | Agent Registry 상태 변경을 처리하고 스캔을 실행하며 Slack 알림 전송 |
| EventBridge 규칙                | `AWS::Events::Rule`               | `PENDING_APPROVAL` 상태 변경 시 CI/CD Lambda 트리거        |
| DynamoDB 테이블                 | `AWS::DynamoDB::Table`            | 레코드별 AI 스캔 결과 및 메타데이터 저장                   |
| S3 버킷                         | (`deploy.sh`에서 자동 생성)       | Lambda 계층 zip 및 AI 스캔 HTML 보고서 저장                |
| Lambda 계층                     | `AWS::Lambda::LayerVersion`       | Cisco AI A2A Scanner 종속성 패키징                          |
| IAM 역할                        | `AWS::IAM::Role`                  | Lambda 함수의 실행 역할                                    |

## 단계별 지침

단계별 지침은 다음 노트북을 참조하세요.

- [EventBridge를 사용한 관리자 승인 워크플로](admin-approval-workflow-notebook.ipynb)
