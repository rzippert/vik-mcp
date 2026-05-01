import pytest
import json
from server import manage_labels

@pytest.mark.asyncio
async def test_label_lifecycle():
    # Create
    res = await manage_labels("create", title="Test Label", hex_color="#ff0000")
    label = json.loads(res)
    label_id = label["id"]
    assert label["title"] == "Test Label"

    # List
    res_list = await manage_labels("list")
    labels = json.loads(res_list)
    assert any(l["id"] == label_id for l in labels)

    # Delete
    res_delete = await manage_labels("delete", label_id=label_id)
    assert "Deleted successfully" in res_delete
