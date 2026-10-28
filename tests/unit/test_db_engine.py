"""Engine kwargs per dialect, uvicorn proxy flags / $PORT, structlog severity key."""

import json
import os

import pytest

import src.helmsman.config.settings as settings_mod
from src.helmsman.db import session as session_mod

PG_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    session_mod.reset_db_state()
    settings_mod._settings = None
    yield
    session_mod.reset_db_state()
    settings_mod._settings = None


@pytest.mark.skipif(not PG_URL.startswith("postgresql"), reason="needs TEST_DATABASE_URL (PostgreSQL)")
def test_postgres_engine_pool_kwargs(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("HELMSMAN_DB_POOL_SIZE", "4")
    monkeypatch.setenv("HELMSMAN_DB_MAX_OVERFLOW", "1")
    engine = session_mod.get_engine()
    pool = engine.pool
    assert engine.dialect.driver == "psycopg"
    assert pool.size() == 4
    assert pool._max_overflow == 1
    assert pool._timeout == 10
    assert pool._recycle == 1800
    assert pool._pre_ping is True
    with engine.connect() as conn:
        assert conn.exec_driver_sql("select 1").scalar() == 1


@pytest.mark.skipif(not PG_URL.startswith("postgresql"), reason="needs TEST_DATABASE_URL (PostgreSQL)")
def test_bare_postgres_scheme_connects(monkeypatch):
    bare = PG_URL.replace("postgresql+psycopg://", "postgres://")
    monkeypatch.setenv("DATABASE_URL", bare)
    engine = session_mod.get_engine()
    assert engine.dialect.driver == "psycopg"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("select 1").scalar() == 1


def test_sqlite_engine_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/sub/x.db")
    engine = session_mod.get_engine()
    assert engine.dialect.name == "sqlite"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"


def test_main_passes_proxy_flags_and_port(monkeypatch):
    import src.__main__ as entry

    captured = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: captured.update(kw))
    monkeypatch.setattr(entry, "create_app", lambda: object())
    monkeypatch.setenv("PORT", "8080")
    entry.main()
    assert captured["proxy_headers"] is True
    assert captured["forwarded_allow_ips"] == "*"
    assert captured["port"] == 8080
    assert captured["host"] == "0.0.0.0"


def test_main_defaults_to_8001(monkeypatch):
    import src.__main__ as entry

    captured = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: captured.update(kw))
    monkeypatch.setattr(entry, "create_app", lambda: object())
    monkeypatch.delenv("PORT", raising=False)
    settings_mod._settings = settings_mod.Settings(_env_file=None)
    entry.main()
    assert captured["port"] == 8001


@pytest.mark.parametrize(
    ("method", "expected"),
    [("info", "INFO"), ("warning", "WARNING"), ("error", "ERROR"), ("debug", "DEBUG"),
     ("critical", "CRITICAL"), ("exception", "ERROR")],
)
def test_logging_severity_key(capsys, method, expected):
    import structlog

    from src.helmsman.observability.logging import configure_logging

    configure_logging("DEBUG")
    getattr(structlog.get_logger("t"), method)("hello")
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["severity"] == expected
    assert line["event"] == "hello"
