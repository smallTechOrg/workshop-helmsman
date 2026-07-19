import type { MilestoneStat } from "@/lib/api";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";

export function MilestoneBars({
  milestoneStats,
  totalParticipants,
  crowdMilestoneId,
}: {
  milestoneStats: MilestoneStat[];
  totalParticipants: number;
  /** The milestone where the largest group of participants currently sits. */
  crowdMilestoneId: number | null;
}) {
  const ordered = [...milestoneStats].sort((a, b) => a.position - b.position);

  return (
    <div className="space-y-3">
      {ordered.map((m) => {
        const isCrowd = m.milestone_id === crowdMilestoneId;
        return (
          <div
            key={m.milestone_id}
            data-testid="milestone-stat"
            className={cn(
              "rounded-lg border px-4 py-3",
              isCrowd
                ? "border-brand-300 bg-brand-50/60"
                : "border-stone-200 bg-white",
            )}
          >
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <p className="min-w-0 truncate text-sm font-medium text-stone-800">
                <span className="mr-1.5 text-stone-400">{m.position + 1}.</span>
                {m.title}
              </p>
              <div className="flex items-center gap-2">
                {isCrowd && <Badge tone="brand">most of the room is here</Badge>}
                <span className="text-sm text-stone-600 tabular-nums">
                  {m.completed_count} / {totalParticipants} ·{" "}
                  {Math.round(m.completed_pct)}%
                </span>
              </div>
            </div>
            <ProgressBar
              value={m.completed_pct}
              size="sm"
              tone="success"
              label={`${m.title} completion`}
            />
          </div>
        );
      })}
    </div>
  );
}
