# Data Model — Workshop Helmsman (v0.1)

## Overview
All state in a single SQLite file (`data/helmsman.db`) or PostgreSQL via `DATABASE_URL`.
SQLAlchemy 2.x declarative models; `Base.metadata.create_all` runs at startup (idempotent).
No migration framework in v0.1 — additive columns only.

## Tables

### workshop
```sql
CREATE TABLE workshop (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  name                VARCHAR(200) NOT NULL,
  created_at          DATETIME NOT NULL,
  expires_at          DATETIME NOT NULL,
  admin_token         VARCHAR(64) NOT NULL UNIQUE,
  participant_slug    VARCHAR(64) NOT NULL UNIQUE,
  milestone_config    TEXT NOT NULL,          -- JSON list of {id,title,description}
  archived            BOOLEAN NOT NULL DEFAULT 0,
  form_template_id    INTEGER REFERENCES form_template(id) ON DELETE SET NULL,
  form_schema_json    TEXT NOT NULL DEFAULT '[]',  -- JSON snapshot of form fields
  help_tips_json      TEXT DEFAULT '',        -- facilitator FAQ tips for LLM
  broadcast_message   TEXT DEFAULT '',        -- current broadcast announcement
  workshop_paused     BOOLEAN NOT NULL DEFAULT 0,
  milestone_order_json TEXT DEFAULT '[]'     -- explicit milestone id order (drag-drop)
);
CREATE INDEX ix_workshop_admin_token ON workshop(admin_token);
CREATE INDEX ix_workshop_participant_slug ON workshop(participant_slug);
```

### form_template
```sql
CREATE TABLE form_template (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        VARCHAR(120) NOT NULL,
  created_at  DATETIME NOT NULL,
  fields_json TEXT NOT NULL DEFAULT '[]'   -- JSON list of field dicts
);
```

### agenda_template
```sql
CREATE TABLE agenda_template (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  name             VARCHAR(120) NOT NULL,
  created_at       DATETIME NOT NULL,
  milestones_json  TEXT NOT NULL DEFAULT '[]'   -- JSON list of {title,description,help_tip}
);
```

### participant
```sql
CREATE TABLE participant (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  workshop_id   INTEGER NOT NULL REFERENCES workshop(id) ON DELETE CASCADE,
  name          VARCHAR(120) NOT NULL,
  joined_at     DATETIME NOT NULL,
  answers_json  TEXT                              -- JSON {field_key: value}
);
CREATE INDEX ix_participant_workshop_id ON participant(workshop_id);
```

### milestone_completion
```sql
CREATE TABLE milestone_completion (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id  INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
  milestone_id    VARCHAR(64) NOT NULL,
  milestone_title VARCHAR(200) NOT NULL,
  completed_at    DATETIME NOT NULL
);
CREATE INDEX ix_milestone_completion_participant_id ON milestone_completion(participant_id);
```

### help_request
```sql
CREATE TABLE help_request (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
  message        TEXT NOT NULL,
  created_at     DATETIME NOT NULL,
  status         VARCHAR(16) NOT NULL DEFAULT 'open'  -- open | on_hold | resolved
);
CREATE INDEX ix_help_request_participant_id ON help_request(participant_id);
CREATE INDEX ix_help_request_created_at ON help_request(created_at);
```

## JSON field shapes

### Milestone (in `workshop.milestone_config`)
```json
[
  {"id": "m0", "title": "Setup", "description": "Environment ready"},
  {"id": "m1", "title": "API Key", "description": "LLM key configured"}
]
```
`milestone_order_json` stores an array of milestone IDs in display order: `["m0","m1","m2","m3"]`

### Form field (in `form_template.fields_json` and `workshop.form_schema_json`)
```json
{
  "key": "display_name",
  "type": "text",
  "label": "Display name",
  "placeholder": "e.g. Priya, anu from Delhi",
  "required": true
}
```
Dropdown variant:
```json
{
  "key": "role",
  "type": "dropdown",
  "label": "Your role",
  "required": false,
  "options": ["Student", "Engineer", "Manager", "Other"]
}
```

### Help tips (in `workshop.help_tips_json`)
Plain text, one tip per line. Optional `topic: tip` format:
```
Setup: Make sure Docker is running before starting
API Key: Use the .env file, don't paste keys in chat
```

### Broadcast message (in `workshop.broadcast_message`)
Plain text shown as a pinned banner on participant tracker. Empty = no active broadcast.

## Indexing strategy
- All FK columns indexed (`workshop_id`, `participant_id`)
- Unique constraints on `admin_token`, `participant_slug`
- `help_request.created_at` for pagination ordering
- Composite index not needed at this scale (100-200 participants/workshop)

## Upgrade notes (v0.1 additive columns)
New columns added to existing `workshop` table:
- `broadcast_message` TEXT DEFAULT ''
- `workshop_paused` BOOLEAN DEFAULT 0
- `milestone_order_json` TEXT DEFAULT '[]'
- `help_tips_json` TEXT DEFAULT ''

Run on upgrade:
```sql
ALTER TABLE workshop ADD COLUMN broadcast_message TEXT DEFAULT '';
ALTER TABLE workshop ADD COLUMN workshop_paused BOOLEAN DEFAULT 0;
ALTER TABLE workshop ADD COLUMN milestone_order_json TEXT DEFAULT '[]';
ALTER TABLE workshop ADD COLUMN help_tips_json TEXT DEFAULT '';
```
SQLAlchemy `create_all` handles this idempotently on next boot.