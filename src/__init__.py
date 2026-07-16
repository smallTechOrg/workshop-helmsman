"""Workshop Helmsman — FastAPI app entrypoint.

Run with:  venv/bin/python -m src
"""

from .main import app  # noqa: F401  (re-export)

__all__ = ["app"]
