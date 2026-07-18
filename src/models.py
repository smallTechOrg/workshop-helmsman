"""SQLAlchemy ORM models for Workshop Helmsman."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Default form schema (Phase 4) ---

DEFAULT_FORM_SCHEMA = [
    {
        "key": "display_name",
        "type": "text",
        "label": "Display name",
        "placeholder": "e.g. Priya, anu from Delhi, J. Smith",
        "required": True,
    }
]


def _utcnow_naive() -> datetime:
    """SQLite stores naive datetimes; return naive UTC consistently."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FormTemplate(Base):
    """A reusable named form schema for workshop join pages.

    `fields_json` is a JSON-encoded list of field dicts:
        [{"key": "display_name", "type": "text"|"dropdown",
          "label": "...", "placeholder": "..." (text only),
          "required": bool, "options": ["A","B","C"] (dropdown only)}, ...]

    Saving a new Workshop records a *snapshot* of the schema on the workshop
    itself (workshop.form_schema_json), so editing a template later never
    mutates historical join-page data.
    """

    __tablename__ = "form_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    def fields(self) -> list[dict]:
        import json

        try:
            data = json.loads(self.fields_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []


# --- Phase 5: Agenda Templates ---

DEFAULT_AGENDA_TEMPLATES = [
    {
        "name": "4-Phase Workshop",
        "milestones": [
            {"title": "Setup", "description": "Environment ready, repo cloned"},
            {"title": "API Key", "description": "LLM provider key configured"},
            {"title": "First Build", "description": "End-to-end hello world shipped"},
            {"title": "Done", "description": "Wrap-up and Q&A"},
        ],
    },
    {
        "name": "6-Phase Sprint",
        "milestones": [
            {"title": "Kickoff", "description": "Goals and team alignment"},
            {"title": "Setup", "description": "Dev environment configured"},
            {"title": "Core Feature", "description": "Primary feature built"},
            {"title": "Testing", "description": "Tests written and passing"},
            {"title": "Polish", "description": "UI and edge cases addressed"},
            {"title": "Demo", "description": "Present working result"},
        ],
    },
    {
        "name": "3-Phase Quickstart",
        "milestones": [
            {"title": "Intro", "description": "Context and learning objectives"},
            {"title": "Build", "description": "Hands-on implementation"},
            {"title": "Review", "description": "Discussion and next steps"},
        ],
    },
]


class AgendaTemplate(Base):
    """A reusable named agenda template (list of milestone configs).

    Each milestone has: ``title`` (required), ``description`` (optional),
    and ``help_tip`` (optional — facilitator tip shown on tracker).

    A Workshop stores a *snapshot* of its milestones when created, so editing
    a template later never mutates existing workshops.
    """

    __tablename__ = "agenda_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    milestones_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    def milestones(self) -> list[dict]:
        import json

        try:
            data = json.loads(self.milestones_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []


class Workshop(Base):
    __tablename__ = "workshop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    admin_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    participant_slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    milestone_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-as-text
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Phase 4: form template link (nullable; SET NULL on delete).
    form_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("form_template.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Phase 4: snapshot of the form schema used at join time. Editing the
    # template later does NOT mutate this.
    form_schema_json: Mapped[str] = mapped_column(
        Text, nullable=False, default=lambda: __import__("json").dumps(DEFAULT_FORM_SCHEMA)
    )

    form_template: Mapped["FormTemplate | None"] = relationship("FormTemplate")
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="workshop",
        cascade="all, delete-orphan",
    )

    def is_expired(self) -> bool:
        # SQLite returns naive datetimes; normalize both sides to naive UTC.
        now = utcnow()
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        exp = self.expires_at
        if exp is not None and exp.tzinfo is not None:
            exp = exp.replace(tzinfo=None)
        return now > exp

    def milestones(self) -> list[dict]:
        import json

        try:
            return json.loads(self.milestone_config)
        except Exception:
            return []

    def form_schema(self) -> list[dict]:
        """Return this workshop's form schema snapshot (list of field dicts).

        Falls back to DEFAULT_FORM_SCHEMA if the stored value is missing or
        malformed, which keeps older workshops usable after the Phase 4 schema
        upgrade.
        """
        import json

        raw = self.form_schema_json
        if not raw:
            return list(DEFAULT_FORM_SCHEMA)
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return list(DEFAULT_FORM_SCHEMA)


class Participant(Base):
    __tablename__ = "participant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshop.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    # Phase 4: captured form answers as a JSON dict {key: value}.
    # Nullable so older phase-1 participants survive the schema upgrade.
    answers_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    workshop: Mapped["Workshop"] = relationship(back_populates="participants")
    completions: Mapped[list["MilestoneCompletion"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
    )
    help_requests: Mapped[list["HelpRequest"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
    )

    def answers(self) -> dict:
        """Return participant's captured answers as a plain dict (empty if none)."""
        import json

        if not self.answers_json:
            return {}
        try:
            data = json.loads(self.answers_json)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


class MilestoneCompletion(Base):
    __tablename__ = "milestone_completion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), index=True
    )
    milestone_id: Mapped[str] = mapped_column(String(64), nullable=False)
    milestone_title: Mapped[str] = mapped_column(String(200), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    participant: Mapped["Participant"] = relationship(back_populates="completions")


class HelpRequest(Base):
    __tablename__ = "help_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    participant: Mapped["Participant"] = relationship(back_populates="help_requests")
