"""SQLAlchemy ORM models for Workshop Helmsman."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class Participant(Base):
    __tablename__ = "participant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshop.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    workshop: Mapped["Workshop"] = relationship(back_populates="participants")
    completions: Mapped[list["MilestoneCompletion"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
    )
    help_requests: Mapped[list["HelpRequest"]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
    )


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
