from datetime import datetime, timezone

from fastapi import HTTPException

from src.helmsman.api._common import api_error, as_utc, iso_z, ok


def test_ok_envelope():
    assert ok({"x": 1}) == {"data": {"x": 1}, "error": None}


def test_api_error_shape():
    exc = api_error("not_found", "Nope.", 404)
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 404
    assert exc.detail == {"code": "not_found", "message": "Nope."}


def test_iso_z_formats_aware_utc_at_seconds_precision():
    dt = datetime(2026, 7, 20, 14, 3, 22, 987654, tzinfo=timezone.utc)
    assert iso_z(dt) == "2026-07-20T14:03:22Z"


def test_iso_z_treats_naive_as_utc():
    dt = datetime(2026, 7, 20, 14, 3, 22)
    assert iso_z(dt) == "2026-07-20T14:03:22Z"


def test_as_utc_converts_other_zones():
    from datetime import timedelta, timezone as tz

    plus_two = tz(timedelta(hours=2))
    dt = datetime(2026, 7, 20, 16, 3, 22, tzinfo=plus_two)
    assert iso_z(dt) == "2026-07-20T14:03:22Z"
    assert as_utc(dt).hour == 14
