# 에피소딕 메모리를 활용한 멀티 에이전트 헬스케어 시스템

에피소딕 메모리는 의미 있는 상호작용 조각을 캡처하고, 중요한 순간을 식별하여 노이즈 없이 집중적으로 검색할 수 있도록 압축적이고 체계적인 기록으로 요약합니다.

반영은 에피소드를 분석하여 인사이트, 패턴 및 결론을 도출합니다 - 이벤트가 왜 중요한지, 그리고 향후 행동에 어떻게 영향을 미쳐야 하는지를 시스템이 이해할 수 있도록 도와 경험을 실행 가능한 지침으로 전환합니다.

Amazon Bedrock AgentCore 메모리를 사용한 **에피소딕 메모리를 활용한 멀티 에이전트 조율**을 보여주는 종합 예제입니다. 이 튜토리얼은 AI 에이전트가 과거 상호작용에서 학습하고 시간이 지남에 따라 의사결정을 개선하는 방법을 보여줍니다.

## 개요

이 튜토리얼은 다음을 갖춘 헬스케어 어시스턴트 시스템을 소개합니다:
- **슈퍼바이저 에이전트**: 환자 질문을 전문 에이전트에게 라우팅
- **청구 에이전트**: 보험 청구 및 청구 쿼리 처리
- **인구통계 에이전트**: 환자 인구통계 정보 관리
- **약물 에이전트**: 약물 및 처방 쿼리 처리

각 에이전트는 **메모리 브랜칭**을 통해 격리된 단기 메모리를 유지하면서, **에피소딕 메모리 전략**을 통해 장기 인사이트를 공유합니다.

## 아키텍처
<div style="text-align:left">
    <img src="architecture.png" width="75%" />
</div>

## 메모리 전략

### 에피소딕

시스템은 다음과 같은 에피소딕 메모리 전략을 사용합니다:

**추출**: 대화 이벤트를 구조화된 에피소드로 변환
- 프롬프트: "Extract patient interactions with healthcare agents"
- 네임스페이스: `healthcare/{actorId}/{sessionId}/`

**통합**: 관련 에피소드 병합
- 프롬프트: "Consolidate healthcare conversations"

**반영**: 교차 세션 인사이트 생성
- 프롬프트: "Generate insights from patient care patterns"
- 네임스페이스: `healthcare/{actorId}/` (정확한 네임스페이스 접두사)

### 메모리 브랜칭

각 에이전트는 자체 메모리 브랜치에서 작동합니다:
- `main`: 슈퍼바이저 에이전트 라우팅 결정
- `claims_agent`: 보험 및 청구 대화
- `demographics_agent`: 환자 정보 업데이트
- `medication_agent`: 처방 논의

**이점:**
- 에이전트가 서로의 대화를 볼 수 없음
- 관심사의 깔끔한 분리
- 모든 에이전트가 공유 장기 메모리에 기여
- 환자 수준 인사이트가 모든 상호작용에 걸쳐 적용

## 사전 요구사항

### AWS 서비스
- **Amazon Bedrock**: Claude Sonnet 4 모델 접근
- **Amazon Bedrock AgentCore 메모리**: 에피소딕 메모리 전략용
- **Amazon HealthLake** (선택 사항): 환자 데이터가 있는 FHIR 데이터스토어
  - 설정 중 Synthea 데이터로 새 데이터스토어 생성 가능
  - 또는 기존 데이터스토어 사용

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

1. 종속성 설치:
```bash
pip install -r requirements.txt
```

2. AWS 자격 증명 구성:
```bash
aws configure
```

## 사용법

### 빠른 시작

1. 노트북 열기:
```bash
jupyter notebook healthcare-data-assistant.ipynb
```

2. 셀을 순차적으로 실행:
   - **1단계**: 환경 설정
   - **2단계**: HealthLake 데이터스토어 구성
   - **3단계**: 에피소딕 전략으로 장기 메모리를 위한 메모리를 도구로 생성
   - **4단계**: 단기 메모리를 위한 브랜치 지원이 포함된 메모리 훅 프로바이더 생성
   - **5단계**: 메모리 브랜칭을 활용한 멀티 에이전트 헬스케어 아키텍처 생성
   - **6단계**: 대화형 채팅으로 테스트
   - **7단계**: 헬스케어 메모리 브랜치 검사
   - **8단계**: 장기 메모리 검증 (에피소드 및 반영)

### 대화형 입력

노트북에서 다음을 요청합니다:
- **HealthLake 데이터스토어 ID**: 기존 데이터스토어 또는 Synthea 데이터로 새로 생성 (실제 환자 정보는 사용되지 않음)
- **HealthLake 리전**: HealthLake의 AWS 리전

### 시스템 테스트

대화형 채팅 (6단계)에서 다음을 할 수 있습니다:
- 보험 청구에 대해 질문
- 인구통계 정보 요청
- 약물 및 처방에 대해 쿼리
- 슈퍼바이저 라우팅 동작 관찰
- 메모리 브랜칭 관찰

