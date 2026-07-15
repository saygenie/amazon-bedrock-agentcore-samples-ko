"""CloudWatch Logs의 관찰성 데이터를 쿼리하는 클라이언트입니다."""

import logging
import time
from typing import List

import boto3

from .models import RuntimeLog, Span, TraceData


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

        if agent_id:
            parse_and_filter = f"""| parse resource.attributes.cloud.resource_id "runtime/*/" as parsedAgentId
        | filter parsedAgentId = '{agent_id}'"""
        else:
            parse_and_filter = ""

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
        {parse_and_filter}
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


class ObservabilityClient:
    """CloudWatch Logs에서 span과 Runtime 로그를 쿼리하는 클라이언트입니다."""

    SPANS_LOG_GROUP = "aws/spans"
    QUERY_TIMEOUT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 2

    def __init__(
        self,
        region_name: str,
        agent_id: str,
        runtime_suffix: str = "DEFAULT",
    ):
        """ObservabilityClient를 초기화합니다.

        인수:
            region_name: AWS 리전 이름
            agent_id: agent별 로그를 쿼리하는 데 사용할 Agent ID
            runtime_suffix: 로그 그룹의 Runtime 접미사(기본값: DEFAULT)
        """
        self.region = region_name
        self.agent_id = agent_id
        self.runtime_suffix = runtime_suffix
        self.runtime_log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-{runtime_suffix}"

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
        self.logger.info("Querying spans for session: %s (agent: %s)", session_id, self.agent_id)

        query_string = self.query_builder.build_spans_by_session_query(session_id, agent_id=self.agent_id)

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=self.SPANS_LOG_GROUP,
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
                log_group_name=self.runtime_log_group,
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
