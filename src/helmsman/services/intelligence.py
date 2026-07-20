"""Proactive-intelligence pure functions — stuck alerts, bottleneck, pace pulse.

Every function here takes already-loaded plain data (no session, no I/O) so it is
directly unit-testable. Callers in snapshots.py load rows and pass them in.
Guards against empty/edge cases — never raises.
"""

from datetime import datetime, timedelta
from statistics import median

from src.helmsman.api._common import as_utc, iso_z


def compute_stuck(
    participants: list[dict],
    workshop_paused: bool,
    stuck_minutes: int,
    now: datetime,
) -> list[dict]:
    """participants: [{"participant_id","name","last_activity_at","current_milestone_id",
    "finished"}]. Stuck = live (not finished), not paused, no activity for >= stuck_minutes."""
    if workshop_paused:
        return []
    threshold = timedelta(minutes=stuck_minutes)
    stuck = []
    for p in participants:
        if p["finished"]:
            continue
        inactive_for = now - as_utc(p["last_activity_at"])
        if inactive_for >= threshold:
            stuck.append(
                {
                    "participant_id": p["participant_id"],
                    "name": p["name"],
                    "minutes_inactive": int(inactive_for.total_seconds() // 60),
                    "current_milestone_id": p["current_milestone_id"],
                }
            )
    return stuck


def compute_bottleneck(
    active_participants: list[dict], milestones_by_id: dict[int, str]
) -> dict | None:
    """active_participants: [{"current_milestone_id"}] — only those active (last_seen
    within the active window). Bottleneck = milestone with the largest group,
    only if that group is >=25% of active participants."""
    total_active = len(active_participants)
    if total_active == 0:
        return None
    counts: dict[int, int] = {}
    for p in active_participants:
        mid = p["current_milestone_id"]
        if mid is None:
            continue
        counts[mid] = counts.get(mid, 0) + 1
    if not counts:
        return None
    best_id, best_count = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))
    if best_count / total_active < 0.25:
        return None
    title = milestones_by_id.get(best_id)
    if title is None:
        return None
    return {"milestone_id": best_id, "title": title, "waiting_count": best_count}


def compute_pulse(
    completion_durations_minutes: list[float],
    planned_minutes_by_milestone: dict[int, int],
    participants_progress: list[dict],
    now: datetime,
) -> dict:
    """completion_durations_minutes: observed actual minutes-per-completed-milestone
    (already computed by caller from consecutive completion timestamps / join time).
    planned_minutes_by_milestone: {milestone_id: minutes} for milestones with a set minutes value.
    participants_progress: [{"joined_at","completed_count","total_count",
      "remaining_planned_minutes"}] — remaining_planned_minutes = sum of `minutes` for
      the participant's not-yet-completed milestones (None entries excluded).
    """
    planned_values = [m for m in planned_minutes_by_milestone.values() if m and m > 0]
    median_planned = median(planned_values) if planned_values else None
    median_actual = median(completion_durations_minutes) if completion_durations_minutes else None

    if median_planned and median_actual is not None:
        pace_ratio = round(median_actual / median_planned, 2)
    else:
        pace_ratio = 1.0

    on_track_flags: list[bool] = []
    for p in participants_progress:
        total = p["total_count"]
        if total <= 0:
            continue
        elapsed_minutes = (now - as_utc(p["joined_at"])).total_seconds() / 60
        total_planned = sum(m for m in planned_minutes_by_milestone.values() if m)
        if total_planned <= 0 or elapsed_minutes <= 0:
            continue
        expected_fraction = min(1.0, elapsed_minutes / total_planned)
        actual_fraction = p["completed_count"] / total
        on_track_flags.append(actual_fraction >= expected_fraction)

    on_track_pct = (
        round(sum(1 for f in on_track_flags if f) / len(on_track_flags) * 100, 1)
        if on_track_flags
        else 0.0
    )

    remaining_values = [
        p["remaining_planned_minutes"]
        for p in participants_progress
        if p["remaining_planned_minutes"] is not None and p["completed_count"] < p["total_count"]
    ]
    projected_finish_at = None
    if remaining_values:
        median_remaining = median(remaining_values)
        eta_minutes = median_remaining * pace_ratio
        projected_finish_at = iso_z(now + timedelta(minutes=eta_minutes))

    return {
        "pace_ratio": pace_ratio,
        "on_track_pct": on_track_pct,
        "projected_finish_at": projected_finish_at,
    }
