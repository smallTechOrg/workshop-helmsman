"""Response envelope + serialization helpers shared by every router."""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request


def ok(data: Any) -> dict:
    return {"data": data, "error": None}


def api_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """SQLite round-trips tz-aware datetimes as naive UTC — normalize either way."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    """ISO 8601 UTC with Z, seconds precision — '2026-07-20T14:03:22Z'."""
    return as_utc(dt).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def request_base_url(request: Request) -> str:
    from src.helmsman.config.settings import get_settings

    configured = get_settings().resolved_base_url
    if configured:
        return configured
    return str(request.base_url).rstrip("/")
