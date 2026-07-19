"use client";

import { useMemo, useState } from "react";
import type { DashboardParticipant, MilestoneStat } from "@/lib/api";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Badge } from "@/components/ui/Badge";
import { CopyButton } from "@/components/ui/CopyButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, timeAgo } from "@/lib/format";

type SortKey = "joined" | "name" | "progress";

export function ParticipantTable({
  participants,
  milestoneStats,
  joinUrl,
  nowMs,
}: {
  participants: DashboardParticipant[];
  milestoneStats: MilestoneStat[];
  joinUrl: string;
  nowMs: number;
}) {
  const [sort, setSort] = useState<SortKey>("joined");
  const [filter, setFilter] = useState("");

  const milestoneOrder = useMemo(
    () => [...milestoneStats].sort((a, b) => a.position - b.position),
    [milestoneStats],
  );

  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? participants.filter((p) => p.name.toLowerCase().includes(q))
      : [...participants];
    switch (sort) {
      case "name":
        filtered.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case "progress":
        filtered.sort(
          (a, b) =>
            b.completed_count - a.completed_count || a.name.localeCompare(b.name),
        );
        break;
      case "joined":
      default:
        filtered.sort((a, b) => a.joined_at.localeCompare(b.joined_at));
        break;
    }
    return filtered;
  }, [participants, sort, filter]);

  if (participants.length === 0) {
    return (
      <EmptyState
        icon="🚪"
        title="No participants yet"
        hint={`Share the join link — everyone who joins appears here live: ${joinUrl}`}
      />
    );
  }

  const totalMilestones = milestoneOrder.length;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label htmlFor="pt-filter" className="sr-only">
          Filter participants by name
        </label>
        <input
          id="pt-filter"
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name…"
          className="w-48 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
        />
        <div
          role="group"
          aria-label="Sort participants"
          className="flex overflow-hidden rounded-lg border border-stone-300 bg-white text-sm"
        >
          {(
            [
              ["joined", "Joined"],
              ["name", "Name"],
              ["progress", "Progress"],
            ] as [SortKey, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setSort(key)}
              aria-pressed={sort === key}
              className={cn(
                "px-3 py-1.5 font-medium",
                sort === key
                  ? "bg-brand-600 text-white"
                  : "text-stone-600 hover:bg-stone-50",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-sm text-stone-500 tabular-nums">
          {rows.length} of {participants.length}
        </span>
      </div>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-center text-sm text-stone-500">
          No participant matches “{filter.trim()}”.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-stone-200">
          <table className="w-full min-w-[760px] border-collapse bg-white text-sm">
            <thead>
              <tr className="border-b border-stone-200 bg-stone-50 text-left text-xs tracking-wide text-stone-500 uppercase">
                <th scope="col" className="px-3 py-2 font-medium">Name</th>
                <th scope="col" className="px-3 py-2 font-medium">Progress</th>
                <th scope="col" className="px-3 py-2 font-medium">Milestones</th>
                <th scope="col" className="px-3 py-2 font-medium">Joined</th>
                <th scope="col" className="px-3 py-2 font-medium">Last seen</th>
                <th scope="col" className="px-3 py-2 font-medium">Personal link</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const completed = new Set(p.completed_milestone_ids);
                return (
                  <tr
                    key={p.id}
                    data-testid="participant-row"
                    className="border-b border-stone-100 last:border-b-0 hover:bg-stone-50/60"
                  >
                    <td className="px-3 py-2.5">
                      <span className="font-medium whitespace-pre-wrap text-stone-800">
                        {p.name}
                      </span>
                      {p.open_help_count > 0 && (
                        <Badge tone="warning" className="ml-2">
                          {p.open_help_count} help
                        </Badge>
                      )}
                    </td>
                    <td data-testid="participant-progress" className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <ProgressBar
                          value={p.progress_pct}
                          size="sm"
                          className="w-24"
                          label={`${p.name}'s progress`}
                        />
                        <span className="text-stone-600 tabular-nums">
                          {p.completed_count}/{totalMilestones}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap items-center gap-1">
                        {milestoneOrder.map((m) => {
                          const done = completed.has(m.milestone_id);
                          const current = p.current_milestone_id === m.milestone_id;
                          return (
                            <span
                              key={m.milestone_id}
                              title={`${m.position + 1}. ${m.title} — ${
                                done ? "done" : current ? "current" : "to do"
                              }`}
                              className={cn(
                                "inline-block size-2.5 rounded-full",
                                done
                                  ? "bg-emerald-500"
                                  : current
                                    ? "bg-white ring-2 ring-brand-500"
                                    : "bg-stone-200",
                              )}
                            />
                          );
                        })}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-stone-500">
                      {timeAgo(p.joined_at, nowMs)}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-stone-500">
                      {timeAgo(p.last_seen_at, nowMs)}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <span
                          data-testid="participant-personal-link"
                          className="max-w-[13rem] truncate font-mono text-xs text-stone-500"
                        >
                          {p.participant_url}
                        </span>
                        <CopyButton
                          text={p.participant_url}
                          aria-label={`Copy ${p.name}'s personal link`}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
