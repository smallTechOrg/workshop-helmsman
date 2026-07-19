"""A 40-participant workshop seeded with a pre-computed expected alert/pulse set —
not a trivially-empty fixture. Verifies compute_stuck/compute_bottleneck/compute_pulse
wired end-to-end through the dashboard snapshot with exact expected results."""

from datetime import timedelta

from sqlalchemy import select, update

from src.helmsman.api._common import utcnow
from src.helmsman.db.models import MilestoneCompletion, Participant
from src.helmsman.db.session import create_db_session
from src.helmsman.services.snapshots import clear_snapshot_cache

FOUR_MILESTONES_BODY = {
    "name": "Big Workshop",
    "description_md": "Scale test.",
    "milestones": [
        {"title": "Milestone 1", "content_md": "…", "minutes": 10},
        {"title": "Milestone 2", "content_md": "…", "minutes": 10},
        {"title": "Milestone 3", "content_md": "…", "minutes": 10},
        {"title": "Milestone 4", "content_md": "…", "minutes": 10},
    ],
}


def test_forty_participant_fixture_produces_expected_alerts_and_pulse(
    client, make_client, admin_headers
):
    created = client.post(
        "/api/admin/workshops", json=FOUR_MILESTONES_BODY, headers=admin_headers
    ).json()["data"]["workshop"]
    admin_token = created["admin_token"]

    workshop_full = client.get(f"/api/f/{admin_token}/workshop").json()["data"]
    m1, m2 = workshop_full["milestones"][0]["id"], workshop_full["milestones"][1]["id"]

    # 17 fillers: joined now, no completions, current_milestone = m1
    filler_tokens = []
    for i in range(17):
        browser = make_client()
        joined = browser.post(
            f"/api/join/{created['join_slug']}", json={"name": f"Filler{i}"}
        ).json()["data"]
        filler_tokens.append(joined["participant_token"])

    # 20 on-pace: complete m1, joined ~15 min ago, completed ~5 min ago (duration 10 min)
    onpace_tokens = []
    for i in range(20):
        browser = make_client()
        joined = browser.post(
            f"/api/join/{created['join_slug']}", json={"name": f"OnPace{i}"}
        ).json()["data"]
        browser.post(f"/api/p/{joined['participant_token']}/milestones/{m1}/complete")
        onpace_tokens.append(joined["participant_token"])

    # 3 stuck-at-m2: complete m1, joined ~30 min ago, completed ~25 min ago (stale activity)
    stuck_tokens = []
    for i in range(3):
        browser = make_client()
        joined = browser.post(
            f"/api/join/{created['join_slug']}", json={"name": f"Stuck{i}"}
        ).json()["data"]
        browser.post(f"/api/p/{joined['participant_token']}/milestones/{m1}/complete")
        stuck_tokens.append(joined["participant_token"])

    now = utcnow()
    with create_db_session() as session:
        onpace_ids = list(
            session.scalars(
                select(Participant.id).where(Participant.token.in_(onpace_tokens))
            )
        )
        session.execute(
            update(Participant)
            .where(Participant.id.in_(onpace_ids))
            .values(joined_at=now - timedelta(minutes=15))
        )
        session.execute(
            update(MilestoneCompletion)
            .where(MilestoneCompletion.participant_id.in_(onpace_ids))
            .values(completed_at=now - timedelta(minutes=5))
        )

        stuck_ids = list(
            session.scalars(
                select(Participant.id).where(Participant.token.in_(stuck_tokens))
            )
        )
        session.execute(
            update(Participant)
            .where(Participant.id.in_(stuck_ids))
            .values(joined_at=now - timedelta(minutes=30))
        )
        session.execute(
            update(MilestoneCompletion)
            .where(MilestoneCompletion.participant_id.in_(stuck_ids))
            .values(completed_at=now - timedelta(minutes=25))
        )

    clear_snapshot_cache()

    # 2 open help requests, to check pulse.open_help_count
    help_browser = make_client()
    help_joined = help_browser.post(
        f"/api/join/{created['join_slug']}", json={"name": "Helpme"}
    ).json()["data"]
    help_browser.post(f"/api/p/{help_joined['participant_token']}/help", json={"message": "stuck 1"})
    help_browser.post(f"/api/p/{help_joined['participant_token']}/help", json={"message": "stuck 2"})

    clear_snapshot_cache()
    dashboard = client.get(f"/api/f/{admin_token}/dashboard?v=-1").json()["data"]

    assert dashboard["stats"]["participant_count"] == 41  # 17 + 20 + 3 + 1 helper

    stuck_ids_reported = {row["participant_id"] for row in dashboard["alerts"]["stuck"]}
    with create_db_session() as session:
        expected_stuck_ids = set(
            session.scalars(select(Participant.id).where(Participant.token.in_(stuck_tokens)))
        )
    assert stuck_ids_reported == expected_stuck_ids
    for row in dashboard["alerts"]["stuck"]:
        assert row["current_milestone_id"] == m2
        assert row["minutes_inactive"] >= 25

    assert dashboard["alerts"]["bottleneck"]["milestone_id"] == m2
    assert dashboard["alerts"]["bottleneck"]["waiting_count"] == 23  # 20 onpace + 3 stuck

    assert dashboard["pulse"]["pace_ratio"] == 1.0
    assert dashboard["pulse"]["open_help_count"] == 2
    assert dashboard["pulse"]["projected_finish_at"] is not None
