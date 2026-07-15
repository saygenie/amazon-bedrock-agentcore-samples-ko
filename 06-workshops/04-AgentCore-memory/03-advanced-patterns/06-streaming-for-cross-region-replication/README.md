# AgentCore Memory 리전 간 복제

[Amazon Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)에 [메모리 레코드 스트리밍](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-record-streaming.html) 기능을 사용하여 active-passive 리전 간 복제를 구현합니다.

AgentCore Memory는 사용자 선호도, 대화 기록, 추출된 사실 등 AI Agent의 장기 지식을 저장합니다. 이 데이터는 Agent 품질에 매우 중요합니다. Primary 리전에 장애가 발생하면 Agent는 축적된 모든 메모리에 액세스할 수 없게 됩니다. 이 솔루션은 secondary 리전에 거의 실시간으로 복제하여 몇 초 안에 failover할 수 있도록 합니다.

## 아키텍처

![아키텍처](images/architecture.png)

### 작동 방식

1. Primary AgentCore Memory에는 **streaming이 활성화**되어 있습니다. 메모리 레코드가 생성되거나 업데이트될 때마다 이벤트가 Kinesis Data Stream에 게시됩니다.
2. **Lambda consumer**는 Event Source Mapping(ESM)을 통해 Kinesis에서 이벤트를 읽고 디코딩한 다음, secondary 리전의 Memory에서 `BatchCreateMemoryRecords`를 호출합니다.
3. Secondary에서 primary로 다시 스트리밍되는 무한 루프를 방지하기 위해 복제된 레코드는 **`replicated/` namespace 접두사**를 사용합니다. Lambda는 이 접두사가 있는 모든 이벤트를 건너뜁니다.
4. Secondary 리전에는 동일한 인프라(Kinesis, Lambda, IAM)가 모두 미리 배포되어 있지만 **streaming은 OFF** 상태이므로 Lambda는 비용 없이 유휴 상태로 유지됩니다.
5. **Failover**에는 두 번의 API 호출이 필요합니다. Secondary에서 streaming을 활성화하고 primary에서 비활성화하며, 몇 초 안에 완료됩니다.

### 주요 지표

| 지표 | 값 |
|:-------|:------|
| RPO(Recovery Point Objective) | 5~15초 |
| RTO(Recovery Time Objective) | 15~30초 |
| Failover 메커니즘 | `update-memory` API를 통한 streaming 전환 |
| 루프 방지 | `replicated/` namespace 접두사 |
| 충돌 해결 | AgentCore Memory 기본 통합 기능 |

## 사전 요구 사항

- 적절한 권한으로 구성된 AWS CLI v2
- Python 3.10+
- `us-east-1` 및 `us-west-2`의 Amazon Bedrock AgentCore 액세스 권한
- 다음 서비스에 대한 권한: CloudFormation, Kinesis, Lambda, IAM, SQS, DynamoDB, S3

## 빠른 시작

노트북에서 전체 과정을 단계별로 안내합니다.

```bash
jupyter notebook 06-memory-cross-region-replication.ipynb
```

또는 노트북 없이 인프라를 직접 배포합니다.

```bash
bash scripts/deploy.sh us-east-1 us-west-2
```

## 프로젝트 구조

```
├── 06-memory-cross-region-replication.ipynb   # 기본 튜토리얼 - 이 파일 실행
├── README.md
├── requirements.txt                           # boto3>=1.42.63
└── scripts/
    ├── deploy.sh                              # 배포 오케스트레이션
    ├── toggle-streaming.sh                    # Failover 전환
    ├── handler.py                             # Lambda 복제 consumer
    ├── regional-stack.yaml                    # 리전별 CloudFormation
    └── global-stack.yaml                      # DynamoDB Global Table
```

### 파일별 역할

**`06-memory-cross-region-replication.ipynb`** - 독립적으로 실행할 수 있는 튜토리얼 노트북입니다. 인프라를 배포하고 메모리 레코드를 생성하며, 복제를 확인하고, failover/failback을 테스트한 후 리소스를 정리합니다. 사용자는 이 노트북을 따라 진행하면 됩니다.

