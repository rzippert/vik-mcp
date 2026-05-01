import os

# Set environment variables BEFORE any other imports
os.environ["VIKUNJA_BASE_URL"] = "http://localhost:3456"
os.environ["VIKUNJA_API_TOKEN"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzc2NjQ1NjYsImlkIjoxLCJqdGkiOiIxMjk4ZjhmZi04OTJiLTQ0MDItYmQxZS05MTcyZmRhNzA3OTkiLCJzaWQiOiIwNjJhMGI0Ni00OGYwLTRlZDktYjgwMS0wNTAyNGU4ZmE1MTMiLCJ0eXBlIjoxLCJ1c2VybmFtZSI6InRlc3R1c2VyIn0.nQsGSXaZOgNRh04G1AXHXWPPdDZpxMYwo_ggCOHguUw"

import pytest
import server

@pytest.fixture(autouse=True)
async def clear_client():
    """Ensure the httpx client is recreated for each test loop."""
    if server._client:
        await server._client.aclose()
        server._client = None
    yield
    if server._client:
        await server._client.aclose()
        server._client = None
