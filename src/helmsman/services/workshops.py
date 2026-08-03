"""Workshop creation — the SINGLE implementation behind both the admin-key route
(`POST /api/admin/workshops`) and the keyless public route (`POST /api/public/workshops`).

The two routes differ only in their auth dependency, `created_via` and `creator_email`;
every validation rule and every side effect lives here so they cannot drift.
"""

import json
import re

import structlog
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.helmsman.api._common import api_error, iso_z, ok
from src.helmsman.db.models import Milestone, Workshop
from src.helmsman.security import generate_admin_token, generate_join_slug
from src.helmsman.services.audit import record_action
from src.helmsman.services.join_form import JoinFormError, validate_field_defs
from src.helmsman.services.milestone_input import (
    MilestoneInputError,
    validate_input_config,
)

log = structlog.get_logger("helmsman")

NAME_MAX = 120
DESCRIPTION_MAX = 10_000
MILESTONES_MAX = 50
MILESTONE_TITLE_MAX = 200
MILESTONE_CONTENT_MAX = 20_000
MILESTONE_MINUTES_MIN = 1
MILESTONE_MINUTES_MAX = 480

CREATOR_EMAIL_MIN = 3
CREATOR_EMAIL_MAX = 254
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_ERROR = "enter a valid email address"


def normalize_creator_email(value: str | None) -> str:
    """Trim + lower-case, then validate per spec/api.md §Phase 6. Raises ValueError."""
    if value is None:
        raise ValueError(EMAIL_ERROR)
    email = value.strip().lower()
    if not (CREATOR_EMAIL_MIN <= len(email) <= CREATOR_EMAIL_MAX):
        raise ValueError(EMAIL_ERROR)
    if not EMAIL_RE.match(email):
        raise ValueError(EMAIL_ERROR)
    return email


def mask_email(email: str) -> str:
    """`asha@example.com` → `as***@example.com` — logs never carry the full address."""
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}" if domain else f"{local[:2]}***"


class MilestoneIn(BaseModel):
    title: str
    content_md: str = ""
    minutes: int | None = None
    input_config: dict | None = None

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
    """The workshop composition body — identical for admin and public creation."""

    name: str
    description_md: str = ""
    milestones: list[MilestoneIn] = Field(min_length=1, max_length=MILESTONES_MAX)
    join_form: list[dict] = Field(default_factory=list)

    @field_validator("join_form")
    @classmethod
    def _check_join_form(cls, value: list[dict]) -> list[dict]:
        try:
            return validate_field_defs(value)
        except JoinFormError as exc:
            raise ValueError(str(exc)) from exc

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


class PublicWorkshopCreate(WorkshopCreate):
    """Public creation body — the admin body plus the required creator email."""

    # validate_default so an OMITTED email fails the same way a blank one does.
    creator_email: str | None = Field(default=None, validate_default=True)

    @field_validator("creator_email")
    @classmethod
    def _check_creator_email(cls, value: str | None) -> str:
        return normalize_creator_email(value)


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


def workshop_urls(base: str, workshop: Workshop) -> dict:
    return {
        "join_url": f"{base}/j/{workshop.join_slug}",
        "facilitator_url": f"{base}/f/{workshop.admin_token}",
    }


def serialize_created_workshop(workshop: Workshop, base: str) -> dict:
    """The full-workshop create payload — identical for both routes (spec/api.md)."""
    return {
        "id": workshop.id,
        "name": workshop.name,
        "description_md": workshop.description_md,
        "status": workshop.status,
        "paused": workshop.paused,
        "ai_enabled": workshop.ai_enabled,
        "admin_token": workshop.admin_token,
        "join_slug": workshop.join_slug,
        **workshop_urls(base, workshop),
        "created_via": workshop.created_via,
        "creator_email": workshop.creator_email,
        "created_at": iso_z(workshop.created_at),
    }


def create_workshop(
    session: Session,
    spec: WorkshopCreate,
    *,
    created_via: str = "admin",
    creator_email: str | None = None,
    base_url: str,
) -> dict:
    """Create the workshop + its milestones + the audit row, and return the API envelope.

    Commits the session so the row is visible before the response reaches the client.
    """
    workshop = Workshop(
        name=spec.name,
        description_md=spec.description_md,
        admin_token=_unique_admin_token(session),
        join_slug=_unique_join_slug(session),
        status="live",
        created_via=created_via,
        creator_email=creator_email,
    )
    workshop.join_form_json = json.dumps(spec.join_form)
    session.add(workshop)
    session.flush()

    for position, milestone in enumerate(spec.milestones):
        try:
            input_config = validate_input_config(milestone.input_config)
        except MilestoneInputError as exc:
            raise api_error("validation_error", str(exc), 422)
        session.add(
            Milestone(
                workshop_id=workshop.id,
                position=position,
                title=milestone.title,
                content_md=milestone.content_md,
                minutes=milestone.minutes,
                input_config_json=json.dumps(input_config) if input_config else None,
            )
        )

    detail = {"name": workshop.name, "milestone_count": len(spec.milestones)}
    if created_via != "admin":
        detail["created_via"] = created_via
    record_action(session, workshop.id, "facilitator", "workshop.create", detail)
    log.info(
        "workshop.created",
        workshop_id=workshop.id,
        name=workshop.name,
        milestone_count=len(spec.milestones),
        created_via=created_via,
        creator_email=mask_email(creator_email) if creator_email else None,
    )

    payload = ok({"workshop": serialize_created_workshop(workshop, base_url)})
    session.commit()
    return payload
