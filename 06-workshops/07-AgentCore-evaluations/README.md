# 개요

Amazon Bedrock AgentCore Evaluations는 실제 상호 작용을 바탕으로 에이전트의 품질을 최적화하도록 지원합니다.

## 주요 기능

AgentCore Observability가 에이전트 상태에 관한 운영 인사이트를 제공한다면, AgentCore Evaluations는 에이전트의 의사 결정 품질과 성능 결과에 중점을 둡니다.

기본 제공 evaluator와 사용자 지정 evaluator를 지원하며, 온디맨드 및 온라인 평가 기능을 모두 제공합니다.

### 기본 제공 및 사용자 지정 evaluator

AgentCore Evaluations는 정확성, 유용성, 안전성과 같은 핵심 요소를 평가하는 13개의 기본 제공 evaluator와 비즈니스별 요구 사항에 맞는 사용자 지정 evaluator 생성 기능을 제공합니다.

온디맨드 평가 API를 사용해 개발 및 배포 중에 에이전트를 테스트하거나, 온라인 평가 API를 사용해 프로덕션 에이전트를 모니터링할 수 있습니다.

### 온디맨드 평가

개별 trace에 기본 제공 및 사용자 지정 metric을 적용하여 동기식 온디맨드 평가를 실행합니다.

시스템은 OpenTelemetry(OTEL) trace를 사용해 점수를 산정하고 다음 항목이 포함된 응답을 반환합니다.
- 점수
- 점수에 대한 설명
- 토큰 사용량

온라인 평가

프로덕션 환경에서는 각 trace를 수동으로 평가하지 않고 모든 상호 작용의 성능을 지속적으로 모니터링해야 합니다. 의미 있는 성능 metric을 생성하는 데는 통계적 표본만으로도 충분한 경우가 많습니다.

AgentCore Evaluations의 온라인 기능은 자동 표본 추출과 평가를 지원합니다.

- 표본 크기와 trace 선택 기준 정의
- 평가 metric 선택(기본 제공 또는 사용자 지정)
- 이후 과정은 AgentCore Evaluations가 처리하여 대규모 에이전트 모니터링에 필요한 성능 데이터를 생성

## 튜토리얼 개요

이 튜토리얼에서는 다음 기능을 다룹니다.
- [사전 요구 사항](00-prereqs): 평가 튜토리얼에서 사용할 샘플 에이전트 생성
- [사용자 지정 evaluator 생성](01-creating-custom-evaluators): 기본 제공 및 사용자 지정 metric을 알아보고 에이전트 평가용 사용자 지정 metric 생성
- [온디맨드 및 온라인 평가 사용](02-running-evaluations): 온디맨드 및 온라인 평가를 사용하여 에이전트를 대규모로 구축, 최적화 및 모니터링하는 방법 학습
- [고급](03-advanced): boto3 SDK로 온디맨드 평가를 위한 Amazon CloudWatch 로그를 쿼리하고, 서로 다른 에이전트 구성의 실험을 시각화하는 로컬 대시보드를 만드는 등 고급 기능 살펴보기
