"""Shared fixtures: isolated SQLite FILE per test (production driver), fresh app,
settings/engine/cache singletons reset around every test.

TEST_ADMIN_KEY is a fixture value owned by this suite (set via env for each test) —
never the operator's real HELMSMAN_ADMIN_KEY from .env.
"""

import pytest
from fastapi.testclient import TestClient

TEST_ADMIN_KEY = "test-admin-key-0123456789"


def _reset_singletons() -> None:
    import src.helmsman.config.settings as settings_module
    from src.helmsman.db.session import reset_db_state
    from src.helmsman.services.snapshots import clear_snapshot_cache

    settings_module._settings = None
    reset_db_state()
    clear_snapshot_cache()


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/helmsman-test.db")
    monkeypatch.setenv("HELMSMAN_ADMIN_KEY", TEST_ADMIN_KEY)
    monkeypatch.setenv("HELMSMAN_BASE_URL", "")
    monkeypatch.setenv("HELMSMAN_LOG_LEVEL", "WARNING")
    _reset_singletons()
    yield
    _reset_singletons()


@pytest.fixture
def make_app():
    """Build a fresh app over the CURRENT env (schema created once per DB file)."""

    def _make():
        from src.helmsman.api import create_app
        from src.helmsman.db.models import Base
        from src.helmsman.db.session import get_engine

        Base.metadata.create_all(get_engine())
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
