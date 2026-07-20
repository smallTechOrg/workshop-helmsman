"""Admin surface — header `X-Admin-Key` (see spec/api.md §Admin surface)."""

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.helmsman.api._common import iso_z, ok, request_base_url
from src.helmsman.db.models import HelpRequest, Milestone, Participant, Workshop
from src.helmsman.db.session import get_session
from src.helmsman.security import (
    generate_admin_token,
    generate_join_slug,
    require_admin_key,
)
from src.helmsman.services.audit import record_action

log = structlog.get_logger("helmsman")

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin_key)])

NAME_MAX = 120
DESCRIPTION_MAX = 10_000
MILESTONES_MAX = 50
MILESTONE_TITLE_MAX = 200
MILESTONE_CONTENT_MAX = 20_000
MILESTONE_MINUTES_MIN = 1
MILESTONE_MINUTES_MAX = 480


class MilestoneIn(BaseModel):
    title: str
    content_md: str = ""
    minutes: int | None = None

    @field_validator("title")
    @classmethod
    def _trim_title(cls, value: str) -> str:
        trimmed = value.strip()
        if not (1 <= len(trimmed) <= MILESTONE_TITLE_MAX):
            raise ValueError(f"milestone title must be 1–{MILESTONE_TITLE_MAX} characters")
        return trimmed

    @field_validator("content_md")
    @classmethod
    def _limit_content(cls, value: str) -> str:
        if len(value) > MILESTONE_CONTENT_MAX:
            raise ValueError(f"milestone content must be at most {MILESTONE_CONTENT_MAX} characters")
        return value

    @field_validator("minutes")
    @classmethod
    def _check_minutes(cls, value: int | None) -> int | None:
        if value is not None and not (MILESTONE_MINUTES_MIN <= value <= MILESTONE_MINUTES_MAX):
            raise ValueError(
                f"minutes must be between {MILESTONE_MINUTES_MIN} and {MILESTONE_MINUTES_MAX}"
            )
        return value


class WorkshopCreate(BaseModel):
    name: str
    description_md: str = ""
    milestones: list[MilestoneIn] = Field(min_length=1, max_length=MILESTONES_MAX)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not (1 <= len(trimmed) <= NAME_MAX):
            raise ValueError(f"name must be 1–{NAME_MAX} characters")
        return trimmed

    @field_validator("description_md")
    @classmethod
    def _limit_description(cls, value: str) -> str:
        if len(value) > DESCRIPTION_MAX:
            raise ValueError(f"description must be at most {DESCRIPTION_MAX} characters")
        return value


def _unique_admin_token(session: Session) -> str:
    while True:
        token = generate_admin_token()
        if session.scalar(select(Workshop.id).where(Workshop.admin_token == token)) is None:
            return token


def _unique_join_slug(session: Session) -> str:
    while True:
        slug = generate_join_slug()
        if session.scalar(select(Workshop.id).where(Workshop.join_slug == slug)) is None:
            return slug


def _workshop_urls(base: str, workshop: Workshop) -> dict:
    return {
        "join_url": f"{base}/j/{workshop.join_slug}",
        "facilitator_url": f"{base}/f/{workshop.admin_token}",
    }


@router.get("/workshops")
def list_workshops(request: Request, session: Session = Depends(get_session)) -> dict:
    base = request_base_url(request)
    workshops = list(
        session.scalars(select(Workshop).order_by(Workshop.created_at.desc(), Workshop.id.desc()))
    )
    participant_counts = dict(
        session.execute(
            select(Participant.workshop_id, func.count(Participant.id)).group_by(
                Participant.workshop_id
            )
        ).all()
    )
    open_help_counts = dict(
        session.execute(
            select(HelpRequest.workshop_id, func.count(HelpRequest.id))
            .where(HelpRequest.status == "open")
            .group_by(HelpRequest.workshop_id)
        ).all()
    )
    rows = [
        {
            "id": w.id,
            "name": w.name,
            "status": w.status,
            "participant_count": participant_counts.get(w.id, 0),
            "open_help_count": open_help_counts.get(w.id, 0),
            "created_at": iso_z(w.created_at),
            "join_slug": w.join_slug,
            **_workshop_urls(base, w),
        }
        for w in workshops
    ]
    return ok({"workshops": rows})


@router.post("/workshops")
def create_workshop(
    body: WorkshopCreate, request: Request, session: Session = Depends(get_session)
) -> dict:
    base = request_base_url(request)
    workshop = Workshop(
        name=body.name,
        description_md=body.description_md,
        admin_token=_unique_admin_token(session),
        join_slug=_unique_join_slug(session),
        status="live",
    )
    session.add(workshop)
    session.flush()

    for position, milestone in enumerate(body.milestones):
        session.add(
            Milestone(
                workshop_id=workshop.id,
                position=position,
                title=milestone.title,
                content_md=milestone.content_md,
                minutes=milestone.minutes,
            )
        )

    record_action(
        session,
        workshop.id,
        "facilitator",
        "workshop.create",
        {"name": workshop.name, "milestone_count": len(body.milestones)},
    )
    log.info(
        "workshop.created",
        workshop_id=workshop.id,
        name=workshop.name,
        milestone_count=len(body.milestones),
    )

    payload = ok(
        {
            "workshop": {
                "id": workshop.id,
                "name": workshop.name,
                "description_md": workshop.description_md,
                "status": workshop.status,
                "paused": workshop.paused,
                "ai_enabled": workshop.ai_enabled,
                "admin_token": workshop.admin_token,
                "join_slug": workshop.join_slug,
                **_workshop_urls(base, workshop),
                "created_at": iso_z(workshop.created_at),
            }
        }
    )
    session.commit()  # visible before the response reaches the client
    return payload
