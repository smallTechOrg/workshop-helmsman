"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

export interface UndoState {
  actionId: number;
  label: string;
  /** ms epoch when the 30s undo window expires. */
  expiresAt: number;
}

/**
 * Fixed-position undo toast — counts down the ~30s undo window and calls
 * `onUndo` if the facilitator clicks Undo before it expires.
 */
export function UndoBanner({
  state,
  busy,
  onUndo,
  onDismiss,
}: {
  state: UndoState | null;
  busy: boolean;
  onUndo: (actionId: number) => void;
  onDismiss: () => void;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!state) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [state]);

  useEffect(() => {
    if (!state) return;
    if (now >= state.expiresAt) onDismiss();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [now, state]);

  if (!state) return null;
  const secsLeft = Math.max(0, Math.ceil((state.expiresAt - now) / 1000));

  return (
    <div
      role="status"
      data-testid="undo-toast"
      className="pointer-events-auto fixed inset-x-0 bottom-4 z-50 mx-auto flex w-full max-w-md items-center justify-between gap-3 rounded-lg border border-stone-700 bg-stone-900 px-4 py-2.5 text-sm text-white shadow-lg"
    >
      <span className="min-w-0 truncate">{state.label}</span>
      <div className="flex shrink-0 items-center gap-2">
        <span className="tabular-nums text-stone-400">{secsLeft}s</span>
        <Button
          size="sm"
          variant="secondary"
          data-testid="undo-button"
          loading={busy}
          onClick={() => onUndo(state.actionId)}
        >
          Undo
        </Button>
      </div>
    </div>
  );
}
