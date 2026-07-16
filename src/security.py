"""Token + slug generation and participant-cookie helpers."""

from __future__ import annotations

import secrets

from fastapi import Cookie, HTTPException, status
from sqlalchemy.orm import Session

from .models import Participant, Workshop

PARTICIPANT_COOKIE = "wid"


def generate_admin_token() -> str:
    """Facilitator dashboard URL token — high-entropy, URL-safe."""
    return secrets.token_urlsafe(32)


def generate_participant_slug() -> str:
    """Shorter, share-friendly URL slug for participants."""
    # 6 bytes → ~8 url-safe chars; 16M possible values, ample for a workshop.
    return secrets.token_urlsafe(6)


def find_workshop_by_admin_token(db: Session, token: str) -> Workshop | None:
    return db.query(Workshop).filter(Workshop.admin_token == token).first()


def find_workshop_by_slug(db: Session, slug: str) -> Workshop | None:
    return db.query(Workshop).filter(Workshop.participant_slug == slug).first()


def find_participant(db: Session, workshop_id: int, participant_id: int) -> Participant | None:
    return (
        db.query(Participant)
        .filter(Participant.id == participant_id, Participant.workshop_id == workshop_id)
        .first()
    )


def require_workshop_by_admin_token(db: Session, token: str) -> Workshop:
    w = find_workshop_by_admin_token(db, token)
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workshop not found")
    return w


def require_workshop_by_slug(db: Session, slug: str) -> Workshop:
    w = find_workshop_by_slug(db, slug)
    if w is None or w.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workshop not found")
    return w


def require_participant(
    workshop_id: int,
    wid: str | None = Cookie(default=None, alias=PARTICIPANT_COOKIE),
) -> int:
    """Resolve the participant ID from the `wid` cookie. 401 if missing/invalid."""
    if not wid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Join the workshop first")
    try:
        return int(wid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
