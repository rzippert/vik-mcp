# VikunjaMCP

An MCP (Model Context Protocol) server that provides LLM-friendly access to [Vikunja](https://vikunja.io/) task management.

## What It Does

Simplifies the full Vikunja API (80+ endpoints) into **7 tools**, **4 resources**, and **2 prompts** — designed for LLMs to manage tasks and projects efficiently.

### Tools

| Tool | Purpose |
|------|---------|
| `list_projects` | List/search all projects |
| `manage_project` | Create, update, or delete a project |
| `search_tasks` | Search/filter tasks with auto-pagination |
| `get_task` | Get full details of a single task |
| `manage_task` | Create, update, or delete tasks (with labels, assignees, reminders) |
| `manage_labels` | List, create, update, or delete labels |
| `manage_comments` | Manage task comments |

### Resources (read-only context)

| URI | Description |
|-----|-------------|
| `vikunja://projects` | All projects overview |
| `vikunja://projects/{id}` | Single project details |
| `vikunja://projects/{id}/tasks` | All tasks in a project |
| `vikunja://labels` | All available labels |

### Prompts

| Prompt | Description |
|--------|-------------|
| `plan_tasks` | Break down a goal into structured tasks |
| `review_project` | Review project status and suggest next actions |

## Key Design Decisions

- **Partial updates** — send only the fields you want to change; the server merges with current state
- **Auto-pagination** — no page numbers; all list endpoints return complete results
- **Unified CRUD** — each `manage_*` tool handles create/update/delete via an `action` parameter
- **Labels & assignees in one call** — `manage_task` can set labels and assignees during create/update
- **Streamable HTTP transport** — runs as an HTTP server for container-friendly deployments
- **Multi-user support** — clients can pass their API token dynamically via the `Authorization: Bearer <token>` HTTP header, allowing one server instance to serve multiple users. If no header is provided, it falls back to the `VIKUNJA_API_TOKEN` env var.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Vikunja instance with an API token

### Installation

```bash
# Clone and enter the directory
cd VikunjaMCP

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your Vikunja URL and API token
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VIKUNJA_BASE_URL` | Base URL of your Vikunja instance | *(required)* |
| `VIKUNJA_API_TOKEN` | Fallback API token. If omitted, clients MUST send an `Authorization: Bearer` header. | `""` |
| `MCP_HOST` | Host address to bind the MCP server | `0.0.0.0` |
| `MCP_PORT` | Port for the MCP server | `8000` |

### Multi-User / Multi-Tenant Support

If you do not set the `VIKUNJA_API_TOKEN` environment variable, the server will require the MCP client to pass the token dynamically in the HTTP headers:

```http
Authorization: Bearer your-api-token
```

This allows a single running instance of `VikunjaMCP` to serve requests for different users securely.

### Running

```bash
# Direct execution
uv run python server.py

# Or via the script entry point
uv run vikunjamcp
```

The server will start on `http://0.0.0.0:8000/mcp` by default.

### Docker

```bash
# Build
docker build -t vikunjamcp .

# Run
docker run -d \
  -p 8000:8000 \
  -e VIKUNJA_BASE_URL=https://vikunja.example.com \
  -e VIKUNJA_API_TOKEN=your-token-here \
  vikunjamcp
```

### MCP Client Configuration

Point your MCP client to the streamable HTTP endpoint:

```
http://your-host:8000/mcp
```

## Development

```bash
# Run with the MCP inspector for testing
uv run fastmcp dev server.py
```
