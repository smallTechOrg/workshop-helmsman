"""Versioned poll-payload builders + the in-process snapshot memo cache.

The changed-payload for a given (kind, workshop_id, state_version) is built once and
shared by every poller at that version (coalescing). A short TTL is the safety net for
data that changes without a version bump (e.g. throttled last_seen_at touches).
Single-worker process model makes this cache correct without external infrastructure.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.helmsman.api._common import as_utc, iso_z, utcnow
from src.helmsman.db.models import (
    Broadcast,
    HelpAnswer,
    HelpRequest,
    Milestone,
    MilestoneCompletion,
    Participant,
    Workshop,
)
from src.helmsman.services.intelligence import compute_bottleneck, compute_pulse, compute_stuck

SNAPSHOT_TTL_SECONDS = 2.0
ACTIVE_WINDOW_SECONDS = 300
RESOLVED_QUEUE_LIMIT = 50

_cache: dict[tuple, tuple[float, dict]] = {}

_monotonic = time.monotonic  # module-level indirection so tests can inject a clock


def clear_snapshot_cache() -> None:
    _cache.clear()


def _memoized(key: tuple, builder: Callable[[], dict]) -> dict:
    now = _monotonic()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < SNAPSHOT_TTL_SECONDS:
        return hit[1]
    value = builder()
    expired = [k for k, (built_at, _) in _cache.items() if now - built_at >= SNAPSHOT_TTL_SECONDS]
    for stale_key in expired:
        _cache.pop(stale_key, None)
    _cache[key] = (now, value)
    return value


# --- version counters (bumped in the SAME transaction as the triggering write) ---


def bump_state_version(workshop: Workshop) -> int:
    workshop.state_version += 1
    return workshop.state_version


def bump_content_version(workshop: Workshop) -> int:
    workshop.content_version += 1
    return workshop.content_version


# --- pure computation helpers (unit-tested) ---


def progress_pct(completed_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return round(completed_count / total_count * 100, 1)


def median_progress_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(median(values)), 1)


def build_distribution(completed_counts: list[int], total_count: int) -> list[dict]:
    """Histogram covering every completed-count 0..total, zeros included."""
    buckets = {n: 0 for n in range(total_count + 1)}
    for count in completed_counts:
        if count in buckets:
            buckets[count] += 1
    return [{"completed_count": n, "participants": buckets[n]} for n in range(total_count + 1)]


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def rank_participants(entries: list[dict]) -> list[dict]:
    """Rank order: completed_count desc → earliest time of reaching that count asc →
    joined_at asc. 1-based rank, no tie-sharing.

    Each entry: {"participant_id", "name", "joined_at", "completion_times": [datetime...]}.
    Returns new dicts with added "completed_count" and "rank".
    """

    def sort_key(entry: dict) -> tuple:
        times = entry["completion_times"]
        count = len(times)
        reached_at = as_utc(max(times)) if times else _EPOCH
        return (-count, reached_at, as_utc(entry["joined_at"]))

    ordered = sorted(entries, key=sort_key)
    return [
        {**entry, "completed_count": len(entry["completion_times"]), "rank": index + 1}
        for index, entry in enumerate(ordered)
    ]


# --- shared row serializers ---


def serialize_answer_facilitator(answer: HelpAnswer) -> dict:
    return {
        "id": answer.id,
        "source": answer.source,
        "answer_md": answer.answer_md,
        "draft": answer.draft,
        "created_at": iso_z(answer.created_at),
        "ai_confidence": float(answer.ai_confidence) if answer.ai_confidence is not None else None,
        "ai_model": answer.ai_model,
        "ai_context": json.loads(answer.ai_context_json) if answer.ai_context_json else None,
    }


def serialize_answer_participant(answer: HelpAnswer) -> dict:
    return {
        "id": answer.id,
        "source": answer.source,
        "answer_md": answer.answer_md,
        "created_at": iso_z(answer.created_at),
    }


def _load_answers(session: Session, help_request_id: int) -> list[HelpAnswer]:
    return list(
        session.scalars(
            select(HelpAnswer)
            .where(HelpAnswer.help_request_id == help_request_id)
            .order_by(HelpAnswer.created_at, HelpAnswer.id)
        )
    )


def serialize_help_request_facilitator(session: Session, help_request: HelpRequest) -> dict:
    participant = session.get(Participant, help_request.participant_id)
    milestone = (
        session.get(Milestone, help_request.milestone_id)
        if help_request.milestone_id is not None
        else None
    )
    return {
        "id": help_request.id,
        "participant_id": help_request.participant_id,
        "participant_name": participant.name if participant else "",
        "milestone_id": help_request.milestone_id,
        "milestone_title": milestone.title if milestone else None,
        "message": help_request.message,
        "status": help_request.status,
        "escalated": help_request.escalated,
        "created_at": iso_z(help_request.created_at),
        "updated_at": iso_z(help_request.updated_at),
        "answers": [
            serialize_answer_facilitator(a) for a in _load_answers(session, help_request.id)
        ],
    }


def serialize_help_request_participant(session: Session, help_request: HelpRequest) -> dict:
    """Tracker row shape — never includes drafts or ai_context."""
    answers = [a for a in _load_answers(session, help_request.id) if not a.draft]
    return {
        "id": help_request.id,
        "message": help_request.message,
        "status": help_request.status,
        "escalated": help_request.escalated,
        "milestone_id": help_request.milestone_id,
        "created_at": iso_z(help_request.created_at),
        "answers": [serialize_answer_participant(a) for a in answers],
    }


# --- bulk loaders ---


def _load_milestones(session: Session, workshop_id: int) -> list[Milestone]:
    return list(
        session.scalars(
            select(Milestone)
            .where(Milestone.workshop_id == workshop_id)
            .order_by(Milestone.position, Milestone.id)
        )
    )


def _load_participants(session: Session, workshop_id: int) -> list[Participant]:
    return list(
        session.scalars(
            select(Participant)
            .where(Participant.workshop_id == workshop_id)
            .order_by(Participant.joined_at, Participant.id)
        )
    )


def _load_completions_by_participant(
    session: Session, workshop_id: int
) -> dict[int, list[tuple[int, datetime]]]:
    rows = session.execute(
        select(
            MilestoneCompletion.participant_id,
            MilestoneCompletion.milestone_id,
            MilestoneCompletion.completed_at,
        )
        .join(Milestone, MilestoneCompletion.milestone_id == Milestone.id)
        .where(Milestone.workshop_id == workshop_id)
    ).all()
    by_participant: dict[int, list[tuple[int, datetime]]] = {}
    for participant_id, milestone_id, completed_at in rows:
        by_participant.setdefault(participant_id, []).append((milestone_id, completed_at))
    return by_participant


def _current_milestone_id(milestones: list[Milestone], completed_ids: set[int]) -> int | None:
    for milestone in milestones:
        if milestone.id not in completed_ids:
            return milestone.id
    return None


def _ordered_completed_ids(milestones: list[Milestone], completed_ids: set[int]) -> list[int]:
    return [m.id for m in milestones if m.id in completed_ids]


def _active_broadcast(session: Session, workshop_id: int) -> Broadcast | None:
    return session.scalar(
        select(Broadcast)
        .where(Broadcast.workshop_id == workshop_id, Broadcast.cleared_at.is_(None))
        .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
    )


def serialize_broadcast(broadcast: Broadcast | None) -> dict | None:
    if broadcast is None:
        return None
    return {
        "id": broadcast.id,
        "message_md": broadcast.message_md,
        "created_at": iso_z(broadcast.created_at),
    }


def _build_alerts_and_pulse(
    session: Session,
    workshop: Workshop,
    milestones: list[Milestone],
    participants: list[Participant],
    completions: dict[int, list[tuple[int, datetime]]],
    open_help_by_participant: dict[int, int],
    help_requests: list[HelpRequest],
    now: datetime,
) -> tuple[dict, dict]:
    total_count = len(milestones)
    milestones_by_id = {m.id: m.title for m in milestones}
    planned_minutes_by_milestone = {m.id: m.minutes for m in milestones if m.minutes}

    last_help_by_participant: dict[int, datetime] = {}
    for hr in help_requests:
        current = last_help_by_participant.get(hr.participant_id)
        if current is None or as_utc(hr.created_at) > as_utc(current):
            last_help_by_participant[hr.participant_id] = hr.created_at

    stuck_input = []
    active_for_bottleneck = []
    completion_durations: list[float] = []
    participants_progress = []

    for p in participants:
        completion_list = sorted(completions.get(p.id, []), key=lambda t: as_utc(t[1]))
        completed_ids = {mid for mid, _ in completion_list}
        finished = total_count > 0 and len(completed_ids) == total_count
        current_milestone_id = _current_milestone_id(milestones, completed_ids)

        candidates = [t for _, t in completion_list]
        if p.id in last_help_by_participant:
            candidates.append(last_help_by_participant[p.id])
        last_activity_at = max(candidates, key=as_utc) if candidates else p.joined_at

        stuck_input.append(
            {
                "participant_id": p.id,
                "name": p.name,
                "last_activity_at": last_activity_at,
                "current_milestone_id": current_milestone_id,
                "finished": finished,
            }
        )

        if (now - as_utc(p.last_seen_at)) <= timedelta(seconds=ACTIVE_WINDOW_SECONDS):
            active_for_bottleneck.append({"current_milestone_id": current_milestone_id})

        previous_at = p.joined_at
        for _, completed_at in completion_list:
            gap_minutes = (as_utc(completed_at) - as_utc(previous_at)).total_seconds() / 60
            if gap_minutes >= 0:
                completion_durations.append(gap_minutes)
            previous_at = completed_at

        remaining_minutes = sum(
            (m.minutes or 0)
            for m in milestones
            if m.id not in completed_ids and m.minutes
        )
        participants_progress.append(
            {
                "joined_at": p.joined_at,
                "completed_count": len(completed_ids),
                "total_count": total_count,
                "remaining_planned_minutes": remaining_minutes if total_count > 0 else None,
            }
        )

    stuck = compute_stuck(stuck_input, workshop.paused, workshop.stuck_minutes, now)
    bottleneck = compute_bottleneck(active_for_bottleneck, milestones_by_id)
    pulse_core = compute_pulse(
        completion_durations, planned_minutes_by_milestone, participants_progress, now
    )
    open_help_count = sum(1 for hr in help_requests if hr.status == "open")

    alerts = {"stuck": stuck, "bottleneck": bottleneck}
    pulse = {
        "pace_ratio": pulse_core["pace_ratio"],
        "on_track_pct": pulse_core["on_track_pct"],
        "open_help_count": open_help_count,
        "projected_finish_at": pulse_core["projected_finish_at"],
    }
    return alerts, pulse


# --- facilitator dashboard snapshot ---


def dashboard_snapshot(session: Session, workshop: Workshop, base_url: str) -> dict:
    key = ("dashboard", workshop.id, workshop.state_version, base_url)
    return _memoized(key, lambda: _build_dashboard(session, workshop, base_url))


def _build_dashboard(session: Session, workshop: Workshop, base_url: str) -> dict:
    milestones = _load_milestones(session, workshop.id)
    participants = _load_participants(session, workshop.id)
    completions = _load_completions_by_participant(session, workshop.id)
    total_count = len(milestones)
    now = utcnow()

    help_requests = list(
        session.scalars(
            select(HelpRequest).where(HelpRequest.workshop_id == workshop.id)
        )
    )
    open_help_by_participant: dict[int, int] = {}
    for hr in help_requests:
        if hr.status == "open":
            open_help_by_participant[hr.participant_id] = (
                open_help_by_participant.get(hr.participant_id, 0) + 1
            )

    participant_rows = []
    completed_counts: list[int] = []
    progress_values: list[float] = []
    finished_count = 0
    active_count = 0
    for p in participants:
        completed_ids = {mid for mid, _ in completions.get(p.id, [])}
        count = len(completed_ids)
        completed_counts.append(count)
        pct = progress_pct(count, total_count)
        progress_values.append(pct)
        if total_count > 0 and count == total_count:
            finished_count += 1
        if (now - as_utc(p.last_seen_at)) <= timedelta(seconds=ACTIVE_WINDOW_SECONDS):
            active_count += 1
        participant_rows.append(
            {
                "id": p.id,
                "name": p.name,
                "joined_at": iso_z(p.joined_at),
                "last_seen_at": iso_z(p.last_seen_at),
                "completed_milestone_ids": _ordered_completed_ids(milestones, completed_ids),
                "completed_count": count,
                "progress_pct": pct,
                "current_milestone_id": _current_milestone_id(milestones, completed_ids),
                "open_help_count": open_help_by_participant.get(p.id, 0),
                "participant_url": f"{base_url}/p/{p.token}",
            }
        )

    per_milestone_completed: dict[int, int] = {m.id: 0 for m in milestones}
    for completion_list in completions.values():
        for milestone_id, _ in completion_list:
            if milestone_id in per_milestone_completed:
                per_milestone_completed[milestone_id] += 1
    milestone_stats = [
        {
            "milestone_id": m.id,
            "position": m.position,
            "title": m.title,
            "completed_count": per_milestone_completed[m.id],
            "completed_pct": progress_pct(per_milestone_completed[m.id], len(participants)),
        }
        for m in milestones
    ]

    status_counts = {"open": 0, "answered": 0, "resolved": 0}
    for hr in help_requests:
        if hr.status in status_counts:
            status_counts[hr.status] += 1

    newest_first = sorted(help_requests, key=lambda hr: (as_utc(hr.created_at), hr.id), reverse=True)
    queue = (
        [hr for hr in newest_first if hr.status == "open"]
        + [hr for hr in newest_first if hr.status == "answered"]
        + [hr for hr in newest_first if hr.status == "resolved"][:RESOLVED_QUEUE_LIMIT]
    )
    help_queue = [serialize_help_request_facilitator(session, hr) for hr in queue]

    alerts, pulse = _build_alerts_and_pulse(
        session,
        workshop,
        milestones,
        participants,
        completions,
        open_help_by_participant,
        help_requests,
        now,
    )
    broadcast = serialize_broadcast(_active_broadcast(session, workshop.id))

    return {
        "changed": True,
        "version": workshop.state_version,
        "content_version": workshop.content_version,
        "workshop": {
            "id": workshop.id,
            "name": workshop.name,
            "status": workshop.status,
            "paused": workshop.paused,
            "ai_enabled": workshop.ai_enabled,
        },
        "stats": {
            "participant_count": len(participants),
            "active_count": active_count,
            "finished_count": finished_count,
            "median_progress_pct": median_progress_pct(progress_values),
            "open_help_count": status_counts["open"],
            "answered_help_count": status_counts["answered"],
            "resolved_help_count": status_counts["resolved"],
        },
        "milestone_stats": milestone_stats,
        "distribution": build_distribution(completed_counts, total_count),
        "participants": participant_rows,
        "help_queue": help_queue,
        "broadcast": broadcast,
        "alerts": alerts,
        "pulse": pulse,
        "spend": None,
    }


# --- participant shared snapshot (per-requester fields are layered on by the router) ---


def participant_shared_snapshot(session: Session, workshop: Workshop) -> dict:
    key = ("participant", workshop.id, workshop.state_version)
    return _memoized(key, lambda: _build_participant_shared(session, workshop))


def _build_participant_shared(session: Session, workshop: Workshop) -> dict:
    milestones = _load_milestones(session, workshop.id)
    participants = _load_participants(session, workshop.id)
    completions = _load_completions_by_participant(session, workshop.id)
    total_count = len(milestones)

    entries = [
        {
            "participant_id": p.id,
            "name": p.name,
            "joined_at": p.joined_at,
            "completion_times": [t for _, t in completions.get(p.id, [])],
        }
        for p in participants
    ]
    ranked = rank_participants(entries)

    leaderboard = [
        {
            "participant_id": entry["participant_id"],
            "rank": entry["rank"],
            "name": entry["name"],
            "completed_count": entry["completed_count"],
            "progress_pct": progress_pct(entry["completed_count"], total_count),
        }
        for entry in ranked
    ]

    return {
        "workshop": {
            "name": workshop.name,
            "status": workshop.status,
            "paused": workshop.paused,
        },
        "milestones": [
            {"id": m.id, "position": m.position, "title": m.title, "minutes": m.minutes}
            for m in milestones
        ],
        "total_count": total_count,
        "leaderboard": leaderboard,
        "rank_by_participant_id": {entry["participant_id"]: entry["rank"] for entry in ranked},
        "broadcast": serialize_broadcast(_active_broadcast(session, workshop.id)),
    }
