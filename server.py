"""
Vikunja MCP Server
==================
A simplified MCP (Model Context Protocol) server for managing tasks and projects
in Vikunja. Wraps the Vikunja REST API into a small set of LLM-friendly tools,
resources, and prompts.

Configuration (environment variables):
    VIKUNJA_BASE_URL  — Base URL of your Vikunja instance (e.g. https://vikunja.example.com)
    VIKUNJA_API_TOKEN — API token for authentication (Bearer token)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("vikunja-mcp")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VIKUNJA_BASE_URL = os.environ.get("VIKUNJA_BASE_URL", "").rstrip("/")
VIKUNJA_API_TOKEN = os.environ.get("VIKUNJA_API_TOKEN", "")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

if not VIKUNJA_BASE_URL:
    logger.warning("VIKUNJA_BASE_URL is not set — server will fail on API calls")
if not VIKUNJA_API_TOKEN:
    logger.warning("VIKUNJA_API_TOKEN is not set — server will fail on API calls")

# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Lazy-init a shared async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=f"{VIKUNJA_BASE_URL}/api/v1",
            headers={
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    return _client


def _get_auth_header() -> str:
    """Retrieve the Authorization header from the incoming request, or fallback to env."""
    try:
        headers = get_http_headers(include_all=True)
        if headers and "authorization" in headers:
            return headers["authorization"]
    except Exception:
        pass

    if VIKUNJA_API_TOKEN:
        return f"Bearer {VIKUNJA_API_TOKEN}"

    raise RuntimeError("Authentication required: No API token provided in Authorization header or VIKUNJA_API_TOKEN environment variable.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
MAX_PAGES = 20  # safety cap to avoid infinite pagination loops
DEFAULT_PER_PAGE = 50


async def _paginated_get(path: str, params: dict | None = None) -> list[dict]:
    """Fetch all pages from a paginated Vikunja endpoint.

    Vikunja returns pagination info via headers:
      - x-pagination-total-pages
      - x-pagination-result-count

    This helper collects every page and returns the merged list.
    """
    client = _get_client()
    headers = {"Authorization": _get_auth_header()}
    params = dict(params or {})
    params.setdefault("per_page", DEFAULT_PER_PAGE)
    params.setdefault("page", 1)

    all_items: list[dict] = []
    for _ in range(MAX_PAGES):
        resp = await client.get(path, params=params, headers=headers)
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            # Some endpoints return a single object or wrapper — just return it
            return [items] if items else []
        all_items.extend(items)

        total_pages = int(resp.headers.get("x-pagination-total-pages", 1))
        current_page = params["page"]
        if current_page >= total_pages:
            break
        params["page"] = current_page + 1

    return all_items


async def _api_get(path: str, params: dict | None = None) -> Any:
    """Simple GET returning parsed JSON."""
    client = _get_client()
    headers = {"Authorization": _get_auth_header()}
    resp = await client.get(path, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def _api_put(path: str, body: dict) -> Any:
    """PUT request (Vikunja uses PUT for creation)."""
    client = _get_client()
    headers = {"Authorization": _get_auth_header()}
    resp = await client.put(path, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def _api_post(path: str, body: dict) -> Any:
    """POST request (Vikunja uses POST for updates)."""
    client = _get_client()
    headers = {"Authorization": _get_auth_header()}
    resp = await client.post(path, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def _api_delete(path: str) -> str:
    """DELETE request, returns confirmation message."""
    client = _get_client()
    headers = {"Authorization": _get_auth_header()}
    resp = await client.delete(path, headers=headers)
    resp.raise_for_status()
    return "Deleted successfully."


def _compact_task(t: dict) -> dict:
    """Return a compact representation of a task for list views."""
    return {
        "id": t.get("id"),
        "title": t.get("title"),
        "done": t.get("done"),
        "priority": t.get("priority"),
        "due_date": t.get("due_date"),
        "project_id": t.get("project_id"),
        "percent_done": t.get("percent_done"),
        "labels": [lb.get("title") for lb in (t.get("labels") or [])],
        "assignees": [
            a.get("username") for a in (t.get("assignees") or [])
        ],
    }


def _compact_project(p: dict) -> dict:
    """Return a compact representation of a project."""
    return {
        "id": p.get("id"),
        "title": p.get("title"),
        "description": p.get("description", "")[:200],
        "is_archived": p.get("is_archived"),
        "identifier": p.get("identifier"),
    }


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "Vikunja",
    instructions=(
        "You are connected to a Vikunja task management instance. "
        "Use the available tools to manage projects and tasks. "
        "When updating a task, you only need to provide the fields you want to change — "
        "the server will merge them with the current task state automatically. "
        "All list endpoints are auto-paginated; you never need to worry about page numbers."
    ),
)


# ============================= TOOLS =====================================

@mcp.tool()
async def list_projects(search: str = "") -> str:
    """List all projects the user has access to.

    Use this to discover available projects before working with tasks.
    Returns a compact list with id, title, description, and archive status.

    Args:
        search: Optional text to filter projects by title.
    """
    params = {}
    if search:
        params["s"] = search
    projects = await _paginated_get("/projects", params)
    result = [_compact_project(p) for p in projects]
    return json.dumps(result, indent=2)


@mcp.tool()
async def manage_project(
    action: str,
    project_id: int | None = None,
    title: str | None = None,
    description: str | None = None,
    is_archived: bool | None = None,
    identifier: str | None = None,
    hex_color: str | None = None,
    parent_project_id: int | None = None,
) -> str:
    """Create, update, or delete a project.

    Actions:
      - "create": Creates a new project. Requires at least `title`.
      - "update": Updates an existing project. Requires `project_id`. Only provide
        the fields you want to change — other fields are left untouched.
      - "delete": Deletes a project. Requires `project_id`.

    Args:
        action: One of "create", "update", or "delete".
        project_id: Required for update and delete.
        title: Project title (required for create).
        description: Project description.
        is_archived: Whether the project is archived.
        identifier: Short identifier used in task references (e.g. "PROJ").
        hex_color: Hex color code for the project (e.g. "#ff5733").
        parent_project_id: ID of a parent project to nest this project under.
    """
    if action == "create":
        if not title:
            return "Error: 'title' is required to create a project."
        body: dict[str, Any] = {"title": title}
        if description is not None:
            body["description"] = description
        if identifier is not None:
            body["identifier"] = identifier
        if hex_color is not None:
            body["hex_color"] = hex_color
        if parent_project_id is not None:
            body["parent_project_id"] = parent_project_id
        result = await _api_put("/projects", body)
        return json.dumps(result, indent=2)

    elif action == "update":
        if not project_id:
            return "Error: 'project_id' is required for update."
        # Fetch current state, merge changes
        current = await _api_get(f"/projects/{project_id}")
        for key, val in {
            "title": title,
            "description": description,
            "is_archived": is_archived,
            "identifier": identifier,
            "hex_color": hex_color,
            "parent_project_id": parent_project_id,
        }.items():
            if val is not None:
                if key == "is_archived" and isinstance(val, str):
                    val = val.lower() == "true"
                current[key] = val
        result = await _api_post(f"/projects/{project_id}", current)
        return json.dumps(result, indent=2)

    elif action == "delete":
        if not project_id:
            return "Error: 'project_id' is required for delete."
        return await _api_delete(f"/projects/{project_id}")

    return f"Error: Unknown action '{action}'. Use 'create', 'update', or 'delete'."


@mcp.tool()
async def search_tasks(
    search: str = "",
    filter: str = "",
    project_id: int | None = None,
    sort_by: str = "",
    order_by: str = "",
) -> str:
    """Search and filter tasks across all projects (or within a specific project).

    This tool auto-paginates — you always get the complete result set (up to a
    safety limit). Returns compact task summaries.

    For advanced filtering, use Vikunja's filter syntax in the `filter` parameter.
    Examples of filter syntax:
      - "done = false"           → only incomplete tasks
      - "priority >= 3"          → high priority tasks
      - "due_date < now"         → overdue tasks
      - "assignees in user123"   → tasks assigned to user123
    See https://vikunja.io/docs/filters/ for the full filter reference.

    Args:
        search: Free-text search across task titles and descriptions.
        filter: Vikunja filter query string for advanced filtering.
        project_id: If provided, only returns tasks from this project.
        sort_by: Field to sort by (e.g. "due_date", "priority", "created", "done").
                 Can be comma-separated for multi-sort.
        order_by: Sort direction: "asc" or "desc". Can be comma-separated to match
                  multiple sort_by fields.
    """
    params: dict[str, Any] = {}
    if search:
        params["s"] = search
    if filter:
        params["filter"] = filter
    if sort_by:
        params["sort_by"] = [s.strip() for s in sort_by.split(",") if s.strip()]
    if order_by:
        params["order_by"] = [o.strip() for o in order_by.split(",") if o.strip()]

    if project_id:
        # Need to find the default view for the project
        views = await _api_get(f"/projects/{project_id}/views")
        if not views:
            return f"Error: No views found for project {project_id}."
        view_id = views[0]["id"]
        tasks = await _paginated_get(
            f"/projects/{project_id}/views/{view_id}/tasks", params
        )
    else:
        tasks = await _paginated_get("/tasks", params)

    result = [_compact_task(t) for t in tasks]
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_task(task_id: int) -> str:
    """Get the full details of a single task, including all metadata.

    Returns the complete task object with: title, description, labels, assignees,
    comments, reminders, related tasks, priority, due dates, percent done, etc.

    Use this when you need full detail about a specific task (e.g. to read its
    description before updating it, or to check its comments).

    Args:
        task_id: The numeric ID of the task to retrieve.
    """
    task = await _api_get(f"/tasks/{task_id}")
    return json.dumps(task, indent=2)


@mcp.tool()
async def manage_task(
    action: str,
    task_id: int | None = None,
    project_id: int | None = None,
    title: str | None = None,
    description: str | None = None,
    done: bool | None = None,
    priority: int | None = None,
    due_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    hex_color: str | None = None,
    percent_done: float | None = None,
    repeat_after: int | None = None,
    is_favorite: bool | None = None,
    labels: list[int] | None = None,
    assignees: list[str] | None = None,
    reminders: list[str] | None = None,
) -> str:
    """Create, update, or delete a task — the main tool for task management.

    This is a high-level tool that handles the common task operations in a single
    call. For updates, you only need to provide the fields you want to change.

    Actions:
      - "create": Creates a new task. Requires `project_id` and `title`.
      - "update": Updates an existing task. Requires `task_id`. Only provide fields
        you want to change — all others remain untouched.
      - "delete": Deletes a task. Requires `task_id`.

    Args:
        action: One of "create", "update", or "delete".
        task_id: Task ID — required for update and delete.
        project_id: Project ID — required for create.
        title: Task title.
        description: Task description (supports markdown).
        done: Whether the task is completed.
        priority: Priority level (0=unset, 1=low, 2=medium, 3=high, 4=urgent).
        due_date: Due date in ISO 8601 format (e.g. "2025-12-31T23:59:59Z").
        start_date: Start date in ISO 8601 format.
        end_date: End date in ISO 8601 format.
        hex_color: Color in hex format (e.g. "#ff5733").
        percent_done: Completion percentage as a float between 0 and 1.
        repeat_after: Repeat interval in seconds (0 to disable).
        is_favorite: Whether to mark the task as a favorite.
        labels: List of label IDs to set on the task (replaces existing labels).
        assignees: List of usernames to assign to the task (replaces existing assignees).
        reminders: List of reminder datetimes in ISO 8601 format.
    """
    if action == "create":
        if not project_id:
            return "Error: 'project_id' is required to create a task."
        if not title:
            return "Error: 'title' is required to create a task."

        body: dict[str, Any] = {"title": title}
        _set_task_fields(body, locals())

        if reminders:
            body["reminders"] = [
                {"reminder": r} for r in reminders
            ]

        result = await _api_put(f"/projects/{project_id}/tasks", body)
        task_id_created = result.get("id")

        # Handle labels and assignees post-creation
        if labels and task_id_created:
            await _set_task_labels(task_id_created, labels)
        if assignees and task_id_created:
            await _set_task_assignees(task_id_created, assignees)

        # Fetch the complete task to return
        final = await _api_get(f"/tasks/{task_id_created}")
        return json.dumps(final, indent=2)

    elif action == "update":
        if not task_id:
            return "Error: 'task_id' is required for update."

        # Fetch current task state
        current = await _api_get(f"/tasks/{task_id}")

        # Merge scalar fields
        _set_task_fields(current, locals())

        if reminders is not None:
            current["reminders"] = [
                {"reminder": r} for r in reminders
            ]

        result = await _api_post(f"/tasks/{task_id}", current)

        # Handle labels and assignees
        if labels is not None:
            await _set_task_labels(task_id, labels)
        if assignees is not None:
            await _set_task_assignees(task_id, assignees)

        final = await _api_get(f"/tasks/{task_id}")
        return json.dumps(final, indent=2)

    elif action == "delete":
        if not task_id:
            return "Error: 'task_id' is required for delete."
        return await _api_delete(f"/tasks/{task_id}")

    return f"Error: Unknown action '{action}'. Use 'create', 'update', or 'delete'."


def _set_task_fields(body: dict, local_vars: dict) -> None:
    """Merge provided task fields into the request body."""
    field_map = {
        "title": "title",
        "description": "description",
        "done": "done",
        "priority": "priority",
        "due_date": "due_date",
        "start_date": "start_date",
        "end_date": "end_date",
        "hex_color": "hex_color",
        "percent_done": "percent_done",
        "repeat_after": "repeat_after",
        "is_favorite": "is_favorite",
    }
    for param_name, api_field in field_map.items():
        val = local_vars.get(param_name)
        if val is not None:
            if api_field in ["done", "is_favorite"]:
                if isinstance(val, str):
                    val = val.lower() == "true"
            body[api_field] = val


async def _set_task_labels(task_id: int, label_ids: list[int]) -> None:
    """Replace all labels on a task using the bulk endpoint."""
    try:
        await _api_post(
            f"/tasks/{task_id}/labels/bulk",
            {"labels": [{"id": lid} for lid in label_ids]},
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to set labels on task {task_id}: {e}")


async def _set_task_assignees(task_id: int, usernames: list[str]) -> None:
    """Set assignees on a task by username.

    First resolves usernames to user IDs via the project users endpoint,
    then uses the bulk assignee endpoint.
    """
    try:
        # Get the task to know which project it belongs to
        task = await _api_get(f"/tasks/{task_id}")
        project_id = task.get("project_id")
        if not project_id:
            return

        # Get users in the project
        project_users = await _api_get(f"/projects/{project_id}/projectusers")
        # project_users is a list of user objects
        username_to_id: dict[str, int] = {}
        if isinstance(project_users, list):
            for u in project_users:
                username_to_id[u.get("username", "")] = u.get("id", 0)

        user_ids = []
        for uname in usernames:
            uid = username_to_id.get(uname)
            if uid:
                user_ids.append(uid)
            else:
                logger.warning(
                    f"Username '{uname}' not found in project {project_id}"
                )

        if user_ids:
            await _api_post(
                f"/tasks/{task_id}/assignees/bulk",
                {"assignees": [{"id": uid} for uid in user_ids]},
            )
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to set assignees on task {task_id}: {e}")


@mcp.tool()
async def manage_labels(
    action: str,
    label_id: int | None = None,
    title: str | None = None,
    description: str | None = None,
    hex_color: str | None = None,
) -> str:
    """List, create, update, or delete labels.

    Labels can be attached to tasks for categorization. Use this tool to manage
    the available labels, then use manage_task with label IDs to assign them.

    Actions:
      - "list": Returns all available labels.
      - "create": Creates a new label. Requires `title`.
      - "update": Updates an existing label. Requires `label_id`.
      - "delete": Deletes a label. Requires `label_id`.

    Args:
        action: One of "list", "create", "update", or "delete".
        label_id: Label ID — required for update and delete.
        title: Label title (required for create).
        description: Label description.
        hex_color: Label color in hex format (e.g. "#ff5733").
    """
    if action == "list":
        labels = await _paginated_get("/labels")
        return json.dumps(labels, indent=2)

    elif action == "create":
        if not title:
            return "Error: 'title' is required to create a label."
        body: dict[str, Any] = {"title": title}
        if description is not None:
            body["description"] = description
        if hex_color is not None:
            body["hex_color"] = hex_color
        result = await _api_put("/labels", body)
        return json.dumps(result, indent=2)

    elif action == "update":
        if not label_id:
            return "Error: 'label_id' is required for update."
        current = await _api_get(f"/labels/{label_id}")
        if title is not None:
            current["title"] = title
        if description is not None:
            current["description"] = description
        if hex_color is not None:
            current["hex_color"] = hex_color
        result = await _api_put(f"/labels/{label_id}", current)
        return json.dumps(result, indent=2)

    elif action == "delete":
        if not label_id:
            return "Error: 'label_id' is required for delete."
        return await _api_delete(f"/labels/{label_id}")

    return f"Error: Unknown action '{action}'. Use 'list', 'create', 'update', or 'delete'."


@mcp.tool()
async def manage_comments(
    action: str,
    task_id: int | None = None,
    comment_id: int | None = None,
    comment: str | None = None,
) -> str:
    """List, create, update, or delete comments on a task.

    Comments are threaded discussions attached to tasks. Use this to read existing
    comments, add new ones, or modify/remove existing ones.

    Actions:
      - "list": Lists all comments on a task. Requires `task_id`.
      - "create": Adds a new comment. Requires `task_id` and `comment`.
      - "update": Edits an existing comment. Requires `task_id`, `comment_id`,
        and `comment`.
      - "delete": Removes a comment. Requires `task_id` and `comment_id`.

    Args:
        action: One of "list", "create", "update", or "delete".
        task_id: The task ID the comment belongs to.
        comment_id: The comment ID — required for update and delete.
        comment: The comment text (supports markdown).
    """
    if not task_id:
        return "Error: 'task_id' is required for all comment operations."

    if action == "list":
        comments = await _paginated_get(f"/tasks/{task_id}/comments")
        return json.dumps(comments, indent=2)

    elif action == "create":
        if not comment:
            return "Error: 'comment' text is required."
        result = await _api_put(
            f"/tasks/{task_id}/comments", {"comment": comment}
        )
        return json.dumps(result, indent=2)

    elif action == "update":
        if not comment_id:
            return "Error: 'comment_id' is required for update."
        if not comment:
            return "Error: 'comment' text is required for update."
        result = await _api_post(
            f"/tasks/{task_id}/comments/{comment_id}", {"comment": comment}
        )
        return json.dumps(result, indent=2)

    elif action == "delete":
        if not comment_id:
            return "Error: 'comment_id' is required for delete."
        return await _api_delete(f"/tasks/{task_id}/comments/{comment_id}")

    return f"Error: Unknown action '{action}'. Use 'list', 'create', 'update', or 'delete'."


# ============================= RESOURCES ==================================

@mcp.resource("vikunja://projects")
async def resource_projects() -> str:
    """All projects the authenticated user has access to.

    Provides a read-only overview of every project including id, title,
    description, and archive status. Use this resource to get context about
    available projects before managing tasks.
    """
    projects = await _paginated_get("/projects")
    result = [_compact_project(p) for p in projects]
    return json.dumps(result, indent=2)


@mcp.resource("vikunja://projects/{project_id}")
async def resource_project(project_id: int) -> str:
    """Full details of a single project.

    Returns the complete project object including its views, settings,
    and owner information.
    """
    project = await _api_get(f"/projects/{project_id}")
    return json.dumps(project, indent=2)


@mcp.resource("vikunja://projects/{project_id}/tasks")
async def resource_project_tasks(project_id: int) -> str:
    """All tasks in a specific project.

    Returns compact task summaries for every task in the project.
    Useful for getting an overview before making changes.
    """
    views = await _api_get(f"/projects/{project_id}/views")
    if not views:
        return json.dumps([], indent=2)
    view_id = views[0]["id"]
    tasks = await _paginated_get(f"/projects/{project_id}/views/{view_id}/tasks")
    result = [_compact_task(t) for t in tasks]
    return json.dumps(result, indent=2)


@mcp.resource("vikunja://labels")
async def resource_labels() -> str:
    """All labels available to the authenticated user.

    Returns the complete list of labels with their IDs, titles, colors,
    and descriptions. Useful for knowing which labels exist before assigning
    them to tasks.
    """
    labels = await _paginated_get("/labels")
    return json.dumps(labels, indent=2)


# ============================= PROMPTS ====================================

@mcp.prompt()
def plan_tasks(goal: str, project_id: int) -> str:
    """Break down a goal into actionable Vikunja tasks.

    Use this prompt when the user has a high-level goal and wants to create
    a structured set of tasks to accomplish it.

    Args:
        goal: The high-level goal or objective to break down.
        project_id: The Vikunja project ID where tasks should be created.
    """
    return f"""You are a task planning assistant connected to Vikunja.

