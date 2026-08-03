"use client";

import { useState } from "react";
import { ApiError, adminCreateWorkshop, type WorkshopFull } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import {
  WorkshopComposer,
  emptyComposerValue,
  validateComposer,
  type ComposerValue,
} from "@/components/create/WorkshopComposer";

export function CreateWorkshopModal({
  open,
  adminKey,
  onClose,
  onCreated,
}: {
  open: boolean;
  adminKey: string;
  onClose: () => void;
  onCreated: (workshop: WorkshopFull) => void;
}) {
  const [value, setValue] = useState<ComposerValue>(emptyComposerValue);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setError(null);
    const checked = validateComposer(value);
    if (!checked.ok) {
      setError(checked.error);
      return;
    }

    setSubmitting(true);
    try {
      const { workshop } = await adminCreateWorkshop(adminKey, checked.body);
      setValue(emptyComposerValue());
      setError(null);
      onCreated(workshop);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong creating the workshop — try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New workshop">
      <div className="space-y-5">
        <WorkshopComposer value={value} onChange={setValue} disabled={submitting} />

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {error}
          </p>
        )}

        <div className="flex items-center justify-end gap-2 border-t border-stone-200 pt-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            data-testid="create-workshop-submit"
            onClick={submit}
            loading={submitting}
          >
            Create workshop
          </Button>
        </div>
      </div>
    </Modal>
  );
}
