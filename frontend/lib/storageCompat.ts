/**
 * One-release localStorage migration (Workshop0 rename). If the new key is
 * absent, read the pre-rename key and write its value under the new key. The
 * old key is deliberately never deleted this release.
 */
export const LEGACY_KEYS: Record<string, string> = {
  workshop0_admin_key: "helmsman_admin_key", // LEGACY-COMPAT
  workshop0_my_workshops: "helmsman_my_workshops", // LEGACY-COMPAT
};

/** Throws if localStorage is unavailable (callers already wrap in try/catch). */
export function getWithLegacy(newKey: string): string | null {
  const current = window.localStorage.getItem(newKey);
  if (current !== null) return current;
  const legacyKey = LEGACY_KEYS[newKey];
  if (!legacyKey) return null;
  const old = window.localStorage.getItem(legacyKey);
  if (old !== null) window.localStorage.setItem(newKey, old);
  return old;
}
