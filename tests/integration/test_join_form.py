"""Custom join-form fields: create/edit definitions, required validation, answers."""

FORM = [
    {"key": "team", "type": "text", "label": "Your team", "required": True},
    {
        "key": "role",
        "type": "dropdown",
        "label": "Your role",
        "required": False,
        "options": ["Student", "Engineer"],
    },
]


def _create(client, admin_headers, join_form):
    body = {
        "name": "Form WS",
        "milestones": [{"title": "M1", "content_md": "", "minutes": None}],
        "join_form": join_form,
    }
    res = client.post("/api/admin/workshops", json=body, headers=admin_headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]["workshop"]


def test_join_form_end_to_end(client, make_client, admin_headers):
    ws = _create(client, admin_headers, FORM)
    slug = ws["join_slug"]

    # Join page exposes the fields.
    info = make_client().get(f"/api/join/{slug}").json()["data"]
    assert [f["key"] for f in info["workshop"]["join_form"]] == ["team", "role"]

    # Missing required field → 422 with a friendly message.
    b = make_client()
    res = b.post(f"/api/join/{slug}", json={"name": "Asha", "answers": {}})
    assert res.status_code == 422
    assert "Your team" in res.json()["detail"]["message"]

    # Dropdown answer must be a listed option.
    res = b.post(
        f"/api/join/{slug}",
        json={"name": "Asha", "answers": {"team": "Platform", "role": "CEO"}},
    )
    assert res.status_code == 422

    # Valid join stores answers; optional field may be omitted.
    res = b.post(
        f"/api/join/{slug}",
        json={"name": "Asha", "answers": {"team": "  Platform  ", "role": "Engineer"}},
    )
    assert res.status_code == 200

    # Facilitator dashboard shows the answers (trimmed).
    dash = client.get(f"/api/f/{ws['admin_token']}/dashboard").json()["data"]
    row = dash["participants"][0]
    assert row["answers"] == {"team": "Platform", "role": "Engineer"}

    # Facilitator can edit the join form; new joiners follow the new rules.
    res = client.patch(
        f"/api/f/{ws['admin_token']}/workshop",
        json={"join_form": [{"key": "team", "type": "text", "label": "Team", "required": False}]},
    )
    assert res.status_code == 200
    b2 = make_client()
    assert b2.post(f"/api/join/{slug}", json={"name": "Ravi"}).status_code == 200

    # GET /workshop exposes the current form for the editor.
    wsfull = client.get(f"/api/f/{ws['admin_token']}/workshop").json()["data"]
    assert wsfull["workshop"]["join_form"] == [
        {"key": "team", "type": "text", "label": "Team", "required": False}
    ]


def test_join_form_definition_validation(client, admin_headers):
    bad = [{"key": "9bad", "type": "text", "label": "X", "required": True}]
    body = {
        "name": "Bad WS",
        "milestones": [{"title": "M1", "content_md": "", "minutes": None}],
        "join_form": bad,
    }
    assert client.post("/api/admin/workshops", json=body, headers=admin_headers).status_code == 422
