"use client";

import { useState } from "react";
import type { MilestoneInputConfig, MilestoneMeta } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/format";

/**
 * Client-side mirror of services/milestone_input.validate_input_value — returns
 * an error message, or null when the value is acceptable. The server re-checks,
 * so this is purely for enabling the button and giving fast feedback.
 */
function validateInput(config: MilestoneInputConfig, raw: string): string | null {
  const value = raw.trim();
  if (!value) return `${config.label} is required.`;
  if (value.length > 500) return `${config.label} is too long.`;
  const isUrl = () => {
    try {
      const u = new URL(value);
      return u.protocol === "http:" || u.protocol === "https:" ? u : null;
    } catch {
      return null;
    }
  };
  if (config.type === "github_url") {
    const u = isUrl();
    if (!u) return "Enter a valid URL (http:// or https://).";
    const host = u.hostname.toLowerCase();
    if (host !== "github.com" && !host.endsWith(".github.com")) {
      return "Enter a GitHub URL (a link on github.com).";
    }
  } else if (config.type === "url") {
    if (!isUrl()) return "Enter a valid URL (http:// or https://).";
  } else if (config.type === "dropdown") {
    if (!(config.options ?? []).includes(value)) return "Choose one of the options.";
  }
  return null;
}

function MilestoneInputField({
  config,
  milestoneId,
  value,
  onChange,
}: {
  config: MilestoneInputConfig;
  milestoneId: number;
  value: string;
  onChange: (v: string) => void;
}) {
  const id = `mi-${milestoneId}`;
  const placeholder =
    config.type === "github_url"
      ? "https://github.com/you/your-repo"
      : config.type === "url"
        ? "https://…"
        : undefined;
  return (
    <div className="mt-3">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-stone-700">
        {config.label}
      </label>
      {config.type === "dropdown" ? (
        <select
          id={id}
          data-testid="milestone-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
        >
          <option value="">Choose…</option>
          {(config.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          data-testid="milestone-input"
          type={config.type === "text" ? "text" : "url"}
          inputMode={config.type === "text" ? undefined : "url"}
          value={value}
          placeholder={placeholder}
          maxLength={500}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 focus:outline-none"
        />
      )}
    </div>
  );
}

export function MilestoneList({
  milestones,
  contentById,
  completedIds,
  currentId,
  paused,
  submittedInputs,
  onToggle,
}: {
  milestones: MilestoneMeta[];
  /** Milestone bodies from the content endpoint; null while still loading. */
  contentById: Map<number, string> | null;
  completedIds: Set<number>;
  currentId: number | null;
  paused: boolean;
  /** {milestone_id: submitted value} the participant already sent, if any. */
  submittedInputs: Record<string, string>;
  onToggle: (milestoneId: number, completed: boolean, input?: string) => Promise<void> | void;
}) {
  // User-driven expansion overrides; default = expanded unless completed.
  const [expandOverride, setExpandOverride] = useState<Record<number, boolean>>({});
  // Draft input values, keyed by milestone id (falls back to what was submitted).
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [pending, setPending] = useState<Record<number, boolean>>({});

  const ordered = [...milestones].sort((a, b) => a.position - b.position);

  const draftFor = (id: number) => drafts[id] ?? submittedInputs[String(id)] ?? "";

  const submitGated = async (id: number, config: MilestoneInputConfig) => {
    const value = draftFor(id).trim();
    if (validateInput(config, value)) return;
    setPending((p) => ({ ...p, [id]: true }));
    try {
      await onToggle(id, true, value);
    } catch {
      // onToggle surfaces its own toast.
    } finally {
      setPending((p) => ({ ...p, [id]: false }));
    }
  };

  return (
    <ol className="space-y-3">
      {ordered.map((m) => {
        const done = completedIds.has(m.id);
        const isCurrent = m.id === currentId;
        const expanded = expandOverride[m.id] ?? !done;
        const body = contentById?.get(m.id);
        const config = m.input_config;
        const draft = draftFor(m.id);
        const inputError = config ? validateInput(config, draft) : null;
        const busy = pending[m.id] ?? false;

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
                // A gated milestone can't be ticked directly — it completes via
                // its "Mark complete" button once the input is valid. Unchecking
                // to redo it stays available.
                disabled={paused || (!!config && !done)}
                aria-disabled={paused || (!!config && !done)}
                aria-checked={done}
                onChange={(e) => {
                  void Promise.resolve(onToggle(m.id, e.target.checked)).catch(() => {});
                }}
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
                {config && !done && <Badge tone="neutral">Input required</Badge>}
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

              {config && (
                <div data-testid="milestone-input-section">
                  <MilestoneInputField
                    config={config}
                    milestoneId={m.id}
                    value={draft}
                    onChange={(v) => setDrafts((d) => ({ ...d, [m.id]: v }))}
                  />
                  {done ? (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-xs text-emerald-700">✓ Submitted</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        data-testid="milestone-input-update"
                        disabled={paused || busy || !!inputError || draft.trim() === (submittedInputs[String(m.id)] ?? "")}
                        onClick={() => config && submitGated(m.id, config)}
                      >
                        Update
                      </Button>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      className="mt-2"
                      data-testid="milestone-complete-gated"
                      disabled={paused || busy || !!inputError}
                      loading={busy}
                      onClick={() => config && submitGated(m.id, config)}
                    >
                      Mark complete
                    </Button>
                  )}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
