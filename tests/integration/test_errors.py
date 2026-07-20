"""Every documented Phase-1 error code is reachable with the exact envelope:
{"detail": {"code", "message"}}."""

import pytest

from tests.conftest import WORKSHOP_BODY


def _assert_error(response, status: int, code: str):
    assert response.status_code == status, response.text
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert isinstance(detail["message"], str) and detail["message"]


# --- invalid_admin_key (401) ---


def test_admin_list_missing_key(client):
    _assert_error(client.get("/api/admin/workshops"), 401, "invalid_admin_key")


def test_admin_list_wrong_key(client):
    _assert_error(
        client.get("/api/admin/workshops", headers={"X-Admin-Key": "wrong-key"}),
        401,
        "invalid_admin_key",
    )


def test_admin_create_wrong_key(client):
    _assert_error(
        client.post(
            "/api/admin/workshops", json=WORKSHOP_BODY, headers={"X-Admin-Key": "wrong-key"}
        ),
        401,
        "invalid_admin_key",
    )


# --- not_found (404): unknown tokens/slugs, never distinguishing wrong vs missing ---


def test_unknown_join_slug_get(client):
    _assert_error(client.get("/api/join/zzzzzzzz"), 404, "not_found")


def test_unknown_join_slug_post(client):
    _assert_error(client.post("/api/join/zzzzzzzz", json={"name": "Priya"}), 404, "not_found")


def test_unknown_participant_token_state(client):
    _assert_error(client.get("/api/p/not-a-token/state"), 404, "not_found")


def test_unknown_participant_token_content(client):
    _assert_error(client.get("/api/p/not-a-token/content"), 404, "not_found")


def test_unknown_participant_token_complete(client):
    _assert_error(client.post("/api/p/not-a-token/milestones/1/complete"), 404, "not_found")


def test_unknown_participant_token_help(client):
    _assert_error(client.post("/api/p/not-a-token/help", json={"message": "x"}), 404, "not_found")


def test_unknown_admin_token_workshop(client):
    _assert_error(client.get("/api/f/not-a-token/workshop"), 404, "not_found")


def test_unknown_admin_token_dashboard(client):
    _assert_error(client.get("/api/f/not-a-token/dashboard"), 404, "not_found")


def test_unknown_admin_token_answer(client):
    _assert_error(
        client.post("/api/f/not-a-token/help/1/answer", json={"answer_md": "x"}),
        404,
        "not_found",
    )


# --- not_found (404): ids outside the token's scope ---


@pytest.fixture
def two_workshops(client, admin_headers, join_participant, make_client):
    first = client.post(
        "/api/admin/workshops", json={**WORKSHOP_BODY, "name": "First"}, headers=admin_headers
    ).json()["data"]["workshop"]
    second = client.post(
        "/api/admin/workshops", json={**WORKSHOP_BODY, "name": "Second"}, headers=admin_headers
    ).json()["data"]["workshop"]
    browser = make_client()
    joined = join_participant(browser, first["join_slug"], "Priya")
    state = browser.get(f"/api/p/{joined['participant_token']}/state").json()["data"]
    help_id = browser.post(
        f"/api/p/{joined['participant_token']}/help", json={"message": "stuck"}
    ).json()["data"]["help_request"]["id"]
    other_joined = join_participant(make_client(), second["join_slug"], "Zoe")
    other_browser = make_client()
    other_state = other_browser.get(f"/api/p/{other_joined['participant_token']}/state").json()[
        "data"
    ]
    return {
        "first": first,
        "second": second,
        "token": joined["participant_token"],
        "milestone_ids": [m["id"] for m in state["milestones"]],
        "other_milestone_ids": [m["id"] for m in other_state["milestones"]],
        "other_token": other_joined["participant_token"],
        "help_id": help_id,
    }


def test_complete_milestone_from_other_workshop_is_not_found(client, two_workshops):
    foreign_milestone = two_workshops["other_milestone_ids"][0]
    _assert_error(
        client.post(
            f"/api/p/{two_workshops['token']}/milestones/{foreign_milestone}/complete"
        ),
        404,
        "not_found",
    )


def test_nonexistent_milestone_is_not_found(client, two_workshops):
    _assert_error(
        client.post(f"/api/p/{two_workshops['token']}/milestones/999999/complete"),
        404,
        "not_found",
    )


def test_answer_help_request_from_other_workshop_is_not_found(client, two_workshops):
    _assert_error(
        client.post(
            f"/api/f/{two_workshops['second']['admin_token']}/help/{two_workshops['help_id']}/answer",
            json={"answer_md": "not yours"},
        ),
        404,
        "not_found",
    )


def test_resolve_other_participants_request_is_not_found(client, two_workshops):
    _assert_error(
        client.post(
            f"/api/p/{two_workshops['other_token']}/help/{two_workshops['help_id']}/resolve"
        ),
        404,
        "not_found",
    )


# --- validation_error (422) ---


def test_join_empty_name(client, workshop):
    _assert_error(
        client.post(f"/api/join/{workshop['join_slug']}", json={"name": "   "}),
        422,
        "validation_error",
    )


