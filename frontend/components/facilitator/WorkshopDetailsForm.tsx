"use client";

import { useState } from "react";
import { ApiError, facilitatorEditWorkshop, type JoinFormField } from "@/lib/api";
import {
  JoinFieldsEditor,
  draftsToFields,
  fieldsToDrafts,
  type JoinFieldDraft,
} from "@/components/facilitator/JoinFieldsEditor";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";

const NAME_MAX = 120;
const DESCRIPTION_MAX = 10_000;

/** Edit the workshop's name and markdown description after creation. */
export function WorkshopDetailsForm({
  token,
  name,
  descriptionMd,
  joinForm,
  onSaved,
}: {
  token: string;
  name: string;
  descriptionMd: string;
  joinForm: JoinFormField[];
  onSaved: () => void;
}) {
  const [draftName, setDraftName] = useState(name);
  const [draftDescription, setDraftDescription] = useState(descriptionMd);
  const [joinFields, setJoinFields] = useState<JoinFieldDraft[]>(() => fieldsToDrafts(joinForm));
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const dirty = true; // join-field rows have no cheap equality; always allow save

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = draftName.trim();
    if (!trimmed || trimmed.length > NAME_MAX) {
      setError(`The name must be 1–${NAME_MAX} characters.`);
      return;
    }
    if (draftDescription.length > DESCRIPTION_MAX) {
      setError(`The description is too long (max ${DESCRIPTION_MAX.toLocaleString()} characters).`);
      return;
    }
    const joinResult = draftsToFields(joinFields);
    if (joinResult.error) {
      setError(joinResult.error);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await facilitatorEditWorkshop(token, {
        name: trimmed,
        description_md: draftDescription,
        join_form: joinResult.fields,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
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

  return (
    <form onSubmit={onSubmit} className="mb-6 border-b border-stone-200 pb-6" data-testid="workshop-details-form">
      <h3 className="mb-3 text-base font-semibold text-stone-900">Workshop details</h3>
      <label className="mb-1 block text-sm font-medium text-stone-700" htmlFor="ws-name">
        Name
      </label>
      <input
        id="ws-name"
        data-testid="workshop-name-edit"
        value={draftName}
        onChange={(e) => setDraftName(e.target.value)}
        maxLength={NAME_MAX}
        className="mb-3 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 focus:outline-none"
      />
      <div className="mb-1 flex items-center justify-between">
        <label className="text-sm font-medium text-stone-700" htmlFor="ws-description">
          Description <span className="font-normal text-stone-400">(markdown, shown to participants)</span>
        </label>
        <button
          type="button"
          className="text-xs font-medium text-brand-600 hover:text-brand-700"
          onClick={() => setPreview((p) => !p)}
        >
          {preview ? "Write" : "Preview"}
        </button>
      </div>
      {preview ? (
        <div className="mb-3 min-h-20 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          {draftDescription.trim() ? (
            <Markdown>{draftDescription}</Markdown>
          ) : (
            <p className="text-sm text-stone-400">Nothing to preview yet.</p>
          )}
        </div>
      ) : (
        <textarea
          id="ws-description"
          data-testid="workshop-description-edit"
          value={draftDescription}
          onChange={(e) => setDraftDescription(e.target.value)}
          rows={4}
          className="mb-3 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 font-mono text-sm focus:border-brand-400 focus:ring-2 focus:ring-brand-100 focus:outline-none"
          placeholder="What this workshop covers, links to prerequisites, anything participants should know…"
        />
      )}
      <div className="mb-3">
        <p className="mb-1 text-sm font-medium text-stone-700">Join form</p>
        <p className="mb-2 text-xs text-amber-600">
          Changes apply to participants who join from now on; existing participants keep their answers.
        </p>
        <JoinFieldsEditor drafts={joinFields} onChange={setJoinFields} />
      </div>
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <Button
          type="submit"
          size="sm"
          data-testid="workshop-details-save"
          disabled={busy}
        >
          {busy ? "Saving…" : "Save details"}
        </Button>
        {saved && <span className="text-sm text-emerald-600">Saved ✓</span>}
      </div>
    </form>
  );
}
