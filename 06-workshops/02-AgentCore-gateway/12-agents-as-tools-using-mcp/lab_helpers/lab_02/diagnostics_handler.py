"""
Lab 02: Strands Diagnostics Agent Lambda 핸들러

이 모듈은 diagnostics agent의 Lambda 핸들러 함수를 제공합니다.
AgentCore Gateway 및 MCP 프로토콜과 함께 작동하도록 설계되었습니다.

기능:
- 사용자 컨텍스트 전파를 위한 actor_id 및 session_id 수락
- Agent 상태를 통한 AgentCore Memory 연동
- 진단 도구(EC2, NGINX, DynamoDB 로그, 지표) 정의
- Lambda의 동기 컨텍스트에서 비동기 Agent 호출 처리
- MCP와 호환되는 구조화된 응답 반환

이벤트 구조(MCP를 통해 Gateway에서 전달):
{
    "query": "User's diagnostic query",
    "actor_id": "user-identifier-from-jwt",
    "session_id": "session-id-for-grouping-calls"
}
"""

import asyncio
import os


def lambda_handler(event, context):
    """
    Strands diagnostics agent를 호출하는 AgentCore Gateway용 Lambda 핸들러입니다.

    MCP 프로토콜을 통해 Gateway에서 query, actor_id 및 session_id를 받습니다.
    Memory hook이 포함된 Strands agent를 생성하고 비동기 방식으로 호출합니다.
    Agent 출력과 요청 메타데이터가 포함된 구조화된 응답을 반환합니다.

    인자:
        event: 다음 키가 포함된 딕셔너리:
            - query (string): 사용자의 진단 쿼리
            - actor_id (string): JWT 토큰의 사용자 식별자
            - session_id (string): 관련 호출을 그룹화하는 세션 ID
        context: Lambda 컨텍스트 객체

    반환:
        다음 구조의 응답 딕셔너리:
            {
                "status": "success" | "error",
                "request_id": "session-id or aws_request_id",
                "agent_input": "user's query",
                "response": "agent's response text",
                "type": "strands_agent_response"
            }
    """
    try:
        # pip으로 설치한 패키지를 찾도록 Python 경로에 lib/ 추가
        import sys

        current_dir = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(current_dir, "lib")
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)

        from strands import Agent, tool
        from lab_helpers import mock_data

        # 환경 변수에서 모델 ID 가져오기(Lambda 구성에서 설정)
        MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-20250514-v1:0")

        # ===================================================================
        # 진단 도구 정의
        # ===================================================================

        @tool(description="Fetch EC2 application logs to identify application errors and issues")
        def get_ec2_logs(limit: int = 10) -> dict:
            """Fetch recent EC2 application logs from mock data"""
            logs = mock_data.get_ec2_logs()
            return {
                "logs": logs[:limit],
                "total": len(logs),
                "errors": [log["message"] for log in logs if "error" in log["message"].lower()][:5],
            }

        @tool(description="Fetch NGINX access/error logs to identify HTTP errors and worker issues")
        def get_nginx_logs(limit: int = 10) -> dict:
            """Fetch NGINX access/error logs from mock data"""
            logs = mock_data.get_nginx_logs()
            return {
                "logs": logs[:limit],
                "total": len(logs),
                "http_errors": [log["message"] for log in logs if "5" in log["message"]][:5],
                "worker_issues": [log["message"] for log in logs if "worker" in log["message"].lower()][:5],
            }

        @tool(description="Fetch DynamoDB operation logs to detect throttling and service issues")
        def get_dynamodb_logs(limit: int = 10) -> dict:
            """Fetch DynamoDB operation logs from mock data"""
            logs = mock_data.get_dynamodb_logs()
            return {
                "logs": logs[:limit],
                "total": len(logs),
                "throttling": [log["message"] for log in logs if "throttl" in log["message"].lower()][:5],
                "unavailable": [log["message"] for log in logs if "unavailable" in log["message"].lower()][:5],
            }

        @tool(description="Fetch CloudWatch metrics (CPU, Memory) to analyze resource utilization")
        def get_cloudwatch_metrics(metric_name: str, limit: int = 10) -> dict:
            """Fetch CloudWatch metrics from mock data"""
            metrics = mock_data.get_metrics(metric_name)
            high_values = [
                m for m in metrics if m.get("Maximum", 0) > (80 if metric_name == "MemoryUtilization" else 85)
            ]
            return {
                "metric": metric_name,
                "data_points": len(metrics),
                "high_utilization_periods": len(high_values),
                "peak_value": max([m.get("Maximum", 0) for m in metrics]) if metrics else 0,
            }

        # ===================================================================
        # 요청 컨텍스트 추출
        # ===================================================================

        # Gateway 이벤트에서 파라미터 추출
        agent_input = event.get("query", "Analyze system logs for issues")
        actor_id = event.get("actor_id", "unknown-actor")
        session_id = event.get("session_id", "default-session")

        # session_id를 요청 추적 ID로 사용(사용자 상호작용마다 고유)
        request_id = session_id

        # Memory hook에서 접근할 수 있도록 Agent 상태에 저장
        agent_state = {"actor_id": actor_id, "session_id": session_id}

        # ===================================================================
        # STRANDS AGENT 생성
        # ===================================================================

        diagnostic_agent = Agent(
            name="system_diagnostics_agent",
            model=MODEL_ID,
            tools=[
                get_ec2_logs,
                get_nginx_logs,
                get_dynamodb_logs,
                get_cloudwatch_metrics,
            ],
            system_prompt="""You are an expert system diagnostics agent. Your role is to analyze system logs and metrics to identify issues and their root causes.

When diagnosing system issues:
1. Start by gathering relevant logs (EC2, NGINX, DynamoDB)
2. Check CloudWatch metrics to understand resource utilization patterns
3. Correlate findings across different sources
4. Provide a clear assessment of severity and recommended actions

Always be thorough in your investigation and provide evidence-based conclusions.""",
            state=agent_state,  # Memory hook에 actor_id와 session_id 전달
        )

        # ===================================================================
        # AGENT를 비동기 방식으로 실행
        # ===================================================================

        # Agent 실행을 위한 비동기 함수 생성
        async def run_agent():
            """Agent를 비동기 방식으로 실행하고 응답을 반환합니다."""
            return await diagnostic_agent.invoke_async(agent_input)

        # 동기 Lambda 컨텍스트에서 비동기 함수 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent_response = loop.run_until_complete(run_agent())
        finally:
            loop.close()

        # ===================================================================
        # 응답 반환
        # ===================================================================

        return {
            "status": "success",
            "request_id": request_id,
            "agent_input": agent_input,
            "actor_id": actor_id,
            "session_id": session_id,
            "response": str(agent_response),
            "type": "strands_agent_response",
        }

    except Exception as e:
        import traceback

        return {
            "status": "error",
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "request_id": context.aws_request_id if context else "unknown",
        }
