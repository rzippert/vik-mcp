import pytest
import json
from server import manage_project, list_projects

@pytest.mark.asyncio
async def test_project_lifecycle():
    # Create
    res = await manage_project("create", title="Test Project")
    project = json.loads(res)
    project_id = project["id"]
    assert project["title"] == "Test Project"

    # List
    res_list = await list_projects()
    projects = json.loads(res_list)
    assert any(p["id"] == project_id for p in projects)

    # Update
    res_update = await manage_project("update", project_id=project_id, title="Updated Project Name")
    updated_project = json.loads(res_update)
    assert updated_project["title"] == "Updated Project Name"

    # Delete
    res_delete = await manage_project("delete", project_id=project_id)
    assert "Deleted successfully" in res_delete
