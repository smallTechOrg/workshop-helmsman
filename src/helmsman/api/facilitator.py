"""Facilitator surface — /api/f/{admin_token}/… (see spec/api.md §Facilitator surface)."""

import json

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.helmsman.api._common import api_error, iso_z, ok, request_base_url, utcnow
from src.helmsman.db.models import (
    Broadcast,
    FacilitatorAction,
    HelpAnswer,
    HelpRequest,
    Milestone,
    MilestoneCompletion,
    Participant,
    Workshop,
)
from src.helmsman.db.session import get_session
from src.helmsman.security import workshop_by_admin_token
from src.helmsman.services.audit import record_action
from src.helmsman.services.snapshots import (
    bump_content_version,
    bump_state_version,
    dashboard_snapshot,
    serialize_broadcast,
    serialize_help_request_facilitator,
)
from src.helmsman.services.undo import apply_undo

log = structlog.get_logger("helmsman")

router = APIRouter(prefix="/api/f/{admin_token}")

ANSWER_MAX = 10_000
AUDIT_EXCERPT_MAX = 200
BROADCAST_MESSAGE_MAX = 4000
MILESTONE_TITLE_MAX = 200
MILESTONE_CONTENT_MAX = 20_000
AUDIT_PAGE_LIMIT_MAX = 100
AUDIT_PAGE_LIMIT_DEFAULT = 50
STUCK_MINUTES_MIN = 2
STUCK_MINUTES_MAX = 120


class AnswerBody(BaseModel):
    answer_md: str

    @field_validator("answer_md")
    @classmethod
    def _check_answer(cls, value: str) -> str:
        if not (1 <= len(value) <= ANSWER_MAX):
            raise ValueError(f"answer_md must be 1–{ANSWER_MAX} characters")
        return value


class BroadcastBody(BaseModel):
    message_md: str

    @field_validator("message_md")
    @classmethod
    def _check_message(cls, value: str) -> str:
        if not (1 <= len(value) <= BROADCAST_MESSAGE_MAX):
            raise ValueError(f"message_md must be 1–{BROADCAST_MESSAGE_MAX} characters")
        return value


class BroadcastClearBody(BaseModel):
    pass


class PauseBody(BaseModel):
    paused: bool


class AdvanceBody(BaseModel):
    milestone_id: int
    participant_ids: list[int] | None = None


class ReorderBody(BaseModel):
    milestone_ids: list[int]


class MilestoneCreateBody(BaseModel):
    title: str
    content_md: str = ""
    minutes: int | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str) -> str:
        if not (1 <= len(value) <= MILESTONE_TITLE_MAX):
            raise ValueError(f"title must be 1–{MILESTONE_TITLE_MAX} characters")
        return value

    @field_validator("content_md")
    @classmethod
    def _check_content(cls, value: str) -> str:
        if len(value) > MILESTONE_CONTENT_MAX:
            raise ValueError(f"content_md must be at most {MILESTONE_CONTENT_MAX} characters")
        return value

    @field_validator("minutes")
    @classmethod
    def _check_minutes(cls, value: int | None) -> int | None:
        if value is not None and not (1 <= value <= 480):
            raise ValueError("minutes must be null or 1–480")
        return value


class MilestonePatchBody(BaseModel):
    title: str | None = None
    content_md: str | None = None
    minutes: int | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str | None:
        if value is not None and not (1 <= len(value) <= MILESTONE_TITLE_MAX):
            raise ValueError(f"title must be 1–{MILESTONE_TITLE_MAX} characters")
        return value

    @field_validator("content_md")
    @classmethod
    def _check_content(cls, value: str | None) -> str | None:
        if value is not None and len(value) > MILESTONE_CONTENT_MAX:
            raise ValueError(f"content_md must be at most {MILESTONE_CONTENT_MAX} characters")
        return value

    @field_validator("minutes")
    @classmethod
    def _check_minutes(cls, value: int | None) -> int | None:
        if value is not None and not (1 <= value <= 480):
            raise ValueError("minutes must be null or 1–480")
        return value


class UndoBody(BaseModel):
    pass


class SettingsBody(BaseModel):
    stuck_minutes: int

    @field_validator("stuck_minutes")
    @classmethod
    def _check_stuck_minutes(cls, value: int) -> int:
        if not (STUCK_MINUTES_MIN <= value <= STUCK_MINUTES_MAX):
            raise ValueError(
                f"stuck_minutes must be {STUCK_MINUTES_MIN}–{STUCK_MINUTES_MAX}"
            )
        return value


