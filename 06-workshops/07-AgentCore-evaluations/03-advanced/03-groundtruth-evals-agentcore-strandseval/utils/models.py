"""trace 데이터 및 평가용 데이터 모델입니다."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from strands_evals.mappers.session_mapper import SessionMapper
    from strands_evals.types.trace import Session


@dataclass
class Span:
    """trace 메타데이터가 포함된 OpenTelemetry span입니다."""

    trace_id: str
    span_id: str
    span_name: str
    start_time_unix_nano: Optional[int] = None
    raw_message: Optional[Dict[str, Any]] = None

    @classmethod
    def from_cloudwatch_result(cls, result: Any) -> "Span":
        """CloudWatch Logs Insights 쿼리 결과로 Span을 생성합니다."""
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default: Any = None) -> Any:
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        def parse_json_field(field_name: str) -> Any:
            value = get_field(field_name)
            if value and isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value

        def get_int_field(field_name: str) -> Optional[int]:
            value = get_field(field_name)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
            return None

        return cls(
            trace_id=get_field("traceId", ""),
            span_id=get_field("spanId", ""),
            span_name=get_field("spanName", ""),
            start_time_unix_nano=get_int_field("startTimeUnixNano"),
            raw_message=parse_json_field("@message"),
        )


@dataclass
class RuntimeLog:
    """에이전트별 로그 그룹의 Runtime 로그 항목입니다."""

    timestamp: str
    message: str
    span_id: Optional[str] = None
    trace_id: Optional[str] = None
    raw_message: Optional[Dict[str, Any]] = None

    @classmethod
    def from_cloudwatch_result(cls, result: Any) -> "RuntimeLog":
        """CloudWatch Logs Insights 쿼리 결과로 RuntimeLog를 생성합니다."""
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default: Any = None) -> Any:
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        def parse_json_field(field_name: str) -> Any:
            value = get_field(field_name)
            if value and isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value

        return cls(
            timestamp=get_field("@timestamp", ""),
            message=get_field("@message", ""),
            span_id=get_field("spanId"),
            trace_id=get_field("traceId"),
            raw_message=parse_json_field("@message"),
        )


@dataclass
class TraceData:
    """span과 Runtime 로그를 포함하는 전체 세션 데이터입니다."""

    session_id: Optional[str] = None
    spans: List[Span] = field(default_factory=list)
    runtime_logs: List[RuntimeLog] = field(default_factory=list)

    def get_trace_ids(self) -> List[str]:
        """span에서 고유한 모든 trace ID를 가져옵니다."""
        return list(set(span.trace_id for span in self.spans if span.trace_id))

    def get_tool_execution_spans(self, tool_name_filter: Optional[str] = None) -> List[str]:
        """도구 실행 span의 span ID를 가져옵니다.

        인수:
            tool_name_filter: 필터링할 선택적 도구 이름(예: "calculate_bmi")

        반환값:
            gen_ai.operation.name == "execute_tool"인 span ID 목록
        """
        tool_span_ids = []

        for span in self.spans:
            if not span.raw_message:
                continue

            attributes = span.raw_message.get("attributes", {})

            # 도구 실행 span인지 확인
            operation_name = attributes.get("gen_ai.operation.name")
            if operation_name != "execute_tool":
                continue

            # 도구 이름 필터가 제공된 경우 적용
            if tool_name_filter:
                tool_name = attributes.get("gen_ai.tool.name")
                if tool_name != tool_name_filter:
                    continue

            tool_span_ids.append(span.span_id)

        return tool_span_ids

    def to_session(self, mapper: SessionMapper) -> Session:
        """제공된 매퍼를 사용하여 Strands Eval Session으로 변환합니다.

        인수:
            mapper: SessionMapper 구현(예: CloudWatchSessionMapper)

        반환값:
            평가 준비가 완료된 Session 객체
        """
        return mapper.map_to_session(self.spans, self.session_id or "")


class EvaluationRequest:
    """평가 API의 요청 페이로드입니다."""

    def __init__(
        self,
        evaluator_id: str,
        session_spans: List[Dict[str, Any]],
        evaluation_target: Optional[Dict[str, Any]] = None,
    ):
        self.evaluator_id = evaluator_id
        self.session_spans = session_spans
        self.evaluation_target = evaluation_target

    def to_api_request(self) -> tuple:
        """API 요청 형식으로 변환합니다.

        반환값:
            (evaluator_id_param, request_body) 튜플
        """
        request_body = {"evaluationInput": {"sessionSpans": self.session_spans}}

        if self.evaluation_target:
            request_body["evaluationTarget"] = self.evaluation_target

        return self.evaluator_id, request_body


@dataclass
class EvaluationResult:
    """평가 API의 결과입니다."""

    evaluator_id: str
    evaluator_name: str
    evaluator_arn: str
    explanation: str
    context: Dict[str, Any]
    value: Optional[float] = None
    label: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None

    @classmethod
    def from_api_response(cls, api_result: Dict[str, Any]) -> "EvaluationResult":
        """API 응답으로 EvaluationResult를 생성합니다."""
        return cls(
            evaluator_id=api_result.get("evaluatorId", ""),
            evaluator_name=api_result.get("evaluatorName", ""),
            evaluator_arn=api_result.get("evaluatorArn", ""),
            explanation=api_result.get("explanation", ""),
            context=api_result.get("context", {}),
            value=api_result.get("value"),  # 없으면 None
            label=api_result.get("label"),  # 없으면 None
            token_usage=api_result.get("tokenUsage"),  # 없으면 None
            error=None,
        )


@dataclass
class EvaluationResults:
    """세션의 평가 결과 모음입니다."""

    session_id: str
    results: List[EvaluationResult] = field(default_factory=list)
    input_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    def add_result(self, result: EvaluationResult) -> None:
        """평가 결과를 추가합니다."""
        self.results.append(result)

    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화를 위해 딕셔너리로 변환합니다."""
        output = {
            "session_id": self.session_id,
            "results": [
                {
                    "evaluator_id": r.evaluator_id,
                    "evaluator_name": r.evaluator_name,
                    "evaluator_arn": r.evaluator_arn,
                    "value": r.value,
                    "label": r.label,
                    "explanation": r.explanation,
                    "context": r.context,
                    "token_usage": r.token_usage,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
        if self.metadata:
            output["metadata"] = self.metadata
        if self.input_data:
            output["input_data"] = self.input_data
        return output


@dataclass
class SessionInfo:
    """검색된 세션에 관한 정보입니다.

    속성:
        session_id: 세션의 고유 식별자
        span_count: span(time_based) 또는 평가(score_based) 수
            - time_based 검색: trace의 실제 span 수
            - score_based 검색: 평가 수(metadata.eval_count에도 포함)
        first_seen: 최초 활동의 타임스탬프
        last_seen: 마지막 활동의 타임스탬프
        trace_count: 고유 trace 수(time_based 검색에만 해당)
        discovery_method: 세션 검색 방식("time_based" 또는 "score_based")
        metadata: 추가 데이터(score_based의 경우 avg_score, min_score, max_score, eval_count)
    """

    session_id: str
    span_count: int
    first_seen: datetime
    last_seen: datetime
    trace_count: Optional[int] = None
    discovery_method: Optional[str] = None  # "time_based" 또는 "score_based"
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화를 위해 딕셔너리로 변환합니다."""
        return {
            "session_id": self.session_id,
            "span_count": self.span_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "trace_count": self.trace_count,
            "discovery_method": self.discovery_method,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionInfo":
        """딕셔너리로 SessionInfo를 생성합니다."""
        first_seen = data["first_seen"]
        last_seen = data["last_seen"]

        # 필요한 경우 datetime 문자열을 파싱하고 시간대 정보가 있는지 확인
        if isinstance(first_seen, str):
            first_seen = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)

        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        return cls(
            session_id=data["session_id"],
            span_count=data["span_count"],
            first_seen=first_seen,
            last_seen=last_seen,
            trace_count=data.get("trace_count"),
            discovery_method=data.get("discovery_method"),
            metadata=data.get("metadata"),
        )


@dataclass
class SessionDiscoveryResult:
    """세션 검색 작업의 결과입니다."""

    sessions: List[SessionInfo]
    discovery_time: datetime
    log_group: str
    time_range_start: datetime
    time_range_end: datetime
    discovery_method: str
    filter_criteria: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화를 위해 딕셔너리로 변환합니다."""
        return {
            "sessions": [s.to_dict() for s in self.sessions],
            "discovery_time": self.discovery_time.isoformat(),
            "log_group": self.log_group,
            "time_range_start": self.time_range_start.isoformat(),
            "time_range_end": self.time_range_end.isoformat(),
            "discovery_method": self.discovery_method,
            "filter_criteria": self.filter_criteria,
        }

    def save_to_json(self, filepath: str) -> None:
        """검색 결과를 JSON 파일로 저장합니다."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str) -> "SessionDiscoveryResult":
        """JSON 파일에서 검색 결과를 불러옵니다."""
        with open(filepath, "r") as f:
            data = json.load(f)

        return cls(
            sessions=[SessionInfo.from_dict(s) for s in data["sessions"]],
            discovery_time=datetime.fromisoformat(data["discovery_time"].replace("Z", "+00:00")),
            log_group=data["log_group"],
            time_range_start=datetime.fromisoformat(data["time_range_start"].replace("Z", "+00:00")),
            time_range_end=datetime.fromisoformat(data["time_range_end"].replace("Z", "+00:00")),
            discovery_method=data["discovery_method"],
            filter_criteria=data.get("filter_criteria"),
        )

    def get_session_ids(self) -> List[str]:
        """세션 ID 목록을 가져옵니다."""
        return [s.session_id for s in self.sessions]
