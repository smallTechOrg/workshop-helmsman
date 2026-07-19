"""Facilitator surface — /api/f/{admin_token}/… (see spec/api.md §Facilitator surface)."""

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.helmsman.api._common import api_error, iso_z, ok, request_base_url, utcnow
from src.helmsman.db.models import HelpAnswer, HelpRequest, Milestone, Workshop
from src.helmsman.db.session import get_session
from src.helmsman.security import workshop_by_admin_token
from src.helmsman.services.audit import record_action
from src.helmsman.services.snapshots import (
    bump_state_version,
    dashboard_snapshot,
    serialize_help_request_facilitator,
)

log = structlog.get_logger("helmsman")

router = APIRouter(prefix="/api/f/{admin_token}")

ANSWER_MAX = 10_000
AUDIT_EXCERPT_MAX = 200


class AnswerBody(BaseModel):
    answer_md: str

    @field_validator("answer_md")
    @classmethod
    def _check_answer(cls, value: str) -> str:
        if not (1 <= len(value) <= ANSWER_MAX):
            raise ValueError(f"answer_md must be 1–{ANSWER_MAX} characters")
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
    return ok(
        {
            "help_request": serialize_help_request_facilitator(session, help_request),
            "version": version,
        }
    )


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
    return ok(
        {
            "help_request": serialize_help_request_facilitator(session, help_request),
            "version": workshop.state_version,
        }
    )
