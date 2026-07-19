"""Participant surface — /api/join/{slug} and /api/p/{token}/… (see spec/api.md)."""

from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.helmsman.api._common import api_error, iso_z, ok, request_base_url, utcnow, as_utc
from src.helmsman.db.models import (
    HelpRequest,
    Milestone,
    MilestoneCompletion,
    Participant,
    Workshop,
)
from src.helmsman.db.session import get_session
from src.helmsman.security import (
    generate_participant_token,
    participant_by_token,
    workshop_by_join_slug,
)
from src.helmsman.services.snapshots import (
    bump_state_version,
    participant_shared_snapshot,
    progress_pct,
    serialize_help_request_participant,
)

log = structlog.get_logger("helmsman")

router = APIRouter(prefix="/api")

PARTICIPANT_NAME_MAX = 80
HELP_MESSAGE_MAX = 4000
COOKIE_MAX_AGE_SECONDS = 2_592_000  # 30 days
LAST_SEEN_TOUCH_SECONDS = 60


class JoinBody(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not (1 <= len(trimmed) <= PARTICIPANT_NAME_MAX):
            raise ValueError(f"name must be 1–{PARTICIPANT_NAME_MAX} characters")
        return trimmed


class HelpBody(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _check_message(cls, value: str) -> str:
        if not (1 <= len(value) <= HELP_MESSAGE_MAX):
            raise ValueError(f"message must be 1–{HELP_MESSAGE_MAX} characters")
        return value


def _cookie_name(workshop_id: int) -> str:
    return f"helmsman_p_{workshop_id}"


def _guard_not_archived(workshop: Workshop) -> None:
    if workshop.status == "archived":
        raise api_error("workshop_archived", "This workshop has been archived and is read-only.", 410)


def _guard_not_paused(workshop: Workshop) -> None:
    if workshop.paused:
        raise api_error(
            "workshop_paused", "This workshop is paused — completions are frozen for now.", 409
        )


def _milestone_in_workshop(session: Session, workshop: Workshop, milestone_id: int) -> Milestone:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None or milestone.workshop_id != workshop.id:
        raise api_error("not_found", "No such milestone in this workshop.", 404)
    return milestone


def _my_completed_ids_by_position(session: Session, participant: Participant) -> list[int]:
    rows = session.execute(
        select(MilestoneCompletion.milestone_id)
        .join(Milestone, MilestoneCompletion.milestone_id == Milestone.id)
        .where(MilestoneCompletion.participant_id == participant.id)
        .order_by(Milestone.position, Milestone.id)
    ).all()
    return [milestone_id for (milestone_id,) in rows]


def _completion_payload(
    session: Session, workshop: Workshop, participant: Participant
) -> dict:
    completed_ids = _my_completed_ids_by_position(session, participant)
    total = session.scalar(
        select(func.count(Milestone.id)).where(Milestone.workshop_id == workshop.id)
    )
    return {
        "completed_milestone_ids": completed_ids,
        "completed_count": len(completed_ids),
        "progress_pct": progress_pct(len(completed_ids), total or 0),
        "version": workshop.state_version,
    }


# --- join ---


@router.get("/join/{join_slug}")
def get_join_page(
    join_slug: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    workshop = workshop_by_join_slug(session, join_slug)
    milestone_count = session.scalar(
        select(func.count(Milestone.id)).where(Milestone.workshop_id == workshop.id)
    )
    participant_count = session.scalar(
        select(func.count(Participant.id)).where(Participant.workshop_id == workshop.id)
    )

    me = None
    cookie_token = request.cookies.get(_cookie_name(workshop.id))
    if cookie_token:
        participant = session.scalar(
            select(Participant).where(Participant.token == cookie_token)
        )
        if participant is not None and participant.workshop_id == workshop.id:
            me = {"participant_token": participant.token, "name": participant.name}

    return ok(
        {
            "workshop": {
                "name": workshop.name,
                "description_md": workshop.description_md,
                "status": workshop.status,
                "milestone_count": milestone_count or 0,
                "participant_count": participant_count or 0,
            },
            "me": me,
        }
    )


@router.post("/join/{join_slug}")
def join_workshop(
    join_slug: str,
    body: JoinBody,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_join_slug(session, join_slug)
    _guard_not_archived(workshop)

    participant = Participant(
        workshop_id=workshop.id,
        name=body.name,
        token=generate_participant_token(),
    )
    session.add(participant)
    bump_state_version(workshop)
    session.flush()

    response.set_cookie(
        key=_cookie_name(workshop.id),
        value=participant.token,
        max_age=COOKIE_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
    )
    log.info(
        "participant.joined",
        workshop_id=workshop.id,
        participant_id=participant.id,
        name=participant.name,
    )
    base = request_base_url(request)
    payload = ok(
        {
            "participant_token": participant.token,
            "participant_url": f"{base}/p/{participant.token}",
            "name": participant.name,
        }
    )
    session.commit()  # visible before the response reaches the client
    return payload


# --- tracker polling ---


def _touch_last_seen(participant: Participant) -> None:
    now = utcnow()
    if (now - as_utc(participant.last_seen_at)) >= timedelta(seconds=LAST_SEEN_TOUCH_SECONDS):
        participant.last_seen_at = now


@router.get("/p/{participant_token}/state")
def poll_state(
    participant_token: str,
    v: int = -1,
    session: Session = Depends(get_session),
) -> dict:
    participant, workshop = participant_by_token(session, participant_token)
    _touch_last_seen(participant)

    if v == workshop.state_version:
        return ok(
            {
                "changed": False,
                "version": workshop.state_version,
                "content_version": workshop.content_version,
            }
        )

    shared = participant_shared_snapshot(session, workshop)
    completed_ids = _my_completed_ids_by_position(session, participant)
    total_count = shared["total_count"]
    rank = shared["rank_by_participant_id"].get(participant.id)

    leaderboard = [
        {
            "rank": row["rank"],
            "name": row["name"],
            "completed_count": row["completed_count"],
            "progress_pct": row["progress_pct"],
            "is_me": row["participant_id"] == participant.id,
        }
        for row in shared["leaderboard"]
    ]

    my_requests = list(
        session.scalars(
            select(HelpRequest)
            .where(HelpRequest.participant_id == participant.id)
            .order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc())
        )
    )

    return ok(
        {
            "changed": True,
            "version": workshop.state_version,
            "content_version": workshop.content_version,
            "workshop": shared["workshop"],
            "milestones": shared["milestones"],
            "me": {
                "id": participant.id,
                "name": participant.name,
                "completed_milestone_ids": completed_ids,
                "completed_count": len(completed_ids),
                "total_count": total_count,
                "progress_pct": progress_pct(len(completed_ids), total_count),
                "rank": rank,
            },
            "leaderboard": leaderboard,
            "broadcast": None,
            "help_requests": [
                serialize_help_request_participant(session, hr) for hr in my_requests
            ],
        }
    )


@router.get("/p/{participant_token}/content")
def get_content(
    participant_token: str,
    cv: int = -1,
    session: Session = Depends(get_session),
) -> dict:
    _participant, workshop = participant_by_token(session, participant_token)

    if cv == workshop.content_version:
        return ok({"changed": False, "content_version": workshop.content_version})

    milestones = list(
        session.scalars(
            select(Milestone)
            .where(Milestone.workshop_id == workshop.id)
            .order_by(Milestone.position, Milestone.id)
        )
    )
    return ok(
        {
            "changed": True,
            "content_version": workshop.content_version,
            "workshop": {"name": workshop.name, "description_md": workshop.description_md},
            "milestones": [
                {
                    "id": m.id,
                    "position": m.position,
                    "title": m.title,
                    "content_md": m.content_md,
                    "minutes": m.minutes,
                }
                for m in milestones
            ],
        }
    )


# --- completions ---


@router.post("/p/{participant_token}/milestones/{milestone_id}/complete")
def complete_milestone(
    participant_token: str,
    milestone_id: int,
    session: Session = Depends(get_session),
) -> dict:
    participant, workshop = participant_by_token(session, participant_token)
    _guard_not_archived(workshop)
    _guard_not_paused(workshop)
    milestone = _milestone_in_workshop(session, workshop, milestone_id)

    existing = session.scalar(
        select(MilestoneCompletion).where(
            MilestoneCompletion.participant_id == participant.id,
            MilestoneCompletion.milestone_id == milestone.id,
        )
    )
    if existing is None:
        session.add(
            MilestoneCompletion(
                participant_id=participant.id,
                milestone_id=milestone.id,
                source="participant",
            )
        )
        bump_state_version(workshop)
        session.flush()
        log.info(
            "milestone.completed",
            workshop_id=workshop.id,
            participant_id=participant.id,
            milestone_id=milestone.id,
        )
    payload = ok(_completion_payload(session, workshop, participant))
    session.commit()  # visible before the response reaches the client
    return payload


@router.post("/p/{participant_token}/milestones/{milestone_id}/uncomplete")
def uncomplete_milestone(
    participant_token: str,
    milestone_id: int,
    session: Session = Depends(get_session),
) -> dict:
    participant, workshop = participant_by_token(session, participant_token)
    _guard_not_archived(workshop)
    _guard_not_paused(workshop)
    milestone = _milestone_in_workshop(session, workshop, milestone_id)

    existing = session.scalar(
        select(MilestoneCompletion).where(
            MilestoneCompletion.participant_id == participant.id,
            MilestoneCompletion.milestone_id == milestone.id,
        )
    )
    if existing is not None:
        session.delete(existing)
        bump_state_version(workshop)
        session.flush()
        log.info(
            "milestone.uncompleted",
            workshop_id=workshop.id,
            participant_id=participant.id,
            milestone_id=milestone.id,
        )
    payload = ok(_completion_payload(session, workshop, participant))
    session.commit()  # visible before the response reaches the client
    return payload


# --- help desk ---


@router.post("/p/{participant_token}/help")
def create_help_request(
    participant_token: str,
    body: HelpBody,
    session: Session = Depends(get_session),
) -> dict:
    participant, workshop = participant_by_token(session, participant_token)
    _guard_not_archived(workshop)

    completed_ids = set(_my_completed_ids_by_position(session, participant))
    milestones = list(
        session.scalars(
            select(Milestone)
            .where(Milestone.workshop_id == workshop.id)
            .order_by(Milestone.position, Milestone.id)
        )
    )
    current_milestone_id = next(
        (m.id for m in milestones if m.id not in completed_ids), None
    )

    help_request = HelpRequest(
        workshop_id=workshop.id,
        participant_id=participant.id,
        milestone_id=current_milestone_id,
        message=body.message,
        status="open",
    )
    session.add(help_request)
    version = bump_state_version(workshop)
    session.flush()
    log.info(
        "help.created",
        workshop_id=workshop.id,
        participant_id=participant.id,
        help_request_id=help_request.id,
        milestone_id=current_milestone_id,
    )
    payload = ok(
        {
            "help_request": serialize_help_request_participant(session, help_request),
            "version": version,
        }
    )
    session.commit()  # visible before the response reaches the client
    return payload


@router.post("/p/{participant_token}/help/{help_request_id}/resolve")
def resolve_own_help_request(
    participant_token: str,
    help_request_id: int,
    session: Session = Depends(get_session),
) -> dict:
    participant, workshop = participant_by_token(session, participant_token)
    _guard_not_archived(workshop)

    help_request = session.get(HelpRequest, help_request_id)
    if help_request is None or help_request.participant_id != participant.id:
        raise api_error("not_found", "No such help request of yours.", 404)

    if help_request.status != "resolved":
        help_request.status = "resolved"
        help_request.updated_at = utcnow()
        bump_state_version(workshop)
        session.flush()
        log.info(
            "help.resolved",
            workshop_id=workshop.id,
            help_request_id=help_request.id,
            resolved_by="participant",
        )
    payload = ok(
        {
            "help_request": serialize_help_request_participant(session, help_request),
            "version": workshop.state_version,
        }
    )
    session.commit()  # visible before the response reaches the client
    return payload
