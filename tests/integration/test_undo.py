"""Undo window enforcement: expiry after 30s, unknown action, double-undo."""

from datetime import timedelta

from sqlalchemy import update


def _backdate_action(action_id: int, seconds: int) -> None:
    from src.helmsman.api._common import utcnow
    from src.helmsman.db.models import FacilitatorAction
    from src.helmsman.db.session import create_db_session

    with create_db_session() as session:
        session.execute(
            update(FacilitatorAction)
            .where(FacilitatorAction.id == action_id)
            .values(created_at=utcnow() - timedelta(seconds=seconds))
        )


def test_undo_after_window_expires(client, workshop):
    admin_token = workshop["admin_token"]
    sent = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "Hello"}
    ).json()["data"]

    _backdate_action(sent["undoable_action_id"], seconds=31)

    result = client.post(f"/api/f/{admin_token}/undo/{sent['undoable_action_id']}", json={})
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "undo_expired"


def test_undo_unknown_action_id_404(client, workshop):
    admin_token = workshop["admin_token"]
    result = client.post(f"/api/f/{admin_token}/undo/999999", json={})
    assert result.status_code == 404
    assert result.json()["detail"]["code"] == "not_found"


def test_double_undo_returns_expired(client, workshop):
    admin_token = workshop["admin_token"]
    sent = client.post(
        f"/api/f/{admin_token}/broadcast", json={"message_md": "Hello"}
    ).json()["data"]

    first = client.post(f"/api/f/{admin_token}/undo/{sent['undoable_action_id']}", json={})
    assert first.status_code == 200, first.text

    second = client.post(f"/api/f/{admin_token}/undo/{sent['undoable_action_id']}", json={})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "undo_expired"


def test_undo_action_from_another_workshop_is_not_found(client, admin_headers):
    from tests.conftest import WORKSHOP_BODY

    workshop_a = client.post(
        "/api/admin/workshops", json=WORKSHOP_BODY, headers=admin_headers
    ).json()["data"]["workshop"]
    workshop_b = client.post(
        "/api/admin/workshops", json=WORKSHOP_BODY, headers=admin_headers
    ).json()["data"]["workshop"]

    sent = client.post(
        f"/api/f/{workshop_a['admin_token']}/broadcast", json={"message_md": "Hello"}
    ).json()["data"]

    result = client.post(
        f"/api/f/{workshop_b['admin_token']}/undo/{sent['undoable_action_id']}", json={}
    )
    assert result.status_code == 404
