from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.helmsman.api._common import api_error, ok
from src.helmsman.db.session import get_session

router = APIRouter(prefix="/api")


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise api_error("internal_error", f"Database check failed: {type(exc).__name__}.", 500)
    return ok({"status": "ok", "db": "ok"})
