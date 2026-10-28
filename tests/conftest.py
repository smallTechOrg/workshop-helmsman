"""Shared fixtures: every test runs against a real PostgreSQL database (harness Rule 5).

`TEST_DATABASE_URL` is REQUIRED (see README "Postgres test setup") and its database
name must end in `_test` — the suite drops/recreates schema `public` there. There is
no SQLite fallback. Schema is built once per session by `alembic upgrade head`; every
test starts from empty tables (TRUNCATE ... RESTART IDENTITY CASCADE).

TEST_ADMIN_KEY is a fixture value owned by this suite (set via env for each test) —
never the operator's real WORKSHOP0_ADMIN_KEY from .env.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_ADMIN_KEY = "test-admin-key-0123456789"


def _require_test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is not set. The suite runs on PostgreSQL only (no SQLite "
            "fallback). See README.md 'Postgres test setup': createdb workshop0_test && "
            'export TEST_DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/workshop0_test"',
            returncode=4,
        )
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql"):
        pytest.exit(
            f"TEST_DATABASE_URL must be a PostgreSQL URL (got driver {parsed.drivername!r}). "
            "See README.md 'Postgres test setup'.",
            returncode=4,
        )
    if not (parsed.database or "").endswith("_test"):
        pytest.exit(
            f"Refusing to run: TEST_DATABASE_URL database {parsed.database!r} does not end "
            "in '_test' (the suite drops schema public). See README.md 'Postgres test setup'.",
            returncode=4,
        )
    return url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _require_test_database_url()


def _reset_singletons() -> None:
    import src.workshop0.config.settings as settings_module
    from src.workshop0.db.session import reset_db_state

    settings_module._settings = None
    reset_db_state()


def alembic_upgrade(url: str, revision: str = "head") -> None:
    """Run alembic against `url` (env.py reads DATABASE_URL via settings)."""
    _alembic_run("upgrade", url, revision)


def alembic_downgrade(url: str, revision: str = "base") -> None:
    _alembic_run("downgrade", url, revision)


def _alembic_run(action: str, url: str, revision: str) -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    import src.workshop0.config.settings as settings_module

    root = Path(__file__).resolve().parents[1]
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    settings_module._settings = None
    try:
        getattr(command, action)(Config(str(root / "alembic.ini")), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        settings_module._settings = None


@pytest.fixture(scope="session", autouse=True)
def _schema(test_database_url):
    """Drop + recreate schema public, then `alembic upgrade head` — once per session."""
    engine = create_engine(test_database_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    alembic_upgrade(test_database_url)
    yield


@pytest.fixture(scope="session")
def _truncate_engine(test_database_url):
    engine = create_engine(test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, test_database_url, _schema, _truncate_engine):
    from src.workshop0.db.models import Base

    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    with _truncate_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("WORKSHOP0_ADMIN_KEY", TEST_ADMIN_KEY)
    monkeypatch.setenv("WORKSHOP0_BASE_URL", "")
    monkeypatch.setenv("WORKSHOP0_LOG_LEVEL", "WARNING")
    _reset_singletons()
    yield
    _reset_singletons()


@pytest.fixture
def scratch_database(test_database_url):
    """Factory: create an empty `<name>_mig_<uuid>` database on the same server; dropped at teardown."""
    created: list[str] = []
    base = make_url(test_database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")

    def _create() -> str:
        name = f"{base.database}_mig_{uuid.uuid4().hex[:8]}"
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        created.append(name)
        return base.set(database=name).render_as_string(hide_password=False)

    yield _create
    import src.workshop0.config.settings as settings_module
    from src.workshop0.db.session import reset_db_state

    settings_module._settings = None
    reset_db_state()
    with admin.connect() as connection:
        for name in created:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def make_app():
    """Build a fresh app over the CURRENT env (schema comes from alembic, once per session)."""

    def _make():
        from src.workshop0.api import create_app
        return create_app()

    return _make


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def make_client(app):
    """Fresh cookie jars over the same app — one per simulated browser/device."""

    def _make():
        return TestClient(app)

    return _make


@pytest.fixture
def admin_headers():
    return {"X-Admin-Key": TEST_ADMIN_KEY}


WORKSHOP_BODY = {
    "name": "LangGraph Lab — July",
    "description_md": "Welcome! Bring a laptop.",
    "milestones": [
        {"title": "Set up your environment", "content_md": "```bash\nuv sync\n```", "minutes": 30},
        {"title": "Configure the API key", "content_md": "Put it in `.env`.", "minutes": 15},
        {"title": "Run the first graph", "content_md": "Now run it.", "minutes": None},
    ],
}


@pytest.fixture
def workshop(client, admin_headers):
    response = client.post("/api/admin/workshops", json=WORKSHOP_BODY, headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["workshop"]


@pytest.fixture
def join_participant():
    def _join(client_, join_slug: str, name: str) -> dict:
        response = client_.post(f"/api/join/{join_slug}", json={"name": name})
        assert response.status_code == 200, response.text
        return response.json()["data"]

    return _join
