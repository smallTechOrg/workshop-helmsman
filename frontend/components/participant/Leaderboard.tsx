"use client";

import type { LeaderboardRow, TrackerMe } from "@/lib/api";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cn } from "@/lib/format";

const MEDAL_STYLES: Record<number, string> = {
  1: "bg-amber-100 text-amber-700 border-amber-300",
  2: "bg-stone-100 text-stone-600 border-stone-300",
  3: "bg-orange-100 text-orange-700 border-orange-300",
};

export function Leaderboard({
  rows,
  me,
}: {
  rows: LeaderboardRow[];
  me: TrackerMe;
}) {
  return (
    <div>
      <p className="mb-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
        You're <span className="font-semibold">#{me.rank}</span> of {rows.length} —{" "}
        {me.completed_count} of {me.total_count} done
      </p>
      <ol data-testid="leaderboard" className="space-y-1">
        {rows.map((row) => (
          <li
            key={`${row.rank}-${row.name}`}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5",
              row.is_me ? "bg-brand-50 ring-1 ring-brand-200" : "hover:bg-stone-50",
            )}
          >
            <span
              className={cn(
                "inline-flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums",
                MEDAL_STYLES[row.rank] ?? "border-transparent text-stone-500",
              )}
            >
              {row.rank}
            </span>
            <span
              className={cn(
                "min-w-0 flex-1 truncate text-sm whitespace-pre",
                row.is_me ? "font-semibold text-brand-900" : "text-stone-700",
              )}
            >
              {row.name}
              {row.is_me && <span className="ml-1.5 text-xs text-brand-600">(you)</span>}
            </span>
            <ProgressBar
              value={row.progress_pct}
              size="sm"
              className="w-14 shrink-0"
              label={`${row.name}'s progress`}
            />
            <span className="w-6 shrink-0 text-right text-xs text-stone-500 tabular-nums">
              {row.completed_count}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
