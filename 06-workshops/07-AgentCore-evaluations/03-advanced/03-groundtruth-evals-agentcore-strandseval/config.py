"""다중 세션 평가를 위한 구성입니다.

AWS 환경과 기본 설정에 맞게 아래 값을 편집하세요.
"""

import os
from typing import Optional


# =============================================================================
# AWS 구성
# =============================================================================
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "YOUR_AWS_ACCOUNT_ID"


# =============================================================================
# CloudWatch 로그 그룹
# =============================================================================

# 에이전트의 OTEL trace가 저장되는 소스 로그 그룹
SOURCE_LOG_GROUP = "your-source-log-group"

# 평가 결과 로그 그룹(점수 기반 검색 및 결과 로깅용). 아직 없다면 Online Evaluator를 설정하여 생성하세요.
# /aws/bedrock-agentcore/evaluations/results/ 접두사가 없는 로그 그룹 이름입니다.
EVAL_RESULTS_LOG_GROUP = "your-evaluation-log-group"

# 평가 결과 로그 그룹의 전체 경로(위 값을 사용해 자동 구성)
EVAL_RESULTS_LOG_GROUP_FULL = f"/aws/bedrock-agentcore/evaluations/results/{EVAL_RESULTS_LOG_GROUP}"


# =============================================================================
# 평가 구성
# =============================================================================

# AgentCore의 Online Evaluation Config ID입니다. 오프라인 평가 결과를 AgentCore
# 대시보드와 연결하는 데 사용합니다. AgentCore console의 Online Evaluations 또는
# CloudWatch 로그 그룹 이름(마지막 대시 뒤의 접미사)에서 확인할 수 있습니다.
# 예: 로그 그룹이 "MyAgent-Evaluation-5MB8aF5rLE"이면 config ID는 "MyAgent-Evaluation-5MB8aF5rLE"입니다.
# 대시보드 시각화를 위해 결과를 CloudWatch에 다시 기록할 때만 필요합니다.
EVALUATION_CONFIG_ID = "your-evaluation-config-id"

# 점수 기반 검색에 사용할 Evaluator 이름입니다. 기존 평가 결과의 Evaluator 이름과
# 일치해야 합니다(예: "Builtin.Correctness" 또는 "Custom.MyEvaluator").
EVALUATOR_NAME = "Builtin.YourEvaluatorName"

# AgentCore Observability 대시보드에 표시되는 에이전트의 서비스 이름입니다.
# CloudWatch > Log groups > 에이전트 로그 그룹에서 service.name 속성을 확인하세요.
SERVICE_NAME = "your-service-name"


# =============================================================================
# 시간 범위 구성
# =============================================================================

# 세션과 trace를 조회할 과거 범위(시간 단위)
LOOKBACK_HOURS = 72


# =============================================================================
# 세션 검색 구성
# =============================================================================

# 검색할 최대 세션 수
MAX_SESSIONS = 100

# 점수 기반 검색의 임계값(필터링을 비활성화하려면 None으로 설정)
MIN_SCORE: Optional[float] = None
MAX_SCORE: Optional[float] = 0.5


# =============================================================================
# 처리 구성
# =============================================================================

# 세션당 평가할 최대 케이스 수(모두 평가하려면 None으로 설정)
MAX_CASES_PER_SESSION: Optional[int] = 10


# =============================================================================
# 파일 경로
# =============================================================================

# 세션 검색 결과의 출력 파일 경로
DISCOVERED_SESSIONS_PATH = "discovered_sessions.json"

# 다중 세션 평가 결과의 출력 파일 경로
RESULTS_JSON_PATH = "multi_session_results.json"


# =============================================================================
# 도우미 함수
# =============================================================================


def setup_cloudwatch_environment() -> None:
    """CloudWatch 로깅용 환경 변수를 구성합니다."""
    os.environ["AWS_REGION"] = AWS_REGION
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION
    os.environ["AWS_ACCOUNT_ID"] = AWS_ACCOUNT_ID
    os.environ["EVALUATION_RESULTS_LOG_GROUP"] = EVAL_RESULTS_LOG_GROUP
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"service.name={SERVICE_NAME}"
