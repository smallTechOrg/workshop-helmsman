"""Milestone advance: creates only missing completions with source facilitator; undoable."""


def test_advance_all_creates_only_missing_completions(
    client, make_client, workshop, join_participant
):
    admin_token = workshop["admin_token"]
    priya_browser, arun_browser = make_client(), make_client()
    priya = join_participant(priya_browser, workshop["join_slug"], "Priya")
    arun = join_participant(arun_browser, workshop["join_slug"], "Arun")

    state = priya_browser.get(f"/api/p/{priya['participant_token']}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]

    # Priya already completed it manually
    priya_browser.post(f"/api/p/{priya['participant_token']}/milestones/{milestone_id}/complete")

    result = client.post(
        f"/api/f/{admin_token}/milestones/advance",
        json={"milestone_id": milestone_id, "participant_ids": None},
    )
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["affected_count"] == 1  # only Arun was missing

    arun_state = arun_browser.get(f"/api/p/{arun['participant_token']}/state?v=-1").json()["data"]
    assert milestone_id in arun_state["me"]["completed_milestone_ids"]


def test_advance_selected_participants(client, make_client, workshop, join_participant):
    admin_token = workshop["admin_token"]
    priya_browser, arun_browser = make_client(), make_client()
    priya = join_participant(priya_browser, workshop["join_slug"], "Priya")
    join_participant(arun_browser, workshop["join_slug"], "Arun")

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    priya_id = next(p["id"] for p in dashboard["participants"] if p["name"] == "Priya")
    state = priya_browser.get(f"/api/p/{priya['participant_token']}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]

    result = client.post(
        f"/api/f/{admin_token}/milestones/advance",
        json={"milestone_id": milestone_id, "participant_ids": [priya_id]},
    ).json()["data"]
    assert result["affected_count"] == 1

    priya_state = priya_browser.get(f"/api/p/{priya['participant_token']}/state?v=-1").json()["data"]
    assert milestone_id in priya_state["me"]["completed_milestone_ids"]


def test_advance_unknown_milestone_returns_not_found(client, workshop):
    admin_token = workshop["admin_token"]
    result = client.post(
        f"/api/f/{admin_token}/milestones/advance",
        json={"milestone_id": 999999, "participant_ids": None},
    )
    assert result.status_code == 404
    assert result.json()["detail"]["code"] == "not_found"


def test_undo_advance_deletes_created_completions(client, make_client, workshop, join_participant):
    admin_token = workshop["admin_token"]
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    state = browser.get(f"/api/p/{joined['participant_token']}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]

    advance = client.post(
        f"/api/f/{admin_token}/milestones/advance",
        json={"milestone_id": milestone_id, "participant_ids": None},
    ).json()["data"]
    assert advance["affected_count"] == 1

    undo = client.post(f"/api/f/{admin_token}/undo/{advance['undoable_action_id']}", json={})
    assert undo.status_code == 200, undo.text

    refreshed = browser.get(f"/api/p/{joined['participant_token']}/state?v=-1").json()["data"]
    assert milestone_id not in refreshed["me"]["completed_milestone_ids"]
