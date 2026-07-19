import type { DashboardStats } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { StubBadge } from "@/components/ui/StubBadge";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium tracking-wide text-stone-500 uppercase">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-stone-900 tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-stone-400">{sub}</p>}
    </Card>
  );
}

export function StatCards({ stats }: { stats: DashboardStats }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Stat label="Participants" value={String(stats.participant_count)} />
      <Stat
        label="Active"
        value={String(stats.active_count)}
        sub="seen in the last 5 min"
      />
      <Stat label="Finished" value={String(stats.finished_count)} />
      <Stat
        label="Median progress"
        value={`${Math.round(stats.median_progress_pct)}%`}
      />
      <Stat
        label="Open help"
        value={String(stats.open_help_count)}
        sub={`${stats.answered_help_count} answered · ${stats.resolved_help_count} resolved`}
      />
      <div
        aria-disabled="true"
        className="rounded-xl border border-dashed border-stone-300 bg-stone-50/70 p-4"
      >
        <p className="text-xs font-medium tracking-wide text-stone-400 uppercase">
          AI spend
        </p>
        <p className="mt-1 text-2xl font-semibold text-stone-300 tabular-nums">$—</p>
        <StubBadge className="mt-1" />
      </div>
    </div>
  );
}
