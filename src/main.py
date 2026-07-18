"""FastAPI application: all routes for Workshop Helmsman (Phases 1-4)."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .db import get_db, init_db, session_scope
from .models import (
    DEFAULT_AGENDA_TEMPLATES,
    DEFAULT_FORM_SCHEMA,
    AgendaTemplate,
    FormTemplate,
    HelpRequest,
    MilestoneCompletion,
    Participant,
    Workshop,
)
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
    _seed_agenda_templates()


# --- Helpers ---

def _utcnow() -> datetime:
    # SQLite stores naive datetimes; return naive UTC to match what comes back.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _seed_agenda_templates() -> None:
    """Seed 2-3 starter agenda templates on first run; idempotent."""
    import json

    with session_scope() as db:
        existing = db.query(AgendaTemplate).count()
        if existing > 0:
            return
        now = _utcnow()
        for tpl in DEFAULT_AGENDA_TEMPLATES:
            at = AgendaTemplate(
                name=tpl["name"],
                created_at=now,
                milestones_json=json.dumps(tpl["milestones"]),
            )
            db.add(at)


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


# --- Phase 4: form schema helpers ---


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify_key(label: str, fallback: str = "field") -> str:
    """Best-effort field key derived from a label.

    "Display name" -> "display_name"; "What's your role?" -> "whats_your_role".
    Used only as an auto-fill suggestion; users can override it manually.
    """
    s = (label or "").strip().lower()
    s = _SLUG_RE.sub("_", s).strip("_")
    return (s or fallback)[:64]


def _normalize_field(raw: dict, idx: int) -> dict | None:
    """Sanitize a single field dict from a posted form.

    Returns None if the field is unusable (no label, no key after sanitize).
    """
    if not isinstance(raw, dict):
        return None
    label = (raw.get("label") or "").strip()
    if not label:
        return None
    key = (raw.get("key") or "").strip()
    if not key:
        key = _slugify_key(label, fallback=f"field_{idx}")
    key = _slugify_key(key.replace(" ", "_"), fallback=f"field_{idx}")
    ftype = raw.get("type")
    if ftype not in ("text", "dropdown"):
        ftype = "text"
    placeholder = (raw.get("placeholder") or "").strip() if ftype == "text" else ""
    required = bool(raw.get("required"))
    options: list[str] = []
    if ftype == "dropdown":
        opts = raw.get("options")
        if isinstance(opts, list):
            for o in opts:
                o = (str(o) if o is not None else "").strip()
                if o:
                    options.append(o)
        elif isinstance(opts, str):
            for line in opts.splitlines():
                line = line.strip()
                if line:
                    options.append(line)
        # Dedupe while preserving order.
        seen: set[str] = set()
        deduped: list[str] = []
        for o in options:
            if o not in seen:
                seen.add(o)
                deduped.append(o)
        options = deduped
        if not options:
            options = ["Yes", "No"]
    field: dict = {
        "key": key,
        "type": ftype,
        "label": label[:200],
        "required": required,
    }
    if ftype == "text":
        field["placeholder"] = placeholder[:200]
    else:
        field["options"] = options[:32]
    return field


def _coerce_fields_json(raw_json: str) -> list[dict]:
    """Parse a JSON string of field dicts into a normalized, deduplicated list.

    Rejects malformed JSON (returns empty list — caller must decide whether
    to default or error). For dicts missing a key/label, we synthesize a
    stable key from the label. Duplicate keys are deduped (later wins).
    """
    if not raw_json or not raw_json.strip():
        return []
    try:
        data = json.loads(raw_json)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    seen_keys: dict[str, int] = {}
    for idx, item in enumerate(data):
        norm = _normalize_field(item, idx)
        if norm is None:
            continue
        key = norm["key"]
        if key in seen_keys:
            # Replace prior occurrence (callers see the most recent).
            j = seen_keys[key]
            out[j] = norm
            continue
        seen_keys[key] = len(out)
        out.append(norm)
    return out


def _ensure_display_name_field(fields: list[dict]) -> list[dict]:
    """Make sure the form has at least one text field marked as the name.

    The 'name' is the field whose key is 'display_name', OR the first field
    if none is so named. If the form is empty, return the default schema.
    """
    if not fields:
        return list(DEFAULT_FORM_SCHEMA)
    return fields


def _display_name_field(schema: list[dict]) -> dict | None:
    """Return the field designated as the participant display name."""
    for f in schema:
        if f.get("key") == "display_name":
            return f
    return schema[0] if schema else None


def _form_keys(schema: list[dict]) -> list[str]:
    """Sorted-stable list of form keys for CSV columns."""
    return [f["key"] for f in schema]


def _collect_form_answers(schema: list[dict], form: dict) -> dict:
    """Given a workshop schema + request.form, return an {key: value} dict.

    Missing required fields are silently included as empty strings so the
    persistence shape is predictable. Junk keys in `form` are ignored.
    """
    out: dict[str, str] = {}
    for f in schema:
        key = f.get("key")
        if not key:
            continue
        # Inputs are named 'field_<key>' so we don't clash with hidden helpers.
        v = form.get(f"field_{key}")
        if v is None:
            v = form.get(key)
        if v is None:
            v = ""
        out[key] = str(v)[:1000]
    return out


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
            form_schema_json=json.dumps(DEFAULT_FORM_SCHEMA),
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
def admin_new_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    default_milestones = "\n".join(
        [
            "Setup: pick your environment and clone the starter",
            "API Key: configure your LLM provider key",
            "First Build: ship a hello-world end-to-end",
            "Done: present and wrap up",
        ]
    )
    templates_list = (
        db.query(FormTemplate).order_by(FormTemplate.created_at.desc()).all()
    )
    agenda_templates = (
        db.query(AgendaTemplate).order_by(AgendaTemplate.created_at.asc()).all()
    )
    return _render(
        request,
        "admin_new.html",
        default_milestones=default_milestones,
        default_ttl=8,
        templates_list=templates_list,
        default_form_fields=DEFAULT_FORM_SCHEMA,
        agenda_templates=agenda_templates,
    )


@app.post("/admin/new")
def admin_new_create(
    request: Request,
    name: str = Form(...),
    milestones: str = Form(""),
    ttl_hours: int = Form(8),
    fields_json: str = Form(""),
    template_id: str = Form(""),
    save_as_template: str = Form(""),
    template_name: str = Form(""),
    agenda_template_id: str = Form(""),
    db: Session = Depends(get_db),
):
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workshop name is required")
    if ttl_hours < 1 or ttl_hours > 7 * 24:
        ttl_hours = 8

    # Resolve milestones: use _parse_milestones (textarea) OR load from agenda template.
    parsed: list[dict]
    if agenda_template_id and agenda_template_id.isdigit():
        agenda_tpl = (
            db.query(AgendaTemplate)
            .filter(AgendaTemplate.id == int(agenda_template_id))
            .first()
        )
        if agenda_tpl is not None:
            agenda_milestones = agenda_tpl.milestones()
            if agenda_milestones:
                # Assign stable ids
                parsed = [
                    {"id": f"m{idx}", **m}
                    for idx, m in enumerate(agenda_milestones)
                ]
            else:
                parsed = _parse_milestones(milestones)
        else:
            parsed = _parse_milestones(milestones)
    else:
        parsed = _parse_milestones(milestones)

    # Resolve form schema:
    # 1. If fields_json has any fields, use that.
    # 2. Else if template_id is set and valid, deep-copy that template's fields.
    # 3. Else default to DEFAULT_FORM_SCHEMA.
    fields = _coerce_fields_json(fields_json)
    template_obj: FormTemplate | None = None
    if not fields:
        if template_id and template_id.isdigit():
            template_obj = (
                db.query(FormTemplate).filter(FormTemplate.id == int(template_id)).first()
            )
            if template_obj is not None:
                fields = deepcopy(template_obj.fields())
    fields = _ensure_display_name_field(fields)
    if not fields:
        fields = list(DEFAULT_FORM_SCHEMA)

    now = _utcnow()
    workshop = Workshop(
        name=name,
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
        admin_token=generate_admin_token(),
        participant_slug=generate_participant_slug(),
        milestone_config=json.dumps(parsed),
        archived=False,
        form_template_id=template_obj.id if template_obj else None,
        form_schema_json=json.dumps(fields),
    )
    db.add(workshop)

    # Optionally save the schema as a new named template.
    if save_as_template and template_name.strip():
        new_tpl = FormTemplate(
            name=template_name.strip()[:120],
            created_at=now,
            fields_json=json.dumps(fields),
        )
        db.add(new_tpl)
        # No flush here — commit at the end.

    db.commit()
    db.refresh(workshop)
    return RedirectResponse(url=f"/admin/{workshop.admin_token}", status_code=303)


# --- Phase 4: global template library ---


@app.get("/admin/templates", response_class=HTMLResponse)
def admin_templates_index(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """List all saved form templates."""
    templates_list = (
        db.query(FormTemplate).order_by(FormTemplate.created_at.desc()).all()
    )
    # Annotate with workshop usage counts.
    for t in templates_list:
        t._usage_count = (
            db.query(Workshop).filter(Workshop.form_template_id == t.id).count()
        )
        t._fields_summary = ", ".join(
            f.get("label", "?") for f in t.fields()
        )[:200]
    return _render(request, "admin_templates.html", templates_list=templates_list)


@app.get("/admin/templates/{tid}", response_class=HTMLResponse)
def admin_templates_edit(
    request: Request, tid: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Edit a single template's schema. Edits template — never touches existing workshop snapshots."""
    template_obj = (
        db.query(FormTemplate).filter(FormTemplate.id == tid).first()
    )
    if template_obj is None:
        raise HTTPException(status_code=404, detail="Template not found")
    schema = template_obj.fields()
    return _render(
        request,
        "admin_template_edit.html",
        template_obj=template_obj,
        form_schema=schema,
        form_schema_json_str=json.dumps(schema),
    )


