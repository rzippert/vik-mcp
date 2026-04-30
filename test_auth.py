from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP("AuthTest")

@mcp.tool()
async def check_auth() -> str:
    headers = get_http_headers(include_all=True)
    return str(headers.get("authorization", "no auth"))

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8888)
