"""Engine + session management. SQLite runs WAL/NORMAL/busy_timeout/foreign_keys pragmas
per connection; any DATABASE_URL (e.g. PostgreSQL) works unchanged."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None

_SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    for pragma in _SQLITE_PRAGMAS:
        cursor.execute(pragma)
    cursor.close()


def _ensure_sqlite_parent_dir(url: str) -> None:
    path = url.split("///", 1)[-1]
    if not path or path == ":memory:":
        return
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        from src.helmsman.config.settings import get_settings

        url = get_settings().database_url
        connect_args: dict = {}
        if url.startswith("sqlite"):
            _ensure_sqlite_parent_dir(url)
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _apply_sqlite_pragmas)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency — one request, one transaction.

    Mutating handlers MUST call session.commit() before returning their response:
    FastAPI runs this teardown only AFTER the response is sent, and clients act on
    mutation responses immediately (poll right after a mutation — spec guarantee).
    The teardown commit is the safety net for read-path writes (last_seen touches).
    """
    with _get_session_factory()() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@contextmanager
def create_db_session() -> Generator[Session, None, None]:
    """Standalone session for scripts and tests."""
    with _get_session_factory()() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def reset_db_state() -> None:
    """Dispose the engine and clear singletons (tests / restart simulation)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
