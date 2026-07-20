"use client";

import { useState } from "react";
import {
  ApiError,
  facilitatorEditParticipant,
  type DashboardParticipant,
  type JoinFormField,
} from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

export function EditParticipantModal({
  token,
  participant,
  joinForm,
  onClose,
  onSaved,
}: {
  token: string;
  /** null closes the modal. */
  participant: DashboardParticipant | null;
  joinForm: JoinFormField[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Re-seed the form whenever a different participant is opened.
  const [seededId, setSeededId] = useState<number | null>(null);
  if (participant && participant.id !== seededId) {
    setSeededId(participant.id);
    setName(participant.name);
    setAnswers({ ...(participant.answers ?? {}) });
    setError(null);
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!participant) return;
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 80) {
      setError("Name must be 1–80 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await facilitatorEditParticipant(token, participant.id, {
        name: trimmed,
        answers,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Couldn't save — ${err.message}`
          : "Couldn't save — check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={participant !== null}
      onClose={onClose}
      title="Edit participant"
      widthClassName="max-w-lg"
    >
      <form onSubmit={submit} data-testid="edit-participant-form">
        <label className="mb-1 block text-sm font-medium text-stone-700" htmlFor="ep-name">
          Name
        </label>
        <input
          id="ep-name"
          data-testid="edit-participant-name"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          className="mb-4 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 focus:outline-none"
        />

        {joinForm.map((f) => (
          <div key={f.key} className="mb-4">
            <label
              className="mb-1 block text-sm font-medium text-stone-700"
              htmlFor={`ep-${f.key}`}
            >
              {f.label}
              {!f.required && (
                <span className="ml-1.5 font-normal text-stone-400">(optional)</span>
              )}
            </label>
            {f.type === "dropdown" ? (
              <select
                id={`ep-${f.key}`}
                data-testid={`edit-participant-field-${f.key}`}
                value={answers[f.key] ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [f.key]: e.target.value }))}
                className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
              >
                <option value="">Choose…</option>
                {(f.options ?? []).map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={`ep-${f.key}`}
                data-testid={`edit-participant-field-${f.key}`}
                value={answers[f.key] ?? ""}
                maxLength={500}
                onChange={(e) => setAnswers((a) => ({ ...a, [f.key]: e.target.value }))}
                className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
              />
            )}
          </div>
        ))}

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" data-testid="edit-participant-save" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
