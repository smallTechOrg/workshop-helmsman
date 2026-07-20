"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { cn } from "@/lib/format";
import type { BroadcastInfo } from "@/lib/api";

/** The "Broadcast" control chip in the header — opens the composer. */
export function BroadcastAction({ onOpen }: { onOpen: () => void }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      data-testid="broadcast-button"
      onClick={onOpen}
    >
      Broadcast
    </Button>
  );
}

/** The active-broadcast strip shown under the header when one is live. */
export function ActiveBroadcastBar({
  broadcast,
  onClear,
  clearing,
}: {
  broadcast: BroadcastInfo;
  onClear: () => void;
  clearing: boolean;
}) {
  return (
    <div className="border-b border-brand-200 bg-brand-50/70 px-4 py-2">
      <div className="mx-auto flex max-w-7xl items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 shrink-0 rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-semibold text-white"
        >
          LIVE
        </span>
        <div className="min-w-0 flex-1 text-sm text-stone-800">
          <Markdown className="prose-sm [&_p]:m-0">{broadcast.message_md}</Markdown>
        </div>
        <Button
          size="sm"
          variant="ghost"
          data-testid="broadcast-clear"
          onClick={onClear}
          loading={clearing}
        >
          Clear
        </Button>
      </div>
    </div>
  );
}

export function BroadcastComposer({
  open,
  submitting,
  onClose,
  onSend,
}: {
  open: boolean;
  submitting: boolean;
  onClose: () => void;
  onSend: (messageMd: string) => Promise<boolean>;
}) {
  const [message, setMessage] = useState("");
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    setMessage("");
    setError(null);
    setTab("write");
    onClose();
  };

  const send = async () => {
    setError(null);
    const trimmed = message.trim();
    if (trimmed.length < 1) {
      setError("Write a message before sending.");
      return;
    }
    if (message.length > 4000) {
      setError("Broadcasts are limited to 4,000 characters.");
      return;
    }
    const ok = await onSend(message);
    if (ok) close();
  };

  return (
    <Modal open={open} onClose={close} title="Broadcast to everyone" widthClassName="max-w-xl">
      <div className="space-y-3">
        <p className="text-sm text-stone-500">
          Pinned at the top of every participant's tracker until you clear it or send a new one.
        </p>
        <div className="flex gap-1" role="tablist" aria-label="Broadcast editor">
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
        {tab === "write" ? (
          <textarea
            data-testid="broadcast-textarea"
            value={message}
            maxLength={4000}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            placeholder="We're taking a 10-minute break — back at 2:15."
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
          />
        ) : (
          <div className="min-h-[7.5rem] rounded-lg border border-stone-200 bg-white px-3 py-2">
            {message.trim() === "" ? (
              <p className="text-sm text-stone-400">Nothing to preview yet.</p>
            ) : (
              <Markdown className="text-sm">{message}</Markdown>
            )}
          </div>
        )}
        {error && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex items-center justify-end gap-2 border-t border-stone-200 pt-3">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button data-testid="broadcast-submit" onClick={send} loading={submitting}>
            Send broadcast
          </Button>
        </div>
      </div>
    </Modal>
  );
}
