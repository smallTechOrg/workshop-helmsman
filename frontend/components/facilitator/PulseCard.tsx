import type { DashboardPulse } from "@/lib/api";
import { Card } from "@/components/ui/Card";

function paceLabel(paceRatio: number): { label: string; tone: string } {
  if (paceRatio <= 1.05) return { label: "On plan", tone: "text-emerald-700" };
  if (paceRatio <= 1.3) return { label: "Slightly slower", tone: "text-amber-700" };
  return { label: "Slower than plan", tone: "text-red-700" };
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function PulseCard({ pulse }: { pulse: DashboardPulse | null }) {
  return (
    <Card className="p-4" data-testid="pulse-card">
      <h3 className="mb-3 text-sm font-semibold text-stone-900">Session pulse</h3>
      {!pulse ? (
        <p className="text-sm text-stone-500">
          Pace, on-track %, and a projected finish time appear once participants make progress.
        </p>
      ) : (
        <dl className="grid grid-cols-2 gap-3 text-sm" data-testid="pulse-stats">
          <div>
            <dt className="text-xs text-stone-500">Pace vs plan</dt>
            <dd className={`font-medium ${paceLabel(pulse.pace_ratio).tone}`}>
              {paceLabel(pulse.pace_ratio).label}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-stone-500">On track</dt>
            <dd className="font-medium text-stone-800 tabular-nums">
              {Math.round(pulse.on_track_pct)}%
            </dd>
          </div>
          <div>
            <dt className="text-xs text-stone-500">Open help</dt>
            <dd className="font-medium text-stone-800 tabular-nums">
              {pulse.open_help_count}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-stone-500">Projected finish</dt>
            <dd className="font-medium text-stone-800">
              {pulse.projected_finish_at ? formatTime(pulse.projected_finish_at) : "—"}
            </dd>
          </div>
        </dl>
      )}
    </Card>
  );
}
