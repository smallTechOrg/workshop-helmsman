"""Threaded help: participant replies, facilitator replies, reopen, resolved_by,
and the read-only room questions view."""


def _setup(client, make_client, admin_headers):
    ws = client.post(
        "/api/admin/workshops",
        json={"name": "Help WS", "milestones": [{"title": "M1", "content_md": "", "minutes": None}]},
        headers=admin_headers,
    ).json()["data"]["workshop"]
    b = make_client()
    p = b.post(f"/api/join/{ws['join_slug']}", json={"name": "Asha"}).json()["data"]
    return ws, b, p


def test_thread_reply_reopen_and_resolved_by(client, make_client, admin_headers):
    ws, b, p = _setup(client, make_client, admin_headers)
    tok = p["participant_token"]
    admin = ws["admin_token"]

    # Participant asks.
    hr = b.post(f"/api/p/{tok}/help", json={"message": "How do I start?"}).json()["data"]["help_request"]
    hid = hr["id"]

    # Facilitator replies → answered.
    client.post(f"/api/f/{admin}/help/{hid}/answer", json={"answer_md": "Run `setup.sh`."})
    state = b.get(f"/api/p/{tok}/state").json()["data"]
    req = state["help_requests"][0]
    assert req["status"] == "answered"
    assert [a["source"] for a in req["answers"]] == ["facilitator"]

    # Participant replies back → reopens to open, thread has both.
    b.post(f"/api/p/{tok}/help/{hid}/reply", json={"message": "That failed with an error."})
    dash = client.get(f"/api/f/{admin}/dashboard").json()["data"]
    qitem = next(h for h in dash["help_queue"] if h["id"] == hid)
    assert qitem["status"] == "open"
    assert [a["source"] for a in qitem["answers"]] == ["facilitator", "participant"]

    # Facilitator resolves → resolved_by facilitator.
    client.post(f"/api/f/{admin}/help/{hid}/resolve", json={})
    dash = client.get(f"/api/f/{admin}/dashboard").json()["data"]
    qitem = next(h for h in dash["help_queue"] if h["id"] == hid)
    assert qitem["status"] == "resolved"
    assert qitem["resolved_by"] == "facilitator"

    # Participant reopens.
    b.post(f"/api/p/{tok}/help/{hid}/reopen", json={})
    req = b.get(f"/api/p/{tok}/state").json()["data"]["help_requests"][0]
    assert req["status"] == "open"
    assert req["resolved_by"] is None

    # Participant resolves → resolved_by participant.
    b.post(f"/api/p/{tok}/help/{hid}/resolve", json={})
    req = b.get(f"/api/p/{tok}/state").json()["data"]["help_requests"][0]
    assert req["status"] == "resolved"
    assert req["resolved_by"] == "participant"


def test_room_open_count_and_room_questions_view(client, make_client, admin_headers):
    ws, b, p = _setup(client, make_client, admin_headers)
    tok = p["participant_token"]

    # A second participant asks too.
    b2 = make_client()
    p2 = b2.post(f"/api/join/{ws['join_slug']}", json={"name": "Ravi"}).json()["data"]
    b2.post(f"/api/p/{p2['participant_token']}/help", json={"message": "Where are the slides?"})
    b.post(f"/api/p/{tok}/help", json={"message": "My venv won't activate."})

    # The room count reflects both open questions on each participant's state.
    state = b.get(f"/api/p/{tok}/state").json()["data"]
    assert state["room_open_help_count"] == 2

    # The room-questions view shows everyone's questions with asker names.
    room = b.get(f"/api/p/{tok}/questions").json()["data"]["questions"]
    askers = {q["asker_name"] for q in room}
    assert askers == {"Asha", "Ravi"}
    assert all("message" in q and "status" in q for q in room)
