# Capability brief — Public landing page + self-service workshop creation

## What we're adding

Workshop Helmsman is currently a private, single-tenant tool: the root URL is an admin
key gate, and only someone holding `HELMSMAN_ADMIN_KEY` can create a workshop. We are
opening it to the public. Two things change, and nothing else.

**1. A public marketing landing page at `/`.** Today `/` 307-redirects into the admin
console. It becomes a real, elaborate marketing page explaining what a facilitator gets
from Workshop Helmsman: live progress dashboard across 300+ participants, content-rich
markdown/code milestones, frictionless name-only joining with cookie auto-resume and
personal cross-device links, a real-time help desk, broadcast/pause/advance room controls,
proactive stuck-and-bottleneck alerts, audit trail, CSV export. Hero with a single primary
CTA ("Create your workshop — free, no signup"), feature sections, a "how it works" walkthrough
of the facilitator→participant loop, and an FAQ covering the honest limits (browser-based
access, no account, keep your dashboard link). It must be visually excellent and consistent
with the existing design system — this is the first thing a stranger sees. Responsive,
light/dark per the existing theme handling.

**2. Self-service workshop creation with no access key.** Anyone can create and host their
own workshop. The creation flow is the *same flow the admin already uses* — same milestone
composer, same markdown/code content, same join-form config — reached from the landing CTA
instead of from behind the key gate. On completion the creator is shown their facilitator
dashboard link (and the join link), and lands on the normal facilitator dashboard.

## Permissions and access model

There are **no user accounts and no login**. Access is entirely link- and browser-based,
exactly as it is today:

- A public creator gets the workshop's `admin_token` facilitator link. That link is their
  only credential. The facilitator surface is already fully scoped to a single workshop by
  `admin_token`, so a public creator automatically cannot see or touch any other workshop.
- On their own workshop a public creator has **full facilitator parity** with an
  admin-created workshop — broadcast, pause, advance, reorder, edit/add/delete milestones,
  undo, help desk, audit tab, CSV export, settings. No reduced tier. The only thing they
  lack is the cross-workshop view.
- The creator's browser remembers their workshop(s) in localStorage so returning to the
  landing page offers "your workshops" quick links. This is a convenience, not auth —
  clearing the browser loses the link, and the landing page + FAQ must say so plainly and
  prompt them to save/copy the dashboard link at creation time.
- **The admin** (holder of `HELMSMAN_ADMIN_KEY`) alone sees the full picture: every
  workshop, public-created ones included, in one list. The admin console moves off `/`.

## Routing

The frontend is a single Next.js static export mounted at `/app`; `/` currently redirects
to `/app/`. After this change:

- `/` → the public marketing landing page.
- The public create flow lives on the public side (e.g. `/app/create/`), no key required.
- The admin console (key gate + all-workshops list, unchanged behaviour) moves to
  `/app/admin/`, with a pretty `/admin` redirect. It is **not** linked from the landing page.
- `/f/<admin_token>`, `/j/<join_slug>`, `/p/<participant_token>` are untouched.

## Abuse guard

Public creation requires an **email address from the creator, collected at the very end of
the flow** — after they have composed the workshop, as the last step before the dashboard
link is revealed. The email is stored on the workshop record and visible to the admin in
the all-workshops list. No mail is sent (there is no mail infrastructure): the dashboard
link is shown on screen and copyable. Validate format, store it, surface it to admin. This
is the deterrent + contact trail; no rate limiting, no cap, no captcha in this phase.

## Constraints

- Same stack, same repo, extend in place: FastAPI + SQLAlchemy + Alembic + SQLite/Postgres,
  Next.js static export, single origin on :8001. No new services, no LLM involvement.
- The public create endpoint must reuse the existing creation service/validation rather
  than forking it, so admin-created and public-created workshops are identical records
  apart from the creator email and a flag marking origin.
- Migration required for the new workshop columns (creator email, origin).
- Existing admin flow, facilitator surface, participant surface and all current tests must
  keep working unchanged.

## Core path for the phase (the one thing that proves it)

A stranger opens `/`, reads the marketing page, clicks "Create your workshop", composes a
workshop with markdown/code milestones, enters their email at the end, is shown their
dashboard + join links, opens the join link in another browser and joins as a participant,
and sees that participant appear live on their own dashboard — never having touched an
access key. Meanwhile the admin at `/admin` enters the key and sees that same workshop in
the full list with the creator's email.
