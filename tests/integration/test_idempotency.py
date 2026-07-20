"""Idempotent complete/uncomplete/resolve — repeats are no-op successes and never
bump the version again."""

import pytest


@pytest.fixture
def tracker(make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    state = browser.get(f"/api/p/{token}/state").json()["data"]
    return {
        "browser": browser,
        "token": token,
        "milestone_ids": [m["id"] for m in state["milestones"]],
    }


def test_recomplete_is_noop_success(tracker):
    browser, token = tracker["browser"], tracker["token"]
    milestone_id = tracker["milestone_ids"][0]
    first = browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete").json()["data"]
    second = browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete").json()["data"]
    assert second == first
    assert second["completed_milestone_ids"] == [milestone_id]
    assert second["version"] == first["version"]


def test_uncomplete_removes_then_noop(tracker):
    browser, token = tracker["browser"], tracker["token"]
    milestone_id = tracker["milestone_ids"][0]
    browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete")
    removed = browser.post(f"/api/p/{token}/milestones/{milestone_id}/uncomplete").json()["data"]
    assert removed["completed_milestone_ids"] == []
    again = browser.post(f"/api/p/{token}/milestones/{milestone_id}/uncomplete").json()["data"]
    assert again == removed


def test_uncomplete_never_completed_is_noop(tracker):
    browser, token = tracker["browser"], tracker["token"]
    result = browser.post(
        f"/api/p/{token}/milestones/{tracker['milestone_ids'][2]}/uncomplete"
    ).json()["data"]
    assert result["completed_count"] == 0


def test_participant_resolve_idempotent(tracker):
    browser, token = tracker["browser"], tracker["token"]
    help_id = browser.post(f"/api/p/{token}/help", json={"message": "stuck"}).json()["data"][
        "help_request"
    ]["id"]
    first = browser.post(f"/api/p/{token}/help/{help_id}/resolve").json()["data"]
    second = browser.post(f"/api/p/{token}/help/{help_id}/resolve").json()["data"]
    assert first["help_request"]["status"] == "resolved"
    assert second == first


def test_facilitator_resolve_idempotent(client, workshop, tracker):
    browser, token = tracker["browser"], tracker["token"]
    help_id = browser.post(f"/api/p/{token}/help", json={"message": "stuck"}).json()["data"][
        "help_request"
    ]["id"]
    first = client.post(f"/api/f/{workshop['admin_token']}/help/{help_id}/resolve").json()["data"]
    second = client.post(f"/api/f/{workshop['admin_token']}/help/{help_id}/resolve").json()["data"]
    assert second == first


def test_facilitator_resolve_audits_only_once(client, workshop, tracker):
    browser, token = tracker["browser"], tracker["token"]
    help_id = browser.post(f"/api/p/{token}/help", json={"message": "stuck"}).json()["data"][
        "help_request"
    ]["id"]
    client.post(f"/api/f/{workshop['admin_token']}/help/{help_id}/resolve")
    client.post(f"/api/f/{workshop['admin_token']}/help/{help_id}/resolve")

    from sqlalchemy import func, select

    from src.helmsman.db.models import FacilitatorAction
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        count = session.scalar(
            select(func.count(FacilitatorAction.id)).where(
                FacilitatorAction.action == "help.resolve"
            )
        )
    assert count == 1
