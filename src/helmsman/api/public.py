"""Public surface — keyless self-service creation (see spec/api.md §Phase 6).

No auth dependency: an `X-Admin-Key` header is neither required nor rejected.
Creation itself is the shared service in services/workshops.py — this route only
adds the required `creator_email` and `created_via="public"`.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.helmsman.api._common import request_base_url
from src.helmsman.db.session import get_session
from src.helmsman.services.workshops import (
    PublicWorkshopCreate,
    create_workshop as create_workshop_record,
)

router = APIRouter(prefix="/api/public")


@router.post("/workshops")
def create_public_workshop(
    body: PublicWorkshopCreate, request: Request, session: Session = Depends(get_session)
) -> dict:
    return create_workshop_record(
        session,
        body,
        created_via="public",
        creator_email=body.creator_email,
        base_url=request_base_url(request),
    )
