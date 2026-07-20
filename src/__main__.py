"""Boot the Workshop Helmsman server: `uv run python -m src` (from the repo root)."""

import uvicorn

from src.helmsman.api import create_app
from src.helmsman.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(),
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.resolved_log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
