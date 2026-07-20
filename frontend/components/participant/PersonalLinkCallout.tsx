"use client";

import { useState } from "react";
import { CopyButton } from "@/components/ui/CopyButton";

/**
 * "Save this link" callout. Dismissing collapses it to a compact row — the
 * personal link itself always stays on the page (it's the cross-device
 * credential and the e2e contract expects it present).
 */
export function PersonalLinkCallout({
  url,
  storageKey,
}: {
  url: string;
  storageKey: string;
}) {
  const [dismissed, setDismissed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(storageKey) === "1";
    } catch {
      return false;
    }
  });

  const dismiss = () => {
    setDismissed(true);
    try {
      window.localStorage.setItem(storageKey, "1");
    } catch {
      // localStorage unavailable — dismissal just won't persist.
    }
  };

  if (dismissed) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm">
        <span className="text-stone-500">Your personal link:</span>
        <span
          data-testid="personal-link"
          className="min-w-0 flex-1 truncate font-mono text-xs text-stone-600"
        >
          {url}
        </span>
        <CopyButton text={url} aria-label="Copy your personal link" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-brand-900">
            This page's link is yours — it works on any device.
          </p>
          <p className="mt-0.5 text-sm text-brand-800">
            Save it to continue on another device or if this browser forgets you.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              data-testid="personal-link"
              className="min-w-0 max-w-full truncate rounded-md border border-brand-200 bg-white px-2 py-1 font-mono text-xs text-brand-900"
            >
              {url}
            </span>
            <CopyButton text={url} aria-label="Copy your personal link" />
          </div>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss this reminder"
          className="rounded-md p-1 text-brand-400 hover:bg-brand-100 hover:text-brand-700"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
