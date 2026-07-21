"use client";

import { useMemo, useState } from "react";
import type { DashboardParticipant, JoinFormField, MilestoneStat } from "@/lib/api";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, timeAgo } from "@/lib/format";

type SortKey = "joined" | "name" | "progress" | "lastseen";

/** Fields get their own column only when at least one participant answered
 * them — an all-blank column wastes space a workshop of 200 can't spare. */
function useAnsweredFields(joinForm: JoinFormField[], participants: DashboardParticipant[]) {
  return useMemo(
    () =>
      joinForm.filter((f) => participants.some((p) => (p.answers ?? {})[f.key]?.trim())),
    [joinForm, participants],
  );
}

export function ParticipantTable({
  participants,
  milestoneStats,
  joinUrl,
  nowMs,
  selectable = false,
  selectedIds,
  onToggleSelect,
  onAdvanceSelected,
  onEditParticipant,
  joinForm = [],
}: {
  participants: DashboardParticipant[];
  milestoneStats: MilestoneStat[];
  joinUrl: string;
  nowMs: number;
  /** Enables the checkbox column + "Advance selected" toolbar. */
  selectable?: boolean;
  selectedIds?: Set<number>;
  onToggleSelect?: (id: number) => void;
  onAdvanceSelected?: (milestoneId: number, milestoneTitle: string, ids: number[]) => void;
  onEditParticipant?: (participant: DashboardParticipant) => void;
  joinForm?: JoinFormField[];
}) {
  const [advanceTarget, setAdvanceTarget] = useState<string>("");
  const [sort, setSort] = useState<SortKey>("progress");
  const [filter, setFilter] = useState("");
  const [answerFilters, setAnswerFilters] = useState<Record<string, string>>({});

  const answeredFields = useAnsweredFields(joinForm, participants);

  // Filters are for the categorical questions — i.e. dropdown fields, which
  // have a fixed, known set of choices. Free-text fields (email, name…) never
  // get a filter. Show a dropdown's filter once its answers actually vary.
  const filterOptions = useMemo(() => {
    const options: Record<string, string[]> = {};
    for (const f of answeredFields) {
      if (f.type !== "dropdown") continue;
      const values = new Set<string>();
      for (const p of participants) {
        const v = (p.answers ?? {})[f.key]?.trim();
        if (v) values.add(v);
      }
      if (values.size > 1) {
        options[f.key] = [...values].sort((a, b) => a.localeCompare(b));
      }
    }
    return options;
  }, [answeredFields, participants]);

  const milestoneOrder = useMemo(
    () => [...milestoneStats].sort((a, b) => a.position - b.position),
    [milestoneStats],
  );

  const activeAnswerFilters = Object.entries(answerFilters).filter(([, v]) => v !== "");

  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    let filtered = q
      ? participants.filter((p) => p.name.toLowerCase().includes(q))
      : [...participants];
    for (const [key, value] of activeAnswerFilters) {
      filtered = filtered.filter((p) => (p.answers ?? {})[key] === value);
    }
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
      case "lastseen":
        // Most recently active on top.
        filtered.sort((a, b) => b.last_seen_at.localeCompare(a.last_seen_at));
        break;
      case "joined":
      default:
        filtered.sort((a, b) => a.joined_at.localeCompare(b.joined_at));
        break;
    }
    return filtered;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [participants, sort, filter, JSON.stringify(answerFilters)]);

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
          className="w-40 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
        />
        {Object.entries(filterOptions).map(([key, values]) => {
          const field = answeredFields.find((f) => f.key === key)!;
          return (
            <select
              key={key}
              aria-label={`Filter by ${field.label}`}
              data-testid="participant-answer-filter"
              value={answerFilters[key] ?? ""}
              onChange={(e) => setAnswerFilters((prev) => ({ ...prev, [key]: e.target.value }))}
              className={cn(
                "rounded-lg border bg-white px-2 py-1.5 text-sm",
                answerFilters[key]
                  ? "border-brand-400 text-brand-800"
                  : "border-stone-300 text-stone-600",
              )}
            >
              <option value="">All {field.label}</option>
              {values.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          );
        })}
        <div
          role="group"
          aria-label="Sort participants"
          className="flex overflow-hidden rounded-lg border border-stone-300 bg-white text-sm"
        >
          {(
            [
              ["progress", "Progress"],
              ["lastseen", "Last seen"],
              ["joined", "Joined"],
              ["name", "Name"],
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
        <span className={cn("text-sm text-stone-500 tabular-nums", !selectable && "ml-auto")}>
          {rows.length} of {participants.length}
        </span>
        {selectable && (
          <div className="ml-auto flex items-center gap-2">
            {selectedIds && selectedIds.size > 0 && (
              <>
                <span className="text-sm text-stone-600 tabular-nums">
                  {selectedIds.size} selected
                </span>
                <select
                  aria-label="Advance selected to milestone"
                  value={advanceTarget}
                  onChange={(e) => setAdvanceTarget(e.target.value)}
                  className="rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm"
                >
                  <option value="">Advance to…</option>
                  {milestoneOrder.map((m) => (
                    <option key={m.milestone_id} value={m.milestone_id}>
                      {m.position + 1}. {m.title}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!advanceTarget}
                  onClick={() => {
                    const m = milestoneOrder.find((mm) => String(mm.milestone_id) === advanceTarget);
                    if (!m || !onAdvanceSelected || !selectedIds) return;
                    onAdvanceSelected(m.milestone_id, m.title, [...selectedIds]);
                    setAdvanceTarget("");
                  }}
                >
                  Advance selected
                </Button>
              </>
            )}
          </div>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-center text-sm text-stone-500">
          {filter.trim()
            ? `No participant matches "${filter.trim()}".`
            : "No participant matches these filters."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-stone-200">
          <table className="w-full min-w-[760px] border-collapse bg-white text-sm">
            <thead>
              <tr className="border-b border-stone-200 bg-stone-50 text-left text-xs tracking-wide text-stone-500 uppercase">
                {selectable && (
                  <th scope="col" className="px-3 py-2 font-medium">
                    <span className="sr-only">Select</span>
                  </th>
                )}
                <th scope="col" className="min-w-[14rem] px-3 py-2 font-medium">Name</th>
                <th scope="col" className="px-3 py-2 font-medium">Progress</th>
                <th scope="col" className="min-w-[12rem] px-3 py-2 font-medium">Milestones</th>
                {answeredFields.map((f) => (
                  <th
                    key={f.key}
                    scope="col"
                    className="px-3 py-2 font-medium whitespace-nowrap"
                  >
                    {f.label}
                  </th>
                ))}
                <th scope="col" className="px-3 py-2 font-medium">Joined</th>
                <th scope="col" className="px-3 py-2 font-medium">Last seen</th>
                <th scope="col" className="px-3 py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
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
                    {selectable && (
                      <td className="px-3 py-2.5">
                        <input
                          type="checkbox"
                          aria-label={`Select ${p.name}`}
                          checked={selectedIds?.has(p.id) ?? false}
                          onChange={() => onToggleSelect?.(p.id)}
                          className="size-4 rounded border-stone-300"
                        />
                      </td>
                    )}
                    <td className="px-3 py-2.5">
                      <span className="font-medium whitespace-nowrap text-stone-800">
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
                        <div className="w-24 shrink-0">
                          <ProgressBar
                            value={p.progress_pct}
                            size="sm"
                            label={`${p.name}'s progress`}
                          />
                        </div>
                        <span className="text-stone-600 tabular-nums">
                          {p.completed_count}/{totalMilestones}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1">
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
                    {answeredFields.map((f) => (
                      <td
                        key={f.key}
                        data-testid="participant-answer-cell"
                        // Size to content — the row scrolls horizontally rather
                        // than clipping. Only genuinely long free text (>24rem)
                        // truncates, with the full value on hover.
                        className="max-w-[24rem] truncate px-3 py-2.5 whitespace-nowrap text-stone-600"
                        title={(p.answers ?? {})[f.key] ?? ""}
                      >
                        {(p.answers ?? {})[f.key] || (
                          <span className="text-stone-300">—</span>
                        )}
                      </td>
                    ))}
                    <td className="px-3 py-2.5 whitespace-nowrap text-stone-500">
                      {timeAgo(p.joined_at, nowMs)}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-stone-500">
                      {timeAgo(p.last_seen_at, nowMs)}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-1.5">
                        {onEditParticipant && (
                          <button
                            type="button"
                            data-testid="participant-edit"
                            onClick={() => onEditParticipant(p)}
                            title={`Edit ${p.name}`}
                            aria-label={`Edit ${p.name}`}
                            className="inline-flex size-7 items-center justify-center rounded-md border border-stone-300 bg-white text-stone-600 shadow-sm transition-colors hover:bg-stone-50 hover:text-stone-800"
                          >
                            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-3.5">
                              <path d="M13.586 3.586a2 2 0 1 1 2.828 2.828l-.793.793-2.828-2.828.793-.793ZM11.379 5.793 3 14.172V17h2.828l8.38-8.379-2.83-2.828Z" />
                            </svg>
                          </button>
                        )}
                        <CopyButton
                          text={p.participant_url}
                          iconOnly
                          data-testid="participant-personal-link"
                          title={`Copy ${p.name}'s personal link`}
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
