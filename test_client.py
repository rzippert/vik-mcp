import asyncio
import os
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://127.0.0.1:8888/mcp", headers={"Authorization": "Bearer TEST_TOKEN"}) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            result = await session.call_tool("check_auth", arguments={})
            print("Tool result:", result.content[0].text)

asyncio.run(main())
