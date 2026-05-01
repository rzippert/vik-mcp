import pytest
import json
from server import manage_project, manage_task, get_task

@pytest.fixture
async def test_project():
    res = await manage_project("create", title="Task Test Project")
    project = json.loads(res)
    yield project
    await manage_project("delete", project_id=project["id"])

@pytest.mark.asyncio
async def test_task_lifecycle(test_project):
    project_id = test_project["id"]

    # Create
    res = await manage_task("create", project_id=project_id, title="Test Task", description="Initial description")
    task = json.loads(res)
    task_id = task["id"]
    assert task["title"] == "Test Task"
    assert task["done"] is False

    # Update scalar fields
    res = await manage_task("update", task_id=task_id, title="Updated Task", done=True)
    task = json.loads(res)
    assert task["title"] == "Updated Task"
    assert task["done"] is True

    # Get details
    res = await get_task(task_id)
    task = json.loads(res)
    assert task["id"] == task_id

    # Delete
    res = await manage_task("delete", task_id=task_id)
    assert "Deleted successfully" in res

@pytest.mark.asyncio
async def test_boolean_coercion(test_project):
    project_id = test_project["id"]
    res = await manage_task("create", project_id=project_id, title="Coercion Task")
    task_id = json.loads(res)["id"]

    # Test string "true"
    res = await manage_task("update", task_id=task_id, done="true")
    assert json.loads(res)["done"] is True

    # Test string "false"
    res = await manage_task("update", task_id=task_id, done="false")
    assert json.loads(res)["done"] is False
