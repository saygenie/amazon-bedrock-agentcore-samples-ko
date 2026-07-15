# Amazon Bedrock AgentCore Runtime 및 Observability를 사용하는 LlamaIndex 에이전트

이 자습서에서는 포괄적인 관측성과 텔레메트리 수집을 갖춘 [LlamaIndex 에이전트](https://developers.llamaindex.ai/python/framework/use_cases/agents/)를 Amazon Bedrock AgentCore Runtime에 배포하는 방법을 살펴봅니다.

## 개요

다음 방법을 학습합니다.
- 산술 도구를 갖춘 LlamaIndex FunctionAgent 생성
- 자동 관측성을 적용하여 에이전트를 AgentCore Runtime에 배포
- 에이전트 워크플로, 도구 호출 및 LLM 상호 작용을 포함한 상세한 텔레메트리 데이터 캡처
- Amazon CloudWatch GenAI Observability 대시보드에서 트레이스와 지표 확인

## 구축할 내용

다음 기능을 갖춘 LlamaIndex 산술 에이전트를 구축합니다.
- 함수 도구를 사용하여 덧셈과 곱셈 수행
- 기본 제공 확장성을 갖춘 Amazon Bedrock AgentCore Runtime에서 실행
- 포괄적인 관측성 데이터 자동 생성
- 상세한 트레이스 정보가 포함된 CloudWatch 대시보드에서 모니터링

## 주요 기능

- **LlamaIndex 통합**: 비동기 워크플로를 갖춘 LlamaIndex FunctionAgent 사용
- **자동 관측성**: LlamaIndex OpenTelemetry 계측을 통한 기본 제공 텔레메트리 수집
- **CloudWatch 통합**: GenAI Observability 대시보드에서 에이전트 성능 확인

## 사전 요구 사항

- 적절한 권한이 있는 AWS 계정
- Amazon Bedrock 모델 액세스 권한(Claude Haiku)
- Python 3.10+
- 구성된 AWS 자격 증명
- Amazon CloudWatch에서 [Transaction Search](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html) 활성화

## 빠른 시작

1. 종속성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```

2. notebook을 실행합니다.
   ```bash
   jupyter notebook runtime_with_llamaindex_and_bedrock_models.ipynb
   ```

3. 단계별 자습서에 따라 관측성을 갖춘 에이전트를 배포합니다.

## 아키텍처

이 자습서에서는 다음 내용을 다룹니다.
- LlamaIndex 계측을 사용한 로컬 개발 및 테스트
- 자동 관측성을 갖춘 AgentCore Runtime 배포
- 트레이스 분석을 위한 CloudWatch 대시보드 액세스
- 향상된 텔레메트리를 위한 수동 스팬 생성

## 파일

- `runtime_with_llamaindex_and_bedrock_models.ipynb` - 기본 자습서 노트북
- `requirements.txt` - LlamaIndex 관측성을 포함한 Python 종속성
- `README.md` - 현재 문서

## 관측성 기능

- **에이전트 워크플로 트레이스**: LlamaIndex FunctionAgent의 전체 실행 흐름
- **도구 호출 모니터링**: 산술 함수 호출 추적
- **LLM 상호 작용 트레이스**: 입력 및 출력 추적을 포함한 Bedrock 모델 호출

## 다음 단계

이 자습서를 완료하면 다음 작업을 수행할 수 있습니다.
- LlamaIndex 에이전트에 더 복잡한 도구와 워크플로 추가
- 상세한 관측성을 갖춘 다중 에이전트 아키텍처 구현
- 트레이스 데이터를 기반으로 사용자 지정 알림 및 모니터링 설정
- 전체 가시성을 유지하면서 프로덕션 워크로드에 맞게 에이전트 확장
