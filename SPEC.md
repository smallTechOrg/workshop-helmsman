# Workshop Helmsman — World-Class UX Specification

## Architecture (Clean Separation)
| URL | Purpose |
|-----|---------|
| `/` | Marketing landing |
| `/console` | **Master console** — secret URL, workshop table, "+ New Workshop" |
| `/console/workshop/new` | **Create Workshop Wizard** — 5 steps |
| `/admin/<token>` | **Per-workshop admin** — broadcast, pause, advance, reorder, CSV |
| `/w/<slug>` | Participant join — instant validation |
| `/w/<slug>/me` | Participant tracker — broadcast banner, progress, milestones, leaderboard |

---

## Create Workshop Wizard — 5 Steps

### Step 1: Basics
- Workshop name (required, max 120 chars)
- Duration: dropdown [2h, 4h, 8h, 16h, 24h, Custom]
- Template picker: dropdown [Blank, 4-Phase, 6-Phase Sprint, 3-Phase Quickstart] — pre-fills milestones

### Step 2: Milestones (Drag-drop reorderable list)
- **Each milestone row:** drag handle | Title (inline edit on click) | Duration dropdown [15m, 30m, 45m, 60m, 90m, 120m, Custom] | Facilitator tip (icon, hover tooltip) | Description (optional, inline edit) | Category badge [Setup, Learning, Hands-on, Break, Q&A, Wrap-up] | Delete
- Add milestone button (+)
- Template picker applies preset milestones

### Step 3: Participant Form Builder
- Always: Full Name (text, required, locked at top)
- Add field: button opens modal → Field type [Text, Email, Dropdown] | Label | Required toggle | Placeholder | Options (for dropdown, comma-separated)
- Fields list: drag to reorder | Edit | Delete
- Required fields marked with *

### Step 4: Knowledge Base / Resources (Future Phase)
- Google Drive folder link input
- Placeholder for future: "Link Google Drive folder for slides, docs, resources"

### Step 5: Review & Create
- Summary cards: Basics | Milestones (count, total time) | Form fields | KB link
- Edit buttons per section
- "Create Workshop" → creates workshop, redirects to `/admin/<token>`

---

## Console (Master) — `/console`
- Table: Name | Created | Status (Live/Ended/Archived) | Attendees | Actions [Admin, Participant link, Edit, Clone, Archive]
- "+ New Workshop" button → `/console/workshop/new`
- Status badges: Live (green), Ended (orange), Archived (gray)

---

## Per-Workshop Admin Dashboard — `/admin/<token>`
**Dashboard Cards (clickable):**
- Live count | Active now | Avg progress % | Help flags

**Tabs:**
- **Participants:** Table with inline actions (Advance, Pause, Broadcast to one)
- **Milestones:** Drag-drop reorder, Advance all, Advance selected, Pause/Resume
- **Broadcast:** Composer + history
- **Help Flags:** List with status pills (Open/On Hold/Resolved)
- **Export CSV**

---

## Participant Flow
- `/w/<slug>` → Join form (instant validation, autocomplete off, autocapitalize words)
- `/w/<slug>/me` → Tracker: progress bar, milestone list (click to complete, disabled when paused), leaderboard, broadcast banner (dismissible), help flag 2-step (preview with LLM suggestion → commit)

---

## Field Types (Form Builder)
| Type | Config |
|------|--------|
| Text | Label, Placeholder, Required |
| Email | Label, Placeholder, Required |
| Dropdown | Label, Options (comma-separated), Required |

**Always required (locked):** Full Name (text, required)

---

## Milestone Fields (Inline Edit on Click)
| Field | Type | Required |
|-------|------|----------|
| Title | Inline text | Yes |
| Description | Inline textarea (optional) | No |
| Duration | Dropdown [15m, 30m, 45m, 60m, 90m, 120m, Custom] | Yes |
| Category | Badge [Setup, Learning, Hands-on, Break, Q&A, Wrap-up] | Yes |
| Facilitator Tip | Tooltip icon (hover) | No |

---

## Visual Language (World-Class)
- **Design tokens:** 8px spacing scale, 4/8/12/16px radius, elevation shadows
- **Color:** Dark default (#0b0f1a bg), accent blue (#7aa2ff), live green, warn amber, danger red
- **Typography:** System font stack, clamp() fluid sizing
- **Motion:** 120ms fast, 200ms normal, 350ms slow; prefers-reduced-motion
- **Touch targets:** 44px minimum
- **Dark default, light mode optional**

---

## Data Model
```python
Workshop: id, name, created_at, expires_at, admin_token, participant_slug, 
          milestone_config (JSON), form_schema (JSON), kb_link, 
          archived, paused, broadcast_message, milestone_order

Milestone: id, title, description, duration_min, category, facilitator_tip, order

FormField: key, type (text|email|dropdown), label, placeholder, required, options

Participant: id, workshop_id, name, answers (JSON), joined_at

MilestoneCompletion: participant_id, milestone_id, milestone_title, completed_at

HelpRequest: participant_id, message, status (open/on_hold/resolved), created_at
```