"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

/**
 * Blocking confirmation for destructive/bulk actions (delete milestone,
 * advance-all, etc). Renders a Modal with Cancel / Confirm.
 */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} title={title} widthClassName="max-w-md">
      <div className="space-y-4">
        <div className="text-sm text-stone-600">{body}</div>
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={onConfirm}
            loading={busy}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** Convenience hook: manages open/busy state for a single confirm-then-run action. */
export function useConfirm() {
  const [pending, setPending] = useState<(() => Promise<void>) | null>(null);
  const [busy, setBusy] = useState(false);

  const ask = (fn: () => Promise<void>) => setPending(() => fn);
  const cancel = () => {
    if (busy) return;
    setPending(null);
  };
  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      await pending();
    } finally {
      setBusy(false);
      setPending(null);
    }
  };

  return { open: pending !== null, busy, ask, cancel, confirm };
}
