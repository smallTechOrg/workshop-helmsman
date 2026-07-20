from fastapi.testclient import TestClient


def test_health_ok_envelope(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok", "db": "ok"}, "error": None}


def test_health_returns_internal_error_when_db_unreachable(monkeypatch, app):
    from src.helmsman.db import session as session_module

    engine = session_module.get_engine()

    def _broken_connect(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(engine, "connect", _broken_connect)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/health")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["code"] == "internal_error"
    assert "message" in body["detail"]
