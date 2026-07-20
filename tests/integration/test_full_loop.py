"""The Phase-1 core loop end-to-end over real HTTP + a real SQLite file:
create → two joins → completions → dashboard reflects → help → answer → seen → resolve.
"""

import json

from sqlalchemy import select


def test_full_core_loop(client, make_client, workshop, join_participant):
    slug = workshop["join_slug"]
    admin_token = workshop["admin_token"]

    priya_browser = make_client()
    arun_browser = make_client()
    priya = join_participant(priya_browser, slug, "Priya")
    arun = join_participant(arun_browser, slug, "Arun")

    # Initial tracker state
    state = priya_browser.get(f"/api/p/{priya['participant_token']}/state").json()["data"]
    assert state["changed"] is True
    milestone_ids = [m["id"] for m in state["milestones"]]
    assert len(milestone_ids) == 3
    assert "content_md" not in state["milestones"][0]
    assert state["me"]["completed_count"] == 0
    assert state["me"]["total_count"] == 3
    assert state["workshop"]["paused"] is False

    # Milestone bodies come from the content endpoint
    content = priya_browser.get(f"/api/p/{priya['participant_token']}/content").json()["data"]
    assert content["changed"] is True
    assert content["milestones"][0]["content_md"] == "```bash\nuv sync\n```"
    assert content["workshop"]["description_md"] == workshop["description_md"]

    # Priya completes two milestones; Arun completes one
    for milestone_id in milestone_ids[:2]:
        result = priya_browser.post(
            f"/api/p/{priya['participant_token']}/milestones/{milestone_id}/complete"
        ).json()["data"]
    assert result["completed_count"] == 2
    assert result["progress_pct"] == 66.7
    arun_browser.post(
        f"/api/p/{arun['participant_token']}/milestones/{milestone_ids[0]}/complete"
    )

    # Dashboard reflects the room
    dashboard = client.get(f"/api/f/{admin_token}/dashboard").json()["data"]
    assert dashboard["changed"] is True
    assert dashboard["stats"]["participant_count"] == 2
    assert dashboard["stats"]["active_count"] == 2
    assert dashboard["stats"]["finished_count"] == 0
    assert dashboard["stats"]["median_progress_pct"] == 50.0
    per_milestone = {m["milestone_id"]: m for m in dashboard["milestone_stats"]}
    assert per_milestone[milestone_ids[0]]["completed_count"] == 2
    assert per_milestone[milestone_ids[0]]["completed_pct"] == 100.0
    assert per_milestone[milestone_ids[1]]["completed_count"] == 1
    assert per_milestone[milestone_ids[2]]["completed_count"] == 0
    assert dashboard["distribution"] == [
        {"completed_count": 0, "participants": 0},
        {"completed_count": 1, "participants": 1},
        {"completed_count": 2, "participants": 1},
        {"completed_count": 3, "participants": 0},
    ]
    rows = {p["name"]: p for p in dashboard["participants"]}
    assert rows["Priya"]["completed_count"] == 2
    assert rows["Priya"]["current_milestone_id"] == milestone_ids[2]
    assert rows["Priya"]["participant_url"].endswith(priya["participant_token"])
    assert dashboard["broadcast"] is None
    assert dashboard["alerts"]["stuck"] == []
    assert dashboard["pulse"]["open_help_count"] == dashboard["stats"]["open_help_count"]
    assert dashboard["spend"] is None

    # Leaderboard on the tracker: Priya rank 1, Arun rank 2
    state = priya_browser.get(f"/api/p/{priya['participant_token']}/state").json()["data"]
    assert state["me"]["rank"] == 1
    assert [(r["rank"], r["name"], r["is_me"]) for r in state["leaderboard"]] == [
        (1, "Priya", True),
        (2, "Arun", False),
    ]

    # Arun asks for help — attached to his current milestone (second one)
    help_result = arun_browser.post(
        f"/api/p/{arun['participant_token']}/help",
        json={"message": "getting a 401 from the API"},
    ).json()["data"]
    help_id = help_result["help_request"]["id"]
    assert help_result["help_request"]["status"] == "open"
    assert help_result["help_request"]["milestone_id"] == milestone_ids[1]

    # It shows in the dashboard queue with participant + milestone context
    dashboard = client.get(f"/api/f/{admin_token}/dashboard").json()["data"]
    assert dashboard["stats"]["open_help_count"] == 1
    queue_row = dashboard["help_queue"][0]
    assert queue_row["id"] == help_id
    assert queue_row["participant_name"] == "Arun"
    assert queue_row["milestone_title"] == "Configure the API key"
    assert queue_row["message"] == "getting a 401 from the API"
    assert queue_row["status"] == "open"
    assert queue_row["answers"] == []

    # Facilitator answers with markdown
    answered = client.post(
        f"/api/f/{admin_token}/help/{help_id}/answer",
        json={"answer_md": "Check `.env` — the key name must be exact."},
    ).json()["data"]
    assert answered["help_request"]["status"] == "answered"
    answer_row = answered["help_request"]["answers"][0]
    assert answer_row["source"] == "facilitator"
    assert answer_row["draft"] is False
    assert answer_row["ai_confidence"] is None
    assert answer_row["ai_model"] is None
    assert answer_row["ai_context"] is None

    # Arun sees the answer on his next poll — participant shape has no draft/ai fields
    state = arun_browser.get(f"/api/p/{arun['participant_token']}/state").json()["data"]
    my_request = state["help_requests"][0]
    assert my_request["status"] == "answered"
    assert my_request["answers"][0]["answer_md"] == "Check `.env` — the key name must be exact."
    assert set(my_request["answers"][0].keys()) == {"id", "source", "answer_md", "created_at"}

    # Arun resolves his own request
    resolved = arun_browser.post(
        f"/api/p/{arun['participant_token']}/help/{help_id}/resolve"
    ).json()["data"]
    assert resolved["help_request"]["status"] == "resolved"

    # Dashboard totals reflect the resolution
    dashboard = client.get(f"/api/f/{admin_token}/dashboard").json()["data"]
    assert dashboard["stats"]["open_help_count"] == 0
    assert dashboard["stats"]["resolved_help_count"] == 1

    # Audit trail: workshop.create + help.answer recorded
    from src.helmsman.db.models import FacilitatorAction
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        actions = [
            row.action
            for row in session.scalars(
                select(FacilitatorAction).order_by(FacilitatorAction.id)
            )
        ]
    assert actions == ["workshop.create", "help.answer"]


def test_facilitator_resolve_writes_audit_row(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    help_id = browser.post(
        f"/api/p/{joined['participant_token']}/help", json={"message": "stuck"}
    ).json()["data"]["help_request"]["id"]

    resolved = client.post(
        f"/api/f/{workshop['admin_token']}/help/{help_id}/resolve"
    ).json()["data"]
    assert resolved["help_request"]["status"] == "resolved"

    from src.helmsman.db.models import FacilitatorAction
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        row = session.scalar(
            select(FacilitatorAction).where(FacilitatorAction.action == "help.resolve")
        )
        assert row is not None
        assert json.loads(row.detail_json)["help_request_id"] == help_id


def test_answer_after_resolved_keeps_status_resolved(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    help_id = browser.post(f"/api/p/{token}/help", json={"message": "stuck"}).json()["data"][
        "help_request"
    ]["id"]
    client.post(f"/api/f/{workshop['admin_token']}/help/{help_id}/resolve")

    answered = client.post(
        f"/api/f/{workshop['admin_token']}/help/{help_id}/answer",
        json={"answer_md": "late follow-up"},
    ).json()["data"]
    assert answered["help_request"]["status"] == "resolved"
    assert len(answered["help_request"]["answers"]) == 1
