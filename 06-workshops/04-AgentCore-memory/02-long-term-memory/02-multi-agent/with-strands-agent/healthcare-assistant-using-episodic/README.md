# Episodic Memory를 사용하는 Multi-Agent 의료 시스템

Episodic Memory는 의미 있는 상호 작용의 일부를 캡처합니다. 중요한 순간을 식별하고 간결하고 체계적인 레코드로 요약하여 불필요한 정보 없이 필요한 내용에 집중해 검색할 수 있도록 합니다.

Reflection은 에피소드를 분석하여 인사이트, 패턴, 결론을 도출합니다. 시스템이 이벤트의 중요성과 향후 동작에 미칠 영향을 이해하도록 도와 경험을 실행 가능한 지침으로 전환합니다.

Amazon Bedrock AgentCore Memory를 사용하여 **Episodic Memory를 활용한 Multi-Agent 조정**을 보여 주는 포괄적인 예제입니다. 이 튜토리얼에서는 AI Agent가 과거 상호 작용에서 학습하고 시간에 따라 의사 결정을 개선하는 방법을 설명합니다.

## 개요

이 튜토리얼에서는 다음 Agent로 구성된 의료 도우미 시스템을 소개합니다.
- **Supervisor Agent**: 환자 질문을 전문 Agent로 라우팅
- **Claims Agent**: 보험 청구 및 비용 청구 쿼리 처리
- **Demographics Agent**: 환자 인구 통계 정보 관리
- **Medication Agent**: 의약품 및 처방 쿼리 처리

각 Agent는 **메모리 분기**를 통해 격리된 단기 메모리를 유지하면서 **Episodic Memory 전략**을 통해 장기 인사이트를 공유합니다.

## 아키텍처
<div style="text-align:left">
    <img src="architecture.png" width="75%" />
</div>

## 메모리 전략

### Episodic 전략

시스템은 다음 구성의 Episodic Memory 전략을 사용합니다.

**추출**: 대화 이벤트를 구조화된 에피소드로 변환
- Prompt: "Extract patient interactions with healthcare agents"
- Namespace: `healthcare/{actorId}/{sessionId}/`

**통합**: 관련 에피소드 병합
- Prompt: "Consolidate healthcare conversations"

**Reflection**: 세션 간 인사이트 생성
- Prompt: "Generate insights from patient care patterns"
- Namespace: `healthcare/{actorId}/` (정확한 namespace 접두사)

### 메모리 분기

각 Agent는 자체 메모리 분기에서 작동합니다.
- `main`: Supervisor Agent의 라우팅 결정
- `claims_agent`: 보험 및 비용 청구 대화
- `demographics_agent`: 환자 정보 업데이트
- `medication_agent`: 처방 논의

**이점:**
- Agent는 서로의 대화를 볼 수 없음
- 명확한 관심사 분리
- 모든 Agent가 공유 장기 메모리에 기여
- 모든 상호 작용에 걸친 환자 수준의 인사이트 제공

## 사전 요구 사항

### AWS 서비스
- **Amazon Bedrock**: Claude Sonnet 4 모델 액세스 권한
- **Amazon Bedrock AgentCore Memory**: Episodic Memory 전략에 사용
- **Amazon HealthLake**(선택 사항): 환자 데이터가 포함된 FHIR 데이터 저장소
  - 설정 중 Synthea 데이터로 새 데이터 저장소 생성 가능
  - 또는 기존 데이터 저장소 사용

### IAM 권한
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "healthlake:DescribeFHIRDatastore",
        "healthlake:CreateFHIRDatastore",
        "healthlake:ReadResource",
        "healthlake:SearchWithGet"
      ],
      "Resource": "*"
    }
  ]
}
```

### Python 환경
- Python 3.10+
- Jupyter Notebook 또는 JupyterLab

## 설치

1. 종속성을 설치합니다.
```bash
pip install -r requirements.txt
```

2. AWS 자격 증명을 구성합니다.
```bash
aws configure
```

## 사용법

### 빠른 시작

1. 노트북을 엽니다.
```bash
jupyter notebook healthcare-data-assistant.ipynb
```

2. 셀을 순서대로 실행합니다.
   - **1단계**: 환경 설정
   - **2단계**: HealthLake 데이터 저장소 구성
   - **3단계**: Episodic Strategy를 사용하는 장기 메모리 도구로 Memory 생성
   - **4단계**: 단기 메모리 분기를 지원하는 Memory Hook Provider 생성
   - **5단계**: 메모리 분기를 사용하는 Multi-Agent 의료 아키텍처 생성
   - **6단계**: 대화형 채팅으로 테스트
   - **7단계**: 의료 메모리 분기 검사
   - **8단계**: 장기 메모리(에피소드 및 reflection) 검증

### 대화형 입력

노트북에서 다음 정보를 입력하라는 메시지가 표시됩니다.
- **HealthLake 데이터 저장소 ID**: 기존 데이터 저장소를 사용하거나 Synthea 데이터로 새 저장소 생성(실제 환자 정보는 사용하지 않음)
- **HealthLake 리전**: HealthLake를 위한 AWS 리전

### 시스템 테스트

대화형 채팅(7단계)에서 다음 작업을 수행할 수 있습니다.
- 보험 청구 관련 질문
- 인구 통계 정보 요청
- 의약품 및 처방 쿼리
- Supervisor 라우팅 동작 확인
- 메모리 분기 관찰

질문 예시:
```
You: What's the status of my insurance claim?
You: Can you tell me about my medications?
You: What's my current address on file?
```

채팅 세션을 종료하려면 `quit`, `exit` 또는 `q`를 입력합니다.

## Memory Browser 통합

노트북을 실행한 후 Memory Browser를 사용해 메모리를 시각화할 수 있습니다.

1. 구성 요약에서 Memory ID를 확인합니다.
2. [Memory Browser](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/06-workshops/04-AgentCore-memory/03-advanced-patterns/04-memory-browser)를 엽니다. `http://localhost:8000`에서 메모리 이벤트, 에피소드, reflection을 시각화하고 탐색할 수 있습니다.
3. Memory ID를 입력해 다음 항목을 탐색합니다.
   - **단기 메모리**: 분기별 이벤트
   - **에피소드**: 세션 수준의 통합 메모리
   - **Reflection**: 환자 수준의 인사이트

