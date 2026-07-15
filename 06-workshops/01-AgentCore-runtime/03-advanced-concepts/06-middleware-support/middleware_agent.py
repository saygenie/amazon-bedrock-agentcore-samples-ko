import time
from datetime import datetime
import traceback
import uuid

from bedrock_agentcore import BedrockAgentCoreApp
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from strands import Agent
from strands.models import BedrockModel
from opentelemetry import baggage, context as otel_context


# Middleware 1: 관찰성(로깅 + 지표)
class ObservabilityMiddleware(BaseHTTPMiddleware):
    """포괄적인 관찰성을 위해 로깅과 지표 수집을 결합합니다."""

    async def dispatch(self, request, call_next):
        # 로깅: 요청 세부 정보 기록
        timestamp = datetime.now().isoformat()
        print(f"\n[{timestamp}] REQUEST: {request.method} {request.url.path}")

        # 지표: 시간 측정 시작
        start_time = time.time()

        # 요청 처리
        response = await call_next(request)

        # 지표: 소요 시간 계산
        duration = time.time() - start_time

        # 로깅: 응답 세부 정보 기록
        print(f"[{timestamp}] RESPONSE: Status {response.status_code} | Duration {duration:.4f}s")

        # baggage에 메타데이터 추가(응답으로 반환됨)
        ctx = baggage.set_baggage("middleware.process_time", f"{duration:.4f}s")
        ctx = baggage.set_baggage("middleware.timestamp", timestamp, ctx)
        otel_context.attach(ctx)

        # 헤더에도 추가(AgentCore에서 제거되지만 CloudWatch에서 확인 가능)
        response.headers["x-process-time"] = f"{duration:.4f}s"

        return response


# Middleware 2: 오류 처리
class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """오류를 적절히 처리하고 오류 응답 형식을 일관되게 지정합니다."""

    async def dispatch(self, request, call_next):
        # 이 요청의 상관관계 ID 생성
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # baggage에 상관관계 ID 추가
        ctx = baggage.set_baggage("correlation.id", correlation_id)
        otel_context.attach(ctx)

        try:
            response = await call_next(request)
            # 헤더에 상관관계 ID 추가(CloudWatch용)
            response.headers["x-correlation-id"] = correlation_id
            return response

        except Exception as e:
            # 컨텍스트와 함께 전체 오류 기록
            error_details = {
                "correlation_id": correlation_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "path": request.url.path,
                "method": request.method,
            }
            print(f"\n❌ ERROR: {error_details}")
            print(f"Traceback: {traceback.format_exc()}")

            # baggage에 오류 정보 추가
            ctx = baggage.set_baggage("error.occurred", "true")
            ctx = baggage.set_baggage("error.type", type(e).__name__, ctx)
            otel_context.attach(ctx)

            # 사용자 친화적인 오류 응답 반환
            return JSONResponse(
                status_code=500,
                content={
                    "error": "An error occurred processing your request",
                    "correlation_id": correlation_id,
                    "message": "Please contact support with this correlation ID",
                },
                headers={"x-correlation-id": correlation_id},
            )


# Middleware 체인으로 앱 생성
# 순서가 중요함: ErrorHandling이 전체를 감싸고 그 안에 Observability가 위치
app = BedrockAgentCoreApp(
    middleware=[
        Middleware(ErrorHandlingMiddleware),
        Middleware(ObservabilityMiddleware),
    ]
)

# Strands agent 초기화
model = BedrockModel(model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0")
agent = Agent(model=model, system_prompt="You are a helpful AI assistant.")


@app.entrypoint
def agent_handler(payload, context):
    """Middleware를 지원하는 Agent입니다."""
    user_message = payload.get("prompt", "Hello!")
    result = agent(user_message)

    return {"response": result.message}


if __name__ == "__main__":
    app.run()
