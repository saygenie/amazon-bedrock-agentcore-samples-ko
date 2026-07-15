"""CloudWatch Logs의 관찰성 데이터를 쿼리하는 클라이언트입니다."""

import logging
import time
from typing import List

import boto3

from datetime import datetime, timezone
from typing import Optional

from .models import RuntimeLog, SessionInfo, Span, TraceData


class CloudWatchQueryBuilder:
    """CloudWatch Logs Insights 쿼리 빌더입니다."""

    @staticmethod
    def build_spans_by_session_query(session_id: str, agent_id: str = None) -> str:
        """aws/spans 로그 그룹에서 세션의 모든 span을 가져오는 쿼리를 생성합니다.

        인수:
            session_id: 필터링 기준이 되는 세션 ID
            agent_id: 필터링 기준이 되는 선택적 에이전트 ID

        반환값:
            CloudWatch Logs Insights 쿼리 문자열
        """
        base_filter = f"attributes.session.id = '{session_id}'"

        return f"""fields @timestamp,
               @message,
               traceId,
               spanId,
               name as spanName,
               kind,
               status.code as statusCode,
               status.message as statusMessage,
               durationNano/1000000 as durationMs,
               attributes.session.id as sessionId,
               startTimeUnixNano,
               endTimeUnixNano,
               parentSpanId,
               events,
               resource.attributes.service.name as serviceName,
               resource.attributes.cloud.resource_id as resourceId,
               attributes.aws.remote.service as serviceType
        | filter {base_filter}
        | sort startTimeUnixNano asc"""

    @staticmethod
    def build_runtime_logs_by_traces_batch(trace_ids: List[str]) -> str:
        """여러 trace의 Runtime 로그를 한 번에 가져오는 최적화된 쿼리를 생성합니다.

        인수:
            trace_ids: 필터링 기준이 되는 trace ID 목록

        반환값:
            CloudWatch Logs Insights 쿼리 문자열
        """
        if not trace_ids:
            return ""

        trace_ids_quoted = ", ".join([f"'{tid}'" for tid in trace_ids])

        return f"""fields @timestamp, @message, spanId, traceId, @logStream
        | filter traceId in [{trace_ids_quoted}]
        | sort @timestamp asc"""

    @staticmethod
    def build_runtime_logs_by_trace_direct(trace_id: str) -> str:
        """trace의 Runtime 로그를 가져오는 쿼리를 생성합니다.

        인수:
            trace_id: 필터링 기준이 되는 trace ID

        반환값:
            CloudWatch Logs Insights 쿼리 문자열
        """
        return f"""fields @timestamp, @message, spanId, traceId, @logStream
        | filter traceId = '{trace_id}'
        | sort @timestamp asc"""

    @staticmethod
    def build_discover_sessions_query() -> str:
        """시간 범위 내의 고유한 세션 ID를 검색하는 쿼리를 생성합니다.

        반환값:
            고유한 세션 ID를 span 수 및 시간 범위와 함께 반환하는
            CloudWatch Logs Insights 쿼리 문자열
        """
        return """fields @timestamp, attributes.session.id as sessionId, traceId
        | filter ispresent(attributes.session.id)
        | stats count(*) as spanCount,
                min(@timestamp) as firstSeen,
                max(@timestamp) as lastSeen,
                count_distinct(traceId) as traceCount
          by sessionId
        | sort lastSeen desc"""

    @staticmethod
    def build_sessions_by_score_query(
        evaluator_name: str,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> str:
        """결과 로그 그룹에서 평가 점수로 세션을 찾는 쿼리를 생성합니다.

        인수:
            evaluator_name: Evaluator 이름(예: "Custom.StrandsEvalOfflineTravelEvaluator")
            min_score: 최소 점수 임계값(포함)
            max_score: 최대 점수 임계값(포함)

        반환값:
            CloudWatch Logs Insights 쿼리 문자열
        """
        # 점수 필터 조건 생성
        score_filters = []
        if min_score is not None:
            score_filters.append(f"`{evaluator_name}` >= {min_score}")
        if max_score is not None:
            score_filters.append(f"`{evaluator_name}` <= {max_score}")

        score_filter_clause = ""
        if score_filters:
            score_filter_clause = "| filter " + " and ".join(score_filters)

        return f"""fields @timestamp,
               attributes.session.id as sessionId,
               attributes.gen_ai.response.id as traceId,
               `{evaluator_name}` as score,
               label
        | filter ispresent(`{evaluator_name}`)
        {score_filter_clause}
        | stats count(*) as evalCount,
                avg(score) as avgScore,
                min(score) as minScore,
                max(score) as maxScore,
                min(@timestamp) as firstEval,
                max(@timestamp) as lastEval
          by sessionId
        | sort avgScore asc"""


class ObservabilityClient:
    """CloudWatch Logs에서 span과 Runtime 로그를 쿼리하는 클라이언트입니다."""

    QUERY_TIMEOUT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 2

    def __init__(
        self,
        region_name: str,
        log_group: str,
        agent_id: str = None,
        runtime_suffix: str = "DEFAULT",
    ):
        """ObservabilityClient를 초기화합니다.

        인수:
            region_name: AWS 리전 이름
            log_group: span/trace용 CloudWatch 로그 그룹 이름
            agent_id: 선택적 Agent ID(현재 필터링에는 사용하지 않음)
            runtime_suffix: 로그 그룹의 Runtime 접미사(기본값: DEFAULT)
        """
        self.region = region_name
        self.log_group = log_group
        self.agent_id = agent_id
        self.runtime_suffix = runtime_suffix

        self.logs_client = boto3.client("logs", region_name=region_name)
        self.query_builder = CloudWatchQueryBuilder()

        self.logger = logging.getLogger("cloudwatch_client")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def query_spans_by_session(
        self,
        session_id: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Span]:
        """aws/spans 로그 그룹에서 세션의 모든 span을 쿼리합니다.

        인수:
            session_id: 쿼리할 세션 ID
            start_time_ms: epoch 이후 밀리초 단위의 시작 시간
            end_time_ms: epoch 이후 밀리초 단위의 종료 시간

        반환값:
            Span 객체 목록
        """
        self.logger.info(
            "Querying spans for session: %s from log group: %s",
            session_id,
            self.log_group,
        )

        query_string = self.query_builder.build_spans_by_session_query(session_id)

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=self.log_group,
            start_time=start_time_ms,
            end_time=end_time_ms,
        )

        spans = [Span.from_cloudwatch_result(result) for result in results]
        self.logger.info("Found %d spans for session %s", len(spans), session_id)

        return spans

    def query_runtime_logs_by_traces(
        self,
        trace_ids: List[str],
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[RuntimeLog]:
        """에이전트별 로그 그룹에서 여러 trace의 Runtime 로그를 쿼리합니다.

        인수:
            trace_ids: 쿼리할 trace ID 목록
            start_time_ms: epoch 이후 밀리초 단위의 시작 시간
            end_time_ms: epoch 이후 밀리초 단위의 종료 시간

        반환값:
            RuntimeLog 객체 목록
        """
        if not trace_ids:
            return []

        self.logger.info("Querying runtime logs for %d traces", len(trace_ids))

        query_string = self.query_builder.build_runtime_logs_by_traces_batch(trace_ids)

        try:
            results = self._execute_cloudwatch_query(
                query_string=query_string,
                log_group_name=self.log_group,
                start_time=start_time_ms,
                end_time=end_time_ms,
            )

            logs = [RuntimeLog.from_cloudwatch_result(result) for result in results]
            self.logger.info("Found %d runtime logs across %d traces", len(logs), len(trace_ids))
            return logs

        except Exception as e:
            self.logger.error("Failed to query runtime logs: %s", str(e))
            return []

    def get_session_data(
        self,
        session_id: str,
        start_time_ms: int,
        end_time_ms: int,
        include_runtime_logs: bool = True,
    ) -> TraceData:
        """span과 선택적 Runtime 로그를 포함한 전체 세션 데이터를 가져옵니다.

        인수:
            session_id: 쿼리할 세션 ID
            start_time_ms: epoch 이후 밀리초 단위의 시작 시간
            end_time_ms: epoch 이후 밀리초 단위의 종료 시간
            include_runtime_logs: Runtime 로그를 가져올지 여부(기본값: True)

        반환값:
            span과 Runtime 로그가 포함된 TraceData 객체
        """
        self.logger.info("Fetching session data for: %s", session_id)

        spans = self.query_spans_by_session(session_id, start_time_ms, end_time_ms)

        session_data = TraceData(
            session_id=session_id,
            spans=spans,
        )

        if include_runtime_logs:
            trace_ids = session_data.get_trace_ids()
            if trace_ids:
                runtime_logs = self.query_runtime_logs_by_traces(trace_ids, start_time_ms, end_time_ms)
                session_data.runtime_logs = runtime_logs

        self.logger.info(
            "Session data retrieved: %d spans, %d traces, %d runtime logs",
            len(session_data.spans),
            len(session_data.get_trace_ids()),
            len(session_data.runtime_logs),
        )

        return session_data

    def discover_sessions(
        self,
        start_time_ms: int,
        end_time_ms: int,
        limit: int = 100,
    ) -> List[SessionInfo]:
        """시간 범위 내에서 고유한 세션 ID를 검색합니다.

        인수:
            start_time_ms: epoch 이후 밀리초 단위의 시작 시간
            end_time_ms: epoch 이후 밀리초 단위의 종료 시간
            limit: 반환할 최대 세션 수(기본값: 100)

        반환값:
            세션 메타데이터가 포함된 SessionInfo 객체 목록
        """
        self.logger.info(
            "Discovering sessions in log group: %s from %s to %s",
            self.log_group,
            datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc),
            datetime.fromtimestamp(end_time_ms / 1000, tz=timezone.utc),
        )

        query_string = self.query_builder.build_discover_sessions_query()

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=self.log_group,
            start_time=start_time_ms,
            end_time=end_time_ms,
        )

        sessions = []
        for result in results[:limit]:
            session_info = self._parse_session_discovery_result(result)
            if session_info:
                session_info.discovery_method = "time_based"
                sessions.append(session_info)

        self.logger.info("Discovered %d sessions", len(sessions))
        return sessions

    def discover_sessions_by_score(
        self,
        evaluation_log_group: str,
        evaluator_name: str,
        start_time_ms: int,
        end_time_ms: int,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: int = 100,
    ) -> List[SessionInfo]:
        """평가 결과 로그 그룹에서 평가 점수를 기준으로 세션을 검색합니다.

        인수:
            evaluation_log_group: 평가 결과가 포함된 로그 그룹
            evaluator_name: 필터링 기준이 되는 Evaluator 이름
            start_time_ms: epoch 이후 밀리초 단위의 시작 시간
            end_time_ms: epoch 이후 밀리초 단위의 종료 시간
            min_score: 최소 점수 임계값(포함)
            max_score: 최대 점수 임계값(포함)
            limit: 반환할 최대 세션 수(기본값: 100)

        반환값:
            세션 메타데이터와 점수 정보가 포함된 SessionInfo 객체 목록
        """
        self.logger.info(
            "Discovering sessions by score in log group: %s (evaluator: %s, score range: %s-%s)",
            evaluation_log_group,
            evaluator_name,
            min_score,
            max_score,
        )

        query_string = self.query_builder.build_sessions_by_score_query(
            evaluator_name=evaluator_name,
            min_score=min_score,
            max_score=max_score,
        )

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=evaluation_log_group,
            start_time=start_time_ms,
            end_time=end_time_ms,
        )

        sessions = []
        for result in results[:limit]:
            session_info = self._parse_score_discovery_result(result)
            if session_info:
                session_info.discovery_method = "score_based"
                sessions.append(session_info)

        self.logger.info("Discovered %d sessions by score", len(sessions))
        return sessions

    def _parse_session_discovery_result(self, result) -> Optional[SessionInfo]:
        """시간 기반 검색을 위해 CloudWatch 결과를 SessionInfo로 파싱합니다."""
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default=None):
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        session_id = get_field("sessionId")
        if not session_id:
            return None

        span_count_str = get_field("spanCount", "0")
        trace_count_str = get_field("traceCount")
        first_seen_str = get_field("firstSeen")
        last_seen_str = get_field("lastSeen")

        # 개수 파싱
        try:
            span_count = int(float(span_count_str))
        except (ValueError, TypeError):
            span_count = 0

        trace_count = None
        if trace_count_str:
            try:
                trace_count = int(float(trace_count_str))
            except (ValueError, TypeError):
                pass

        # 타임스탬프 파싱 - 유효한 타임스탬프가 필요하며 now()로 대체하지 않음
        first_seen = None
        last_seen = None
        if first_seen_str:
            try:
                first_seen = datetime.fromisoformat(first_seen_str.replace("Z", "+00:00"))
                # 시간대 정보가 있는지 확인
                if first_seen.tzinfo is None:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Failed to parse first_seen '{first_seen_str}': {e}")
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                # 시간대 정보가 있는지 확인
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Failed to parse last_seen '{last_seen_str}': {e}")

        # 타임스탬프가 누락된 세션 건너뛰기
        if first_seen is None or last_seen is None:
            self.logger.warning(f"Session {session_id} missing timestamps, skipping")
            return None

        return SessionInfo(
            session_id=session_id,
            span_count=span_count,
            first_seen=first_seen,
            last_seen=last_seen,
            trace_count=trace_count,
        )

    def _parse_score_discovery_result(self, result) -> Optional[SessionInfo]:
        """점수 기반 검색을 위해 CloudWatch 결과를 SessionInfo로 파싱합니다.

        참고: 점수 기반 검색에서 span_count는 trace의 span 수가 아니라
        평가 수(이 세션에서 발견된 평가 수)를 나타냅니다.
        명확성을 위해 실제 eval_count도 메타데이터에 저장됩니다.
        """
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default=None):
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        session_id = get_field("sessionId")
        if not session_id:
            return None

        eval_count_str = get_field("evalCount", "0")
        avg_score_str = get_field("avgScore", "0")
        min_score_str = get_field("minScore", "0")
        max_score_str = get_field("maxScore", "0")
        first_eval_str = get_field("firstEval")
        last_eval_str = get_field("lastEval")

        # 개수와 점수 파싱
        try:
            eval_count = int(float(eval_count_str))
        except (ValueError, TypeError):
            eval_count = 0

        try:
            avg_score = float(avg_score_str)
        except (ValueError, TypeError):
            avg_score = 0.0

        try:
            min_score = float(min_score_str)
        except (ValueError, TypeError):
            min_score = 0.0

        try:
            max_score = float(max_score_str)
        except (ValueError, TypeError):
            max_score = 0.0

        # 타임스탬프 파싱 - 유효한 타임스탬프가 필요하며 now()로 대체하지 않음
        first_seen = None
        last_seen = None
        if first_eval_str:
            try:
                first_seen = datetime.fromisoformat(first_eval_str.replace("Z", "+00:00"))
                # 시간대 정보가 있는지 확인
                if first_seen.tzinfo is None:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Failed to parse first_eval '{first_eval_str}': {e}")
        if last_eval_str:
            try:
                last_seen = datetime.fromisoformat(last_eval_str.replace("Z", "+00:00"))
                # 시간대 정보가 있는지 확인
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Failed to parse last_eval '{last_eval_str}': {e}")

        # 타임스탬프가 누락된 세션 건너뛰기
        if first_seen is None or last_seen is None:
            self.logger.warning(f"Session {session_id} missing timestamps, skipping")
            return None

        return SessionInfo(
            session_id=session_id,
            span_count=eval_count,  # 점수 기반: eval_count(docstring 참조)
            first_seen=first_seen,
            last_seen=last_seen,
            metadata={
                "avg_score": avg_score,
                "min_score": min_score,
                "max_score": max_score,
                "eval_count": eval_count,
            },
        )

    def _execute_cloudwatch_query(
        self,
        query_string: str,
        log_group_name: str,
        start_time: int,
        end_time: int,
    ) -> list:
        """CloudWatch Logs Insights 쿼리를 실행하고 결과를 기다립니다.

        인수:
            query_string: CloudWatch Logs Insights 쿼리
            log_group_name: 쿼리할 로그 그룹
            start_time: epoch 이후 밀리초 단위의 시작 시간
            end_time: epoch 이후 밀리초 단위의 종료 시간

        반환값:
            결과 딕셔너리 목록

        예외:
            TimeoutError: 제한 시간 안에 쿼리가 완료되지 않는 경우
            Exception: 쿼리가 실패하는 경우
        """
        self.logger.debug("Starting CloudWatch query on log group: %s", log_group_name)

        try:
            response = self.logs_client.start_query(
                logGroupName=log_group_name,
                startTime=start_time // 1000,
                endTime=end_time // 1000,
                queryString=query_string,
            )
        except self.logs_client.exceptions.ResourceNotFoundException as e:
            self.logger.error("Log group not found: %s", log_group_name)
            raise Exception(f"Log group not found: {log_group_name}") from e

        query_id = response["queryId"]
        self.logger.debug("Query started with ID: %s", query_id)

        start_poll_time = time.time()
        while True:
            elapsed = time.time() - start_poll_time
            if elapsed > self.QUERY_TIMEOUT_SECONDS:
                raise TimeoutError(f"Query {query_id} timed out after {self.QUERY_TIMEOUT_SECONDS} seconds")

            result = self.logs_client.get_query_results(queryId=query_id)
            status = result["status"]

            if status == "Complete":
                results = result.get("results", [])
                self.logger.debug("Query completed with %d results", len(results))
                return results
            elif status == "Failed" or status == "Cancelled":
                raise Exception(f"Query {query_id} failed with status: {status}")

            time.sleep(self.POLL_INTERVAL_SECONDS)
