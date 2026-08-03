"use client";

/**
 * Landing-page section 4 (spec/capabilities.md C5 §4) — a small client island so
 * the rest of the landing page stays a static server component.
 *
 * Renders NOTHING on a fresh browser: no empty state, no teaser. It only shows
 * once this browser has created a workshop.
 */

import { useEffect, useState } from "react";
import { CopyButton } from "@/components/ui/CopyButton";
import { formatDate } from "@/lib/format";
import {
  forgetLocalWorkshop,
  loadLocalWorkshops,
  type LocalWorkshop,
} from "@/lib/localWorkshops";

export function YourWorkshops() {
  // `null` = not read yet (server render + first paint): render nothing, so
  // there is no hydration mismatch and no layout shift for fresh browsers.
  const [items, setItems] = useState<LocalWorkshop[] | null>(null);

  useEffect(() => {
    setItems(loadLocalWorkshops());
  }, []);

  if (items === null || items.length === 0) return null;

  return (
    <section
      id="your-workshops"
      data-testid="your-workshops"
      aria-labelledby="your-workshops-heading"
      className="border-y border-brand-100 bg-brand-50/60"
    >
      <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6">
        <h2
          id="your-workshops-heading"
          className="text-2xl font-semibold tracking-tight text-stone-900 sm:text-3xl"
        >
          Your workshops
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-stone-600">
          Remembered by this browser only — not an account. Keep your dashboard link
          somewhere safe.
        </p>

        <ul className="mt-6 grid gap-4 sm:grid-cols-2">
          {items.map((w) => (
            <li
              key={w.facilitator_url}
              className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm"
            >
              <div>
                <h3 className="text-base font-semibold text-stone-900">{w.name}</h3>
                <p className="mt-0.5 text-xs text-stone-500">
                  Created {formatDate(w.created_at)}
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <a
                    data-testid="your-workshop-link"
                    href={w.facilitator_url}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-700"
                  >
                    Open dashboard
                    <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
                      <path fillRule="evenodd" d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z" clipRule="evenodd" />
                    </svg>
                  </a>
                  <CopyButton
                    text={w.join_url}
                    label="Copy join link"
                    className="px-2.5 py-1.5 text-sm"
                    aria-label={`Copy the join link for ${w.name}`}
                  />
                  <button
                    type="button"
                    onClick={() => setItems(forgetLocalWorkshop(w.facilitator_url))}
                    className="ml-auto rounded-lg px-2 py-1 text-xs font-medium text-stone-500 hover:bg-stone-200 hover:text-stone-700"
                  >
                    Forget
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
