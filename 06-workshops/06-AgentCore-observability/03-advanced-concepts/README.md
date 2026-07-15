# 고급 관측성 개념

이 섹션에서는 Amazon Bedrock AgentCore의 고급 관측성 패턴과 기법을 다루며, 정교한 사용자 지정 모니터링 및 디버깅 기능을 구현하도록 안내합니다.

## 제공되는 자습서

### 01-custom-span-creation/

- **노트북**: `Custom_Span_Creation.ipynb`
- **설명**: 작업을 상세히 추적하기 위한 사용자 지정 스팬 생성 방법 학습
- **기능**: 수동 스팬 생성, 사용자 지정 속성
- **사용 사례**: 세분화된 모니터링, 디버깅

### 02-data-protection/

- **노트북**: `data_protection.ipynb`
- **설명**: 에이전트 워크플로의 민감한 정보를 위한 포괄적인 데이터 보호 구현
- **기능**: Bedrock Guardrails 통합, CloudWatch Logs Data Protection, PII 탐지 및 마스킹
- **사용 사례**: 규정 준수(GDPR, HIPAA, CCPA), 민감한 데이터 처리, 개인 정보 보호

## 학습 내용

- **사용자 지정 스팬 생성**: 특정 작업에 상세한 트레이싱 추가
- **스팬 속성**: 사용자 지정 메타데이터로 트레이스 보강
- **중첩 스팬**: 계층형 트레이스 구조 생성
- **성능 모니터링**: 에이전트 워크플로의 병목 지점 식별
- **오류 추적**: 예외와 실패를 캡처하고 추적
- **데이터 보호**: 로그와 트레이스에서 민감한 데이터 탐지 및 마스킹 구현
- **규정 준수 통합**: Bedrock Guardrails 및 CloudWatch Data Protection 구성

## 시작하기

1. 자습서 디렉터리로 이동합니다.
2. `.env.example`을 `.env`로 복사하고 다음을 구성합니다.
   - AWS 자격 증명
   - CloudWatch 로그 그룹 설정
   - OpenTelemetry 구성
3. 사용 중인 AWS 리전에서 CloudWatch Transaction Search를 활성화합니다.
4. 종속성을 설치합니다: `pip install -r requirements.txt`
5. Jupyter notebook을 열어 실행합니다.

## 사전 요구 사항

- 기본 OpenTelemetry 개념에 대한 이해
- Amazon CloudWatch 사용 경험
- 에이전트 프레임워크 사용 경험(권장)
- 적절한 권한이 있는 AWS 계정

## 다루는 고급 패턴

- **수동 계측**: 사용자 지정 span을 추가하는 시점과 방법
- **사용자 지정 지표**: 도메인별 측정값 생성
- **데이터 보호 정책**: 민감한 정보 필터 구성
- **다계층 보안**: Guardrails와 CloudWatch Data Protection 결합

## 정리

자습서를 완료한 후 다음을 수행합니다.

1. 예제에서 생성한 CloudWatch 로그 그룹을 삭제합니다.
2. 테스트 리소스를 제거합니다.
3. 환경 구성 파일을 정리합니다.
