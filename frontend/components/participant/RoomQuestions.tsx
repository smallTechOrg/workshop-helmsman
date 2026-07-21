"use client";

import { useState } from "react";
import { ApiError, participantRoomQuestions, type RoomQuestion } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { HelpStatusBadge } from "@/components/ui/Badge";
import { Markdown } from "@/components/ui/Markdown";
import { cn, timeAgo } from "@/lib/format";

/**
 * Ambient "the room is asking" indicator + an on-demand modal listing every
 * question in the workshop (read-only). The list is fetched only when opened,
 * so it never bloats the tracker's poll loop or disturbs the main view.
 */
export function RoomQuestions({
  token,
  openCount,
  nowMs,
}: {
  token: string;
  openCount: number;
  nowMs: number;
}) {
  const [open, setOpen] = useState(false);
  const [questions, setQuestions] = useState<RoomQuestion[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await participantRoomQuestions(token);
      setQuestions(res.questions);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't load the room's questions — try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const openModal = () => {
    setOpen(true);
    void load();
  };

  return (
    <>
      <button
        type="button"
        data-testid="room-questions-open"
        onClick={openModal}
        className="mt-3 flex w-full items-center justify-between gap-2 rounded-lg border border-stone-200 bg-white px-3 py-2 text-left text-sm transition-colors hover:bg-stone-50"
      >
        <span className="text-stone-600">
          {openCount > 0 ? (
            <>
              <span className="font-semibold text-brand-700">
                {openCount} {openCount === 1 ? "question" : "questions"}
              </span>{" "}
              open in the room
            </>
          ) : (
            "See the room's questions"
          )}
        </span>
        <span className="shrink-0 text-xs font-medium text-brand-600">View all →</span>
      </button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Questions from the room"
        widthClassName="max-w-2xl"
      >
        {loading && <p className="text-sm text-stone-500">Loading…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {questions && questions.length === 0 && (
          <p className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-3 py-6 text-center text-sm text-stone-500">
            No questions yet — be the first to ask.
          </p>
        )}
        {questions && questions.length > 0 && (
          <ul className="space-y-3" data-testid="room-questions-list">
            {questions.map((q) => (
              <li
                key={q.id}
                data-testid="room-question"
                className="rounded-lg border border-stone-200 bg-white p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-stone-800">{q.asker_name}</span>
                  <div className="flex items-center gap-2">
                    <HelpStatusBadge status={q.status} />
                    <span className="text-xs text-stone-400">{timeAgo(q.created_at, nowMs)}</span>
                  </div>
                </div>
                <p className="mt-1.5 text-sm whitespace-pre-wrap text-stone-700">{q.message}</p>
                {q.answers.length > 0 && (
                  <ul className="mt-2 space-y-1.5">
                    {q.answers.map((a) => (
                      <li
                        key={a.id}
                        className={cn(
                          "rounded-lg px-3 py-1.5 text-sm",
                          a.source === "participant"
                            ? "bg-stone-50 text-stone-600"
                            : "border border-brand-100 bg-brand-50/50 text-stone-700",
                        )}
                      >
                        <span className="mr-1 text-xs font-medium text-stone-400">
                          {a.source === "ai"
                            ? "AI"
                            : a.source === "facilitator"
                              ? "Facilitator"
                              : q.asker_name}
                          :
                        </span>
                        <Markdown className="inline text-sm">{a.answer_md}</Markdown>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </>
  );
}
