"use client";

import { useState } from "react";
import type { HelpQueueItem } from "@/lib/api";
import { Badge, HelpStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, timeAgo } from "@/lib/format";

function QueueItem({
  item,
  nowMs,
  onAnswer,
  onResolve,
  busy,
}: {
  item: HelpQueueItem;
  nowMs: number;
  onAnswer: (id: number, answerMd: string) => Promise<boolean>;
  onResolve: (id: number) => void;
  busy: boolean;
}) {
  const [draft, setDraft] = useState("");
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    const text = draft.trim();
    if (text === "") {
      setError("Write an answer first.");
      return;
    }
    if (text.length > 10000) {
      setError("That answer is too long (max 10,000 characters).");
      return;
    }
    setError(null);
    const ok = await onAnswer(item.id, text);
    if (ok) {
      setDraft("");
      setTab("write");
    }
  };

  const visibleAnswers = item.answers.filter((a) => !a.draft);

  return (
    <li
      data-testid="help-queue-item"
      className="rounded-lg border border-stone-200 bg-white p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-medium whitespace-pre-wrap text-stone-900">
            {item.participant_name}
          </span>
          {item.milestone_title && (
            <Badge tone="neutral" className="max-w-[12rem] truncate">
              {item.milestone_title}
            </Badge>
          )}
          {item.escalated && <Badge tone="danger">Escalated</Badge>}
        </div>
        <div className="flex items-center gap-2">
          <HelpStatusBadge status={item.status} />
          <span className="text-xs whitespace-nowrap text-stone-400">
            {timeAgo(item.created_at, nowMs)}
          </span>
        </div>
      </div>

      <p className="mt-2 text-sm whitespace-pre-wrap text-stone-700">{item.message}</p>

      {visibleAnswers.length > 0 && (
        <ul className="mt-3 space-y-2">
          {visibleAnswers.map((a) => (
            <li
              key={a.id}
              className="rounded-lg border border-brand-100 bg-brand-50/50 px-3 py-2"
            >
              <p className="mb-1 text-xs font-medium text-brand-700">
                {a.source === "ai" ? "AI" : "Facilitator"} ·{" "}
                {timeAgo(a.created_at, nowMs)}
              </p>
              <Markdown className="text-sm">{a.answer_md}</Markdown>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 border-t border-stone-100 pt-3">
        <div className="mb-1.5 flex gap-1" role="tablist" aria-label="Answer composer">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "write"}
            onClick={() => setTab("write")}
            className={cn(
              "rounded-md px-2 py-1 text-xs font-medium",
              tab === "write" ? "bg-stone-200 text-stone-800" : "text-stone-500 hover:bg-stone-100",
            )}
          >
            Write
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "preview"}
            onClick={() => setTab("preview")}
            className={cn(
              "rounded-md px-2 py-1 text-xs font-medium",
              tab === "preview" ? "bg-stone-200 text-stone-800" : "text-stone-500 hover:bg-stone-100",
            )}
          >
            Preview
          </button>
        </div>
        <textarea
          data-testid="help-answer-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={3}
          maxLength={10000}
          hidden={tab !== "write"}
          placeholder="Answer in markdown — code blocks welcome…"
          aria-label={`Answer ${item.participant_name}'s request`}
          className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
        />
        {tab === "preview" && (
          <div className="min-h-[4.5rem] rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
            {draft.trim() === "" ? (
              <p className="text-sm text-stone-400">Nothing to preview yet.</p>
            ) : (
              <Markdown className="text-sm">{draft}</Markdown>
            )}
          </div>
        )}
        {error && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {error}
          </p>
        )}
        <div className="mt-2 flex items-center gap-2">
          <Button
            size="sm"
            data-testid="help-answer-submit"
            onClick={send}
            loading={busy}
          >
            Answer
          </Button>
          <Button
            size="sm"
            variant="secondary"
            data-testid="help-resolve-button"
            onClick={() => onResolve(item.id)}
            disabled={busy || item.status === "resolved"}
          >
            Mark resolved
          </Button>
        </div>
      </div>
    </li>
  );
}

export function HelpQueue({
  queue,
  nowMs,
  onAnswer,
  onResolve,
  busyIds,
}: {
  queue: HelpQueueItem[];
  nowMs: number;
  onAnswer: (id: number, answerMd: string) => Promise<boolean>;
  onResolve: (id: number) => void;
  busyIds: Set<number>;
}) {
  const open = queue
    .filter((h) => h.status === "open")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const answered = queue
    .filter((h) => h.status === "answered")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const resolved = queue
    .filter((h) => h.status === "resolved")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

  if (queue.length === 0) {
    return (
      <div data-testid="help-queue">
        <EmptyState
          icon="🧭"
          title="No open help requests"
          hint="The room is cruising. Requests from participants appear here the moment they're sent."
        />
      </div>
    );
  }

  const renderItem = (item: HelpQueueItem) => (
    <QueueItem
      key={item.id}
      item={item}
      nowMs={nowMs}
      onAnswer={onAnswer}
      onResolve={onResolve}
      busy={busyIds.has(item.id)}
    />
  );

  return (
    <div data-testid="help-queue" className="space-y-4">
      {open.length + answered.length === 0 && (
        <p className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-4 text-center text-sm text-stone-500">
          Nothing waiting — every request has been resolved.
        </p>
      )}
      {open.length > 0 && <ul className="space-y-3">{open.map(renderItem)}</ul>}
      {answered.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase">
            Answered — awaiting resolution
          </h4>
          <ul className="space-y-3">{answered.map(renderItem)}</ul>
        </div>
      )}
      {resolved.length > 0 && (
        <details className="rounded-lg border border-stone-200 bg-stone-50/60">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-stone-600 select-none">
            Resolved ({resolved.length})
          </summary>
          <ul className="space-y-3 px-4 pb-4">{resolved.map(renderItem)}</ul>
        </details>
      )}
    </div>
  );
}
