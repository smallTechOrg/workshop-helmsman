"use client";

import { useState, useEffect } from "react";
import { Markdown } from "@/components/ui/Markdown";
import type { BroadcastInfo } from "@/lib/api";

/**
 * Pinned facilitator broadcast banner. Dismiss is local-only — the banner
 * reappears if a NEW broadcast (different id) arrives.
 */
export function BroadcastBanner({ broadcast }: { broadcast: BroadcastInfo | null }) {
  const [dismissedId, setDismissedId] = useState<number | null>(null);

  useEffect(() => {
    if (!broadcast) return;
    // Nothing to do — dismissal is tracked per id, re-shows automatically
    // whenever the id changes (handled by the render check below).
  }, [broadcast]);

  if (!broadcast || dismissedId === broadcast.id) return null;

  return (
    <div
      role="status"
      data-testid="broadcast-banner"
      className="border-b border-brand-200 bg-brand-50/80 px-4 py-2.5"
    >
      <div className="mx-auto flex max-w-6xl items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 shrink-0 rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-semibold text-white"
        >
          FACILITATOR
        </span>
        <div className="min-w-0 flex-1 text-sm text-stone-800">
          <Markdown className="prose-sm [&_p]:m-0">{broadcast.message_md}</Markdown>
        </div>
        <button
          type="button"
          aria-label="Dismiss broadcast"
          onClick={() => setDismissedId(broadcast.id)}
          className="shrink-0 rounded-md p-1 text-stone-500 hover:bg-stone-200/60 hover:text-stone-700"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
