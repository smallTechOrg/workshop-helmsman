"""Audit trail: every Phase-2 action writes a row; GET /audit pagination + undone_at."""


def test_broadcast_and_pause_write_audit_rows(client, workshop):
    admin_token = workshop["admin_token"]
    client.post(f"/api/f/{admin_token}/broadcast", json={"message_md": "Hi"})
    client.post(f"/api/f/{admin_token}/pause", json={"paused": True})

    audit = client.get(f"/api/f/{admin_token}/audit").json()["data"]
    actions = [a["action"] for a in audit["actions"]]
    assert "broadcast.send" in actions
    assert "workshop.pause" in actions


def test_settings_and_milestone_edit_write_audit_rows(client, workshop):
    admin_token = workshop["admin_token"]
    got = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    milestone_id = got["milestones"][0]["id"]

    client.patch(f"/api/f/{admin_token}/settings", json={"stuck_minutes": 15})
    client.patch(f"/api/f/{admin_token}/milestones/{milestone_id}", json={"title": "Renamed"})
    client.post(f"/api/f/{admin_token}/milestones", json={"title": "New", "content_md": "", "minutes": None})
    client.delete(f"/api/f/{admin_token}/milestones/{milestone_id}")

    audit = client.get(f"/api/f/{admin_token}/audit").json()["data"]
    actions = [a["action"] for a in audit["actions"]]
    assert actions.count("settings.update") == 1
    assert actions.count("milestone.edit") == 3  # patch, add, delete


def test_audit_newest_first_and_pagination(client, workshop):
    admin_token = workshop["admin_token"]
    for i in range(5):
        client.post(f"/api/f/{admin_token}/broadcast", json={"message_md": f"msg {i}"})

    page1 = client.get(f"/api/f/{admin_token}/audit?limit=3").json()["data"]
    assert len(page1["actions"]) == 3
    assert page1["has_more"] is True
    ids = [a["id"] for a in page1["actions"]]
    assert ids == sorted(ids, reverse=True)

    page2 = client.get(
        f"/api/f/{admin_token}/audit?before_id={ids[-1]}&limit=3"
    ).json()["data"]
    assert all(a["id"] < ids[-1] for a in page2["actions"])
    assert page2["has_more"] is False


def test_undo_populates_undone_at(client, workshop):
    admin_token = workshop["admin_token"]
    sent = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "Hi"}
    ).json()["data"]
    client.post(f"/api/f/{admin_token}/undo/{sent['undoable_action_id']}", json={})

    audit = client.get(f"/api/f/{admin_token}/audit").json()["data"]
    original = next(a for a in audit["actions"] if a["id"] == sent["undoable_action_id"])
    assert original["undone_at"] is not None

    undo_row = next(a for a in audit["actions"] if a["action"] == "undo.apply")
    assert undo_row["detail"]["original_action_id"] == sent["undoable_action_id"]
