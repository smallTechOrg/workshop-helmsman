"use client";

import { useEffect, useRef, useState } from "react";
import type { TrackerHelpRequest } from "@/lib/api";
import { HelpStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { StubBadge } from "@/components/ui/StubBadge";
import { cn, timeAgo } from "@/lib/format";

export function HelpPanel({
  requests,
  nowMs,
  submitting,
  archived,
  onSubmit,
  onResolve,
}: {
  requests: TrackerHelpRequest[];
  nowMs: number;
  submitting: boolean;
  archived: boolean;
  onSubmit: (message: string) => Promise<boolean>;
  onResolve: (id: number) => void;
}) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Flash newly-arrived answers (they land via poll).
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
    knownAnswerIds.current = new Set(
      requests.flatMap((r) => r.answers.map((a) => a.id)),
    );
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

  const sorted = [...requests].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  );

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
          Stuck? Ask here — answers appear right on this page.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {sorted.map((r) => (
            <li
              key={r.id}
              data-testid="help-item"
              className="rounded-lg border border-stone-200 bg-white p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <HelpStatusBadge status={r.status} data-testid="help-status" />
                <span className="text-xs text-stone-400">
                  {timeAgo(r.created_at, nowMs)}
                </span>
              </div>
              <p className="mt-2 text-sm whitespace-pre-wrap text-stone-700">
                {r.message}
              </p>
              {r.answers.length > 0 && (
                <ul className="mt-2 space-y-2">
                  {r.answers.map((a) => (
                    <li
                      key={a.id}
                      className={cn(
                        "rounded-lg border border-brand-100 bg-brand-50/50 px-3 py-2",
                        newAnswerIds.has(a.id) && "animate-flash",
                      )}
                    >
                      <p className="mb-1 text-xs font-medium text-brand-700">
                        {a.source === "ai" ? "AI" : "Facilitator"} ·{" "}
                        {timeAgo(a.created_at, nowMs)}
                      </p>
                      <div data-testid="help-answer">
                        <Markdown className="text-sm">{a.answer_md}</Markdown>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {r.id >= 0 && r.status !== "resolved" && (
                <div className="mt-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    data-testid="help-resolve"
                    onClick={() => onResolve(r.id)}
                  >
                    Mark resolved
                  </Button>
                </div>
              )}
            </li>
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