@app.post("/admin/templates/{tid}")
def admin_templates_save(
    request: Request,
    tid: int,
    name: str = Form(""),
    fields_json: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    template_obj = (
        db.query(FormTemplate).filter(FormTemplate.id == tid).first()
    )
    if template_obj is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if name.strip():
        template_obj.name = name.strip()[:120]
    fields = _coerce_fields_json(fields_json)
    fields = _ensure_display_name_field(fields)
    if not fields:
        fields = list(DEFAULT_FORM_SCHEMA)
    template_obj.fields_json = json.dumps(fields)
    db.commit()
    return RedirectResponse(url=f"/admin/templates/{tid}", status_code=303)


@app.post("/admin/templates/{tid}/delete")
def admin_templates_delete(
    request: Request, tid: int, db: Session = Depends(get_db)
) -> RedirectResponse:
    """Delete a template. Existing workshops' snapshots remain intact."""
    template_obj = (
        db.query(FormTemplate).filter(FormTemplate.id == tid).first()
    )
    if template_obj is None:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template_obj)
    db.commit()
    return RedirectResponse(url="/admin/templates", status_code=303)


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
    templates_list = (
        db.query(FormTemplate).order_by(FormTemplate.created_at.desc()).all()
    )
    agenda_templates = (
        db.query(AgendaTemplate).order_by(AgendaTemplate.created_at.asc()).all()
    )
    return _render(
        request,
        "admin_edit.html",
        workshop=workshop,
        milestones_text=milestones_text,
        ttl_hours=ttl_hours,
        form_schema=workshop.form_schema(),
        form_schema_json_str=json.dumps(workshop.form_schema()),
        form_template_id=workshop.form_template_id,
        templates_list=templates_list,
        agenda_templates=agenda_templates,
    )