**`scripts/deploy.sh`** - 전체 최초 배포를 조정합니다.
1. Lambda 함수를 패키징하여 두 리전의 S3에 업로드
2. active 리전 추적을 위한 DynamoDB Global Table 배포
3. 리전별 CloudFormation stack 배포(Kinesis, Lambda, SQS DLQ, IAM role, CloudWatch alarm)
4. AgentCore Memory 인스턴스 생성(primary는 streaming ON, secondary는 OFF)
5. 각 Lambda가 복제 대상을 알 수 있도록 리전 간 Memory ID로 stack 업데이트
6. active 리전으로 DynamoDB 구성 테이블의 초기 데이터 설정

**`scripts/toggle-streaming.sh`** - Memory 인스턴스에서 streaming을 활성화하거나 비활성화합니다. 새로운 active 리전에서 활성화하고 기존 리전에서 비활성화하는 failover 메커니즘입니다. 내부적으로 `update-memory --stream-delivery-resources`를 호출합니다.

**`scripts/handler.py`** - Kinesis stream 이벤트를 소비하고 복제하는 Lambda 함수입니다. 주요 동작은 다음과 같습니다.
- 복제할 수 없는 `StreamingEnabled` 및 `MemoryRecordDeleted` 이벤트 건너뛰기
- 무한 루프를 방지하기 위해 `replicated/` namespace 접두사 확인
- 재시도 시 중복이 생성되지 않도록 결정적 request ID 생성
- 재시도할 수 없는 오류는 SQS DLQ로 전송하고, 재시도 가능한 오류는 ESM 재시도를 위해 발생시킴
- DLQ 쓰기 실패를 기록하되 Lambda가 중단되지 않도록 처리

**`scripts/regional-stack.yaml`** - 각 리전에 배포되는 CloudFormation template입니다. 다음 리소스를 생성합니다.
- Kinesis Data Stream(1 shard, 24시간 보존)
- SQS Dead Letter Queue(14일 보존)
- Memory streaming 및 Lambda 실행을 위한 IAM role
- Kinesis ESM을 사용하는 Lambda 함수(오류 시 이분할, 최대 3회 재시도)
- Lambda 오류, DLQ 깊이, 복제 지연에 대한 CloudWatch alarm

**`scripts/global-stack.yaml`** - 현재 active 상태인 리전을 추적하는 DynamoDB Global Table용 CloudFormation template입니다. 한 번 배포하면 두 리전에 자동으로 복제됩니다.

## 장애 조치(Failover)

```bash
# 장애 조치: primary → secondary
# 복제 공백을 방지하려면 secondary를 먼저 활성화
bash scripts/toggle-streaming.sh enable us-west-2
bash scripts/toggle-streaming.sh disable us-east-1

# 원복: secondary → primary
bash scripts/toggle-streaming.sh enable us-east-1
bash scripts/toggle-streaming.sh disable us-west-2
```

순서가 중요합니다. 항상 기존 경로를 비활성화하기 전에 새 경로를 활성화하세요. 두 리전에서 잠시 streaming이 모두 활성화되더라도 루프 방지 기능이 안전하게 처리합니다.

## 비용

### 고정 비용(항상 실행)

| 리소스 | 비용 | 참고 |
|:---------|:-----|:------|
| Kinesis(1 shard × 2개 리전) | 월 약 $22 | Shard-hour 요금 |
| DynamoDB Global Table | 월 약 $0.25 | 단일 레코드, on-demand |
| CloudWatch Alarm(3개 × 2개 리전) | 월 약 $0.60 | 표준 해상도 |

### 변동 비용(사용량에 비례)

| 리소스 | 비용 |
|:---------|:-----|
| Kinesis PutRecord | 레코드 100만 개당 $0.014 |
| Lambda 호출 | 100만 회당 $0.20 + 실행 시간 |
| AgentCore Memory 쓰기 | 레코드별 요금 |

Secondary의 Kinesis shard는 유휴 상태에서도 월 약 $11의 비용이 발생합니다. 이는 즉각적인 failover 준비 상태를 유지하는 비용입니다.

## 알려진 제한 사항

- 삭제는 복제되지 않음(AgentCore Memory 통합을 통한 원격 정리)
- 업데이트는 새로운 Create로 복제됨(통합 기능이 중복 제거 처리)
- 단일 AWS 계정만 지원(계정 간 복제에는 추가 IAM role 필요)
- 수동 failover(Route 53 health check + Step Functions로 자동화 가능)
- `deploy.sh`는 최초 배포 전용이며, 재배포하려면 먼저 Memory 인스턴스를 삭제해야 함