The user wants to accomplish the following goal:
"{goal}"

Tasks should be created in project ID {project_id}.

Instructions:
1. Break the goal into 3-7 concrete, actionable tasks.
2. For each task, determine:
   - A clear, specific title
   - A brief description with acceptance criteria
   - Priority (1=low, 2=medium, 3=high, 4=urgent)
   - Due date if applicable (use ISO 8601 format)
3. Create all tasks using the manage_task tool with action="create".
4. Consider task dependencies and order them logically.
5. After creating all tasks, provide a summary of what was created.
"""


@mcp.prompt()
def review_project(project_id: int) -> str:
    """Review all tasks in a project and suggest next actions.

    Use this prompt to get an overview of a project's status and
    recommendations for what to work on next.

    Args:
        project_id: The Vikunja project ID to review.
    """
    return f"""You are a project review assistant connected to Vikunja.

Review project ID {project_id} by following these steps:

1. First, use the search_tasks tool to get all tasks in the project.
2. Analyze the tasks by status:
   - How many are done vs. incomplete?
   - Are there overdue tasks?
   - What are the highest priority incomplete tasks?
3. Provide a structured summary:
   - Overall project health (on track / at risk / behind)
   - Top 3 tasks to focus on next (with reasons)
   - Any overdue tasks that need immediate attention
   - Suggestions for improvement (e.g. tasks that should be reprioritized)
"""


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main():
    """Run the Vikunja MCP server over streamable HTTP."""
    logger.info(f"Starting Vikunja MCP server on {MCP_HOST}:{MCP_PORT}/mcp")
    mcp.run(
        transport="streamable-http",
        host=MCP_HOST,
        port=MCP_PORT,
    )


if __name__ == "__main__":
    main()