**⏱️ 참고**: 대화가 끝난 후 에피소드와 reflection을 생성하는 데 10~15분이 걸립니다. 에피소드/reflection이 즉시 나타나지 않으면 잠시 후 다시 확인하세요.

## 주요 개념

### 1. Multi-Agent 조정
- 라우팅을 위한 Supervisor 패턴
- 도메인 전문성을 갖춘 전문 Agent
- 실시간 데이터를 위한 동적 도구 사용

### 2. 메모리 분기
- Agent별로 격리된 대화
- 분기별 이벤트 저장
- 공유 세션 맥락

### 3. Episodic Memory
- 추출, 통합, reflection prompt
- 세션 수준 에피소드
- 환자 수준 reflection

### 4. HealthLake 통합
- 동적 FHIR 쿼리
- 실시간 환자 데이터 액세스
- 모든 데이터는 Synthea에서 생성한 합성 데이터이며 실제 환자 정보는 사용하지 않음

## 사용자 지정

### 새 Agent 추가

```python
@tool
def get_patient_allergies(patient_id: str = PATIENT_ID) -> dict:
    """Get patient allergies from HealthLake"""
    return query_healthlake('AllergyIntolerance', {'patient': patient_id})

allergy_agent = Agent(
    model="global.anthropic.claude-sonnet-4-20250514-v1:0",
    system_prompt="You handle patient allergies. Use get_patient_allergies tool.",
    tools=[get_patient_allergies]
)
```

### 다른 모델 사용

Agent 생성 시 `model` 파라미터를 변경합니다.
```python
Agent(
    model="anthropic.claude-3-5-sonnet-20241022-v2:0",  # 다른 모델
    system_prompt="...",
    tools=[...]
)
```
## 추가 리소스

- [Episodic Memory 모범 사례](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html#memory-episodic-retrieve-episodes) - Agent 성능을 개선하기 위해 에피소드를 검색하는 방법


## 문제 해결

### 분기 생성 오류
"Branch rootEventId is required when creating a branch"가 표시되는 경우:
- **Jupyter kernel을 다시 시작합니다**(Kernel → Restart).
- 수정된 `HealthcareMemoryHooks` 클래스를 다시 로드하도록 처음부터 **모든 셀을 다시 실행합니다**.
- 이 수정 사항은 전문 Agent 분기를 생성하기 전에 main 분기에 초기 이벤트가 존재하도록 보장합니다.

### Memory Hook 오류
"MemorySession.add_turns() got an unexpected keyword argument 'branch_name'"이 표시되는 경우:
- 노트북이 캐시된 이전 코드를 사용하고 있음을 의미합니다.
- **Kernel을 다시 시작하고** 모든 셀을 다시 실행하여 API 수정 사항을 적용합니다.
- 수정된 코드는 `branch={"name": branch_name}` 형식을 사용합니다.

### 모델을 사용할 수 없음
"serviceUnavailableException"이 표시되면 다음 사항을 확인하세요.
- global inference profile 사용: `global.anthropic.claude-sonnet-4-20250514-v1:0`
- 또는 사용 중인 리전의 리전별 profile 사용

### HealthLake 액세스 거부
IAM 권한에 다음 항목이 포함되어 있는지 확인하세요.
- `healthlake:DescribeFHIRDatastore`
- `healthlake:ReadResource`
- `healthlake:SearchWithGet`

### Memory 생성 실패
다음 사항을 확인하세요.
- IAM role에 Bedrock 호출 권한이 있음


## 정리

튜토리얼을 완료한 후 지속적인 요금이 발생하지 않도록 리소스를 정리할 수 있습니다.

1. 노트북 끝에 있는 **Cleanup** 셀을 실행합니다.
2. 다음 리소스를 삭제할지 묻는 메시지가 표시됩니다.
   - **Memory**: AgentCore Memory 인스턴스
   - **HealthLake 데이터 저장소**: FHIR 데이터 저장소(선택 사항)

필요에 따라 각 리소스를 개별적으로 삭제할 수 있습니다.

### 수동 정리

필요한 경우 리소스를 수동으로 삭제할 수도 있습니다.

```bash
# Memory 삭제
aws bedrock-agentcore-cp delete-memory --memory-id <MEMORY_ID> --region us-east-1

# HealthLake datastore 삭제
aws healthlake delete-fhir-datastore --datastore-id <DATASTORE_ID> --region <REGION>
```

## 자세히 알아보기

- [AgentCore Memory 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory.html)
- [Strands Agents 가이드](https://strandsagents.com)
- [HealthLake FHIR API](https://docs.aws.amazon.com/healthlake/latest/devguide/working-with-FHIR-healthlake.html)
- [Memory 분기 패턴](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory-branching.html)
