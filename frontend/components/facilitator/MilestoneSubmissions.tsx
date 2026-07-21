"use client";

import { useState } from "react";
import type { DashboardParticipant, MilestoneStat } from "@/lib/api";

/**
 * Collects, per input-gated milestone, what each participant submitted (the
 * GitHub URL, link, text, or choice they entered to complete it). Renders
 * nothing when no milestone requires an input.
 */
export function MilestoneSubmissions({
  milestoneStats,
  participants,
}: {
  milestoneStats: MilestoneStat[];
  participants: DashboardParticipant[];
}) {
  const gated = milestoneStats.filter((m) => m.input_config);
  const [openId, setOpenId] = useState<number | null>(gated[0]?.milestone_id ?? null);

  if (gated.length === 0) return null;

  return (
    <div className="space-y-3" data-testid="milestone-submissions">
      {gated.map((m) => {
        const isUrl =
          m.input_config?.type === "github_url" || m.input_config?.type === "url";
        const rows = participants
          .map((p) => ({ name: p.name, value: p.milestone_inputs?.[String(m.milestone_id)] }))
          .filter((r): r is { name: string; value: string } => Boolean(r.value));
        const open = openId === m.milestone_id;
        return (
          <div
            key={m.milestone_id}
            data-testid="submission-group"
            className="rounded-lg border border-stone-200"
          >
            <button
              type="button"
              onClick={() => setOpenId(open ? null : m.milestone_id)}
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
            >
              <span className="min-w-0 truncate text-sm font-medium text-stone-800">
                {m.position + 1}. {m.title}
                <span className="ml-2 font-normal text-stone-400">
                  ({m.input_config?.label})
                </span>
              </span>
              <span className="shrink-0 text-xs text-stone-500">
                {rows.length} submitted
              </span>
            </button>
            {open && (
              <ul className="divide-y divide-stone-100 border-t border-stone-100">
                {rows.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-stone-400">
                    No submissions yet.
                  </li>
                ) : (
                  rows.map((r, i) => (
                    <li
                      key={i}
                      className="flex items-baseline justify-between gap-3 px-3 py-1.5 text-sm"
                    >
                      <span className="shrink-0 font-medium text-stone-700">{r.name}</span>
                      {isUrl ? (
                        <a
                          href={r.value}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="min-w-0 truncate text-right font-mono text-xs text-brand-600 hover:underline"
                        >
                          {r.value}
                        </a>
                      ) : (
                        <span className="min-w-0 truncate text-right text-stone-600">
                          {r.value}
                        </span>
                      )}
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
