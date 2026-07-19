"use client";

import { useState } from "react";
import type { MilestoneMeta } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Markdown } from "@/components/ui/Markdown";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/format";

export function MilestoneList({
  milestones,
  contentById,
  completedIds,
  currentId,
  paused,
  onToggle,
}: {
  milestones: MilestoneMeta[];
  /** Milestone bodies from the content endpoint; null while still loading. */
  contentById: Map<number, string> | null;
  completedIds: Set<number>;
  currentId: number | null;
  paused: boolean;
  onToggle: (milestoneId: number, completed: boolean) => void;
}) {
  // User-driven expansion overrides; default = expanded unless completed.
  const [expandOverride, setExpandOverride] = useState<Record<number, boolean>>({});

  const ordered = [...milestones].sort((a, b) => a.position - b.position);

  return (
    <ol className="space-y-3">
      {ordered.map((m) => {
        const done = completedIds.has(m.id);
        const isCurrent = m.id === currentId;
        const expanded = expandOverride[m.id] ?? !done;
        const body = contentById?.get(m.id);

        return (
          <li
            key={m.id}
            data-testid="milestone-item"
            className={cn(
              "rounded-xl border bg-white shadow-sm transition-colors",
              isCurrent
                ? "border-brand-300 ring-1 ring-brand-300"
                : done
                  ? "border-emerald-200"
                  : "border-stone-200",
            )}
          >
            <div className="flex items-center gap-3 px-4 py-3">
              <input
                type="checkbox"
                data-testid="milestone-toggle"
                className="check-input"
                checked={done}
                disabled={paused}
                onChange={(e) => onToggle(m.id, e.target.checked)}
                aria-label={`Mark “${m.title}” ${done ? "not done" : "done"}`}
              />
              <button
                type="button"
                onClick={() =>
                  setExpandOverride((prev) => ({ ...prev, [m.id]: !expanded }))
                }
                aria-expanded={expanded}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
              >
                <span
                  className={cn(
                    "min-w-0 flex-1 font-medium",
                    done ? "text-stone-400 line-through" : "text-stone-900",
                  )}
                >
                  <span className="mr-1.5 text-stone-400">{m.position + 1}.</span>
                  {m.title}
                </span>
                {isCurrent && !done && <Badge tone="brand">You are here</Badge>}
                {m.minutes !== null && (
                  <Badge tone="neutral">{m.minutes} min</Badge>
                )}
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className={cn(
                    "size-4 shrink-0 text-stone-400 transition-transform",
                    expanded && "rotate-180",
                  )}
                >
                  <path
                    fillRule="evenodd"
                    d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </div>

            {/* Body stays in the DOM; visibility is toggled so state is cheap. */}
            <div
              hidden={!expanded}
              className="border-t border-stone-100 px-4 py-3 pl-[3.25rem]"
            >
              {body !== undefined ? (
                body.trim() === "" ? (
                  <p className="text-sm text-stone-400">
                    No instructions for this milestone — just do it and check it off.
                  </p>
                ) : (
                  <Markdown>{body}</Markdown>
                )
              ) : (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-16 w-full" />
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
