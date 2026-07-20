from datetime import timedelta
from types import SimpleNamespace

from src.helmsman.api._common import utcnow
from src.helmsman.api.participant import LAST_SEEN_TOUCH_SECONDS, _touch_last_seen


def test_touch_skipped_within_throttle_window():
    recent = utcnow() - timedelta(seconds=LAST_SEEN_TOUCH_SECONDS - 5)
    participant = SimpleNamespace(last_seen_at=recent)
    _touch_last_seen(participant)
    assert participant.last_seen_at == recent


def test_touch_applied_after_throttle_window():
    stale = utcnow() - timedelta(seconds=LAST_SEEN_TOUCH_SECONDS + 5)
    participant = SimpleNamespace(last_seen_at=stale)
    _touch_last_seen(participant)
    assert participant.last_seen_at > stale
