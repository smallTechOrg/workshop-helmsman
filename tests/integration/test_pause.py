"""Pause: blocks complete AND uncomplete with workshop_paused; resume unblocks; undo."""


def test_pause_blocks_complete_and_uncomplete(client, make_client, workshop, join_participant):
    admin_token = workshop["admin_token"]
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    state = browser.get(f"/api/p/{token}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]

    browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete")

    pause = client.post(f"/api/f/{admin_token}/pause", json={"paused": True})
    assert pause.status_code == 200, pause.text
    assert pause.json()["data"]["paused"] is True

    blocked_complete = browser.post(
        f"/api/p/{token}/milestones/{milestone_id}/complete"
    )
    assert blocked_complete.status_code == 409
    assert blocked_complete.json()["detail"]["code"] == "workshop_paused"

    other_milestone = state["milestones"][1]["id"]
    blocked_uncomplete = browser.post(
        f"/api/p/{token}/milestones/{other_milestone}/uncomplete"
    )
    assert blocked_uncomplete.status_code == 409
    assert blocked_uncomplete.json()["detail"]["code"] == "workshop_paused"


def test_resume_unblocks_completions(client, make_client, workshop, join_participant):
    admin_token = workshop["admin_token"]
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    state = browser.get(f"/api/p/{token}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]

    client.post(f"/api/f/{admin_token}/pause", json={"paused": True})
    resume = client.post(f"/api/f/{admin_token}/pause", json={"paused": False})
    assert resume.json()["data"]["paused"] is False

    result = browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete")
    assert result.status_code == 200, result.text


def test_undo_pause_restores_previous_state(client, workshop):
    admin_token = workshop["admin_token"]
    pause = client.post(f"/api/f/{admin_token}/pause", json={"paused": True}).json()["data"]
    assert pause["paused"] is True

    undo = client.post(f"/api/f/{admin_token}/undo/{pause['undoable_action_id']}", json={})
    assert undo.status_code == 200, undo.text

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    assert dashboard["workshop"]["paused"] is False
