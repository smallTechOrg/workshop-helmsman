"""Undo — apply the inverse of an undoable FacilitatorAction within the 30 s window."""

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from src.helmsman.api._common import api_error, as_utc, utcnow
from src.helmsman.db.models import Broadcast, FacilitatorAction, MilestoneCompletion, Workshop
from src.helmsman.services.audit import record_action
from src.helmsman.services.snapshots import bump_state_version

UNDO_WINDOW_SECONDS = 30


def apply_undo(session: Session, workshop: Workshop, action_id: int) -> int:
    """Applies the inverse of the given action in this transaction; returns new state_version.
    Raises api_error(not_found) / api_error(undo_expired) as appropriate."""
    action = session.get(FacilitatorAction, action_id)
    if action is None or action.workshop_id != workshop.id:
        raise api_error("not_found", "No such action in this workshop.", 404)

    if action.undone_at is not None:
        raise api_error("undo_expired", "This action was already undone.", 409)

    now = utcnow()
    if (now - as_utc(action.created_at)) > timedelta(seconds=UNDO_WINDOW_SECONDS):
        raise api_error("undo_expired", "The 30-second undo window has passed.", 409)

    undo_data = json.loads(action.undo_data_json) if action.undo_data_json else {}

    if action.action == "broadcast.send":
        sent_id = json.loads(action.detail_json).get("broadcast_id")
        if sent_id is not None:
            created = session.get(Broadcast, sent_id)
            if created is not None:
                session.delete(created)
        previous_id = undo_data.get("previous_broadcast_id")
        if previous_id is not None:
            previous = session.get(Broadcast, previous_id)
            if previous is not None:
                previous.cleared_at = None
    elif action.action in ("workshop.pause", "workshop.resume"):
        workshop.paused = undo_data.get("previous_paused", False)
    elif action.action in ("milestone.advance_all", "milestone.advance_selected"):
        completion_ids = undo_data.get("completion_ids", [])
        if completion_ids:
            for completion in session.query(MilestoneCompletion).filter(
                MilestoneCompletion.id.in_(completion_ids)
            ):
                session.delete(completion)
    else:
        raise api_error("not_found", "This action cannot be undone.", 404)

    action.undone_at = now
    version = bump_state_version(workshop)
    record_action(
        session,
        workshop.id,
        "facilitator",
        "undo.apply",
        {"original_action_id": action.id, "original_action": action.action},
    )
    session.flush()
    return version
