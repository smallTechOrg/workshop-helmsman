"""Phase 6 — keyless public creation, parity, isolation and admin oversight.

Every assertion here is a gate condition from spec/roadmap.md §Phase 6.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.conftest import TEST_ADMIN_KEY, WORKSHOP_BODY

REPO_ROOT = Path(__file__).resolve().parents[2]

PUBLIC_BODY = {**WORKSHOP_BODY, "creator_email": "Asha@Example.com "}


def _create_public(client, **overrides) -> dict:
    return client.post("/api/public/workshops", json={**PUBLIC_BODY, **overrides})


def _workshop_count(client, admin_headers) -> int:
    listing = client.get("/api/admin/workshops", headers=admin_headers)
    assert listing.status_code == 200, listing.text
    return len(listing.json()["data"]["workshops"])


# --- happy path -------------------------------------------------------------


def test_public_create_stores_row_with_public_origin_and_email(client, admin_headers):
    response = _create_public(client)
    assert response.status_code == 200, response.text
    workshop = response.json()["data"]["workshop"]

    assert workshop["created_via"] == "public"
    assert workshop["creator_email"] == "asha@example.com"  # trimmed + lower-cased
    assert len(workshop["admin_token"]) == 43
    assert workshop["status"] == "live"
    assert workshop["paused"] is False
    assert workshop["join_url"].endswith(f"/j/{workshop['join_slug']}")
    assert workshop["facilitator_url"].endswith(f"/f/{workshop['admin_token']}")

    # the row is real and identical in shape to an admin-created one
    row = next(
        w
        for w in client.get("/api/admin/workshops", headers=admin_headers).json()["data"][
            "workshops"
        ]
        if w["id"] == workshop["id"]
    )
    assert row["created_via"] == "public"
    assert row["creator_email"] == "asha@example.com"
    content = client.get(f"/api/f/{workshop['admin_token']}/workshop").json()["data"]
    assert [m["title"] for m in content["milestones"]] == [
        m["title"] for m in WORKSHOP_BODY["milestones"]
    ]


def test_public_create_writes_workshop_create_audit_row(client):
    workshop = _create_public(client).json()["data"]["workshop"]
    actions = client.get(f"/api/f/{workshop['admin_token']}/audit").json()["data"]["actions"]
    create_rows = [a for a in actions if a["action"] == "workshop.create"]
    assert len(create_rows) == 1
    assert create_rows[0]["detail"]["created_via"] == "public"
    assert "creator_email" not in create_rows[0]["detail"]


# --- edge / error paths -----------------------------------------------------


@pytest.mark.parametrize("email", [" ", "a@b", "no-at.example.com"])
def test_malformed_email_is_422_and_creates_nothing(client, admin_headers, email):
    before = _workshop_count(client, admin_headers)
    response = _create_public(client, creator_email=email)
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "validation_error"
    assert detail["message"] == "creator_email: enter a valid email address"
    assert _workshop_count(client, admin_headers) == before


def test_missing_email_is_422_and_creates_nothing(client, admin_headers):
    before = _workshop_count(client, admin_headers)
    response = client.post("/api/public/workshops", json=WORKSHOP_BODY)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"
    assert _workshop_count(client, admin_headers) == before


def test_public_create_still_enforces_the_admin_body_validation(client, admin_headers):
    before = _workshop_count(client, admin_headers)
    response = _create_public(client, name="   ")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"

    response = _create_public(client, milestones=[])
    assert response.status_code == 422
    assert _workshop_count(client, admin_headers) == before


# --- keyless vs key-gated ---------------------------------------------------


def test_public_route_is_keyless_while_admin_route_still_requires_the_key(client):
    assert client.post("/api/public/workshops", json=PUBLIC_BODY).status_code == 200

    denied = client.post("/api/admin/workshops", json=WORKSHOP_BODY)
    assert denied.status_code == 401
    assert denied.json()["detail"]["code"] == "invalid_admin_key"


def test_public_route_ignores_a_supplied_admin_key_header(client):
    response = client.post(
        "/api/public/workshops", json=PUBLIC_BODY, headers={"X-Admin-Key": "totally-wrong"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["workshop"]["created_via"] == "public"


# --- facilitator parity + isolation ----------------------------------------


def test_public_workshop_has_full_facilitator_parity(client, join_participant):
    workshop = _create_public(client).json()["data"]["workshop"]
    token = workshop["admin_token"]
    participant = join_participant(client, workshop["join_slug"], "Priya")

    broadcast = client.post(f"/api/f/{token}/broadcast", json={"message_md": "Five minutes left"})
    assert broadcast.status_code == 200, broadcast.text
    assert broadcast.json()["data"]["broadcast"]["message_md"] == "Five minutes left"

    pause = client.post(f"/api/f/{token}/pause", json={"paused": True})
    assert pause.status_code == 200, pause.text
    assert pause.json()["data"]["paused"] is True
    client.post(f"/api/f/{token}/pause", json={"paused": False})

    milestone_id = client.get(f"/api/f/{token}/workshop").json()["data"]["milestones"][0]["id"]
    advance = client.post(
        f"/api/f/{token}/milestones/advance",
        json={"milestone_id": milestone_id, "participant_ids": None},
    )
    assert advance.status_code == 200, advance.text
    assert advance.json()["data"]["affected_count"] == 1

    state = client.get(f"/api/p/{participant['participant_token']}/state").json()["data"]
    assert state["me"]["completed_milestone_ids"] == [milestone_id]


def test_public_admin_token_cannot_touch_another_workshop(client, workshop, join_participant):
    """`workshop` is the admin-created fixture; the public token must not reach it."""
    public = _create_public(client).json()["data"]["workshop"]
    other_milestone_id = client.get(f"/api/f/{workshop['admin_token']}/workshop").json()["data"][
        "milestones"
    ][0]["id"]
    other_participant = join_participant(client, workshop["join_slug"], "Arun")

    advance = client.post(
        f"/api/f/{public['admin_token']}/milestones/advance",
        json={"milestone_id": other_milestone_id, "participant_ids": None},
    )
    assert advance.status_code == 404
    assert advance.json()["detail"]["code"] == "not_found"

    dashboard = client.get(f"/api/f/{public['admin_token']}/dashboard").json()["data"]
    assert all(p["name"] != "Arun" for p in dashboard["participants"])
    assert other_participant["participant_token"]


# --- admin oversight --------------------------------------------------------


def test_admin_list_reports_both_origins(client, admin_headers):
    admin_created = client.post(
        "/api/admin/workshops", json={**WORKSHOP_BODY, "name": "Admin one"}, headers=admin_headers
    ).json()["data"]["workshop"]
    public_created = _create_public(client, name="Public one").json()["data"]["workshop"]

    rows = {
        w["id"]: w
        for w in client.get("/api/admin/workshops", headers=admin_headers).json()["data"][
            "workshops"
        ]
    }
    assert rows[admin_created["id"]]["created_via"] == "admin"
    assert rows[admin_created["id"]]["creator_email"] is None
    assert rows[public_created["id"]]["created_via"] == "public"
    assert rows[public_created["id"]]["creator_email"] == "asha@example.com"


def test_admin_create_response_reports_admin_origin_and_no_email(client, admin_headers):
    response = client.post("/api/admin/workshops", json=WORKSHOP_BODY, headers=admin_headers)
    assert response.status_code == 200
    workshop = response.json()["data"]["workshop"]
    assert workshop["created_via"] == "admin"
    assert workshop["creator_email"] is None


def test_creator_email_never_leaks_to_facilitator_or_participant_surfaces(
    client, join_participant
):
    workshop = _create_public(client).json()["data"]["workshop"]
    token = workshop["admin_token"]
    participant = join_participant(client, workshop["join_slug"], "Priya")
    ptoken = participant["participant_token"]
    client.post(f"/api/p/{ptoken}/help", json={"message": "stuck on the key"})

    payloads = [
        client.get(f"/api/f/{token}/workshop").text,
        client.get(f"/api/f/{token}/dashboard").text,
        client.get(f"/api/f/{token}/audit").text,
        client.get(f"/api/f/{token}/participants.csv").text,
        client.get(f"/api/join/{workshop['join_slug']}").text,
        client.get(f"/api/p/{ptoken}/state").text,
        client.get(f"/api/p/{ptoken}/content").text,
    ]
    for payload in payloads:
        assert "asha@example.com" not in payload.lower()
        assert "creator_email" not in payload


# --- migration 0004 ---------------------------------------------------------


def test_migration_0004_adds_the_columns_and_backfills_existing_rows(monkeypatch, tmp_path):
    """Upgrade to 0003, insert a pre-Phase-6 row, then upgrade to 0004."""
    db_path = tmp_path / "public-creation-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import src.helmsman.config.settings as settings_module
    from src.helmsman.db.session import reset_db_state

    settings_module._settings = None
    reset_db_state()

    config = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(config, "0003")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            assert "creator_email" not in {
                c["name"] for c in inspect(engine).get_columns("workshop")
            }
            connection.execute(
                text(
                    "INSERT INTO workshop (name, description_md, admin_token, join_slug, status,"
                    " grace_hours, paused, state_version, content_version, ai_enabled,"
                    " join_form_json, stuck_minutes, created_at, updated_at)"
                    " VALUES ('Legacy', '', 'legacy-token', 'legacyslg', 'live', 24, 0, 0, 0, 0,"
                    " '[]', 10, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        columns = {c["name"]: c for c in inspect(engine).get_columns("workshop")}
        assert columns["creator_email"]["nullable"] is True
        assert columns["created_via"]["nullable"] is False
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT created_via, creator_email FROM workshop WHERE name = 'Legacy'")
            ).one()
        assert row.created_via == "admin"  # server_default backfilled the pre-existing row
        assert row.creator_email is None
    finally:
        engine.dispose()

    # and the migrated schema serves both create routes
    from fastapi.testclient import TestClient

    from src.helmsman.api import create_app

    client = TestClient(create_app())
    public = client.post("/api/public/workshops", json=PUBLIC_BODY)
    assert public.status_code == 200, public.text
    listing = client.get("/api/admin/workshops", headers={"X-Admin-Key": TEST_ADMIN_KEY}).json()
    origins = {w["name"]: w["created_via"] for w in listing["data"]["workshops"]}
    assert origins["Legacy"] == "admin"
    assert origins[WORKSHOP_BODY["name"]] == "public"
