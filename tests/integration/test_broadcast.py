"""Broadcast: send → appears in dashboard + participant poll; undo restores previous; clear."""


def test_send_broadcast_appears_in_dashboard_and_participant_poll(
    client, make_client, workshop, join_participant
):
    admin_token = workshop["admin_token"]
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]

    result = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "Lunch in 5!"}
    )
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["broadcast"]["message_md"] == "Lunch in 5!"
    assert "undoable_action_id" in data
    version = data["version"]

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    assert dashboard["broadcast"]["message_md"] == "Lunch in 5!"

    state = browser.get(f"/api/p/{token}/state?v=-1").json()["data"]
    assert state["broadcast"]["message_md"] == "Lunch in 5!"
    assert state["version"] == version


def test_undo_broadcast_within_window_restores_previous(client, workshop):
    admin_token = workshop["admin_token"]

    first = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "First"}
    ).json()["data"]

    second = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "Second"}
    ).json()["data"]

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    assert dashboard["broadcast"]["message_md"] == "Second"

    undo = client.post(f"/api/f/{admin_token}/undo/{second['undoable_action_id']}", json={})
    assert undo.status_code == 200, undo.text

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    assert dashboard["broadcast"]["message_md"] == "First"


def test_undo_first_broadcast_clears_it_entirely(client, workshop):
    admin_token = workshop["admin_token"]
    sent = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "Only one"}
    ).json()["data"]

    client.post(f"/api/f/{admin_token}/undo/{sent['undoable_action_id']}", json={})

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    assert dashboard["broadcast"] is None


def test_clear_broadcast(client, workshop):
    admin_token = workshop["admin_token"]
    client.post(f"/api/f/{admin_token}/broadcast", json={"message_md": "Hello"})

    result = client.post(f"/api/f/{admin_token}/broadcast/clear", json={})
    assert result.status_code == 200, result.text

    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]
    assert dashboard["broadcast"] is None


def test_clear_broadcast_is_noop_when_none_active(client, workshop):
    admin_token = workshop["admin_token"]
    result = client.post(f"/api/f/{admin_token}/broadcast/clear", json={})
    assert result.status_code == 200, result.text


def test_broadcast_message_validation(client, workshop):
    admin_token = workshop["admin_token"]
    result = client.post(f"/api/f/{admin_token}/broadcast", json={"message_md": ""})
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "validation_error"

    too_long = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "x" * 4001}
    )
    assert too_long.status_code == 422
