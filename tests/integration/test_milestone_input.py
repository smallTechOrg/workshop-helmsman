"""Per-milestone completion inputs: configure, gate, submit, and view."""


def _create(client, admin_headers):
    body = {
        "name": "Input WS",
        "milestones": [
            {"title": "Setup", "content_md": "", "minutes": None},
            {
                "title": "Push your repo",
                "content_md": "",
                "minutes": None,
                "input_config": {"type": "github_url", "label": "Your repo URL"},
            },
        ],
    }
    res = client.post("/api/admin/workshops", json=body, headers=admin_headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]["workshop"]


def test_github_url_gate_end_to_end(client, make_client, admin_headers):
    ws = _create(client, admin_headers)
    token = ws["admin_token"]

    b = make_client()
    p = b.post(f"/api/join/{ws['join_slug']}", json={"name": "Asha"}).json()["data"]
    ptok = p["participant_token"]

    # The gated milestone advertises its input config in tracker state.
    state = b.get(f"/api/p/{ptok}/state").json()["data"]
    gated = next(m for m in state["milestones"] if m["input_config"])
    other = next(m for m in state["milestones"] if not m["input_config"])
    assert gated["input_config"] == {"type": "github_url", "label": "Your repo URL"}
    mid = gated["id"]

    # An ungated milestone completes with no input.
    assert b.post(f"/api/p/{ptok}/milestones/{other['id']}/complete").status_code == 200

    # Completing the gated one with no / non-GitHub input is rejected.
    assert b.post(f"/api/p/{ptok}/milestones/{mid}/complete").status_code == 422
    assert (
        b.post(
            f"/api/p/{ptok}/milestones/{mid}/complete",
            json={"input": "https://example.com/x"},
        ).status_code
        == 422
    )

    # A valid GitHub URL completes it and stores the value.
    res = b.post(
        f"/api/p/{ptok}/milestones/{mid}/complete",
        json={"input": "https://github.com/asha/lab"},
    )
    assert res.status_code == 200, res.text

    state = b.get(f"/api/p/{ptok}/state").json()["data"]
    assert mid in state["me"]["completed_milestone_ids"]
    assert state["me"]["milestone_inputs"][str(mid)] == "https://github.com/asha/lab"

    # A re-submit updates the stored value.
    b.post(
        f"/api/p/{ptok}/milestones/{mid}/complete",
        json={"input": "https://github.com/asha/lab2"},
    )
    state = b.get(f"/api/p/{ptok}/state").json()["data"]
    assert state["me"]["milestone_inputs"][str(mid)] == "https://github.com/asha/lab2"

    # The facilitator dashboard exposes the submission.
    dash = client.get(f"/api/f/{token}/dashboard").json()["data"]
    row = dash["participants"][0]
    assert row["milestone_inputs"][str(mid)] == "https://github.com/asha/lab2"
    stat = next(s for s in dash["milestone_stats"] if s["milestone_id"] == mid)
    assert stat["input_config"]["type"] == "github_url"


def test_configure_and_clear_input_on_milestone(client, make_client, admin_headers):
    ws = _create(client, admin_headers)
    token = ws["admin_token"]
    wsfull = client.get(f"/api/f/{token}/workshop").json()["data"]
    plain = next(m for m in wsfull["milestones"] if m["input_config"] is None)

    # Add a dropdown input requirement to a previously-plain milestone.
    res = client.patch(
        f"/api/f/{token}/milestones/{plain['id']}",
        json={
            "input_config": {
                "type": "dropdown",
                "label": "Pick one",
                "options": ["A", "B"],
            }
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["milestone"]["input_config"]["options"] == ["A", "B"]

    # A dropdown with no options is rejected.
    assert (
        client.patch(
            f"/api/f/{token}/milestones/{plain['id']}",
            json={"input_config": {"type": "dropdown", "label": "x", "options": []}},
        ).status_code
        == 422
    )

    # A participant must choose a listed option.
    b = make_client()
    p = b.post(f"/api/join/{ws['join_slug']}", json={"name": "Sam"}).json()["data"]
    ptok = p["participant_token"]
    assert (
        b.post(
            f"/api/p/{ptok}/milestones/{plain['id']}/complete",
            json={"input": "Z"},
        ).status_code
        == 422
    )
    assert (
        b.post(
            f"/api/p/{ptok}/milestones/{plain['id']}/complete",
            json={"input": "A"},
        ).status_code
        == 200
    )

    # Clearing the requirement (null) lets it complete with no input.
    client.patch(f"/api/f/{token}/milestones/{plain['id']}", json={"input_config": None})
    p2 = make_client()
    p2j = p2.post(f"/api/join/{ws['join_slug']}", json={"name": "Ravi"}).json()["data"]
    assert (
        p2.post(
            f"/api/p/{p2j['participant_token']}/milestones/{plain['id']}/complete"
        ).status_code
        == 200
    )
