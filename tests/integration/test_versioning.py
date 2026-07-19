"""Version counters: bumped in the same transaction as every mutation type;
unchanged polls short-circuit to the tiny payload; content only moves with cv."""


def _dashboard_version(client, admin_token: str) -> tuple[int, int]:
    data = client.get(f"/api/f/{admin_token}/dashboard").json()["data"]
    return data["version"], data["content_version"]


def test_new_workshop_starts_at_version_zero(client, workshop):
    version, content_version = _dashboard_version(client, workshop["admin_token"])
    assert version == 0
    assert content_version == 0


def test_every_mutation_type_bumps_state_version(client, make_client, workshop, join_participant):
    admin_token = workshop["admin_token"]
    browser = make_client()

    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    assert _dashboard_version(client, admin_token)[0] == 1  # join

    state = browser.get(f"/api/p/{token}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]

    completed = browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete").json()["data"]
    assert completed["version"] == 2  # complete

    uncompleted = browser.post(f"/api/p/{token}/milestones/{milestone_id}/uncomplete").json()["data"]
    assert uncompleted["version"] == 3  # uncomplete

    help_result = browser.post(f"/api/p/{token}/help", json={"message": "stuck"}).json()["data"]
    assert help_result["version"] == 4  # help create
    help_id = help_result["help_request"]["id"]

    answered = client.post(
        f"/api/f/{admin_token}/help/{help_id}/answer", json={"answer_md": "try again"}
    ).json()["data"]
    assert answered["version"] == 5  # facilitator answer

    resolved = browser.post(f"/api/p/{token}/help/{help_id}/resolve").json()["data"]
    assert resolved["version"] == 6  # participant resolve

    second_help = browser.post(f"/api/p/{token}/help", json={"message": "another"}).json()["data"]
    assert second_help["version"] == 7
    facilitator_resolved = client.post(
        f"/api/f/{admin_token}/help/{second_help['help_request']['id']}/resolve"
    ).json()["data"]
    assert facilitator_resolved["version"] == 8  # facilitator resolve


def test_unchanged_dashboard_poll_short_circuits(client, workshop):
    version, content_version = _dashboard_version(client, workshop["admin_token"])
    body = client.get(f"/api/f/{workshop['admin_token']}/dashboard?v={version}").json()
    assert body == {
        "data": {"changed": False, "version": version, "content_version": content_version},
        "error": None,
    }


def test_unchanged_state_poll_short_circuits(make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    version = browser.get(f"/api/p/{token}/state").json()["data"]["version"]
    body = browser.get(f"/api/p/{token}/state?v={version}").json()
    assert body == {
        "data": {"changed": False, "version": version, "content_version": 0},
        "error": None,
    }


def test_stale_v_returns_full_payload(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    version = browser.get(f"/api/p/{token}/state").json()["data"]["version"]

    state = browser.get(f"/api/p/{token}/state").json()["data"]
    milestone_id = state["milestones"][0]["id"]
    browser.post(f"/api/p/{token}/milestones/{milestone_id}/complete")

    refreshed = browser.get(f"/api/p/{token}/state?v={version}").json()["data"]
    assert refreshed["changed"] is True
    assert refreshed["version"] == version + 1
    assert refreshed["me"]["completed_count"] == 1


def test_state_mutations_never_bump_content_version(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    state = browser.get(f"/api/p/{token}/state").json()["data"]
    browser.post(f"/api/p/{token}/milestones/{state['milestones'][0]['id']}/complete")
    browser.post(f"/api/p/{token}/help", json={"message": "stuck"})

    _, content_version = _dashboard_version(client, workshop["admin_token"])
    assert content_version == 0


def test_content_endpoint_short_circuits_on_matching_cv(make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]

    full = browser.get(f"/api/p/{token}/content").json()["data"]
    assert full["changed"] is True
    cv = full["content_version"]

    unchanged = browser.get(f"/api/p/{token}/content?cv={cv}").json()
    assert unchanged == {
        "data": {"changed": False, "content_version": cv},
        "error": None,
    }


def test_mutation_responses_include_new_version(make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    state = browser.get(f"/api/p/{token}/state").json()["data"]
    result = browser.post(
        f"/api/p/{token}/milestones/{state['milestones'][0]['id']}/complete"
    ).json()["data"]
    assert result["version"] == state["version"] + 1
