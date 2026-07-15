"""streaming Notebook(04-streaming.ipynb)용 MCP 서버입니다.

도구:
  - streaming_demo  - 서버가 SSE를 통해 내보내는 progress notification
  - failing_demo    - stream 중간 도구 예외
  - logging_demo    - 서버가 내보내는 `notifications/message` 이벤트
  - keepalive_demo  - 주기적인 progress를 통한 장기 실행 keep-alive
  - getOrder        - 단순 동기화 sanity 도구
"""

import asyncio

from fastmcp import Context, FastMCP

mcp = FastMCP(name="labstream")


@mcp.tool()
async def streaming_demo(ctx: Context, steps: int = 5) -> str:
    """Emit `steps` progress notifications over ~`steps/2` seconds, then return."""
    for i in range(steps):
        await ctx.report_progress(
            progress=i + 1, total=steps, message=f"Step {i + 1}/{steps}"
        )
        await asyncio.sleep(0.5)
    return f"Completed {steps} steps."


@mcp.tool()
async def failing_demo(ctx: Context, steps: int = 3) -> str:
    """Emit `steps` progress notifications then raise."""
    for i in range(steps):
        await ctx.report_progress(
            progress=i + 1, total=steps, message=f"Step {i + 1}/{steps}"
        )
        await asyncio.sleep(0.3)
    raise RuntimeError("intentional failure for mid-stream error test")


@mcp.tool()
async def logging_demo(ctx: Context) -> str:
    """Emit one log event at each severity (`notifications/message` events)."""
    await ctx.debug("debug message")
    await ctx.info("info message")
    await ctx.warning("warning message")
    await ctx.error("error message")
    return "logged"


@mcp.tool()
async def keepalive_demo(
    ctx: Context,
    duration_seconds: int = 60,
    interval_seconds: int = 30,
    emit_progress: bool = True,
) -> dict:
    """Sleep for `duration_seconds`, optionally emitting a progress
    notification every `interval_seconds` to keep the SSE connection alive."""
    started = asyncio.get_event_loop().time()
    iterations = 0
    while True:
        elapsed = asyncio.get_event_loop().time() - started
        if elapsed >= duration_seconds:
            break
        if emit_progress:
            await ctx.report_progress(
                progress=int(elapsed),
                total=duration_seconds,
                message=f"alive at {int(elapsed)}s/{duration_seconds}s",
            )
        iterations += 1
        sleep_for = min(interval_seconds, duration_seconds - elapsed)
        if sleep_for <= 0:
            break
        await asyncio.sleep(sleep_for)
    return {
        "duration_seconds_requested": duration_seconds,
        "elapsed_seconds": round(asyncio.get_event_loop().time() - started, 1),
        "iterations": iterations,
        "emit_progress": emit_progress,
    }


@mcp.tool()
def getOrder() -> int:
    """Trivial sync sanity tool."""
    return 123


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        stateless_http=True,  # nosec B104
    )  # nosec B104 - AgentCore Runtime 컨테이너는 모든 인터페이스에 바인딩해야 함
