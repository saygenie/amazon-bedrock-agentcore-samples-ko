"""다중 세션을 지원하는 CloudWatch-Strands Eval 변환 유틸리티입니다.

이 모듈은 다음 유틸리티를 제공합니다:
- CloudWatch Logs에서 OTEL trace 쿼리(ObservabilityClient)
- CloudWatch 로그 그룹에서 세션 검색(시간 기반 및 점수 기반)
- CloudWatch span을 Strands Eval Session 형식으로 매핑(CloudWatchSessionMapper)
- span, 세션, 평가 결과용 데이터 모델
- 원본 trace ID를 사용하는 사용자 지정 CloudWatch 로깅(send_evaluation_to_cloudwatch)

참고: 구성은 Notebook과 같은 디렉터리의 config.py에 있습니다.
"""

from .cloudwatch_client import CloudWatchQueryBuilder, ObservabilityClient
from .evaluation_cloudwatch_logger import (
    EvaluationLogConfig,
    log_evaluation_batch,
    send_evaluation_to_cloudwatch,
)
from .models import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationResults,
    RuntimeLog,
    SessionDiscoveryResult,
    SessionInfo,
    Span,
    TraceData,
)
from .session_mapper import CloudWatchSessionMapper

__all__ = [
    # CloudWatch 클라이언트
    "ObservabilityClient",
    "CloudWatchQueryBuilder",
    # 세션 매퍼
    "CloudWatchSessionMapper",
    # 사용자 지정 CloudWatch 로거
    "send_evaluation_to_cloudwatch",
    "log_evaluation_batch",
    "EvaluationLogConfig",
    # 모델
    "Span",
    "RuntimeLog",
    "TraceData",
    "SessionInfo",
    "SessionDiscoveryResult",
    "EvaluationRequest",
    "EvaluationResult",
    "EvaluationResults",
]
