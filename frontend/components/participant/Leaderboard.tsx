"use client";

import type { LeaderboardRow, TrackerMe } from "@/lib/api";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cn } from "@/lib/format";

const MEDAL_STYLES: Record<number, string> = {
  1: "bg-amber-100 text-amber-700 border-amber-300",
  2: "bg-stone-100 text-stone-600 border-stone-300",
  3: "bg-orange-100 text-orange-700 border-orange-300",
};

// Server sends the top N plus (when outside it) the caller's own row.
const TOP_N = 15;

export function Leaderboard({
  rows,
  me,
  participantsCount,
}: {
  rows: LeaderboardRow[];
  me: TrackerMe;
  participantsCount: number;
}) {
  const topRows = rows.filter((row) => row.rank <= TOP_N);
  const myTrailingRow = rows.find((row) => row.is_me && row.rank > TOP_N);
  return (
    <div>
      <p className="mb-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
        You're <span className="font-semibold">#{me.rank}</span> of {participantsCount} —{" "}
        {me.completed_count} of {me.total_count} done
      </p>
      {participantsCount > topRows.length && (
        <p className="mb-1.5 px-1 text-xs text-stone-400">
          Top {Math.min(TOP_N, participantsCount)} of {participantsCount}
        </p>
      )}
      <ol data-testid="leaderboard" className="space-y-1">
        {[...topRows, ...(myTrailingRow ? [myTrailingRow] : [])].map((row) => (
          <li
            key={`${row.rank}-${row.name}`}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5",
              row.is_me ? "bg-brand-50 ring-1 ring-brand-200" : "hover:bg-stone-50",
              row.rank > TOP_N && "mt-2 border-t border-dashed border-stone-200 pt-2",
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
                "min-w-0 flex-1 truncate text-sm",
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
