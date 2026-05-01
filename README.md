# vik-mcp

An MCP (Model Context Protocol) server that provides an LLM-friendly, scientifically optimized interface to [Vikunja](https://vikunja.io/) task management.

## 🧠 Why This Exists (The Rationale)

Building an MCP server for a complex task manager requires more than just passing API endpoints to an LLM. It requires designing for both **LLM Context Limitations** and **Human Cognitive Psychology**.

### 1. Tool & Resource Selection: Designing for the LLM
The native Vikunja API has over 80+ endpoints. Exposing all of them would overwhelm an LLM's context window and lead to hallucinated tool calls. 
* **Flattened CRUD:** We condensed task management into a single `manage_task` tool. The LLM simply declares an `action` ("create", "update", "delete") and passes the fields it wants to change. The server handles fetching the current state and merging partial updates.
* **Auto-Pagination:** LLMs struggle with multi-step pagination loops. `vik-mcp` automatically collects all pages behind the scenes and returns a unified array.
* **Resources over Tools:** We expose `vikunja://` URIs as Resources so the LLM can instantly read project states and label lists without burning a tool call just to look around.

### 2. Prompt Selection: Designing for Human Executive Function
Task managers often become "graveyards of good intentions" that trigger decision fatigue. The built-in prompts turn the LLM from a simple database-entry bot into an **executive-functioning coach**, built on scientifically proven productivity principles:
* **`make_my_day`**: Cures analysis paralysis. Instead of showing the user 50 open tasks, the AI uses the **Pareto Principle (80/20)** to select 1-3 high-impact tasks (MITs), groups shallow admin work to prevent **Context Switching**, and builds a daily schedule aligned with 90-minute **Ultradian rhythms**.
* **`plan_tasks`**: Uses **Implementation Intentions** and **Micro-productivity**. It forces the LLM to break vague goals into 3-7 physical next actions starting with verbs, ensuring the brain registers them as actionable rather than overwhelming.
* **`review_project`**: Actively sweeps for overdue or "stale" tasks to close open mental loops (reducing the **Zeigarnik Effect**), proposing whether to defer, delete, or break them down.

---

## 🛠️ Capabilities

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

### Resources (Read-only Context)
| URI | Description |
|-----|-------------|
| `vikunja://projects` | All projects overview |
| `vikunja://projects/{id}` | Single project details |
| `vikunja://projects/{id}/tasks` | All tasks in a project |
| `vikunja://labels` | All available labels |

### Prompts
| Prompt | Description |
|--------|-------------|
| `make_my_day` | Scans backlog and builds a biologically-optimized daily schedule |
| `plan_tasks` | Breaks down a goal into concrete, time-estimated micro-tasks |
| `review_project` | Reviews project health and suggests MITs (Most Important Tasks) |

---

## 🔌 Connecting to Clients

By default, `vik-mcp` runs as an HTTP server using Server-Sent Events (SSE), making it perfect for containerized deployments and modern IDEs.

### Cursor
1. Open Cursor Settings > Features > MCP.
2. Click **+ Add New MCP Server**.
3. Set Name to `Vikunja`.
4. Set Type to **SSE**.
5. Set URL to `http://localhost:8000/mcp` (or your deployed URL).
6. Click **Save**.

### Windsurf
1. Open Windsurf Settings > MCP.
2. Click **Add Server**.
3. Choose **SSE** as the connection type.
4. Name it `Vikunja`.
5. Enter the URL: `http://localhost:8000/mcp`.

### Claude Desktop
*Note: Claude Desktop natively expects `stdio` (command-line) execution rather than HTTP/SSE.* 

If you want to use this with Claude Desktop locally, change the transport in `server.py` to `"stdio"` (`mcp.run(transport="stdio")`), then add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vikunja": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/absolute/path/to/vik-mcp/server.py"
      ],
      "env": {
        "VIKUNJA_BASE_URL": "https://vikunja.yourdomain.com",
        "VIKUNJA_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Vikunja instance with an API token

### Installation
```bash
# Clone and enter the directory
cd vik-mcp

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
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
This allows a single running Docker instance of `vik-mcp` to serve requests for different users securely.

### Running Local Server
```bash
uv run python server.py
# Server will start on http://0.0.0.0:8000/mcp
```

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