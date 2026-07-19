"""SQLAlchemy ORM models for Workshop Helmsman (World-Class UX)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import json

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MilestoneCategory(str, Enum):
    SETUP = "setup"
    CORE_LEARNING = "learning"
    HANDS_ON = "hands_on"
    BREAK = "break"
    ASSESSMENT = "assessment"
    WRAP_UP = "wrap_up"


class FormFieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    DROPDOWN = "dropdown"
    MULTI_SELECT = "multi_select"
    FILE = "file"
    URL = "url"
    TEXTAREA = "textarea"


# Default milestone configuration for new workshops
DEFAULT_MILESTONE_CONFIG = [
    {
        "id": "m0",
        "title": "Setup",
        "description": "Environment ready, repo cloned",
        "duration_min": 30,
        "category": MilestoneCategory.SETUP.value,
        "help_tip": "Verify everyone can run the starter",
    },
    {
        "id": "m1",
        "title": "API Key",
        "description": "LLM provider key configured",
        "duration_min": 15,
        "category": MilestoneCategory.SETUP.value,
        "help_tip": "Use env var, not hardcoded",
    },
    {
        "id": "m2",
        "title": "First Build",
        "description": "End-to-end hello world shipped",
        "duration_min": 60,
        "category": MilestoneCategory.HANDS_ON.value,
        "help_tip": "Run the test suite after",
    },
    {
        "id": "m3",
        "title": "Done",
        "description": "Wrap-up and Q&A",
        "duration_min": 15,
        "category": MilestoneCategory.WRAP_UP.value,
        "help_tip": "Capture feedback before they leave",
    },
]

# Default form schema for new workshops
DEFAULT_FORM_SCHEMA = [
    {"key": "display_name", "type": "text", "label": "Full Name", "required": True},
    {"key": "email", "type": "email", "label": "Email Address", "required": False},
    {"key": "role", "type": "dropdown", "label": "Role", "required": False, "options": ["Student", "Developer", "Designer", "Manager", "Other"]},
    {"key": "company", "type": "text", "label": "Company", "required": False},
    {"key": "skill_level", "type": "dropdown", "label": "Skill Level", "required": False, "options": ["Beginner", "Intermediate", "Advanced"]},
    {"key": "team", "type": "text", "label": "Team", "required": False},
]


# --- Phase 5: Agenda Templates ---

DEFAULT_AGENDA_TEMPLATES = [
    {
        "name": "Web Development Workshop",
        "milestones": [
            {
                "title": "Setup",
                "description": "Install Node.js, clone repo, install dependencies",
                "duration_min": 30,
                "category": MilestoneCategory.SETUP.value,
                "help_tip": "Use nvm for Node version management",
            },
            {
                "title": "Frontend Basics",
                "description": "Learn React components and state management",
                "duration_min": 60,
                "category": MilestoneCategory.CORE_LEARNING.value,
                "help_tip": "Start with functional components",
            },
            {
                "title": "Build a Todo App",
                "description": "Apply learning by building a todo application",
                "duration_min": 90,
                "category": MilestoneCategory.HANDS_ON.value,
                "help_tip": "Use local storage for persistence",
            },
            {
                "title": "Break",
                "description": "Coffee and networking",
                "duration_min": 15,
                "category": MilestoneCategory.BREAK.value,
                "help_tip": "Stay hydrated!",
            },
            {
                "title": "Testing & Debugging",
                "description": "Write unit tests and debug common issues",
                "duration_min": 45,
                "category": MilestoneCategory.ASSESSMENT.value,
                "help_tip": "Use Jest and React Testing Library",
            },
            {
                "title": "Deployment",
                "description": "Deploy the app to Vercel or Netlify",
                "duration_min": 30,
                "category": MilestoneCategory.WRAP_UP.value,
                "help_tip": "Set up custom domain and environment variables",
            },
        ],
    },
    {
        "name": "Data Science Bootcamp",
        "milestones": [
            {
                "title": "Environment Setup",
                "description": "Install Python, Jupyter, and essential libraries",
                "duration_min": 30,
                "category": MilestoneCategory.SETUP.value,
                "help_tip": "Use conda or virtualenv",
            },
            {
                "title": "Data Wrangling",
                "description": "Clean and explore datasets with Pandas",
                "duration_min": 60,
                "category": MilestoneCategory.CORE_LEARNING.value,
                "help_tip": "Learn pandas DataFrame operations",
            },
            {
                "title": "Machine Learning Model",
                "description": "Build and evaluate a predictive model",
                "duration_min": 90,
                "category": MilestoneCategory.HANDS_ON.value,
                "help_tip": "Start with linear regression",
            },
            {
                "title": "Break",
                "description": "Snack and stretch",
                "duration_min": 10,
                "category": MilestoneCategory.BREAK.value,
                "help_tip": "Take a short walk",
            },
            {
                "title": "Model Evaluation",
                "description": "Assess model performance and tune hyperparameters",
                "duration_min": 45,
                "category": MilestoneCategory.ASSESSMENT.value,
                "help_tip": "Use cross-validation",
            },
            {
                "title": "Presentation",
                "description": "Present findings and get feedback",
                "duration_min": 30,
                "category": MilestoneCategory.WRAP_UP.value,
                "help_tip": "Use slides and tell a story",
            },
        ],
    },
]


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
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    admin_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    participant_slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # New fields for world-class UX
    difficulty_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    milestone_config_json: Mapped[str] = mapped_column(Text, nullable=False, default=json.dumps(DEFAULT_MILESTONE_CONFIG))
    form_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default=json.dumps(DEFAULT_FORM_SCHEMA))
    kb_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kb_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Existing fields that were missing
    broadcast_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    milestone_order_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    form_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("form_template.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    participants: Mapped[list["Participant"]] = relationship(back_populates="workshop", cascade="all, delete-orphan")

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        now = utcnow()
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        exp = self.expires_at
        if exp.tzinfo is not None:
            exp = exp.replace(tzinfo=None)
        return now > exp

    def milestones(self) -> list[dict]:
        try:
            data = json.loads(self.milestone_config_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def ordered_milestones(self) -> list[dict]:
        # For simplicity, we return milestones in the order they are stored.
        # In the future, we might want to store an explicit order.
        return self.milestones()

    def form_schema(self) -> list[dict]:
        try:
            data = json.loads(self.form_schema_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []


class Participant(Base):
    __tablename__ = "participant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workshop_id: Mapped[int] = mapped_column(
        ForeignKey("workshop.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    answers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workshop: Mapped["Workshop"] = relationship(back_populates="participants")
    completions: Mapped[list["MilestoneCompletion"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    help_requests: Mapped[list["HelpRequest"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )

    def answers(self) -> dict:
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
    status: Mapped[str] = mapped_column(
        SQLEnum("open", "on_hold", "resolved", name="help_status"),
        default="open",
        nullable=False,
    )

    participant: Mapped["Participant"] = relationship(back_populates="help_requests")


# Helper constants and functions
HELP_STATUSES = ("open", "on_hold", "resolved")