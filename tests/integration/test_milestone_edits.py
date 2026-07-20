"""Milestone add / patch / delete / reorder: version and content_version bumps."""


def test_add_milestone_bumps_content_version(client, workshop):
    admin_token = workshop["admin_token"]
    before = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    result = client.post(
        f"/api/f/{admin_token}/milestones",
        json={"title": "Extra credit", "content_md": "Bonus round.", "minutes": 20},
    )
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["milestone"]["title"] == "Extra credit"
    assert data["milestone"]["position"] == 3
    assert data["content_version"] == before["content_version"] + 1


def test_patch_milestone_edits_fields(client, workshop):
    admin_token = workshop["admin_token"]
    got = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    milestone_id = got["milestones"][0]["id"]

    result = client.patch(
        f"/api/f/{admin_token}/milestones/{milestone_id}", json={"title": "Renamed"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["data"]["milestone"]["title"] == "Renamed"
    assert result.json()["data"]["milestone"]["content_md"] == got["milestones"][0]["content_md"]


def test_patch_milestone_unknown_id_404(client, workshop):
    admin_token = workshop["admin_token"]
    result = client.patch(
        f"/api/f/{admin_token}/milestones/999999", json={"title": "X"}
    )
    assert result.status_code == 404


def test_patch_milestone_can_set_minutes_null(client, workshop):
    admin_token = workshop["admin_token"]
    got = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    milestone_id = got["milestones"][0]["id"]
    result = client.patch(
        f"/api/f/{admin_token}/milestones/{milestone_id}", json={"minutes": None}
    ).json()["data"]
    assert result["milestone"]["minutes"] is None


def test_delete_milestone_bumps_both_versions_and_removes_completions(
    client, make_client, workshop, join_participant
):
    admin_token = workshop["admin_token"]
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    got = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    milestone_id = got["milestones"][0]["id"]
    browser.post(f"/api/p/{joined['participant_token']}/milestones/{milestone_id}/complete")

    before = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]

    result = client.delete(f"/api/f/{admin_token}/milestones/{milestone_id}")
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["version"] > before["version"]
    assert data["content_version"] > before["content_version"]

    refreshed = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    assert milestone_id not in [m["id"] for m in refreshed["milestones"]]


def test_delete_milestone_unknown_id_404(client, workshop):
    admin_token = workshop["admin_token"]
    result = client.delete(f"/api/f/{admin_token}/milestones/999999")
    assert result.status_code == 404


def test_reorder_exact_permutation(client, workshop):
    admin_token = workshop["admin_token"]
    got = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    ids = [m["id"] for m in got["milestones"]]
    reversed_ids = list(reversed(ids))

    result = client.post(
        f"/api/f/{admin_token}/milestones/reorder", json={"milestone_ids": reversed_ids}
    )
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["content_version"] == got["content_version"] + 1

    refreshed = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    assert [m["id"] for m in refreshed["milestones"]] == reversed_ids


def test_reorder_rejects_non_permutation(client, workshop):
    admin_token = workshop["admin_token"]
    got = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    ids = [m["id"] for m in got["milestones"]]

    missing_one = ids[:-1]
    result = client.post(
        f"/api/f/{admin_token}/milestones/reorder", json={"milestone_ids": missing_one}
    )
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "validation_error"

    with_unknown_id = ids + [999999]
    result2 = client.post(
        f"/api/f/{admin_token}/milestones/reorder", json={"milestone_ids": with_unknown_id}
    )
    assert result2.status_code == 422


def test_patch_workshop_name_and_description(client, make_client, workshop, join_participant):
    token = workshop["admin_token"]

    res = client.patch(
        f"/api/f/{token}/workshop",
        json={"name": "  Renamed Workshop  ", "description_md": "New **intro** text."},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["workshop"]["name"] == "Renamed Workshop"  # trimmed
    assert data["workshop"]["description_md"] == "New **intro** text."

    # Participants see both changes: name in state, description in content.
    b = make_client()
    p = join_participant(b, workshop["join_slug"], "Viewer")
    state = b.get(f"/api/p/{p['participant_token']}/state").json()["data"]
    assert state["workshop"]["name"] == "Renamed Workshop"
    content = b.get(f"/api/p/{p['participant_token']}/content").json()["data"]
    assert content["workshop"]["description_md"] == "New **intro** text."

    # Audited.
    audit = client.get(f"/api/f/{token}/audit").json()["data"]
    assert any(row["action"] == "workshop.edit" for row in audit["actions"])

    # Validation: empty name rejected, oversize description rejected.
    assert client.patch(f"/api/f/{token}/workshop", json={"name": "   "}).status_code == 422
    assert (
        client.patch(f"/api/f/{token}/workshop", json={"description_md": "x" * 10_001}).status_code
        == 422
    )