@app.post("/admin/{admin_token}/edit")
def admin_edit_save(
    request: Request,
    admin_token: str,
    name: str = Form(...),
    milestones: str = Form(""),
    ttl_hours: int = Form(8),
    fields_json: str = Form(""),
    agenda_template_id: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    workshop = require_workshop_by_admin_token(db, admin_token)
    workshop.name = (name or "").strip() or workshop.name

    # Resolve milestones: use _parse_milestones (textarea) OR load from agenda template.
    parsed: list[dict]
    if agenda_template_id and agenda_template_id.isdigit():
        agenda_tpl = (
            db.query(AgendaTemplate)
            .filter(AgendaTemplate.id == int(agenda_template_id))
            .first()
        )
        if agenda_tpl is not None:
            agenda_milestones = agenda_tpl.milestones()
            if agenda_milestones:
                parsed = [
                    {"id": f"m{idx}", **m}
                    for idx, m in enumerate(agenda_milestones)
                ]
            else:
                parsed = _parse_milestones(milestones)
        else:
            parsed = _parse_milestones(milestones)
    else:
        parsed = _parse_milestones(milestones)

    workshop.milestone_config = json.dumps(parsed)
    workshop.expires_at = _utcnow() + timedelta(hours=max(1, min(ttl_hours, 168)))

    fields = _coerce_fields_json(fields_json)
    fields = _ensure_display_name_field(fields)
    if not fields:
        fields = list(DEFAULT_FORM_SCHEMA)
    workshop.form_schema_json = json.dumps(fields)
    # NOTE: editing a workshop does NOT rewrite form_template_id. The template
    # is a starting point; the snapshot is what the join page uses.
    db.commit()
    return RedirectResponse(url=f"/admin/{admin_token}", status_code=303)


# --- Admin: export CSV ---

@app.get("/admin/{admin_token}/export.csv")
def admin_export_csv(
    admin_token: str,
    db: Session = Depends(get_db),
):
    """Stream a CSV of all participants, completions, help requests, and form answers.

    Columns:
      - core (always): participant_name, joined_at, milestone_title,
        completed_at, help_message, help_created_at
      - per-form-field (Phase 4): one column per schema key, in schema order,
        named `field_<key>` for clarity.

    Rows: one row per (participant, milestone). If a participant has no
    completions but has help requests, we emit one row with empty milestone
    columns and one row per help request. Helper-extra help requests beyond
    the milestone count are emitted as additional rows with blank milestone
    columns.
    """
    workshop = require_workshop_by_admin_token(db, admin_token)
    schema = workshop.form_schema()
    form_keys = _form_keys(schema)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = [
        "participant_name",
        "joined_at",
        "milestone_title",
        "completed_at",
        "help_message",
        "help_created_at",
    ] + [f"field_{k}" for k in form_keys]
    writer.writerow(header)

    participants = (
        db.query(Participant)
        .filter(Participant.workshop_id == workshop.id)
        .order_by(Participant.joined_at.asc())
        .all()
    )
    for p in participants:
        answers = p.answers()
        # Per-participant column tuple: empty unless row is tied to a milestone slot.
        help_reqs = sorted(p.help_requests, key=lambda h: h.created_at)
        if not p.completions and not help_reqs:
            row = [p.name, p.joined_at.isoformat(), "", "", "", ""]
            for k in form_keys:
                row.append(answers.get(k, ""))
            writer.writerow(row)
            continue
        comp_by_mid = {c.milestone_id: c for c in p.completions}
        all_mids = sorted(comp_by_mid.keys())
        all_help_idx = 0
        for mid in all_mids:
            c = comp_by_mid[mid]
            help_msg = ""
            help_ts = ""
            if all_help_idx < len(help_reqs):
                h = help_reqs[all_help_idx]
                help_msg = h.message
                help_ts = h.created_at.isoformat()
                all_help_idx += 1
            row = [
                p.name,
                p.joined_at.isoformat(),
                c.milestone_title,
                c.completed_at.isoformat(),
                help_msg,
                help_ts,
            ]
            for k in form_keys:
                row.append(answers.get(k, ""))
            writer.writerow(row)
        while all_help_idx < len(help_reqs):
            h = help_reqs[all_help_idx]
            row = [p.name, p.joined_at.isoformat(), "", "", h.message, h.created_at.isoformat()]
            for k in form_keys:
                row.append(answers.get(k, ""))
            writer.writerow(row)
            all_help_idx += 1

    buffer.seek(0)
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
    src_schema = src.form_schema()

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
        # Snapshot the form schema; do NOT carry the template id (a clone
        # is a fresh workshop — if the user later edits the snapshot, we
        # don't muddle authorship with the original template).
        form_template_id=None,
        form_schema_json=json.dumps(src_schema),
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
    """Full timeline for one participant: completions + help requests.

    Phase 4: also surfaces the captured join-form answers as a 'Join inputs'
    panel, falling back to a sensible default if answers are missing.
    """
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
    schema = workshop.form_schema()
    answers = participant.answers()
    # Render the answers panel — ordered by schema when possible.
    # Pass pre-built (label, value) tuples to the template for simplicity.
    answers_panel: list[tuple[str, str]] = []
    for f in schema:
        v = answers.get(f.get("key", ""), "")
        label = f.get("label") or f.get("key") or ""
        answers_panel.append((label, str(v)))
    # If schema is empty but participant has answers, render them raw.
    if not schema and answers:
        for k, v in answers.items():
            answers_panel.append((k, str(v)))
    return _render(
        request,
        "participant_drilldown.html",
        workshop=workshop,
        participant=participant,
        completions=completions,
        help_requests=help_reqs,
        answers_panel=answers_panel,
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

    schema = workshop.form_schema()
    name_field = _display_name_field(schema)
    # Convenient view for the template: list of form fields to render.
    return _render(
        request,
        "participant_join.html",
        workshop=workshop,
        form_schema=schema,
        name_field=name_field,
    )


@app.post("/w/{slug}")
def participant_register(
    request: Request,
    slug: str,
    # Sentinel Form(...) parameters ensure FastAPI parses the multipart body
    # into request._form. We re-read it inside the handler so we can iterate
    # over the *arbitrary* set of field inputs the workshop schema defines.
    name: str = Form(""),
    db: Session = Depends(get_db),
):
    workshop = require_workshop_by_slug(db, slug)
    if workshop.is_expired():
        return _render(request, "workshop_expired.html", workshop=workshop)

    schema = workshop.form_schema()

    # The display name comes from the canonical 'display_name' field, OR the
    # first schema field, OR the legacy `name` POST. This makes Phase 4
    # backwards-compatible with Phase 1-3 join-page submissions.
    name_field = _display_name_field(schema)
    name_field_key = name_field.get("key") if name_field else "display_name"

    # We can't easily mix dynamic Form() params with a fixed signature, so
    # we manually read the whole form body. FastAPI's `Depends` injection
    # for Form(...) parses the body once into request._form; by using a
    # hidden Form(...) sentinel below we ensure that has run before this
    # code reads it. (Sentinel itself is discarded.)
    form_data = getattr(request, "_form", None)
    form: dict[str, str] = {}
    if form_data is not None:
        try:
            form = {k: form_data.get(k) for k in form_data.keys()}
        except Exception:
            form = {}

    # Accept answers from the dynamic form.
    answers = _collect_form_answers(schema, form)

    name = ""
    if name_field_key in answers:
        name = (answers.get(name_field_key) or "").strip()
    if not name:
        legacy = form.get("name")
        if legacy is not None:
            name = str(legacy).strip()
    if not name:
        for k, v in answers.items():
            v = (v or "").strip()
            if v:
                name = v
                break

    if not name:
        raise HTTPException(status_code=400, detail="Display name is required")
    if len(name) > 120:
        name = name[:120]

    # Persist the answers as JSON (the captured *inputs* — what they
    # submitted), and ALSO write the canonical display name into the legacy
    # participant.name column so dashboards keep working unchanged.
    participant = Participant(
        workshop_id=workshop.id,
        name=name,
        answers_json=json.dumps(answers) if answers else None,
    )
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
        # Phase 4: include the form schema so the participant tracker can
        # surface captured answers if/when we later add a per-participant
        # view there. (No client-side reliance on this in Phase 4.)
        "form_schema": getattr(db.query(Workshop).filter(Workshop.id == workshop.id).first(), "form_schema", lambda: [])(),
    }


# --- Phase 4: form-template management (admin) ---


@app.get("/admin/{admin_token}/form", response_class=HTMLResponse)
def admin_form_edit(
    request: Request,
    admin_token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Edit the form schema for THIS workshop (the snapshot, not the template)."""
    workshop = require_workshop_by_admin_token(db, admin_token)
    schema = workshop.form_schema()
    return _render(
        request,
        "admin_form.html",
        workshop=workshop,
        form_schema=schema,
        form_schema_json_str=json.dumps(schema),
    )


@app.post("/admin/{admin_token}/form")
def admin_form_save(
    request: Request,
    admin_token: str,
    fields_json: str = Form(""),
    save_as_template: str = Form(""),
    template_name: str = Form(""),
    template_id: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save the form schema snapshot, optionally (also) save as a new/updated template."""
    workshop = require_workshop_by_admin_token(db, admin_token)
    fields = _coerce_fields_json(fields_json)
    fields = _ensure_display_name_field(fields)
    if not fields:
        fields = list(DEFAULT_FORM_SCHEMA)
    workshop.form_schema_json = json.dumps(fields)

    template_obj: FormTemplate | None = None
    if save_as_template and template_name.strip():
        # If template_id was passed, update it; else create a new one.
        if template_id and template_id.isdigit():
            template_obj = (
                db.query(FormTemplate)
                .filter(FormTemplate.id == int(template_id))
                .first()
            )
            if template_obj is not None:
                template_obj.name = template_name.strip()[:120]
                template_obj.fields_json = json.dumps(fields)
        else:
            template_obj = FormTemplate(
                name=template_name.strip()[:120],
                created_at=_utcnow(),
                fields_json=json.dumps(fields),
            )
            db.add(template_obj)
            db.flush()
            workshop.form_template_id = template_obj.id

    db.commit()
    return RedirectResponse(url=f"/admin/{admin_token}", status_code=303)


@app.get("/admin/{admin_token}/form-template", response_class=HTMLResponse)
def admin_form_template_pick(
    request: Request,
    admin_token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Pick a saved template to overwrite THIS workshop's snapshot."""
    workshop = require_workshop_by_admin_token(db, admin_token)
    templates_list = (
        db.query(FormTemplate).order_by(FormTemplate.created_at.desc()).all()
    )
    return _render(
        request,
        "admin_form_template.html",
        workshop=workshop,
        templates_list=templates_list,
        form_schema=workshop.form_schema(),
    )


@app.post("/admin/{admin_token}/form-template/apply/{tid}")
def admin_form_template_apply(
    request: Request,
    admin_token: str,
    tid: int,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Replace the workshop's form-schema snapshot with a deep-copy of the template.

    IMPORTANT: historical workshops that already collected answers are
    unaffected — only this workshop's JOIN page gets the new fields.
    """
    workshop = require_workshop_by_admin_token(db, admin_token)
    template_obj = (
        db.query(FormTemplate).filter(FormTemplate.id == tid).first()
    )
    if template_obj is None:
        raise HTTPException(status_code=404, detail="Template not found")
    fresh_fields = deepcopy(template_obj.fields())
    if not fresh_fields:
        fresh_fields = list(DEFAULT_FORM_SCHEMA)
    workshop.form_schema_json = json.dumps(fresh_fields)
    workshop.form_template_id = template_obj.id
    db.commit()
    return RedirectResponse(url=f"/admin/{admin_token}", status_code=303)


