# Self-Managed Memory 전략을 사용하는 요리 도우미(인용 포함)

이 샘플은 향상된 인용 추적 기능을 갖춘 Amazon Bedrock AgentCore의 Self-Managed Memory 전략을 보여 줍니다. 기본 요리 도우미 예제에서 확장된 버전으로, 추출된 장기 메모리에 포괄적인 인용 정보를 추가합니다.

## 차이점

이 샘플은 추출된 메모리의 출처를 추적하는 인용 기능을 추가합니다.

### 인용 기능

1. **출처 추적**: 추출된 각 메모리에 출처 관련 메타데이터가 포함됩니다.
   - Session ID 및 Actor ID
   - 시작 및 종료 timestamp
   - 원본 단기 메모리 payload가 저장된 S3 URI
   - 추출 job ID

2. **인용 메타데이터**: 구조화된 인용 정보가 메모리 메타데이터에 저장됩니다.
   ```python
   citation_info = {
       'source_type': 'short_term_memory',
       'session_id': session_id,
       'actor_id': actor_id,
       'starting_timestamp': starting_timestamp,
       'ending_timestamp': timestamp,
       's3_uri': s3_location,
       's3_payload_location': s3_location,
       'extraction_job_id': job_id
   }
   ```

3. **사람이 읽을 수 있는 인용**: 각 메모리 콘텐츠에 인용 텍스트가 추가됩니다.
   ```
   [Citation: Extracted from session {session_id}, actor {actor_id}, source: {s3_location}, job: {job_id}, timestamp: {timestamp}]
   ```

### 수정된 파일

#### `lambda_function.py`

주요 변경 사항은 `MemoryExtractor` 클래스에 있습니다.

- `extract_memories()` 메서드가 이제 `s3_location` 및 `job_id` 파라미터를 받습니다.
- `_format_extracted_memories()` 메서드는 인용 정보를 구성하고 메모리 콘텐츠에 추가합니다.
- 인용 정보를 추적하도록 로깅을 개선했습니다.

**주요 메서드**: `_format_extracted_memories`(97행)
이 메서드는 추출된 메모리를 메타데이터 및 인용 정보와 함께 형식화하여 장기 메모리에서 단기 메모리의 출처까지 추적할 수 있는 연결을 만듭니다.

#### `agentcore_self_managed_memory_demo.ipynb`

인용 기능의 실제 작동 방식을 보여 주도록 업데이트되었으며, 추출된 메모리에 출처 표시가 포함되는 방식을 확인할 수 있습니다.

## 사용 사례

이 인용 기능 강화 버전은 다음 용도에 특히 유용합니다.

1. **감사 추적**: 메모리 출처에 대한 전체 기록 유지
2. **디버깅**: 원본 대화 맥락까지 역추적
3. **규정 준수**: 데이터 계보 및 출처 표시 요구 사항 충족
4. **메모리 검증**: S3의 원본 소스와 비교하여 메모리 콘텐츠 검증

## 사전 요구 사항

기본 요리 도우미 예제와 같습니다.
- Python 3.11+
- 구성된 AWS 자격 증명
- Claude 모델을 사용할 수 있는 Amazon Bedrock 액세스 권한
- 필수 AWS 서비스: Lambda, S3, SNS, SQS

## 설정

기본 요리 도우미 예제와 동일한 설정 과정을 따릅니다. 노트북에서는 다음 과정을 안내합니다.

1. 인용을 지원하는 Lambda 함수 생성
2. 트리거 조건을 사용하는 메모리 전략 설정
3. 향상된 인용 기능 테스트

## 기본 샘플과 비교

| 기능 | 기본 샘플 | 인용 포함 |
|---------|------------|----------------|
| 메모리 추출 | ✅ | ✅ |
| S3 payload 추적 | ❌ | ✅ |
| 출처 표시 | ❌ | ✅ |
| Job ID 추적 | ❌ | ✅ |
| Timestamp 맥락 | ❌ | ✅ |
| 인용 메타데이터 | ❌ | ✅ |

## 문서

Self-managed Memory 전략에 대한 자세한 내용은 [Amazon Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-self-managed-strategies.html)를 참조하세요.
