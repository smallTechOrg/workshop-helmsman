"use client";

import { useEffect, useRef, useState } from "react";
import type { TrackerHelpRequest } from "@/lib/api";
import { HelpStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { StubBadge } from "@/components/ui/StubBadge";
import { cn, timeAgo } from "@/lib/format";

/** One help request rendered as a conversation thread. */
function HelpThread({
  request,
  nowMs,
  archived,
  newAnswerIds,
  onReply,
  onResolve,
  onReopen,
}: {
  request: TrackerHelpRequest;
  nowMs: number;
  archived: boolean;
  newAnswerIds: Set<number>;
  onReply: (id: number, message: string) => Promise<boolean>;
  onResolve: (id: number) => void;
  onReopen: (id: number) => void;
}) {
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const sendReply = async () => {
    const text = reply.trim();
    if (text === "") {
      setError("Type your reply first.");
      return;
    }
    if (text.length > 4000) {
      setError("That's a bit long — keep it under 4,000 characters.");
      return;
    }
    setError(null);
    setSending(true);
    const ok = await onReply(request.id, text);
    setSending(false);
    if (ok) setReply("");
  };

  const optimistic = request.id < 0;

  return (
    <li
      data-testid="help-item"
      className="rounded-lg border border-stone-200 bg-white p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <HelpStatusBadge status={request.status} data-testid="help-status" />
          {request.status === "resolved" && request.resolved_by && (
            <span className="text-xs text-stone-400">
              resolved by {request.resolved_by === "participant" ? "you" : "facilitator"}
            </span>
          )}
        </div>
        <span className="text-xs text-stone-400">{timeAgo(request.created_at, nowMs)}</span>
      </div>

      {/* Thread: the original question is the participant's first message, then
          every reply in order, aligned by who wrote it. */}
      <div className="mt-2 space-y-2">
        <div className="flex justify-end">
          <div className="max-w-[85%] rounded-lg rounded-br-sm bg-brand-600 px-3 py-2 text-sm whitespace-pre-wrap text-white">
            {request.message}
          </div>
        </div>
        {request.answers.map((a) => {
          const mine = a.source === "participant";
          return (
            <div key={a.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
              <div
                data-testid={mine ? "help-reply-mine" : "help-answer"}
                className={cn(
                  "max-w-[85%] rounded-lg px-3 py-2",
                  mine
                    ? "rounded-br-sm bg-brand-600 text-white"
                    : "rounded-bl-sm border border-brand-100 bg-brand-50/60 text-stone-700",
                  newAnswerIds.has(a.id) && "animate-flash",
                )}
              >
                {!mine && (
                  <p className="mb-1 text-xs font-medium text-brand-700">
                    {a.source === "ai" ? "AI" : "Facilitator"} · {timeAgo(a.created_at, nowMs)}
                  </p>
                )}
                <Markdown className={cn("text-sm", mine && "[&_*]:!text-white")}>
                  {a.answer_md}
                </Markdown>
              </div>
            </div>
          );
        })}
      </div>

      {!optimistic && !archived && (
        <div className="mt-3 border-t border-stone-100 pt-2.5">
          <label htmlFor={`help-reply-${request.id}`} className="sr-only">
            Reply
          </label>
          <textarea
            id={`help-reply-${request.id}`}
            data-testid="help-reply-input"
            value={reply}
            maxLength={4000}
            rows={2}
            onChange={(e) => setReply(e.target.value)}
            placeholder="Reply…"
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
          />
          {error && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {error}
            </p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <Button
              size="sm"
              data-testid="help-reply-submit"
              onClick={sendReply}
              loading={sending}
            >
              Reply
            </Button>
            {request.status !== "resolved" ? (
              <Button
                size="sm"
                variant="secondary"
                data-testid="help-resolve"
                onClick={() => onResolve(request.id)}
              >
                Mark resolved
              </Button>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                data-testid="help-reopen"
                onClick={() => onReopen(request.id)}
              >
                Reopen
              </Button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export function HelpPanel({
  requests,
  nowMs,
  submitting,
  archived,
  onSubmit,
  onReply,
  onResolve,
  onReopen,
}: {
  requests: TrackerHelpRequest[];
  nowMs: number;
  submitting: boolean;
  archived: boolean;
  onSubmit: (message: string) => Promise<boolean>;
  onReply: (id: number, message: string) => Promise<boolean>;
  onResolve: (id: number) => void;
  onReopen: (id: number) => void;
}) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Flash newly-arrived replies (they land via poll).
  const knownAnswerIds = useRef<Set<number> | null>(null);
  const newAnswerIds = new Set<number>();
  if (knownAnswerIds.current !== null) {
    for (const r of requests) {
      for (const a of r.answers) {
        if (!knownAnswerIds.current.has(a.id)) newAnswerIds.add(a.id);
      }
    }
  }
  useEffect(() => {
    knownAnswerIds.current = new Set(requests.flatMap((r) => r.answers.map((a) => a.id)));
  }, [requests]);

  const submit = async () => {
    const text = message.trim();
    if (text === "") {
      setError("Tell us what you're stuck on first.");
      return;
    }
    if (text.length > 4000) {
      setError("That's a bit long — keep it under 4,000 characters.");
      return;
    }
    setError(null);
    const ok = await onSubmit(text);
    if (ok) setMessage("");
  };

  const sorted = [...requests].sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <div>
      <h2 className="mb-2 text-base font-semibold text-stone-900">Need help?</h2>
      <label htmlFor="help-message" className="sr-only">
        What are you stuck on?
      </label>
      <textarea
        id="help-message"
        data-testid="help-input"
        value={message}
        maxLength={4000}
        onChange={(e) => setMessage(e.target.value)}
        rows={3}
        disabled={archived}
        placeholder="What are you stuck on? Your facilitator sees this immediately."
        className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500 disabled:bg-stone-100"
      />
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
      <div className="mt-2">
        <Button
          size="sm"
          data-testid="help-submit"
          onClick={submit}
          loading={submitting}
          disabled={archived}
        >
          Ask for help
        </Button>
      </div>

      {sorted.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-stone-300 bg-stone-50 px-3 py-4 text-center text-sm text-stone-500">
          Stuck? Ask here — answers appear right on this page, and you can reply back.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {sorted.map((r) => (
            <HelpThread
              key={r.id}
              request={r}
              nowMs={nowMs}
              archived={archived}
              newAnswerIds={newAnswerIds}
              onReply={onReply}
              onResolve={onResolve}
              onReopen={onReopen}
            />
          ))}
        </ul>
      )}

      <div className="mt-4 flex items-center justify-between gap-2 rounded-lg border border-dashed border-stone-300 bg-stone-50/70 px-3 py-2.5">
        <p className="text-xs text-stone-400">
          Announcements from your facilitator will appear here.
        </p>
        <StubBadge />
      </div>
    </div>
  );
}
