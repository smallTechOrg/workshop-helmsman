"""Admin surface — header `X-Admin-Key` (see spec/api.md §Admin surface)."""

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.helmsman.api._common import iso_z, ok, request_base_url
from src.helmsman.db.models import HelpRequest, Participant, Workshop
from src.helmsman.db.session import get_session
from src.helmsman.security import require_admin_key
from src.helmsman.services.workshops import (  # re-exported: the shared request models
    MilestoneIn,
    WorkshopCreate,
    create_workshop as create_workshop_record,
    workshop_urls,
)

__all__ = ["router", "MilestoneIn", "WorkshopCreate"]

log = structlog.get_logger("helmsman")

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin_key)])


@router.get("/workshops")
def list_workshops(request: Request, session: Session = Depends(get_session)) -> dict:
    base = request_base_url(request)
    workshops = list(
        session.scalars(select(Workshop).order_by(Workshop.created_at.desc(), Workshop.id.desc()))
    )
    participant_counts = dict(
        session.execute(
            select(Participant.workshop_id, func.count(Participant.id)).group_by(
                Participant.workshop_id
            )
        ).all()
    )
    open_help_counts = dict(
        session.execute(
            select(HelpRequest.workshop_id, func.count(HelpRequest.id))
            .where(HelpRequest.status == "open")
            .group_by(HelpRequest.workshop_id)
        ).all()
    )
    rows = [
        {
            "id": w.id,
            "name": w.name,
            "status": w.status,
            "participant_count": participant_counts.get(w.id, 0),
            "open_help_count": open_help_counts.get(w.id, 0),
            "created_at": iso_z(w.created_at),
            "join_slug": w.join_slug,
            **workshop_urls(base, w),
            "created_via": w.created_via,
            "creator_email": w.creator_email,
        }
        for w in workshops
    ]
    return ok({"workshops": rows})


@router.post("/workshops")
def create_workshop(
    body: WorkshopCreate, request: Request, session: Session = Depends(get_session)
) -> dict:
    return create_workshop_record(
        session,
        body,
        created_via="admin",
        creator_email=None,
        base_url=request_base_url(request),
    )
