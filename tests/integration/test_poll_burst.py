"""Poll burst at the stated scale: 300 participants, one completion, 300 sequential
state polls. With no cross-request memo (architecture.md §Live-update point 5), every
payload must be identical in `leaderboard` and `version`, and the leaderboard must match
values computed independently from the seeded data (top-15 plus the caller's own row), so
a truncated/sampled/stale board would be observably different."""

from datetime import timedelta

from sqlalchemy import select

from src.workshop0.api._common import utcnow
from src.workshop0.db.models import Participant, Workshop
from src.workshop0.db.session import create_db_session
from src.workshop0.security import generate_participant_token

PARTICIPANTS = 300
POLLS = 300
TOP_N = 15  # participant.py LEADERBOARD_TOP_N

BODY = {
    "name": "Burst Workshop",
    "description_md": "Poll burst.",
    "milestones": [
        {"title": f"Milestone {i}", "content_md": "…", "minutes": 10} for i in (1, 2, 3)
    ],
}


def test_three_hundred_polls_after_one_completion_are_identical_and_correct(
    client, admin_headers
):
    created = client.post("/api/admin/workshops", json=BODY, headers=admin_headers).json()[
        "data"
    ]["workshop"]
    admin_token = created["admin_token"]
    m1 = client.get(f"/api/f/{admin_token}/workshop").json()["data"]["milestones"][0]["id"]

    # Bulk-seed 300 participants with distinct, strictly increasing joined_at.
    base = utcnow() - timedelta(hours=1)
    tokens = [generate_participant_token() for _ in range(PARTICIPANTS)]
    with create_db_session() as session:
        workshop_id = session.scalar(
            select(Workshop.id).where(Workshop.join_slug == created["join_slug"])
        )
        session.add_all(
            Participant(
                workshop_id=workshop_id,
                name=f"P{i:03d}",
                token=tokens[i],
                joined_at=base + timedelta(seconds=i),
            )
            for i in range(PARTICIPANTS)
        )
        session.commit()

    # One completion by a participant who joined mid-pack -> becomes rank 1.
    completer = 150
    done = client.post(f"/api/p/{tokens[completer]}/milestones/{m1}/complete")
    assert done.status_code == 200

    # Expected board computed from the seed: completer first, then join order.
    order = [completer] + [i for i in range(PARTICIPANTS) if i != completer]
    expected_rank = {idx: pos + 1 for pos, idx in enumerate(order)}

    def expected_board(me: int) -> list[dict]:
        rows = order[:TOP_N] + ([me] if me not in order[:TOP_N] else [])
        return [
            {
                "rank": expected_rank[i],
                "name": f"P{i:03d}",
                "completed_count": 1 if i == completer else 0,
                "progress_pct": round(100 / 3, 1) if i == completer else 0,
                "is_me": i == me,
            }
            for i in rows
        ]

    me = PARTICIPANTS - 1  # last to join -> rank 300, outside top-N
    first = client.get(f"/api/p/{tokens[me]}/state?v=-1").json()["data"]
    assert first["changed"] is True
    assert first["participants_count"] == PARTICIPANTS
    assert first["me"]["rank"] == PARTICIPANTS
    assert len(first["leaderboard"]) == TOP_N + 1
    got = [{**row, "progress_pct": row["progress_pct"]} for row in first["leaderboard"]]
    want = expected_board(me)
    for g, w in zip(got, want):
        assert g["rank"] == w["rank"] and g["name"] == w["name"]
        assert g["completed_count"] == w["completed_count"] and g["is_me"] == w["is_me"]
        assert abs(g["progress_pct"] - w["progress_pct"]) < 0.1
    assert [r["name"] for r in got] == [r["name"] for r in want]
    assert got[0]["name"] == f"P{completer:03d}" and got[0]["completed_count"] == 1
    assert got[-1]["is_me"] is True and got[-1]["rank"] == PARTICIPANTS

    # The burst: every payload identical in leaderboard and version.
    for n in range(POLLS):
        data = client.get(f"/api/p/{tokens[me]}/state?v=-1").json()["data"]
        assert data["version"] == first["version"], f"poll {n}: version drifted"
        assert data["leaderboard"] == first["leaderboard"], f"poll {n}: leaderboard differs"

    # A caller inside the top-N sees exactly TOP_N rows with their own row flagged.
    top = client.get(f"/api/p/{tokens[completer]}/state?v=-1").json()["data"]
    assert len(top["leaderboard"]) == TOP_N
    assert [r["is_me"] for r in top["leaderboard"]] == [True] + [False] * (TOP_N - 1)
    assert top["leaderboard"][1:] == first["leaderboard"][1:TOP_N]