예제 질문:
```
You: What's the status of my insurance claim?
You: Can you tell me about my medications?
You: What's my current address on file?
```

채팅 세션을 종료하려면 `quit`, `exit` 또는 `q`를 입력하세요.

## 메모리 브라우저 통합

노트북 실행 후 메모리 브라우저를 사용하여 메모리를 시각화할 수 있습니다:

1. 구성 요약에서 메모리 ID를 확인
2. [메모리 브라우저](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/04-AgentCore-memory/03-advanced-patterns/04-memory-browser)를 열어 `http://localhost:8000`에서 메모리 이벤트, 에피소드 및 반영을 시각화하고 탐색
3. 메모리 ID를 입력하여 탐색:
   - **단기 메모리**: 브랜치별 이벤트
   - **에피소드**: 세션 수준 통합 메모리
   - **반영**: 환자 수준 인사이트

**참고**: 에피소드 및 반영 생성은 대화 후 10-15분이 소요됩니다. 에피소드/반영이 즉시 나타나지 않으면 나중에 다시 확인하세요.

## 시연된 주요 개념

### 1. 멀티 에이전트 조율
- 라우팅을 위한 슈퍼바이저 패턴
- 도메인 전문성을 갖춘 전문 에이전트
- 실시간 데이터를 위한 동적 도구 사용

### 2. 메모리 브랜칭
- 에이전트별 격리된 대화
- 브랜치별 이벤트 저장
- 공유 세션 컨텍스트

### 3. 에피소딕 메모리
- 추출, 통합 및 반영 프롬프트
- 세션 수준 에피소드
- 환자 수준 반영

### 4. HealthLake 통합
- 동적 FHIR 쿼리
- 실시간 환자 데이터 접근
- 모든 데이터는 합성 데이터(Synthea로 생성) - 실제 환자 정보는 사용되지 않음

## 커스터마이징

### 새 에이전트 추가

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

에이전트 생성 시 `model` 파라미터를 변경:
```python
Agent(
    model="anthropic.claude-3-5-sonnet-20241022-v2:0",  # 다른 모델
    system_prompt="...",
    tools=[...]
)
```
## 추가 리소스

- [에피소딕 메모리 모범 사례](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html#memory-episodic-retrieve-episodes) - 에이전트 성능 향상을 위한 에피소드 검색 방법 학습


## 문제 해결

### 브랜치 생성 오류
"Branch rootEventId is required when creating a branch" 오류가 표시되면:
- **Jupyter 커널을 재시작**하세요 (Kernel -> Restart)
- 처음부터 **모든 셀을 다시 실행**하여 수정된 `HealthcareMemoryHooks` 클래스를 다시 로드
- 수정 사항은 전문 에이전트 브랜치를 포크하기 전에 main 브랜치에 초기 이벤트가 있도록 보장

### 메모리 훅 오류
"MemorySession.add_turns() got an unexpected keyword argument 'branch_name'" 오류가 표시되면:
- 노트북이 캐시된/이전 코드를 사용하고 있음을 나타냄
- **커널을 재시작**하고 모든 셀을 다시 실행하여 API 수정 사항 적용
- 수정된 코드는 `branch={"name": branch_name}` 형식을 사용

### 모델 사용 불가
"serviceUnavailableException"이 표시되면 다음을 확인:
- 글로벌 추론 프로파일 사용: `global.anthropic.claude-sonnet-4-20250514-v1:0`
- 또는 해당 리전의 리전별 프로파일

### HealthLake 접근 거부
IAM 권한에 다음이 포함되어 있는지 확인:
- `healthlake:DescribeFHIRDatastore`
- `healthlake:ReadResource`
- `healthlake:SearchWithGet`

### 메모리 생성 실패
다음을 확인:
- IAM 역할에 Bedrock 호출 권한이 있는지


## 정리

튜토리얼 완료 후 지속적인 비용을 방지하기 위해 리소스를 정리할 수 있습니다:

1. 노트북 끝의 **정리** 셀을 실행
2. 삭제 여부를 선택할 수 있는 프롬프트가 표시됩니다:
   - **메모리**: AgentCore 메모리 인스턴스
   - **HealthLake 데이터스토어**: FHIR 데이터스토어 (선택 사항)

각 리소스는 필요에 따라 독립적으로 삭제할 수 있습니다.

### 수동 정리

필요한 경우 수동으로 리소스를 삭제할 수도 있습니다:

```bash
# 메모리 삭제
aws bedrock-agentcore-cp delete-memory --memory-id <MEMORY_ID> --region us-east-1

# HealthLake 데이터스토어 삭제
aws healthlake delete-fhir-datastore --datastore-id <DATASTORE_ID> --region <REGION>
```

## 더 알아보기

- [AgentCore 메모리 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory.html)
- [Strands 에이전트 가이드](https://strandsagents.com)
- [HealthLake FHIR API](https://docs.aws.amazon.com/healthlake/latest/devguide/working-with-FHIR-healthlake.html)
- [메모리 브랜칭 패턴](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-memory-branching.html)


