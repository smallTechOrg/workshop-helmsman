"""Application settings — exact env var names per spec/architecture.md §Environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "sqlite:///data/helmsman.db"
DEFAULT_PORT = 8001
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _strip_inline_comment(value: str) -> str:
    return value.split("#", 1)[0].strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    port: int = Field(default=DEFAULT_PORT)
    helmsman_admin_key: str = Field(default="")
    helmsman_base_url: str = Field(default="")
    helmsman_log_level: str = Field(default="INFO")
    openrouter_api_key: str = Field(default="")
    helmsman_ai_model: str = Field(default="anthropic/claude-sonnet-4-6")
    helmsman_ai_confidence: float = Field(default=0.75)

    @property
    def resolved_admin_key(self) -> str:
        return self.helmsman_admin_key.strip()

    @property
    def resolved_base_url(self) -> str:
        return _strip_inline_comment(self.helmsman_base_url).rstrip("/")

    @property
    def resolved_log_level(self) -> str:
        level = _strip_inline_comment(self.helmsman_log_level).upper()
        return level if level in _LOG_LEVELS else "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
