"""FastAPI application: all routes for Workshop Helmsman Phase 1."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .db import get_db, init_db
from .models import HelpRequest, MilestoneCompletion, Participant, Workshop
from .security import (
    PARTICIPANT_COOKIE,
    find_participant,
    find_workshop_by_admin_token,
    find_workshop_by_slug,
    generate_admin_token,
    generate_participant_slug,
    require_workshop_by_admin_token,
    require_workshop_by_slug,
)

# --- Paths & app bootstrap ---

HERE = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = HERE / "frontend" / "templates"
STATIC_DIR = HERE / "frontend" / "static"

app = FastAPI(title="Workshop Helmsman", version="0.1.0")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _on_startup() -> None:
    init_db()


# --- Helpers ---

def _utcnow() -> datetime:
    # SQLite stores naive datetimes; return naive UTC to match what comes back.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_milestones(raw: str) -> list[dict]:
    """Parse lines into [{id, title, description}]."""
    parsed: list[dict] = []
    for idx, line in enumerate((raw or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            title, description = line.split(":", 1)
            title = title.strip()
            description = description.strip()
        else:
            title = line
            description = ""
        if not title:
            continue
        parsed.append({"id": f"m{idx}", "title": title, "description": description})
    if not parsed:
        # Sensible default — facilitator gets 4 phases even if they submit blank.
        parsed = [
            {"id": "m0", "title": "Setup", "description": "Environment ready"},
            {"id": "m1", "title": "API Key", "description": "API key configured"},
            {"id": "m2", "title": "First Build", "description": "First working build"},
            {"id": "m3", "title": "Done", "description": "Workshop wrap-up"},
        ]
    return parsed


def _render(request: Request, template: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, template, ctx)


def _participant_progress(participant: Participant, milestones: list[dict]) -> dict:
    completed_ids = {c.milestone_id for c in participant.completions}
    return {
        "participant": participant,
        "completed_ids": completed_ids,
        "completed_count": len(completed_ids),
        "total": len(milestones),
        "pct": int(round(100 * len(completed_ids) / max(len(milestones), 1))),
    }


# --- Health & landing ---

@app.get("/healthz", response_class=JSONResponse)
def healthz(db: Session = Depends(get_db)) -> dict:
    try:
        # Cheap query — proves DB reachable.
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": str(exc)})


@app.get("/", response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    # Bootstrap a DEMO workshop the first time anyone hits /, so facilitators
    # can poke at a working session immediately.
    demo = (
        db.query(Workshop)
        .filter(Workshop.admin_token == "demo-workshop-admin-token")
        .first()
    )
    if demo is None:
        milestones = _parse_milestones(
            "Setup: pick your environment\nAPI Key: configure your LLM key\nFirst Build: run your hello-world\nDone: workshop wrap-up"
        )
        now = _utcnow()
        demo = Workshop(
            name="(demo) Quick Walkthrough",
            created_at=now,
            expires_at=now + timedelta(days=1),
            admin_token="demo-workshop-admin-token",
            participant_slug="demo-walkthrough",
            milestone_config=json.dumps(milestones),
            archived=False,
        )
        db.add(demo)
        db.commit()

    recent = (
        db.query(Workshop).order_by(desc(Workshop.created_at)).limit(10).all()
    )
    return _render(
        request,
        "landing.html",
        demo_admin=demo.admin_token,
        demo_slug=demo.participant_slug,
        workshops=recent,
    )


# --- Admin: create workshop ---

@app.get("/admin/new", response_class=HTMLResponse)
def admin_new_form(request: Request) -> HTMLResponse:
    default_milestones = "\n".join(
        [
            "Setup: pick your environment and clone the starter",
            "API Key: configure your LLM provider key",
            "First Build: ship a hello-world end-to-end",
            "Done: present and wrap up",
        ]
    )
    return _render(
        request,
        "admin_new.html",
        default_milestones=default_milestones,
        default_ttl=8,
    )


@app.post("/admin/new")
def admin_new_create(
    request: Request,
    name: str = Form(...),
    milestones: str = Form(""),
    ttl_hours: int = Form(8),
    db: Session = Depends(get_db),
):
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workshop name is required")
    if ttl_hours < 1 or ttl_hours > 7 * 24:
        ttl_hours = 8
    parsed = _parse_milestones(milestones)
    now = _utcnow()
    workshop = Workshop(
        name=name,
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
        admin_token=generate_admin_token(),
        participant_slug=generate_participant_slug(),
        milestone_config=json.dumps(parsed),
        archived=False,
    )
    db.add(workshop)
    db.commit()
    return RedirectResponse(url=f"/admin/{workshop.admin_token}", status_code=303)


# --- Admin: dashboard ---

@app.get("/admin/{admin_token}", response_class=HTMLResponse)
def admin_dashboard(
    request: Request, admin_token: str, db: Session = Depends(get_db)
) -> HTMLResponse:
    workshop = require_workshop_by_admin_token(db, admin_token)
    milestones = workshop.milestones()
    participants = (
        db.query(Participant)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(Participant.joined_at.asc())
        .all()
    )
    rows = [_participant_progress(p, milestones) for p in participants]
    help_requests = (
        db.query(HelpRequest)
        .join(Participant, HelpRequest.participant_id == Participant.id)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(desc(HelpRequest.created_at))
        .limit(20)
        .all()
    )
    # Per-milestone completion stats across all participants.
    stats: list[dict] = []
    for m in milestones:
        c = (
            db.query(MilestoneCompletion)
            .join(Participant, MilestoneCompletion.participant_id == Participant.id)
            .filter(
                Participant.workshop_id == workshop.id,
                MilestoneCompletion.milestone_id == m["id"],
            )
            .count()
        )
        stats.append({**m, "count": c, "pct": int(round(100 * c / max(len(participants), 1)))})
    # Cohort stacked-bar: how many participants have completed 0, 1, 2, ... milestones?
    COHORT_COLORS = ["#ef6a6a", "#d68c44", "#e4c44a", "#44d39a", "#7aa2ff", "#b07fdb", "#ec8898", "#88d4ab"]
    total = len(participants)
    done_counts: dict[int, int] = {}
    for r in rows:
        k = r["completed_count"]
        done_counts[k] = done_counts.get(k, 0) + 1
    max_milestones = len(milestones)
    segments = []
    for k in range(max_milestones + 1):
        cnt = done_counts.get(k, 0)
        if cnt > 0 or k == 0:
            segments.append({
                "label": f"{k} done" if k < max_milestones else "all done",
                "count": cnt,
                "color": COHORT_COLORS[k % len(COHORT_COLORS)],
            })
    # Always show at least one segment
    if not segments and total == 0:
        segments = [{"label": "0 done", "count": 0, "color": COHORT_COLORS[0]}]
    total_done = sum(r["completed_count"] for r in rows)
    cohort_bar = {
        "segments": segments,
        "total": total,
        "pct": int(round(100 * total_done / max(total * max(1, max_milestones), 1))),
    }
    return _render(
        request,
        "admin_dashboard.html",
        workshop=workshop,
        rows=rows,
        milestones=milestones,
        stats=stats,
        help_requests=help_requests,
        participant_count=len(participants),
        cohort_bar=cohort_bar,
    )


# --- Admin: edit workshop ---

@app.get("/admin/{admin_token}/edit", response_class=HTMLResponse)
def admin_edit_form(
    request: Request, admin_token: str, db: Session = Depends(get_db)
) -> HTMLResponse:
    workshop = require_workshop_by_admin_token(db, admin_token)
    milestones = workshop.milestones()
    # Build textarea text: "title: description" per line
    milestones_text = "\n".join(
        f"{m['title']}: {m['description']}" if m.get("description") else m["title"]
        for m in milestones
    )
    # TTL as hours from now (at least 1) — normalize to naive for subtraction
    now = _utcnow()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    exp = workshop.expires_at
    if exp.tzinfo is not None:
        exp = exp.replace(tzinfo=None)
    ttl_hours = max(1, round((exp - now).total_seconds() / 3600))
    return _render(
        request,
        "admin_edit.html",
        workshop=workshop,
        milestones_text=milestones_text,
        ttl_hours=ttl_hours,
    )


@app.post("/admin/{admin_token}/edit")
def admin_edit_save(
    request: Request,
    admin_token: str,
    name: str = Form(...),
    milestones: str = Form(""),
    ttl_hours: int = Form(8),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    workshop = require_workshop_by_admin_token(db, admin_token)
    workshop.name = (name or "").strip() or workshop.name
    parsed = _parse_milestones(milestones)
    workshop.milestone_config = json.dumps(parsed)
    workshop.expires_at = _utcnow() + timedelta(hours=max(1, min(ttl_hours, 168)))
    db.commit()
    return RedirectResponse(url=f"/admin/{admin_token}", status_code=303)


# --- Admin: export CSV ---

@app.get("/admin/{admin_token}/export.csv")
def admin_export_csv(
    admin_token: str,
    db: Session = Depends(get_db),
):
    """Stream a CSV of all participants, completions, and help requests."""
    import csv
    import io

    workshop = require_workshop_by_admin_token(db, admin_token)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "participant_name",
            "joined_at",
            "milestone_title",
            "completed_at",
            "help_message",
            "help_created_at",
        ]
    )

    # Left-join participants → completions → help_requests
    participants = (
        db.query(Participant)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(Participant.joined_at.asc())
        .all()
    )
    for p in participants:
        # Each participant may have 0..N completions and 0..M help requests.
        # Emit one row per completion (N rows) or, if none, one row with only
        # participant data; then one row per help_request (M rows).
        help_reqs = sorted(p.help_requests, key=lambda h: h.created_at)
        if not p.completions and not help_reqs:
            writer.writerow([p.name, p.joined_at.isoformat(), "", "", "", ""])
            continue
        comp_by_mid = {c.milestone_id: c for c in p.completions}
        all_mids = sorted(comp_by_mid.keys())
        all_help_idx = 0
        # Emit one row per milestone (use first help_request for that milestone slot)
        for mid in all_mids:
            c = comp_by_mid[mid]
            help_msg = ""
            help_ts = ""
            # Pair help requests round-robin to milestones
            if all_help_idx < len(help_reqs):
                h = help_reqs[all_help_idx]
                help_msg = h.message
                help_ts = h.created_at.isoformat()
                all_help_idx += 1
            writer.writerow(
                [
                    p.name,
                    p.joined_at.isoformat(),
                    c.milestone_title,
                    c.completed_at.isoformat(),
                    help_msg,
                    help_ts,
                ]
            )
        # Remaining help requests (beyond milestone count) with blank completion cols
        while all_help_idx < len(help_reqs):
            h = help_reqs[all_help_idx]
            writer.writerow([p.name, p.joined_at.isoformat(), "", "", h.message, h.created_at.isoformat()])
            all_help_idx += 1

    buffer.seek(0)
    from starlette.responses import StreamingResponse
    ts = _utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"workshop-{workshop.name}-{ts}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Admin: clone workshop ---

@app.post("/admin/{admin_token}/clone")
def admin_clone(
    request: Request,
    admin_token: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Create a new workshop with the same milestone config but fresh tokens."""
    src = require_workshop_by_admin_token(db, admin_token)
    src_milestones = src.milestones()

    # Compute TTL: use the same default (8h) rather than copying the absolute
    # expiry timestamp, so a 10-minute-old workshop still gives full 8h.
    DEFAULT_TTL_HOURS = 8
    now = _utcnow()
    clone = Workshop(
        name=src.name,
        created_at=now,
        expires_at=now + timedelta(hours=DEFAULT_TTL_HOURS),
        admin_token=generate_admin_token(),
        participant_slug=generate_participant_slug(),
        milestone_config=json.dumps(src_milestones),
        archived=False,
    )
    db.add(clone)
    db.commit()
    return RedirectResponse(url=f"/admin/{clone.admin_token}", status_code=303)