def _help_request_in_workshop(
    session: Session, workshop: Workshop, help_request_id: int
) -> HelpRequest:
    help_request = session.get(HelpRequest, help_request_id)
    if help_request is None or help_request.workshop_id != workshop.id:
        raise api_error("not_found", "No such help request in this workshop.", 404)
    return help_request


def _guard_not_archived(workshop: Workshop) -> None:
    if workshop.status == "archived":
        raise api_error("workshop_archived", "This workshop has been archived and is read-only.", 410)


def _milestone_in_workshop(session: Session, workshop: Workshop, milestone_id: int) -> Milestone:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None or milestone.workshop_id != workshop.id:
        raise api_error("not_found", "No such milestone in this workshop.", 404)
    return milestone


@router.get("/workshop")
def get_workshop(
    admin_token: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    base = request_base_url(request)
    milestones = list(
        session.scalars(
            select(Milestone)
            .where(Milestone.workshop_id == workshop.id)
            .order_by(Milestone.position, Milestone.id)
        )
    )
    return ok(
        {
            "content_version": workshop.content_version,
            "workshop": {
                "id": workshop.id,
                "name": workshop.name,
                "description_md": workshop.description_md,
                "status": workshop.status,
                "paused": workshop.paused,
                "ai_enabled": workshop.ai_enabled,
                "join_slug": workshop.join_slug,
                "join_url": f"{base}/j/{workshop.join_slug}",
                "facilitator_url": f"{base}/f/{workshop.admin_token}",
                "created_at": iso_z(workshop.created_at),
            },
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


@router.get("/dashboard")
def poll_dashboard(
    admin_token: str,
    request: Request,
    v: int = -1,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    if v == workshop.state_version:
        return ok(
            {
                "changed": False,
                "version": workshop.state_version,
                "content_version": workshop.content_version,
            }
        )
    return ok(dashboard_snapshot(session, workshop, request_base_url(request)))


@router.post("/help/{help_request_id}/answer")
def answer_help_request(
    admin_token: str,
    help_request_id: int,
    body: AnswerBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)
    help_request = _help_request_in_workshop(session, workshop, help_request_id)

    session.add(
        HelpAnswer(
            help_request_id=help_request.id,
            source="facilitator",
            answer_md=body.answer_md,
        )
    )
    if help_request.status != "resolved":
        help_request.status = "answered"
    help_request.updated_at = utcnow()
    version = bump_state_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "help.answer",
        {
            "help_request_id": help_request.id,
            "participant_id": help_request.participant_id,
            "excerpt": body.answer_md[:AUDIT_EXCERPT_MAX],
        },
    )
    session.flush()
    log.info(
        "help.answered",
        workshop_id=workshop.id,
        help_request_id=help_request.id,
        participant_id=help_request.participant_id,
    )
    payload = ok(
        {
            "help_request": serialize_help_request_facilitator(session, help_request),
            "version": version,
        }
    )
    session.commit()  # visible before the response reaches the client
    return payload


# --- Phase 2: facilitator command & proactive intelligence ---


@router.post("/broadcast")
def send_broadcast(
    admin_token: str,
    body: BroadcastBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    previous = session.scalar(
        select(Broadcast).where(
            Broadcast.workshop_id == workshop.id, Broadcast.cleared_at.is_(None)
        )
    )
    previous_id = previous.id if previous is not None else None
    if previous is not None:
        previous.cleared_at = utcnow()

    broadcast = Broadcast(workshop_id=workshop.id, message_md=body.message_md)
    session.add(broadcast)
    session.flush()

    version = bump_state_version(workshop)
    action = record_action(
        session,
        workshop.id,
        "facilitator",
        "broadcast.send",
        {"broadcast_id": broadcast.id, "excerpt": body.message_md[:AUDIT_EXCERPT_MAX]},
    )
    action.undo_data_json = json.dumps({"previous_broadcast_id": previous_id})
    session.flush()
    log.info("broadcast.sent", workshop_id=workshop.id, broadcast_id=broadcast.id)
    payload = ok(
        {
            "broadcast": serialize_broadcast(broadcast),
            "version": version,
            "undoable_action_id": action.id,
        }
    )
    session.commit()
    return payload


@router.post("/broadcast/clear")
def clear_broadcast(
    admin_token: str,
    body: BroadcastClearBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    active = session.scalar(
        select(Broadcast).where(
            Broadcast.workshop_id == workshop.id, Broadcast.cleared_at.is_(None)
        )
    )
    if active is not None:
        active.cleared_at = utcnow()
        version = bump_state_version(workshop)
        record_action(
            session, workshop.id, "facilitator", "broadcast.clear", {"broadcast_id": active.id}
        )
        session.flush()
    else:
        version = workshop.state_version
    payload = ok({"version": version})
    session.commit()
    return payload


@router.post("/pause")
def set_pause(
    admin_token: str,
    body: PauseBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    previous_paused = workshop.paused
    workshop.paused = body.paused
    version = bump_state_version(workshop)
    action = record_action(
        session,
        workshop.id,
        "facilitator",
        "workshop.pause" if body.paused else "workshop.resume",
        {"paused": body.paused},
    )
    action.undo_data_json = json.dumps({"previous_paused": previous_paused})
    session.flush()
    log.info("workshop.paused" if body.paused else "workshop.resumed", workshop_id=workshop.id)
    payload = ok(
        {
            "paused": workshop.paused,
            "version": version,
            "undoable_action_id": action.id,
        }
    )
    session.commit()
    return payload


@router.post("/milestones/advance")
def advance_milestone(
    admin_token: str,
    body: AdvanceBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)
    milestone = _milestone_in_workshop(session, workshop, body.milestone_id)

    if body.participant_ids is None:
        participant_ids = list(
            session.scalars(
                select(Participant.id).where(Participant.workshop_id == workshop.id)
            )
        )
    else:
        participant_ids = list(body.participant_ids)
        rows = list(
            session.scalars(
                select(Participant.id).where(
                    Participant.workshop_id == workshop.id,
                    Participant.id.in_(participant_ids),
                )
            )
        )
        if len(set(rows)) != len(set(participant_ids)):
            raise api_error(
                "not_found", "One or more participant ids are not in this workshop.", 404
            )

    already_completed = set(
        session.scalars(
            select(MilestoneCompletion.participant_id).where(
                MilestoneCompletion.milestone_id == milestone.id,
                MilestoneCompletion.participant_id.in_(participant_ids),
            )
        )
    )
    to_create = [pid for pid in participant_ids if pid not in already_completed]

    created_ids: list[int] = []
    for pid in to_create:
        completion = MilestoneCompletion(
            participant_id=pid, milestone_id=milestone.id, source="facilitator"
        )
        session.add(completion)
        session.flush()
        created_ids.append(completion.id)

    version = bump_state_version(workshop)
    action = record_action(
        session,
        workshop.id,
        "facilitator",
        "milestone.advance_all" if body.participant_ids is None else "milestone.advance_selected",
        {
            "milestone_id": milestone.id,
            "participant_ids": body.participant_ids,
            "affected_count": len(created_ids),
        },
    )
    action.undo_data_json = json.dumps({"completion_ids": created_ids})
    session.flush()
    log.info(
        "milestone.advanced",
        workshop_id=workshop.id,
        milestone_id=milestone.id,
        affected_count=len(created_ids),
    )
    payload = ok(
        {
            "affected_count": len(created_ids),
            "version": version,
            "undoable_action_id": action.id,
        }
    )
    session.commit()
    return payload


@router.post("/milestones/reorder")
def reorder_milestones(
    admin_token: str,
    body: ReorderBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    milestones = list(
        session.scalars(select(Milestone).where(Milestone.workshop_id == workshop.id))
    )
    existing_ids = {m.id for m in milestones}
    if set(body.milestone_ids) != existing_ids or len(body.milestone_ids) != len(existing_ids):
        raise api_error(
            "validation_error",
            "milestone_ids must be an exact permutation of this workshop's milestones.",
            422,
        )

    by_id = {m.id: m for m in milestones}
    for position, milestone_id in enumerate(body.milestone_ids):
        by_id[milestone_id].position = position

    version = bump_state_version(workshop)
    content_version = bump_content_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "milestone.reorder",
        {"milestone_ids": body.milestone_ids},
    )
    session.flush()
    payload = ok({"version": version, "content_version": content_version})
    session.commit()
    return payload


@router.post("/milestones")
def create_milestone(
    admin_token: str,
    body: MilestoneCreateBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    max_position = session.scalar(
        select(Milestone.position)
        .where(Milestone.workshop_id == workshop.id)
        .order_by(Milestone.position.desc())
        .limit(1)
    )
    next_position = (max_position + 1) if max_position is not None else 0

    milestone = Milestone(
        workshop_id=workshop.id,
        position=next_position,
        title=body.title,
        content_md=body.content_md,
        minutes=body.minutes,
    )
    session.add(milestone)
    session.flush()

    content_version = bump_content_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "milestone.edit",
        {"op": "add", "milestone_id": milestone.id, "title": milestone.title},
    )
    session.flush()
    payload = ok(
        {
            "milestone": {
                "id": milestone.id,
                "position": milestone.position,
                "title": milestone.title,
                "content_md": milestone.content_md,
                "minutes": milestone.minutes,
            },
            "version": workshop.state_version,
            "content_version": content_version,
        }
    )
    session.commit()
    return payload


@router.patch("/milestones/{milestone_id}")
def patch_milestone(
    admin_token: str,
    milestone_id: int,
    body: MilestonePatchBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)
    milestone = _milestone_in_workshop(session, workshop, milestone_id)

    fields_set = body.model_fields_set
    if "title" in fields_set and body.title is not None:
        milestone.title = body.title
    if "content_md" in fields_set and body.content_md is not None:
        milestone.content_md = body.content_md
    if "minutes" in fields_set:
        milestone.minutes = body.minutes

    content_version = bump_content_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "milestone.edit",
        {"op": "edit", "milestone_id": milestone.id, "fields": sorted(fields_set)},
    )
    session.flush()
    payload = ok(
        {
            "milestone": {
                "id": milestone.id,
                "position": milestone.position,
                "title": milestone.title,
                "content_md": milestone.content_md,
                "minutes": milestone.minutes,
            },
            "version": workshop.state_version,
            "content_version": content_version,
        }
    )
    session.commit()
    return payload


@router.delete("/milestones/{milestone_id}")
def delete_milestone(
    admin_token: str,
    milestone_id: int,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)
    milestone = _milestone_in_workshop(session, workshop, milestone_id)

    session.query(MilestoneCompletion).filter(
        MilestoneCompletion.milestone_id == milestone.id
    ).delete(synchronize_session=False)
    session.delete(milestone)

    version = bump_state_version(workshop)
    content_version = bump_content_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "milestone.edit",
        {"op": "delete", "milestone_id": milestone_id},
    )
    session.flush()
    payload = ok({"version": version, "content_version": content_version})
    session.commit()
    return payload


@router.post("/undo/{action_id}")
def undo_action(
    admin_token: str,
    action_id: int,
    body: UndoBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    version = apply_undo(session, workshop, action_id)
    payload = ok({"version": version})
    session.commit()
    return payload


@router.get("/audit")
def get_audit(
    admin_token: str,
    before_id: int | None = None,
    limit: int = AUDIT_PAGE_LIMIT_DEFAULT,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)

    if not (1 <= limit <= AUDIT_PAGE_LIMIT_MAX):
        raise api_error(
            "validation_error", f"limit must be 1–{AUDIT_PAGE_LIMIT_MAX}.", 422
        )

    stmt = (
        select(FacilitatorAction)
        .where(FacilitatorAction.workshop_id == workshop.id)
        .order_by(FacilitatorAction.id.desc())
    )
    if before_id is not None:
        stmt = stmt.where(FacilitatorAction.id < before_id)
    rows = list(session.scalars(stmt.limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]

    

    return ok(
        {
            "actions": [
                {
                    "id": row.id,
                    "actor": row.actor,
                    "action": row.action,
                    "detail": json.loads(row.detail_json) if row.detail_json else {},
                    "created_at": iso_z(row.created_at),
                    "undone_at": iso_z(row.undone_at) if row.undone_at else None,
                }
                for row in rows
            ],
            "has_more": has_more,
        }
    )


@router.patch("/settings")
def patch_settings(
    admin_token: str,
    body: SettingsBody,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)

    workshop.stuck_minutes = body.stuck_minutes
    version = bump_state_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "settings.update",
        {"stuck_minutes": body.stuck_minutes},
    )
    session.flush()
    payload = ok({"stuck_minutes": workshop.stuck_minutes, "version": version})
    session.commit()
    return payload


@router.post("/help/{help_request_id}/resolve")
def resolve_help_request(
    admin_token: str,
    help_request_id: int,
    session: Session = Depends(get_session),
) -> dict:
    workshop = workshop_by_admin_token(session, admin_token)
    _guard_not_archived(workshop)
    help_request = _help_request_in_workshop(session, workshop, help_request_id)

    if help_request.status != "resolved":
        help_request.status = "resolved"
        help_request.updated_at = utcnow()
        bump_state_version(workshop)
        record_action(
            session,
            workshop.id,
            "facilitator",
            "help.resolve",
            {
                "help_request_id": help_request.id,
                "participant_id": help_request.participant_id,
            },
        )
        session.flush()
        log.info(
            "help.resolved",
            workshop_id=workshop.id,
            help_request_id=help_request.id,
            resolved_by="facilitator",
        )
    payload = ok(
        {
            "help_request": serialize_help_request_facilitator(session, help_request),
            "version": workshop.state_version,
        }
    )
    session.commit()  # visible before the response reaches the client
    return payload
