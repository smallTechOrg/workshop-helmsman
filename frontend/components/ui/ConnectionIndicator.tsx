"use client";

/**
 * Quiet "reconnecting…" pill — appears after 2 consecutive failed polls,
 * clears silently on recovery (architecture.md §Error handling).
 */
export function ConnectionIndicator({ reconnecting }: { reconnecting: boolean }) {
  if (!reconnecting) return null;
  return (
    <span
      role="status"
      className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800"
    >
      <span
        aria-hidden="true"
        className="size-1.5 animate-pulse rounded-full bg-amber-500"
      />
      Reconnecting…
    </span>
  );
}
