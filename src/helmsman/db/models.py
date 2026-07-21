"""All SQLAlchemy models — the FULL v0.2 schema per spec/data-model.md.

Later-phase tables/columns exist from Phase 1 so no mid-season migrate-and-backfill
is ever needed. Portable types only (Integer/String/Text/Boolean/DateTime/Numeric;
JSON stored as Text) — PostgreSQL-ready via DATABASE_URL.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Workshop(Base):
    __tablename__ = "workshop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    admin_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    join_slug: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="live", index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    join_form_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    stuck_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    cloned_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("workshop.id"), nullable=True, index=True
    )
    agenda_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("agenda_template.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Milestone(Base):
    __tablename__ = "milestone"
    __table_args__ = (Index("ix_milestone_workshop_id_position", "workshop_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional per-milestone completion input (JSON: {type,label,options?}).
    # Null ⇒ no input required; see services/milestone_input.py.
    input_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Participant(Base):
    __tablename__ = "participant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    token: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MilestoneCompletion(Base):
    __tablename__ = "milestone_completion"
    __table_args__ = (
        UniqueConstraint("participant_id", "milestone_id", name="uq_completion_participant_milestone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestone.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="participant")
    # The value the participant submitted, when the milestone required an input.
    input_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class HelpRequest(Base):
    __tablename__ = "help_request"
    __table_args__ = (
        Index("ix_help_request_workshop_status_created", "workshop_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_id: Mapped[int | None] = mapped_column(
        ForeignKey("milestone.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    # Who last marked it resolved: "participant" | "facilitator" (null while open).
    resolved_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class HelpAnswer(Base):
    __tablename__ = "help_answer"
    __table_args__ = (
        Index("ix_help_answer_request_created", "help_request_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    help_request_id: Mapped[int] = mapped_column(
        ForeignKey("help_request.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_md: Mapped[str] = mapped_column(Text, nullable=False)
    draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Broadcast(Base):
    __tablename__ = "broadcast"
    __table_args__ = (Index("ix_broadcast_workshop_cleared", "workshop_id", "cleared_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), nullable=False
    )
    message_md: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FacilitatorAction(Base):
    __tablename__ = "facilitator_action"
    __table_args__ = (
        Index("ix_facilitator_action_workshop_created", "workshop_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int | None] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    undo_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )


class AgendaTemplate(Base):
    __tablename__ = "agenda_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class AgendaTemplateMilestone(Base):
    __tablename__ = "agenda_template_milestone"
    __table_args__ = (
        Index("ix_agenda_template_milestone_template_position", "template_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("agenda_template.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class JoinFormTemplate(Base):
    __tablename__ = "join_form_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class AiUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_workshop_created", "workshop_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), nullable=False
    )
    help_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("help_request.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
