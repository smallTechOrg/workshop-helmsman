"use client";

import { useState } from "react";
import {
  ApiError,
  participantEditProfile,
  type JoinFormField,
  type TrackerMe,
} from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";

/**
 * The participant's own "about me" card — name plus whatever custom join-form
 * answers they gave — editable in place. It also carries the personal link
 * (the cross-device credential) in a compact row, so the big save-your-link
 * callout is no longer needed.
 */
export function ProfileCard({
  token,
  me,
  joinForm,
  personalUrl,
  archived,
  onSaved,
}: {
  token: string;
  me: TrackerMe;
  joinForm: JoinFormField[];
  personalUrl: string;
  archived: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(me.name);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = () => {
    setName(me.name);
    setAnswers({ ...(me.answers ?? {}) });
    setError(null);
    setEditing(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 80) {
      setError("Name must be 1–80 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await participantEditProfile(token, { name: trimmed, answers });
      setEditing(false);
      onSaved();
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

  // Only show answers for fields that still exist in the join form, in order.
  const filled = joinForm
    .map((f) => ({ field: f, value: (me.answers ?? {})[f.key]?.trim() }))
    .filter((row) => row.value);

  return (
    <Card className="p-4" data-testid="profile-card">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-lg font-semibold text-stone-900">{me.name}</p>
          <p className="text-xs text-stone-400">Your details</p>
        </div>
        {!archived && (
          <button
            type="button"
            data-testid="profile-edit"
            onClick={open}
            className="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-brand-600 hover:bg-brand-50"
          >
            Edit
          </button>
        )}
      </div>

      {filled.length > 0 && (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          {filled.map(({ field, value }) => (
            <div key={field.key} className="contents">
              <dt className="text-stone-500">{field.label}</dt>
              <dd className="min-w-0 break-words text-stone-800">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-3 flex items-center gap-2 border-t border-stone-100 pt-3">
        <span className="shrink-0 text-xs text-stone-500">Your link:</span>
        <span
          data-testid="personal-link"
          className="min-w-0 flex-1 truncate font-mono text-xs text-stone-500"
        >
          {personalUrl}
        </span>
        <CopyButton
          text={personalUrl}
          iconOnly
          aria-label="Copy your personal link"
          title="Copy your personal link — it works on any device"
        />
      </div>

      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title="Edit your details"
        widthClassName="max-w-lg"
      >
        <form onSubmit={submit} data-testid="profile-edit-form">
          <label className="mb-1 block text-sm font-medium text-stone-700" htmlFor="pp-name">
            Name
          </label>
          <input
            id="pp-name"
            data-testid="profile-name-input"
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            className="mb-4 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 focus:outline-none"
          />

          {joinForm.map((f) => (
            <div key={f.key} className="mb-4">
              <label
                className="mb-1 block text-sm font-medium text-stone-700"
                htmlFor={`pp-${f.key}`}
              >
                {f.label}
                {!f.required && (
                  <span className="ml-1.5 font-normal text-stone-400">(optional)</span>
                )}
              </label>
              {f.type === "dropdown" ? (
                <select
                  id={`pp-${f.key}`}
                  data-testid={`profile-field-${f.key}`}
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
                  id={`pp-${f.key}`}
                  data-testid={`profile-field-${f.key}`}
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
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" data-testid="profile-save" disabled={busy}>
              {busy ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
}
