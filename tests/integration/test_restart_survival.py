"""Resilience rule: dispose the engine + app, build a NEW app over the SAME DB file —
every piece of state must survive (nothing lives only in process memory)."""

from fastapi.testclient import TestClient

from tests.conftest import TEST_ADMIN_KEY


def _restart(make_app) -> TestClient:
    import src.helmsman.config.settings as settings_module
    from src.helmsman.db.session import reset_db_state
    from src.helmsman.services.snapshots import clear_snapshot_cache

    settings_module._settings = None
    reset_db_state()
    clear_snapshot_cache()
    return TestClient(make_app())


def test_full_state_survives_server_restart(client, make_app, workshop, join_participant, make_client):
    admin_token = workshop["admin_token"]
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]

    state = browser.get(f"/api/p/{token}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]
    browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete")
    help_id = browser.post(f"/api/p/{token}/help", json={"message": "stuck on step 2"}).json()[
        "data"
    ]["help_request"]["id"]
    client.post(f"/api/f/{admin_token}/help/{help_id}/answer", json={"answer_md": "try `uv sync`"})
    version_before = client.get(f"/api/f/{admin_token}/dashboard").json()["data"]["version"]

    fresh_client = _restart(make_app)

    # Admin list intact
    listing = fresh_client.get(
        "/api/admin/workshops", headers={"X-Admin-Key": TEST_ADMIN_KEY}
    ).json()["data"]["workshops"]
    assert [w["id"] for w in listing] == [workshop["id"]]
    assert listing[0]["participant_count"] == 1

    # Dashboard intact, version preserved (came from the DB, not memory)
    dashboard = fresh_client.get(f"/api/f/{admin_token}/dashboard").json()["data"]
    assert dashboard["version"] == version_before
    assert dashboard["stats"]["participant_count"] == 1
    assert dashboard["stats"]["answered_help_count"] == 1
    assert dashboard["help_queue"][0]["answers"][0]["answer_md"] == "try `uv sync`"

    # Participant token still works with full state
    state = fresh_client.get(f"/api/p/{token}/state").json()["data"]
    assert state["me"]["name"] == "Priya"
    assert state["me"]["completed_milestone_ids"] == [milestone_id]
    assert state["help_requests"][0]["status"] == "answered"

    # Unchanged-poll short-circuit still consistent after restart
    unchanged = fresh_client.get(f"/api/p/{token}/state?v={state['version']}").json()["data"]
    assert unchanged == {
        "changed": False,
        "version": state["version"],
        "content_version": state["content_version"],
    }


def test_writes_after_restart_continue_the_version_sequence(
    client, make_app, workshop, join_participant, make_client
):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]

    fresh_client = _restart(make_app)
    state = fresh_client.get(f"/api/p/{token}/state").json()["data"]
    result = fresh_client.post(
        f"/api/p/{token}/milestones/{state['milestones'][0]['id']}/complete"
    ).json()["data"]
    assert result["version"] == state["version"] + 1
