from datetime import datetime, timedelta, timezone

from src.helmsman.services import snapshots
from src.helmsman.services.snapshots import (
    build_distribution,
    clear_snapshot_cache,
    median_progress_pct,
    progress_pct,
    rank_participants,
)

T0 = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)


def _entry(pid: int, name: str, joined_minutes: int, completion_minutes: list[int]) -> dict:
    return {
        "participant_id": pid,
        "name": name,
        "joined_at": T0 + timedelta(minutes=joined_minutes),
        "completion_times": [T0 + timedelta(minutes=m) for m in completion_minutes],
    }


def test_progress_pct_rounds_to_one_decimal():
    assert progress_pct(1, 8) == 12.5
    assert progress_pct(2, 3) == 66.7


def test_progress_pct_zero_total_is_zero():
    assert progress_pct(0, 0) == 0.0


def test_median_progress_even_count_averages_middle_two():
    assert median_progress_pct([0.0, 25.0, 50.0, 100.0]) == 37.5


def test_median_progress_empty_is_zero():
    assert median_progress_pct([]) == 0.0


def test_distribution_covers_every_count_with_zeros():
    rows = build_distribution([0, 0, 2], total_count=3)
    assert rows == [
        {"completed_count": 0, "participants": 2},
        {"completed_count": 1, "participants": 0},
        {"completed_count": 2, "participants": 1},
        {"completed_count": 3, "participants": 0},
    ]


def test_rank_orders_by_completed_count_desc():
    ranked = rank_participants(
        [_entry(1, "One", 0, [10]), _entry(2, "Two", 1, [10, 20]), _entry(3, "Three", 2, [])]
    )
    assert [e["participant_id"] for e in ranked] == [2, 1, 3]
    assert [e["rank"] for e in ranked] == [1, 2, 3]


def test_rank_tie_broken_by_earliest_reach_time():
    ranked = rank_participants(
        [_entry(1, "Late", 0, [5, 40]), _entry(2, "Early", 1, [5, 20])]
    )
    assert [e["participant_id"] for e in ranked] == [2, 1]


def test_rank_zero_completions_tie_broken_by_joined_at():
    ranked = rank_participants([_entry(1, "Second", 5, []), _entry(2, "First", 1, [])])
    assert [e["participant_id"] for e in ranked] == [2, 1]


def test_rank_has_no_tie_sharing():
    ranked = rank_participants(
        [_entry(1, "A", 0, [10]), _entry(2, "B", 1, [10])]
    )
    assert [e["rank"] for e in ranked] == [1, 2]


def test_memo_cache_returns_same_object_within_ttl():
    clear_snapshot_cache()
    builds = []
    result_a = snapshots._memoized(("k", 1), lambda: builds.append(1) or {"n": len(builds)})
    result_b = snapshots._memoized(("k", 1), lambda: builds.append(1) or {"n": len(builds)})
    assert result_a is result_b
    assert len(builds) == 1


def test_memo_cache_rebuilds_after_ttl(monkeypatch):
    clear_snapshot_cache()
    fake_now = [100.0]
    monkeypatch.setattr(snapshots, "_monotonic", lambda: fake_now[0])
    snapshots._memoized(("k", 2), lambda: {"first": True})
    fake_now[0] += snapshots.SNAPSHOT_TTL_SECONDS + 0.1
    rebuilt = snapshots._memoized(("k", 2), lambda: {"second": True})
    assert rebuilt == {"second": True}


def test_memo_cache_prunes_expired_entries(monkeypatch):
    clear_snapshot_cache()
    fake_now = [100.0]
    monkeypatch.setattr(snapshots, "_monotonic", lambda: fake_now[0])
    snapshots._memoized(("old", 1), lambda: {"v": 1})
    fake_now[0] += snapshots.SNAPSHOT_TTL_SECONDS + 0.1
    snapshots._memoized(("new", 1), lambda: {"v": 2})
    assert ("old", 1) not in snapshots._cache
    assert ("new", 1) in snapshots._cache


def test_memo_cache_distinct_keys_build_separately():
    clear_snapshot_cache()
    a = snapshots._memoized(("k", 1), lambda: {"v": 1})
    b = snapshots._memoized(("k", 2), lambda: {"v": 2})
    assert a != b
