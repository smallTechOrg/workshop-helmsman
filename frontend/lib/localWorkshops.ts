/**
 * "Your workshops" — a browser-local convenience list of workshops created from
 * this browser (spec/capabilities.md C5 §4, C6 §Success screen).
 *
 * This is NEVER authentication. The workshop's `facilitator_url` is the only
 * credential; this list just saves the creator from losing it in their history.
 * Clearing the browser loses the list (and the link) — the landing page and FAQ
 * say so plainly.
 */

const LS_KEY = "helmsman_my_workshops";
const MAX_ENTRIES = 20;

export interface LocalWorkshop {
  name: string;
  facilitator_url: string;
  join_url: string;
  created_at: string;
}

function isEntry(v: unknown): v is LocalWorkshop {
  if (typeof v !== "object" || v === null) return false;
  const o = v as Record<string, unknown>;
  return (
    typeof o.name === "string" &&
    typeof o.facilitator_url === "string" &&
    typeof o.join_url === "string" &&
    typeof o.created_at === "string"
  );
}

/** Never throws: private-mode browsers and corrupt values yield `[]`. */
export function loadLocalWorkshops(): LocalWorkshop[] {
  if (typeof window === "undefined") return [];
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(LS_KEY);
  } catch {
    return [];
  }
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isEntry).slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

/** Prepends `entry` (de-duped by facilitator_url), capped at the 20 newest. */
export function saveLocalWorkshop(entry: LocalWorkshop): LocalWorkshop[] {
  const next = [
    entry,
    ...loadLocalWorkshops().filter(
      (w) => w.facilitator_url !== entry.facilitator_url,
    ),
  ].slice(0, MAX_ENTRIES);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(LS_KEY, JSON.stringify(next));
    } catch {
      // Private mode / quota — the reveal screen still shows the links.
    }
  }
  return next;
}

/** Used by "Forget this workshop" — removes the entry, not the workshop. */
export function forgetLocalWorkshop(facilitatorUrl: string): LocalWorkshop[] {
  const next = loadLocalWorkshops().filter(
    (w) => w.facilitator_url !== facilitatorUrl,
  );
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(LS_KEY, JSON.stringify(next));
    } catch {
      // ignore
    }
  }
  return next;
}
