# vik-mcp

An MCP (Model Context Protocol) server that provides an LLM-friendly, scientifically optimized interface to [Vikunja](https://vikunja.io/) task management.

## 🧠 Why This Exists (The Rationale)

Building an MCP server for a complex task manager requires more than just passing API endpoints to an LLM. It requires designing for both **LLM Context Limitations** and **Human Cognitive Psychology**.

### 1. Tool & Resource Selection: Designing for the LLM
The native Vikunja API has over 80+ endpoints. Exposing all of them would overwhelm an LLM's context window and lead to hallucinated tool calls. 
* **Flattened CRUD:** We condensed task management into a single `manage_task` tool. The LLM simply declares an `action` ("create", "update", "delete") and passes the fields it wants to change. The server handles fetching the current state and merging partial updates.
* **Auto-Pagination:** LLMs struggle with multi-step pagination loops. `vik-mcp` automatically collects all pages behind the scenes and returns a unified array.
* **Resources over Tools:** We expose `vik://` URIs as Resources so the LLM can instantly read project states and label lists without burning a tool call just to look around.

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
| `vik://projects` | All projects overview |
| `vik://projects/{project}` | Single project details — accepts project title (case-insensitive) or numeric ID |
| `vik://projects/{project}/tasks` | All tasks in a project (literal `tasks` keyword) |
| `vik://projects/{project}/{task}` | A single task by title within a project (numeric ID also works) |
| `vik://tasks` | All tasks across every project (global backlog) |
| `vik://labels` | All available labels |
| `vik://labels/{label}` | Single label details — accepts label title (case-insensitive) or numeric ID |
| `vik://labels/{label}/tasks` | All tasks tagged with a specific label |
| `vik://last` | 10 most recently updated tasks |

### Prompts
| Prompt | Description |
|--------|-------------|
| `make_my_day` | Scans backlog and builds a biologically-optimized daily schedule |
| `plan_tasks` | Breaks down a goal into concrete, time-estimated micro-tasks |
| `review_project` | Reviews project health and suggests MITs (Most Important Tasks) |

---

## 🔌 Connecting to Clients

The recommended way to use `vik-mcp` is via Docker using the images published to the GitHub Container Registry.

### 1. Claude Desktop
Add this to your `claude_desktop_config.json` (usually in `~/Library/Application Support/Claude/` on macOS or `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "vikunja": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "VIKUNJA_BASE_URL=https://vikunja.yourdomain.com",
        "-e", "VIKUNJA_API_TOKEN=your-api-token",
        "ghcr.io/rzippert/vik-mcp:latest"
      ]
    }
  }
}
```

### 2. VS Code (Copilot)
If you are using the GitHub Copilot extension with MCP support, add this to your settings:

```json
"github.copilot.chat.mcp.servers": {
  "vikunja": {
    "command": "docker",
    "args": [
      "run",
      "-i",
      "--rm",
      "-e", "VIKUNJA_BASE_URL=https://vikunja.yourdomain.com",
      "-e", "VIKUNJA_API_TOKEN=your-api-token",
      "ghcr.io/rzippert/vik-mcp:latest"
    ]
  }
}
```

### 3. Continue.dev
Add this to your `config.json` (usually in `~/.continue/config.json`):

```json
"mcpServers": [
  {
    "name": "vikunja",
    "command": "docker",
    "args": [
      "run",
      "-i",
      "--rm",
      "-e", "VIKUNJA_BASE_URL=https://vikunja.yourdomain.com",
      "-e", "VIKUNJA_API_TOKEN=your-api-token",
      "ghcr.io/rzippert/vik-mcp:latest"
    ]
  }
]
```

### 4. Advanced: Docker Compose (Streaming HTTP Mode)
If you prefer to run the server as a persistent background service (e.g., on a remote server or local cluster), you can use Docker Compose and connect via HTTP.

**docker-compose.yml**
```yaml
services:
  vik-mcp:
    image: ghcr.io/rzippert/vik-mcp:latest
    ports:
      - "8000:8000"
    environment:
      - VIKUNJA_BASE_URL=https://vikunja.yourdomain.com
      - VIKUNJA_API_TOKEN=your-api-token
    restart: unless-stopped
```

**VS Code / Cursor / Windsurf (HTTP Config)**
| Setting | Value |
|---------|-------|
| Transport Type | Streamable HTTP |
| URL | `http://localhost:8000/mcp` |

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

### Docker & Container Deployment

The easiest way to run `vik-mcp` is using the official Docker image.

#### Using the GitHub Container Registry (Recommended)
```bash
docker pull ghcr.io/rzippert/vik-mcp:latest

docker run -d \
  -p 8000:8000 \
  -e VIKUNJA_BASE_URL=https://vikunja.example.com \
  -e VIKUNJA_API_TOKEN=your-token-here \
  ghcr.io/rzippert/vik-mcp:latest
```

#### Local Build
```bash
# Build locally
docker build -t vikunjamcp .

# Run locally built image
docker run -d \
  -p 8000:8000 \
  -e VIKUNJA_BASE_URL=https://vikunja.example.com \
  -e VIKUNJA_API_TOKEN=your-token-here \
  vikunjamcp
```