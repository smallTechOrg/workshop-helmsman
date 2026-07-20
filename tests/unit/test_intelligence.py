"""Pure-function tests for proactive intelligence: stuck, bottleneck, pulse."""

from datetime import datetime, timedelta, timezone

from src.helmsman.services.intelligence import compute_bottleneck, compute_pulse, compute_stuck

T0 = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


def _p(pid, name, last_activity_minutes_ago, current_milestone_id, finished=False):
    return {
        "participant_id": pid,
        "name": name,
        "last_activity_at": T0 - timedelta(minutes=last_activity_minutes_ago),
        "current_milestone_id": current_milestone_id,
        "finished": finished,
    }


def test_stuck_flags_inactive_participants():
    participants = [_p(1, "Priya", 20, 5), _p(2, "Arun", 1, 5)]
    stuck = compute_stuck(participants, workshop_paused=False, stuck_minutes=10, now=T0)
    assert [s["participant_id"] for s in stuck] == [1]
    assert stuck[0]["minutes_inactive"] == 20
    assert stuck[0]["current_milestone_id"] == 5


def test_stuck_excludes_finished_participants():
    participants = [_p(1, "Priya", 30, None, finished=True)]
    stuck = compute_stuck(participants, workshop_paused=False, stuck_minutes=10, now=T0)
    assert stuck == []


def test_stuck_empty_when_workshop_paused():
    participants = [_p(1, "Priya", 30, 5)]
    stuck = compute_stuck(participants, workshop_paused=True, stuck_minutes=10, now=T0)
    assert stuck == []


def test_stuck_empty_participant_list():
    assert compute_stuck([], workshop_paused=False, stuck_minutes=10, now=T0) == []


def test_bottleneck_none_when_no_active_participants():
    assert compute_bottleneck([], {1: "Setup"}) is None


def test_bottleneck_none_when_below_quarter_threshold():
    active = [{"current_milestone_id": 1}] + [{"current_milestone_id": i} for i in range(2, 6)]
    # milestone 1 has only 1/5 = 20% < 25%
    assert compute_bottleneck(active, {1: "Setup", 2: "A", 3: "B", 4: "C", 5: "D"}) is None


def test_bottleneck_detected_at_or_above_quarter():
    active = [{"current_milestone_id": 1}] * 3 + [{"current_milestone_id": 2}]
    result = compute_bottleneck(active, {1: "Setup", 2: "Configure"})
    assert result == {"milestone_id": 1, "title": "Setup", "waiting_count": 3}


def test_bottleneck_ignores_finished_participants_with_no_current_milestone():
    active = [{"current_milestone_id": None}, {"current_milestone_id": None}]
    assert compute_bottleneck(active, {}) is None


def test_pulse_defaults_when_no_data():
    result = compute_pulse([], {}, [], now=T0)
    assert result["pace_ratio"] == 1.0
    assert result["on_track_pct"] == 0.0
    assert result["projected_finish_at"] is None


def test_pulse_pace_ratio_faster_than_planned():
    result = compute_pulse(
        completion_durations_minutes=[10, 10, 10],
        planned_minutes_by_milestone={1: 20, 2: 20},
        participants_progress=[],
        now=T0,
    )
    assert result["pace_ratio"] == 0.5


def test_pulse_on_track_pct_and_projection():
    progress = [
        {
            "joined_at": T0 - timedelta(minutes=5),
            "completed_count": 2,
            "total_count": 4,
            "remaining_planned_minutes": 20,
        },
        {
            "joined_at": T0 - timedelta(minutes=5),
            "completed_count": 0,
            "total_count": 4,
            "remaining_planned_minutes": 40,
        },
    ]
    result = compute_pulse(
        completion_durations_minutes=[15],
        planned_minutes_by_milestone={1: 10, 2: 10, 3: 10, 4: 10},
        participants_progress=progress,
        now=T0,
    )
    assert result["on_track_pct"] == 50.0
    assert result["projected_finish_at"] is not None
