import * as fs from 'node:fs';
import * as path from 'node:path';

/** Single origin (architecture.md §Process model): one uvicorn worker on :8001. */
export const ORIGIN = 'http://localhost:8001';
/** Canonical app base — the built Next.js export mounted by FastAPI. */
export const APP_BASE = `${ORIGIN}/app`;

let cachedAdminKey: string | null = null;

/**
 * Resolve HELMSMAN_ADMIN_KEY: process.env first, else parse the repo-root
 * `.env` file (simple line parse — no dotenv dependency). The value is only
 * ever typed into the admin-key field; it is never logged or asserted on.
 */
export function adminKey(): string {
  if (cachedAdminKey) return cachedAdminKey;

  const fromEnv = process.env.HELMSMAN_ADMIN_KEY;
  if (fromEnv && fromEnv.trim()) {
    cachedAdminKey = fromEnv.trim();
    return cachedAdminKey;
  }

  const envPath = path.resolve(__dirname, '..', '..', '.env');
  let raw: string;
  try {
    raw = fs.readFileSync(envPath, 'utf8');
  } catch {
    throw new Error(
      'HELMSMAN_ADMIN_KEY is not set in the environment and the repo-root .env file is not readable. ' +
        'Run `cp .env.example .env` and set HELMSMAN_ADMIN_KEY before the e2e gate.',
    );
  }

  for (const line of raw.split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?HELMSMAN_ADMIN_KEY\s*=\s*(.*)$/);
    if (!match) continue;
    let value = match[1].trim();
    if (
      (value.startsWith('"') && value.endsWith('"') && value.length >= 2) ||
      (value.startsWith("'") && value.endsWith("'") && value.length >= 2)
    ) {
      value = value.slice(1, -1);
    }
    if (value) {
      cachedAdminKey = value;
      return cachedAdminKey;
    }
  }

  throw new Error(
    'HELMSMAN_ADMIN_KEY is missing/empty in both the environment and the repo-root .env file.',
  );
}

/**
 * Pull the first absolute pretty URL of a given kind (/j/, /p/ or /f/) out of
 * an element's visible text (link elements may also contain copy-button text).
 */
export function extractUrl(text: string, kind: '/j/' | '/p/' | '/f/'): string {
  const escaped = kind.replace(/\//g, '\\/');
  const re = new RegExp(`https?:\\/\\/\\S+${escaped}[A-Za-z0-9_-]+`);
  const match = text.match(re);
  if (!match) {
    throw new Error(`Expected a full ${kind} URL in element text, got: ${JSON.stringify(text)}`);
  }
  return match[0];
}