def test_join_name_too_long(client, workshop):
    _assert_error(
        client.post(f"/api/join/{workshop['join_slug']}", json={"name": "x" * 81}),
        422,
        "validation_error",
    )


def test_join_missing_name_field(client, workshop):
    _assert_error(
        client.post(f"/api/join/{workshop['join_slug']}", json={}), 422, "validation_error"
    )


def test_create_workshop_without_milestones(client, admin_headers):
    _assert_error(
        client.post(
            "/api/admin/workshops",
            json={"name": "Lab", "milestones": []},
            headers=admin_headers,
        ),
        422,
        "validation_error",
    )


def test_create_workshop_bad_minutes(client, admin_headers):
    _assert_error(
        client.post(
            "/api/admin/workshops",
            json={"name": "Lab", "milestones": [{"title": "t", "minutes": 0}]},
            headers=admin_headers,
        ),
        422,
        "validation_error",
    )


def test_empty_answer_md(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    help_id = browser.post(
        f"/api/p/{joined['participant_token']}/help", json={"message": "stuck"}
    ).json()["data"]["help_request"]["id"]
    _assert_error(
        client.post(
            f"/api/f/{workshop['admin_token']}/help/{help_id}/answer",
            json={"answer_md": ""},
        ),
        422,
        "validation_error",
    )


def test_help_message_too_long(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    _assert_error(
        browser.post(
            f"/api/p/{joined['participant_token']}/help", json={"message": "x" * 4001}
        ),
        422,
        "validation_error",
    )


def test_non_integer_poll_version_param(client, workshop):
    _assert_error(
        client.get(f"/api/f/{workshop['admin_token']}/dashboard?v=abc"),
        422,
        "validation_error",
    )


def test_validation_error_message_is_human_readable(client, workshop):
    response = client.post(f"/api/join/{workshop['join_slug']}", json={"name": "   "})
    message = response.json()["detail"]["message"]
    assert "name" in message
    # the raw FastAPI 422 array shape never reaches clients
    assert not isinstance(response.json()["detail"], list)


# --- workshop_paused (409) ---


@pytest.fixture
def paused_tracker(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    state = browser.get(f"/api/p/{joined['participant_token']}/state").json()["data"]

    from sqlalchemy import update

    from src.helmsman.db.models import Workshop
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        # Direct-DB stand-in for the Phase-2 pause endpoint — which also bumps
        # state_version per the data-model version-bump rules.
        session.execute(
            update(Workshop)
            .where(Workshop.id == workshop["id"])
            .values(paused=True, state_version=Workshop.state_version + 1)
        )
    return {"browser": browser, "token": joined["participant_token"], "state": state}


def test_complete_while_paused(paused_tracker):
    milestone_id = paused_tracker["state"]["milestones"][0]["id"]
    _assert_error(
        paused_tracker["browser"].post(
            f"/api/p/{paused_tracker['token']}/milestones/{milestone_id}/complete"
        ),
        409,
        "workshop_paused",
    )


def test_uncomplete_while_paused(paused_tracker):
    milestone_id = paused_tracker["state"]["milestones"][0]["id"]
    _assert_error(
        paused_tracker["browser"].post(
            f"/api/p/{paused_tracker['token']}/milestones/{milestone_id}/uncomplete"
        ),
        409,
        "workshop_paused",
    )


def test_state_poll_still_works_while_paused(paused_tracker):
    state = paused_tracker["browser"].get(
        f"/api/p/{paused_tracker['token']}/state"
    ).json()["data"]
    assert state["workshop"]["paused"] is True


# --- workshop_archived (410) ---


@pytest.fixture
def archived(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    state = browser.get(f"/api/p/{joined['participant_token']}/state").json()["data"]

    from sqlalchemy import update

    from src.helmsman.db.models import Workshop
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        # Direct-DB stand-in for the Phase-3 archive transition — which also bumps
        # state_version per the data-model version-bump rules.
        session.execute(
            update(Workshop)
            .where(Workshop.id == workshop["id"])
            .values(status="archived", state_version=Workshop.state_version + 1)
        )
    return {"browser": browser, "token": joined["participant_token"], "state": state}


def test_join_archived_workshop(client, workshop, archived):
    _assert_error(
        client.post(f"/api/join/{workshop['join_slug']}", json={"name": "Late"}),
        410,
        "workshop_archived",
    )


def test_complete_on_archived_workshop(archived):
    milestone_id = archived["state"]["milestones"][0]["id"]
    _assert_error(
        archived["browser"].post(
            f"/api/p/{archived['token']}/milestones/{milestone_id}/complete"
        ),
        410,
        "workshop_archived",
    )


def test_help_on_archived_workshop(archived):
    _assert_error(
        archived["browser"].post(f"/api/p/{archived['token']}/help", json={"message": "x"}),
        410,
        "workshop_archived",
    )


def test_archived_workshop_still_returns_state_read_only(archived):
    state = archived["browser"].get(f"/api/p/{archived['token']}/state").json()["data"]
    assert state["workshop"]["status"] == "archived"
