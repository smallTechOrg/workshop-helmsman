"""last_seen_at touch: one conditional UPDATE, no read-then-write."""

import threading
from datetime import timedelta

from sqlalchemy import select

from src.helmsman.api._common import as_utc, utcnow
from src.helmsman.api.participant import LAST_SEEN_TOUCH_SECONDS, _touch_last_seen
from src.helmsman.db.models import Participant
from src.helmsman.db.session import create_db_session


def _joined(workshop, make_client, join_participant) -> int:
    join_participant(make_client(), workshop["join_slug"], "Priya")
    with create_db_session() as session:
        return session.scalar(select(Participant.id))


def _set_age(participant_id: int, seconds: int):
    stamp = utcnow() - timedelta(seconds=seconds)
    with create_db_session() as session:
        participant = session.get(Participant, participant_id)
        participant.last_seen_at = stamp
    return stamp


def _last_seen(participant_id: int):
    with create_db_session() as session:
        return as_utc(session.get(Participant, participant_id).last_seen_at)


def test_touch_skipped_when_30s_old(workshop, make_client, join_participant):
    pid = _joined(workshop, make_client, join_participant)
    stamp = _set_age(pid, 30)
    with create_db_session() as session:
        assert _touch_last_seen(session, pid) is False
    assert _last_seen(pid) == as_utc(stamp)


def test_touch_applied_when_90s_old(workshop, make_client, join_participant):
    pid = _joined(workshop, make_client, join_participant)
    stamp = _set_age(pid, 90)
    with create_db_session() as session:
        assert _touch_last_seen(session, pid) is True
    assert _last_seen(pid) > as_utc(stamp) + timedelta(seconds=LAST_SEEN_TOUCH_SECONDS)


def test_touch_unknown_participant_is_noop(workshop):
    with create_db_session() as session:
        assert _touch_last_seen(session, 999_999) is False


def test_two_sessions_polling_at_once_yield_one_effective_update(
    workshop, make_client, join_participant
):
    pid = _joined(workshop, make_client, join_participant)
    _set_age(pid, 90)
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def poll():
        with create_db_session() as session:
            barrier.wait(timeout=10)
            results.append(_touch_last_seen(session, pid))

    threads = [threading.Thread(target=poll) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(results) == [False, True]
