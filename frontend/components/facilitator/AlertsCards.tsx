import type { DashboardAlerts } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export function StuckCard({ alerts }: { alerts: DashboardAlerts | null }) {
  const stuck = alerts?.stuck ?? [];
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-stone-900">Stuck participants</h3>
        {stuck.length > 0 && <Badge tone="warning">{stuck.length}</Badge>}
      </div>
      {stuck.length === 0 ? (
        <p data-testid="stuck-clear" className="text-sm text-stone-500">
          All clear — everyone's active.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {stuck.map((s) => (
            <li
              key={s.participant_id}
              data-testid="stuck-alert-card"
              className="flex items-center justify-between gap-2 text-sm"
            >
              <span className="min-w-0 truncate text-stone-800">{s.name}</span>
              <span className="shrink-0 text-stone-500 tabular-nums">
                {s.minutes_inactive} minutes inactive
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function BottleneckCard({ alerts }: { alerts: DashboardAlerts | null }) {
  const bottleneck = alerts?.bottleneck ?? null;
  return (
    <Card className="p-4">
      <h3 className="mb-2 text-sm font-semibold text-stone-900">Bottleneck</h3>
      {!bottleneck ? (
        <p data-testid="bottleneck-clear" className="text-sm text-stone-500">
          All clear — no pile-up right now.
        </p>
      ) : (
        <p data-testid="bottleneck-row" className="text-sm text-stone-700">
          <span className="font-medium">{bottleneck.title}</span> — {bottleneck.waiting_count}{" "}
          waiting here
        </p>
      )}
    </Card>
  );
}
