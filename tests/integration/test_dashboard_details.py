"""Dashboard/leaderboard fine print: ranking order, help-queue ordering + resolved cap,
timestamp format, snapshot coalescing."""

import re
from datetime import timedelta

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_leaderboard_rank_earlier_reach_time_wins(
    client, make_client, workshop, join_participant
):
    slug = workshop["join_slug"]
    fast_browser, slow_browser = make_client(), make_client()
    fast = join_participant(fast_browser, slug, "Fast")
    slow = join_participant(slow_browser, slug, "Slow")

    state = fast_browser.get(f"/api/p/{fast['participant_token']}/state").json()["data"]
    milestone_ids = [m["id"] for m in state["milestones"]]

    # Slow reaches count=1 first, then Fast — same count, Slow ranks higher
    slow_browser.post(f"/api/p/{slow['participant_token']}/milestones/{milestone_ids[0]}/complete")
    fast_browser.post(f"/api/p/{fast['participant_token']}/milestones/{milestone_ids[0]}/complete")

    from sqlalchemy import update

    from src.helmsman.db.models import MilestoneCompletion
    from src.helmsman.db.session import create_db_session
    from src.helmsman.api._common import utcnow

    # Make the reach-times unambiguous (SQLite stores microseconds; force a clear gap)
    with create_db_session() as session:
        session.execute(
            update(MilestoneCompletion)
            .where(MilestoneCompletion.participant_id == 1)
            .values(completed_at=utcnow() + timedelta(seconds=30))
        )

    from src.helmsman.services.snapshots import clear_snapshot_cache

    clear_snapshot_cache()
    state = slow_browser.get(f"/api/p/{slow['participant_token']}/state").json()["data"]
    names_in_order = [row["name"] for row in state["leaderboard"]]
    assert names_in_order == ["Slow", "Fast"]
    assert [row["rank"] for row in state["leaderboard"]] == [1, 2]


def test_help_queue_open_block_first_newest_first_within(
    client, make_client, workshop, join_participant
):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    ids = [
        browser.post(f"/api/p/{token}/help", json={"message": f"q{i}"}).json()["data"][
            "help_request"
        ]["id"]
        for i in range(3)
    ]
    # Answer the first request → it moves to the answered block
    client.post(
        f"/api/f/{workshop['admin_token']}/help/{ids[0]}/answer", json={"answer_md": "a"}
    )

    queue = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]["help_queue"]
    assert [(row["id"], row["status"]) for row in queue] == [
        (ids[2], "open"),
        (ids[1], "open"),
        (ids[0], "answered"),
    ]


def test_help_queue_caps_resolved_at_50_with_totals_in_stats(
    client, make_client, workshop, join_participant
):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")

    from datetime import timedelta

    from src.helmsman.api._common import utcnow
    from src.helmsman.db.models import HelpRequest, Workshop
    from src.helmsman.db.session import create_db_session

    base_time = utcnow()
    with create_db_session() as session:
        participant_id = 1
        for i in range(55):
            session.add(
                HelpRequest(
                    workshop_id=workshop["id"],
                    participant_id=participant_id,
                    milestone_id=None,
                    message=f"old question {i}",
                    status="resolved",
                    created_at=base_time + timedelta(seconds=i),
                    updated_at=base_time + timedelta(seconds=i),
                )
            )
        ws = session.get(Workshop, workshop["id"])
        ws.state_version += 1

    dashboard = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
    resolved_rows = [r for r in dashboard["help_queue"] if r["status"] == "resolved"]
    assert len(resolved_rows) == 50
    assert dashboard["stats"]["resolved_help_count"] == 55
    # newest resolved first
    assert resolved_rows[0]["message"] == "old question 54"


