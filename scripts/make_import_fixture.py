"""Build a realistic SQLite database through the REAL app, for rehearsing the
SQLite -> PostgreSQL import (scripts/sqlite_to_postgres.py).

    uv run python scripts/make_import_fixture.py --out /path/to/fixture.db

Everything goes through the HTTP API of the real FastAPI app over a fresh SQLite file
migrated by `alembic upgrade head`: 3 workshops, 320 participants in one (more than
one 500-row batch once completions are counted), 960 completions, help requests with
facilitator answers and participant replies, broadcasts and audit rows. All data is
synthetic. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURE_ADMIN_KEY = "fixture-admin-key-0123456789"
BIG_PARTICIPANTS = 320
BIG_MILESTONES = 3


def _milestones(count: int) -> list[dict]:
    return [
        {"title": f"Step {i + 1}", "content_md": f"Do step **{i + 1}**.", "minutes": 10 + i}
        for i in range(count)
    ]


def build_fixture(out: Path) -> dict:
    """Create the fixture DB at `out`; return a few facts about it (for tests/logging)."""
    out = Path(out).resolve()
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing file: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)

    os.environ["DATABASE_URL"] = f"sqlite:///{out}"
    os.environ["WORKSHOP0_ADMIN_KEY"] = FIXTURE_ADMIN_KEY
    os.environ["WORKSHOP0_BASE_URL"] = ""
    os.environ["WORKSHOP0_LOG_LEVEL"] = "WARNING"

    import src.workshop0.config.settings as settings_module
    from src.workshop0.db.session import reset_db_state

    settings_module._settings = None
    reset_db_state()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    from fastapi.testclient import TestClient

    from src.workshop0.api import create_app

    client = TestClient(create_app())
    admin = {"X-Admin-Key": FIXTURE_ADMIN_KEY}

    def create(name: str, milestones: int) -> dict:
        r = client.post(
            "/api/admin/workshops",
            json={"name": name, "description_md": f"{name} description", "milestones": _milestones(milestones)},
            headers=admin,
        )
        assert r.status_code == 200, r.text
        w = r.json()["data"]["workshop"]
        detail = client.get(f"/api/f/{w['admin_token']}/workshop").json()["data"]
        return {
            "admin_token": w["admin_token"],
            "join_slug": w["join_slug"],
            "milestone_ids": [m["id"] for m in detail["milestones"]],
        }

    def join(slug: str, name: str) -> str:
        r = client.post(f"/api/join/{slug}", json={"name": name})
        assert r.status_code == 200, r.text
        return r.json()["data"]["participant_token"]

    big = create("Fixture Big Workshop", BIG_MILESTONES)
    small = create("Fixture Small Workshop", 4)
    empty = create("Fixture Empty Workshop", 2)

    tokens = [join(big["join_slug"], f"Person {i:03d}") for i in range(BIG_PARTICIPANTS)]
    for token in tokens:
        for mid in big["milestone_ids"]:
            r = client.post(f"/api/p/{token}/milestones/{mid}/complete")
            assert r.status_code == 200, r.text

    small_tokens = [join(small["join_slug"], f"Small {i}") for i in range(12)]
    for i, token in enumerate(small_tokens):
        for mid in small["milestone_ids"][: i % 5]:
            assert client.post(f"/api/p/{token}/milestones/{mid}/complete").status_code == 200

    # Help requests: asks, facilitator answers, participant replies, resolution.
    for workshop, workers in ((big, tokens[:6]), (small, small_tokens[:3])):
        for i, token in enumerate(workers):
            r = client.post(f"/api/p/{token}/help", json={"message": f"I am stuck on thing {i}"})
            assert r.status_code == 200, r.text
            hid = r.json()["data"]["help_request"]["id"]
            if i % 2 == 0:
                a = client.post(
                    f"/api/f/{workshop['admin_token']}/help/{hid}/answer",
                    json={"answer_md": f"Try again, #{i}."},
                )
                assert a.status_code == 200, a.text
                rep = client.post(f"/api/p/{token}/help/{hid}/reply", json={"message": "Thanks, still stuck"})
                assert rep.status_code == 200, rep.text
            if i % 3 == 0:
                client.post(f"/api/f/{workshop['admin_token']}/help/{hid}/resolve")

    # Broadcasts (one cleared, one active), pause toggle, a milestone edit -> audit rows.
    for workshop, texts in ((big, ["Welcome!", "Lunch at 1"]), (small, ["Hello small"])):
        for text in texts:
            r = client.post(f"/api/f/{workshop['admin_token']}/broadcast", json={"message_md": text})
            assert r.status_code == 200, r.text
        if len(texts) > 1:
            client.post(f"/api/f/{workshop['admin_token']}/broadcast/clear", json={})
    client.post(f"/api/f/{small['admin_token']}/pause", json={"paused": True})
    client.post(f"/api/f/{small['admin_token']}/pause", json={"paused": False})
    client.patch(
        f"/api/f/{big['admin_token']}/milestones/{big['milestone_ids'][0]}",
        json={"title": "Step 1 (edited)"},
    )

    from sqlalchemy import func, select

    from src.workshop0.db.models import (
        AgendaTemplate,
        AgendaTemplateMilestone,
        AiUsage,
        Base,
        HelpRequest,
        JoinFormTemplate,
        Workshop,
    )
    from src.workshop0.db.session import create_db_session

    # Tables with no public API yet (templates, AI usage): seed a few rows directly so
    # every app table, including Numeric and nullable-FK columns, is exercised.
    with create_db_session() as session:
        template = AgendaTemplate(name="Fixture template", description_md="t")
        session.add(template)
        session.flush()
        session.add_all(
            AgendaTemplateMilestone(template_id=template.id, position=i, title=f"T{i}", minutes=5)
            for i in range(3)
        )
        session.add(JoinFormTemplate(name="Fixture form", fields_json="[]"))
        workshop_id = session.scalar(select(Workshop.id).where(Workshop.join_slug == big["join_slug"]))
        help_id = session.scalar(select(HelpRequest.id).where(HelpRequest.workshop_id == workshop_id))
        session.add_all(
            [
                AiUsage(workshop_id=workshop_id, help_request_id=help_id, purpose="answer",
                        model="fixture/model", prompt_tokens=120, completion_tokens=40,
                        cost_usd=0.000123, latency_ms=850),
                AiUsage(workshop_id=workshop_id, help_request_id=None, purpose="answer",
                        model="fixture/model", prompt_tokens=1, completion_tokens=1,
                        cost_usd=0, latency_ms=1),
            ]
        )
        session.commit()

    with create_db_session() as session:
        counts = {
            t.name: session.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables
        }
    reset_db_state()
    settings_module._settings = None
    return {"path": str(out), "big": big, "small": small, "empty": empty, "big_tokens": tokens, "counts": counts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="path of the SQLite file to create")
    args = parser.parse_args(argv)
    facts = build_fixture(Path(args.out))
    print(f"fixture written: {facts['path']}")
    for name, n in facts["counts"].items():
        print(f"  {name:28s} {n:>6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
