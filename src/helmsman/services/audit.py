"""Audit-trail writes into facilitator_action (audit + undo + AI log share one table)."""

import json

from sqlalchemy.orm import Session

from src.helmsman.db.models import FacilitatorAction


def record_action(
    session: Session,
    workshop_id: int | None,
    actor: str,
    action: str,
    detail: dict,
) -> FacilitatorAction:
    row = FacilitatorAction(
        workshop_id=workshop_id,
        actor=actor,
        action=action,
        detail_json=json.dumps(detail, ensure_ascii=False),
    )
    session.add(row)
    return row