def test_timestamps_are_iso_8601_z(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    browser.post(f"/api/p/{token}/help", json={"message": "stuck"})

    dashboard = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
    row = dashboard["participants"][0]
    assert ISO_Z.match(row["joined_at"])
    assert ISO_Z.match(row["last_seen_at"])
    queue_row = dashboard["help_queue"][0]
    assert ISO_Z.match(queue_row["created_at"])
    assert ISO_Z.match(queue_row["updated_at"])


def test_snapshot_is_coalesced_across_pollers_at_same_version(
    client, make_client, workshop, join_participant
):
    join_participant(make_client(), workshop["join_slug"], "Priya")

    import src.helmsman.services.snapshots as snapshots

    calls = {"n": 0}
    original = snapshots._build_dashboard

    def counting_build(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    snapshots._build_dashboard = counting_build
    try:
        snapshots.clear_snapshot_cache()
        for _ in range(5):
            data = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
            assert data["changed"] is True
    finally:
        snapshots._build_dashboard = original
    assert calls["n"] == 1


def test_empty_workshop_dashboard_has_consistent_zero_state(client, workshop):
    dashboard = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
    assert dashboard["stats"] == {
        "participant_count": 0,
        "active_count": 0,
        "finished_count": 0,
        "median_progress_pct": 0.0,
        "open_help_count": 0,
        "answered_help_count": 0,
        "resolved_help_count": 0,
    }
    assert dashboard["participants"] == []
    assert dashboard["help_queue"] == []
    assert len(dashboard["distribution"]) == 4  # counts 0..3, zeros included
    assert all(bucket["participants"] == 0 for bucket in dashboard["distribution"])


def test_state_poll_touches_stale_last_seen_without_version_bump(
    client, make_client, workshop, join_participant
):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]

    from sqlalchemy import update

    from src.helmsman.api._common import utcnow
    from src.helmsman.db.models import Participant
    from src.helmsman.db.session import create_db_session
    from src.helmsman.services.snapshots import ACTIVE_WINDOW_SECONDS, clear_snapshot_cache

    with create_db_session() as session:
        session.execute(
            update(Participant).values(
                last_seen_at=utcnow() - timedelta(seconds=ACTIVE_WINDOW_SECONDS + 100)
            )
        )

    clear_snapshot_cache()
    dashboard = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
    assert dashboard["stats"]["active_count"] == 0
    version_before = dashboard["version"]

    state = browser.get(f"/api/p/{token}/state").json()["data"]
    assert state["version"] == version_before  # the touch never bumps the version

    clear_snapshot_cache()  # simulate TTL expiry (the safety net for touch-only changes)
    dashboard = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
    assert dashboard["stats"]["active_count"] == 1


def test_finished_participant_counted(client, make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    token = joined["participant_token"]
    state = browser.get(f"/api/p/{token}/state").json()["data"]
    for m in state["milestones"]:
        browser.post(f"/api/p/{token}/milestones/{m['id']}/complete")

    dashboard = client.get(f"/api/f/{workshop['admin_token']}/dashboard").json()["data"]
    assert dashboard["stats"]["finished_count"] == 1
    assert dashboard["stats"]["median_progress_pct"] == 100.0
    row = dashboard["participants"][0]
    assert row["current_milestone_id"] is None
    assert row["progress_pct"] == 100.0


def test_leaderboard_capped_at_top_15_plus_me(client, make_client, workshop, join_participant):
    """At scale the tracker payload sends only the top 15 + the caller's own row."""
    slug = workshop["join_slug"]
    browsers = [make_client() for _ in range(20)]
    joined = [
        join_participant(b, slug, f"P{i:02d}") for i, b in enumerate(browsers)
    ]

    # First 16 participants complete a milestone so P19 (idle) ranks below top 15.
    state = browsers[0].get(f"/api/p/{joined[0]['participant_token']}/state").json()["data"]
    first_milestone = state["milestones"][0]["id"]
    for b, j in zip(browsers[:16], joined[:16]):
        b.post(f"/api/p/{j['participant_token']}/milestones/{first_milestone}/complete")

    from src.helmsman.services.snapshots import clear_snapshot_cache

    clear_snapshot_cache()

    last = browsers[19].get(f"/api/p/{joined[19]['participant_token']}/state").json()["data"]
    assert last["participants_count"] == 20
    rows = last["leaderboard"]
    # top 15 + the caller's own trailing row
    assert len(rows) == 16
    assert [r["rank"] <= 15 for r in rows[:15]] == [True] * 15
    mine = rows[-1]
    assert mine["is_me"] is True and mine["rank"] > 15

    # A participant inside the top 15 gets exactly 15 rows (no duplicate self row).
    top = browsers[0].get(f"/api/p/{joined[0]['participant_token']}/state").json()["data"]
    assert len(top["leaderboard"]) == 15
    assert sum(1 for r in top["leaderboard"] if r["is_me"]) == 1
