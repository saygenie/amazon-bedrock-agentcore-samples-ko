"""session 관리 Notebook(05-session-management.ipynb)용 MCP 서버입니다.

다음을 시연합니다.
  - 도구 호출 간 session 연속성(session_counter)
  - Session 격리(새 `Mcp-Session-Id`에서 counter 초기화)
  - 영속화된 client-sid ↔ target-sid 매핑(session별 counter로 확인 가능)

이 서버는 AgentCore Runtime에 배포되고 `sessionConfiguration`이 활성화되며
`streamingConfiguration.enableResponseStreaming`은 없는(streaming 비활성화)
gateway를 통해 제공됩니다. Lambda 인터셉터는 사용하지 않습니다.
"""

from collections import defaultdict
from contextlib import asynccontextmanager

from fastmcp import Context, FastMCP


@asynccontextmanager
async def lifespan(server: FastMCP):
    """프로세스별 상태이며 counter는 `Mcp-Session-Id`를 키로 사용합니다."""
    yield {"session_counters": defaultdict(int)}


mcp = FastMCP(name="labsession", lifespan=lifespan)


def _session_id(ctx: Context) -> str:
    """fastmcp 버전 전반에서 가능한 범위 내에서 session ID를 추출합니다."""
    return (
        getattr(ctx, "session_id", None)
        or getattr(getattr(ctx, "session", None), "session_id", None)
        or "unknown"
    )


@mcp.tool()
async def session_counter(ctx: Context) -> dict:
    """Per-session counter — calls within the same `Mcp-Session-Id` see incrementing values."""
    counters = ctx.request_context.lifespan_context["session_counters"]
    sid = _session_id(ctx)
    counters[sid] += 1
    return {"session_id": sid, "count": counters[sid]}


@mcp.tool()
def getOrder() -> int:
    """Trivial sync sanity tool."""
    return 123


@mcp.tool()
def updateOrder(orderId: int) -> int:
    """Trivial sync sanity tool — returns a fixed ack."""
    return 456


if __name__ == "__main__":
# stateless_http=False는 fastmcp의 내부 session ID를 계속 사용할 수 있게 하며,
# gateway의 `sessionConfiguration`은 *클라이언트* 측 session ID를 제공
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        stateless_http=False,  # nosec B104
    )  # nosec B104 - AgentCore Runtime 컨테이너는 모든 인터페이스에 바인딩해야 함
