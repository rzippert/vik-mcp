FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation to improve startup time
ENV UV_COMPILE_BYTECODE=1

# Copy project files
COPY pyproject.toml uv.lock README.md server.py ./

# Install the project and its dependencies
RUN uv sync --frozen --no-dev

# Expose the MCP streamable-http port
EXPOSE 8000

ENTRYPOINT ["uv", "run", "vikunjamcp"]
