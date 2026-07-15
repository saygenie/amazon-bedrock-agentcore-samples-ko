from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    host="0.0.0.0",
    stateless_http=True,  # nosec B104
)  # nosec B104 - AgentCore Runtime 컨테이너는 모든 인터페이스에 바인딩해야 함


@mcp.tool()
def getOrder() -> int:
    """Get an order"""
    return 123


@mcp.tool()
def updateOrder(orderId: int) -> int:
    """Update existing order"""
    return 456


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