# --- Admin: archive workshop ---

@app.post("/admin/{admin_token}/archive")
def admin_archive(
    request: Request,
    admin_token: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Soft-delete: mark workshop as archived, redirects back to dashboard."""
    workshop = require_workshop_by_admin_token(db, admin_token)
    workshop.archived = True
    db.commit()
    return RedirectResponse(url=f"/admin/{admin_token}", status_code=303)


# --- Admin: per-participant drill-down ---

@app.get("/admin/{admin_token}/participant/{pid}", response_class=HTMLResponse)
def admin_participant_drilldown(
    request: Request,
    admin_token: str,
    pid: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Full timeline for one participant: completions + help requests."""
    workshop = require_workshop_by_admin_token(db, admin_token)
    participant = find_participant(db, workshop.id, pid)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    completions = (
        db.query(MilestoneCompletion)
        .filter(MilestoneCompletion.participant_id == pid)
        .order_by(MilestoneCompletion.completed_at.asc())
        .all()
    )
    help_reqs = (
        db.query(HelpRequest)
        .filter(HelpRequest.participant_id == pid)
        .order_by(HelpRequest.created_at.asc())
        .all()
    )
    return _render(
        request,
        "participant_drilldown.html",
        workshop=workshop,
        participant=participant,
        completions=completions,
        help_requests=help_reqs,
    )


# --- Local workshops index (Phase 3) ---

@app.get("/workshops", response_class=HTMLResponse)
def workshops_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    items = (
        db.query(Workshop).order_by(desc(Workshop.created_at)).limit(50).all()
    )
    # Attach participant counts.
    for w in items:
        w._participant_count = (
            db.query(Participant)
            .filter(Participant.workshop_id == w.id)
            .count()
        )
    return _render(request, "workshops_index.html", items=items)


# --- Participant: join ---

@app.get("/w/{slug}", response_class=HTMLResponse)
def participant_join(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    wid: str | None = None,
) -> HTMLResponse:
    workshop = find_workshop_by_slug(db, slug)
    if workshop is None:
        raise HTTPException(status_code=404, detail="Workshop not found")
    if workshop.archived:
        return _render(request, "workshop_archived.html", workshop=workshop)
    if workshop.is_expired():
        return _render(request, "workshop_expired.html", workshop=workshop)

    # If `wid` cookie maps to a participant in this workshop, fast-path to tracker.
    existing_pid: int | None = None
    cookie_wid = request.cookies.get(PARTICIPANT_COOKIE)
    if cookie_wid is not None:
        try:
            pid = int(cookie_wid)
            p = find_participant(db, workshop.id, pid)
            if p is not None:
                existing_pid = pid
        except ValueError:
            pass

    if existing_pid is not None:
        return RedirectResponse(url=f"/w/{slug}/me", status_code=303)

    return _render(request, "participant_join.html", workshop=workshop)


@app.post("/w/{slug}")
def participant_register(
    request: Request,
    slug: str,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    workshop = require_workshop_by_slug(db, slug)
    if workshop.is_expired():
        return _render(request, "workshop_expired.html", workshop=workshop)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if len(name) > 120:
        name = name[:120]

    participant = Participant(workshop_id=workshop.id, name=name)
    db.add(participant)
    db.commit()
    db.refresh(participant)

    response = RedirectResponse(url=f"/w/{slug}/me", status_code=303)
    response.set_cookie(
        key=PARTICIPANT_COOKIE,
        value=str(participant.id),
        max_age=60 * 60 * 12,  # 12 hours — survives workshop length
        httponly=True,
        samesite="lax",
        path=f"/w/{slug}",
    )
    return response


# --- Participant: personal tracker ---

def _resolve_participant(
    request: Request, db: Session, slug: str
) -> tuple[Workshop, Participant]:
    workshop = require_workshop_by_slug(db, slug)
    if workshop.is_expired():
        raise HTTPException(status_code=404, detail="Workshop has ended")
    cookie = request.cookies.get(PARTICIPANT_COOKIE)
    if not cookie:
        raise HTTPException(status_code=401, detail="Join the workshop first")
    try:
        pid = int(cookie)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
    participant = find_participant(db, workshop.id, pid)
    if participant is None:
        raise HTTPException(status_code=401, detail="Join the workshop first")
    return workshop, participant


@app.get("/w/{slug}/me", response_class=HTMLResponse)
def participant_me(
    request: Request, slug: str, db: Session = Depends(get_db)
) -> HTMLResponse:
    workshop, participant = _resolve_participant(request, db, slug)
    milestones = workshop.milestones()
    completed_ids: dict[str, datetime] = {
        c.milestone_id: c.completed_at for c in participant.completions
    }

    # Leaderboard for everyone in this workshop.
    all_participants = (
        db.query(Participant)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(Participant.joined_at.asc())
        .all()
    )
    leaderboard = []
    for p in all_participants:
        done = {c.milestone_id for c in p.completions}
        leaderboard.append(
            {
                "id": p.id,
                "name": p.name,
                "joined_at": p.joined_at.isoformat(),
                "completed_count": len(done),
                "total": len(milestones),
                "pct": int(round(100 * len(done) / max(len(milestones), 1))),
                "is_me": p.id == participant.id,
            }
        )

    help_recent = (
        db.query(HelpRequest)
        .join(Participant, HelpRequest.participant_id == Participant.id)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(desc(HelpRequest.created_at))
        .limit(20)
        .all()
    )
    return _render(
        request,
        "participant_tracker.html",
        workshop=workshop,
        participant=participant,
        milestones=milestones,
        completed_ids=completed_ids,
        leaderboard=leaderboard,
        latest_help=help_recent,
    )


@app.post("/w/{slug}/me/complete/{milestone_id}")
def participant_complete(
    request: Request,
    slug: str,
    milestone_id: str,
    db: Session = Depends(get_db),
):
    workshop, participant = _resolve_participant(request, db, slug)
    milestone = next((m for m in workshop.milestones() if m["id"] == milestone_id), None)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    existing = (
        db.query(MilestoneCompletion)
        .filter(
            MilestoneCompletion.participant_id == participant.id,
            MilestoneCompletion.milestone_id == milestone_id,
        )
        .first()
    )
    if existing is None:
        completion = MilestoneCompletion(
            participant_id=participant.id,
            milestone_id=milestone_id,
            milestone_title=milestone["title"],
        )
        db.add(completion)
        db.commit()
    return RedirectResponse(url=f"/w/{slug}/me", status_code=303)


@app.post("/w/{slug}/me/help")
def participant_help(
    request: Request,
    slug: str,
    message: str = Form(""),
    db: Session = Depends(get_db),
):
    workshop, participant = _resolve_participant(request, db, slug)
    message = (message or "").strip()
    if message:
        # Cap to keep DB tidy.
        if len(message) > 2000:
            message = message[:2000]
        req = HelpRequest(participant_id=participant.id, message=message)
        db.add(req)
        db.commit()
    return RedirectResponse(url=f"/w/{slug}/me", status_code=303)


@app.get("/w/{slug}/data", response_class=JSONResponse)
def participant_poll(
    request: Request, slug: str, since: str | None = None, db: Session = Depends(get_db)
):
    """JSON endpoint polled by the participant tracker every ~4s."""
    workshop = find_workshop_by_slug(db, slug)
    if workshop is None or workshop.archived:
        raise HTTPException(status_code=404, detail="Workshop not found")

    milestones = workshop.milestones()
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None

    all_participants = (
        db.query(Participant)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(Participant.joined_at.asc())
        .all()
    )
    leaderboard = []
    for p in all_participants:
        done = {c.milestone_id for c in p.completions}
        leaderboard.append(
            {
                "id": p.id,
                "name": p.name,
                "completed_count": len(done),
                "total": len(milestones),
                "pct": int(round(100 * len(done) / max(len(milestones), 1))),
            }
        )

    help_recent = (
        db.query(HelpRequest)
        .join(Participant, HelpRequest.participant_id == Participant.id)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(desc(HelpRequest.created_at))
        .limit(20)
        .all()
    )
    help_payload = []
    for h in help_recent:
        help_payload.append(
            {
                "id": h.id,
                "participant_id": h.participant_id,
                "participant_name": h.participant.name,
                "message": h.message,
                "created_at": h.created_at.isoformat(),
            }
        )

    return {
        "ok": True,
        "server_time": _utcnow().isoformat(),
        "leaderboard": leaderboard,
        "help_requests": help_payload,
        "milestones": milestones,
    }
