import pytest

from src.helmsman.config.settings import get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    from src.helmsman.config.settings import Settings

    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///data/helmsman.db"
    assert settings.port == 8001
    assert settings.resolved_log_level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///elsewhere.db")
    monkeypatch.setenv("PORT", "9999")
    import src.helmsman.config.settings as m

    m._settings = None
    settings = get_settings()
    assert settings.database_url == "sqlite:///elsewhere.db"
    assert settings.port == 9999


def test_log_level_tolerates_inline_comment(monkeypatch):
    monkeypatch.setenv("HELMSMAN_LOG_LEVEL", "debug   # verbose")
    import src.helmsman.config.settings as m

    m._settings = None
    assert get_settings().resolved_log_level == "DEBUG"


def test_invalid_log_level_falls_back_to_info(monkeypatch):
    monkeypatch.setenv("HELMSMAN_LOG_LEVEL", "chatty")
    import src.helmsman.config.settings as m

    m._settings = None
    assert get_settings().resolved_log_level == "INFO"


def test_base_url_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("HELMSMAN_BASE_URL", "https://helm.example.com/")
    import src.helmsman.config.settings as m

    m._settings = None
    assert get_settings().resolved_base_url == "https://helm.example.com"


def test_missing_admin_key_fails_startup_hard(monkeypatch):
    monkeypatch.setenv("HELMSMAN_ADMIN_KEY", "   ")
    import src.helmsman.config.settings as m

    m._settings = None
    from src.helmsman.api import create_app

    with pytest.raises(RuntimeError, match="HELMSMAN_ADMIN_KEY"):
        create_app()


def test_missing_openrouter_key_is_never_an_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    import src.helmsman.config.settings as m

    m._settings = None
    from src.helmsman.api import create_app

    app = create_app()
    assert app is not None
