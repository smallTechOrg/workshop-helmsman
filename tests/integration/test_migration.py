"""The 0001_initial migration creates the FULL v0.2 schema on a fresh DB and
`alembic current` reports a non-blank revision."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "workshop",
    "milestone",
    "participant",
    "milestone_completion",
    "help_request",
    "help_answer",
    "broadcast",
    "facilitator_action",
    "agenda_template",
    "agenda_template_milestone",
    "join_form_template",
    "ai_usage",
    "alembic_version",
}


def _alembic_config() -> Config:
    return Config(str(REPO_ROOT / "alembic.ini"))


def test_upgrade_head_creates_full_schema_and_stamps_revision(monkeypatch, tmp_path):
    db_path = tmp_path / "migration-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import src.helmsman.config.settings as settings_module

    settings_module._settings = None

    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == EXPECTED_TABLES

        # help_corpus (Phase-4 FTS5) is NOT created by 0001_initial
        assert "help_corpus" not in inspector.get_table_names()

        # unique constraints that make the API idempotent/secure
        workshop_indexes = {
            idx["name"]: idx for idx in inspector.get_indexes("workshop")
        }
        assert workshop_indexes["ix_workshop_admin_token"]["unique"]
        assert workshop_indexes["ix_workshop_join_slug"]["unique"]
        completion_uniques = inspector.get_unique_constraints("milestone_completion")
        assert any(
            set(uc["column_names"]) == {"participant_id", "milestone_id"}
            for uc in completion_uniques
        )

        # the stamped revision matches the script head (what `alembic current` prints)
        with engine.connect() as connection:
            from sqlalchemy import text

            stamped = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        head = ScriptDirectory.from_config(config).get_current_head()
        assert stamped == head
        assert stamped  # non-blank
    finally:
        engine.dispose()


def test_migrated_schema_serves_the_api(monkeypatch, tmp_path):
    """App over an alembic-migrated DB (not metadata.create_all) serves the core loop."""
    db_path = tmp_path / "migrated-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import src.helmsman.config.settings as settings_module
    from src.helmsman.db.session import reset_db_state

    settings_module._settings = None
    reset_db_state()

    command.upgrade(_alembic_config(), "head")

    from fastapi.testclient import TestClient

    from src.helmsman.api import create_app
    from tests.conftest import TEST_ADMIN_KEY, WORKSHOP_BODY

    client = TestClient(create_app())
    workshop = client.post(
        "/api/admin/workshops", json=WORKSHOP_BODY, headers={"X-Admin-Key": TEST_ADMIN_KEY}
    ).json()["data"]["workshop"]
    joined = client.post(
        f"/api/join/{workshop['join_slug']}", json={"name": "Priya"}
    ).json()["data"]
    state = client.get(f"/api/p/{joined['participant_token']}/state").json()["data"]
    assert state["me"]["name"] == "Priya"
    assert state["me"]["total_count"] == 3
