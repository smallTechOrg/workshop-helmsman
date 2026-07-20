import type { DistributionBucket } from "@/lib/api";

/** Histogram of participants by completed-count — the room's shape at a glance. */
export function DistributionChart({
  distribution,
}: {
  distribution: DistributionBucket[];
}) {
  const ordered = [...distribution].sort(
    (a, b) => a.completed_count - b.completed_count,
  );
  const max = Math.max(1, ...ordered.map((b) => b.participants));

  return (
    <div>
      <div
        role="img"
        aria-label="Histogram of participants by number of milestones completed"
        className="flex h-28 items-end gap-1.5"
      >
        {ordered.map((b) => (
          <div
            key={b.completed_count}
            className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1 self-stretch"
          >
            <span className="text-[10px] text-stone-500 tabular-nums">
              {b.participants > 0 ? b.participants : ""}
            </span>
            <div
              className="w-full rounded-t-sm bg-brand-500/80 transition-[height] duration-500"
              style={{
                height: `${Math.max(b.participants > 0 ? 6 : 2, (b.participants / max) * 80)}%`,
              }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5 border-t border-stone-200 pt-1">
        {ordered.map((b) => (
          <span
            key={b.completed_count}
            className="min-w-0 flex-1 text-center text-[10px] text-stone-400 tabular-nums"
          >
            {b.completed_count}
          </span>
        ))}
      </div>
      <p className="mt-1 text-center text-[11px] text-stone-400">
        milestones completed
      </p>
    </div>
  );
}
