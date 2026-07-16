"""SQLAlchemy engine + session bootstrap for Workshop Helmsman."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _default_url() -> str:
    # data/ lives next to the repo root when running `python -m src`
    here = Path(__file__).resolve().parent.parent
    data_dir = here / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "helmsman.db"
    return f"sqlite:///{db_path}"


DATABASE_URL = os.environ.get("DATABASE_URL", _default_url())


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables. Idempotent — safe to call on every boot."""
    # Imported lazily to avoid circular import (models import Base from here).
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Session:
    """Context-managed session that commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Session:
    """FastAPI dependency — yields a session, closes it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
