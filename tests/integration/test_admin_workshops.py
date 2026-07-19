import json
import re

from sqlalchemy import select

from tests.conftest import WORKSHOP_BODY

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_create_workshop_returns_full_object(workshop):
    assert workshop["name"] == "LangGraph Lab — July"
    assert workshop["description_md"] == "Welcome! Bring a laptop."
    assert workshop["status"] == "live"
    assert workshop["paused"] is False
    assert workshop["ai_enabled"] is False
    assert len(workshop["admin_token"]) == 43
    assert len(workshop["join_slug"]) == 8
    assert workshop["join_url"] == f"http://testserver/j/{workshop['join_slug']}"
    assert workshop["facilitator_url"] == f"http://testserver/f/{workshop['admin_token']}"
    assert ISO_Z.match(workshop["created_at"])


def test_create_workshop_writes_audit_row(workshop):
    from src.helmsman.db.models import FacilitatorAction
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        row = session.scalar(
            select(FacilitatorAction).where(FacilitatorAction.action == "workshop.create")
        )
        assert row is not None
        assert row.workshop_id == workshop["id"]
        assert row.actor == "facilitator"
        detail = json.loads(row.detail_json)
        assert detail["name"] == workshop["name"]
        assert detail["milestone_count"] == 3


def test_create_workshop_persists_milestones_in_order(client, admin_headers, workshop):
    response = client.get(f"/api/f/{workshop['admin_token']}/workshop")
    milestones = response.json()["data"]["milestones"]
    assert [m["position"] for m in milestones] == [0, 1, 2]
    assert [m["title"] for m in milestones] == [
        "Set up your environment",
        "Configure the API key",
        "Run the first graph",
    ]
    assert milestones[0]["content_md"] == "```bash\nuv sync\n```"
    assert milestones[2]["minutes"] is None


def test_list_workshops_sorted_desc_with_counts(client, admin_headers, join_participant):
    first = client.post(
        "/api/admin/workshops", json={**WORKSHOP_BODY, "name": "First"}, headers=admin_headers
    ).json()["data"]["workshop"]
    second = client.post(
        "/api/admin/workshops", json={**WORKSHOP_BODY, "name": "Second"}, headers=admin_headers
    ).json()["data"]["workshop"]

    join_participant(client, first["join_slug"], "Priya")

    listing = client.get("/api/admin/workshops", headers=admin_headers).json()["data"]["workshops"]
    assert [w["name"] for w in listing] == ["Second", "First"]
    by_id = {w["id"]: w for w in listing}
    assert by_id[first["id"]]["participant_count"] == 1
    assert by_id[second["id"]]["participant_count"] == 0
    assert by_id[first["id"]]["open_help_count"] == 0
    assert "admin_token" not in listing[0]
    assert by_id[first["id"]]["facilitator_url"].endswith(first["admin_token"])


def test_list_workshops_empty(client, admin_headers):
    listing = client.get("/api/admin/workshops", headers=admin_headers).json()
    assert listing == {"data": {"workshops": []}, "error": None}


def test_base_url_override_used_for_share_links(monkeypatch, make_app, admin_headers):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("HELMSMAN_BASE_URL", "https://helm.example.com")
    import src.helmsman.config.settings as settings_module

    settings_module._settings = None
    client = TestClient(make_app())
    workshop = client.post(
        "/api/admin/workshops", json=WORKSHOP_BODY, headers=admin_headers
    ).json()["data"]["workshop"]
    assert workshop["join_url"] == f"https://helm.example.com/j/{workshop['join_slug']}"
    assert workshop["facilitator_url"] == f"https://helm.example.com/f/{workshop['admin_token']}"
