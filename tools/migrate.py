"""Phase 4 + Phase 6 schema migrations.

Idempotent. Run with:

    venv/bin/python tools/migrate.py

Walks the existing SQLite DB and:
  1. Adds `form_template_id` (FK → form_template.id, ON DELETE SET NULL)
     and `form_schema_json` columns to `workshop` if missing.
  2. Adds `answers_json` (NULL-able TEXT) to `participant` if missing.
  3. Creates the `form_template` and `agenda_template` tables if missing
     (create_all handles it).
  4. Backfills any existing workshop rows whose `form_schema_json` IS NULL
     or empty with the Phase-4 default schema (a single `display_name`
     text field), so demo data from Phases 1-3 keeps working with no
     manual edits.
  5. Phase 6: adds `help_request.status` column (default 'open') and
     `workshop.help_tips_json` column (nullable TEXT). Backfills any
     existing help_requests whose status is NULL/empty to 'open'.

Re-running is safe — every step is a no-op when its conditions don't hold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from src.db import engine, init_db  # noqa: E402
from src.models import DEFAULT_FORM_SCHEMA  # noqa: E402


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_columns(conn) -> list[str]:
    """Add Phase-4 + Phase-6 columns if missing. Returns list of columns added."""
    added: list[str] = []
    # Inspect first (outside any transaction).
    need_ftid = not _column_exists(conn, "workshop", "form_template_id")
    need_schema = not _column_exists(conn, "workshop", "form_schema_json")
    need_answers = not _column_exists(conn, "participant", "answers_json")
    # Phase 6:
    need_help_status = not _column_exists(conn, "help_request", "status")
    need_help_tips = not _column_exists(conn, "workshop", "help_tips_json")

    if need_ftid:
        conn.exec_driver_sql(
            "ALTER TABLE workshop ADD COLUMN form_template_id INTEGER "
            "REFERENCES form_template(id) ON DELETE SET NULL"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_workshop_form_template_id "
            "ON workshop(form_template_id)"
        )
        added.append("workshop.form_template_id")
    if need_schema:
        conn.exec_driver_sql("ALTER TABLE workshop ADD COLUMN form_schema_json TEXT")
        added.append("workshop.form_schema_json")
    if need_answers:
        conn.exec_driver_sql("ALTER TABLE participant ADD COLUMN answers_json TEXT")
        added.append("participant.answers_json")
    if need_help_tips:
        conn.exec_driver_sql("ALTER TABLE workshop ADD COLUMN help_tips_json TEXT")
        added.append("workshop.help_tips_json")
    if need_help_status:
        conn.exec_driver_sql(
            "ALTER TABLE help_request ADD COLUMN status VARCHAR(16) "
            "NOT NULL DEFAULT 'open'"
        )
        added.append("help_request.status")
    conn.commit()
    return added


def _backfill_form_schemas(conn) -> int:
    """Set form_schema_json to the Phase-4 default on existing workshops.

    Only touches rows where the column is NULL or empty — fresh workshops
    created post-upgrade are left alone (they carry whatever the creator
    set, including empty arrays if they hand-cleared the field list).
    Returns the number of rows updated.
    """
    rows = conn.exec_driver_sql(
        "SELECT id FROM workshop WHERE form_schema_json IS NULL OR form_schema_json = ''"
    ).fetchall()
    default_json = json.dumps(DEFAULT_FORM_SCHEMA)
    for (wid,) in rows:
        conn.exec_driver_sql(
            "UPDATE workshop SET form_schema_json = ? WHERE id = ?",
            (default_json, wid),
        )
    conn.commit()
    return len(rows)


def _backfill_help_status(conn) -> int:
    """Set status='open' on existing rows where the column came up empty.

    SQLite ALTER TABLE ADD COLUMN applies the DEFAULT to NEW rows only;
    pre-existing rows get whatever default value the kernel fills in
    (usually NULL for TEXT, even with NOT NULL DEFAULT in older SQLite
    versions). Phase 6 help_request.status needs to be non-NULL 'open'
    for every historical row.
    """
    res = conn.exec_driver_sql(
        "UPDATE help_request SET status = 'open' "
        "WHERE status IS NULL OR status = ''"
    )
    conn.commit()
    return res.rowcount or 0


def main() -> int:
    # Ensure tables exist (idempotent).
    init_db()

    added_columns: list[str] = []
    schema_backfilled = 0
    status_backfilled = 0

    with engine.connect() as conn:
        if not _table_exists(conn, "form_template"):
            print("[migrate] form_template table created by create_all()")
        if not _table_exists(conn, "agenda_template"):
            print("[migrate] agenda_template table created by create_all()")
        added_columns = _ensure_columns(conn)
        schema_backfilled = _backfill_form_schemas(conn)
        status_backfilled = _backfill_help_status(conn)

    print(f"[migrate] columns added: {added_columns or 'none'}")
    print(f"[migrate] workshops backfilled with default form schema: {schema_backfilled}")
    print(f"[migrate] help_requests backfilled with status='open': {status_backfilled}")
    print("[migrate] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
