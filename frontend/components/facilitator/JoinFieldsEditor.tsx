"use client";

import type { JoinFormField } from "@/lib/api";
import { Button } from "@/components/ui/Button";

export interface JoinFieldDraft {
  key: string;
  label: string;
  type: "text" | "dropdown";
  required: boolean;
  options: string; // comma-separated in the editor; split on submit
}

export function draftsToFields(drafts: JoinFieldDraft[]): {
  fields?: JoinFormField[];
  error?: string;
} {
  const fields: JoinFormField[] = [];
  const seen = new Set<string>();
  for (const [i, d] of drafts.entries()) {
    const label = d.label.trim();
    if (!label) continue; // blank rows are dropped, matching milestone rows
    const key =
      d.key.trim() ||
      label
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .replace(/^([0-9])/, "f$1")
        .slice(0, 40);
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(key)) {
      return { error: `Join field ${i + 1}: couldn't derive a valid key from the label.` };
    }
    if (seen.has(key)) {
      return { error: `Join field ${i + 1}: duplicate field "${key}".` };
    }
    seen.add(key);
    const field: JoinFormField = { key, label, type: d.type, required: d.required };
    if (d.type === "dropdown") {
      const options = d.options
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean);
      if (options.length === 0) {
        return { error: `Join field ${i + 1} ("${label}"): dropdown needs at least one option.` };
      }
      field.options = options;
    }
    fields.push(field);
  }
  return { fields };
}

export function fieldsToDrafts(fields: JoinFormField[]): JoinFieldDraft[] {
  return fields.map((f) => ({
    key: f.key,
    label: f.label,
    type: f.type,
    required: f.required,
    options: (f.options ?? []).join(", "),
  }));
}

/** Row editor for custom join-form fields (used at create time and in Manage workshop). */
export function JoinFieldsEditor({
  drafts,
  onChange,
}: {
  drafts: JoinFieldDraft[];
  onChange: (next: JoinFieldDraft[]) => void;
}) {
  const update = (i: number, patch: Partial<JoinFieldDraft>) =>
    onChange(drafts.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  return (
    <div data-testid="join-fields-editor">
      <p className="mb-2 text-sm text-stone-500">
        Participants always give their name. Add extra questions for the join form below.
      </p>
      <div className="space-y-3">
        {drafts.map((d, i) => (
          <div
            key={i}
            data-testid="join-field-row"
            className="rounded-lg border border-stone-200 bg-stone-50 p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <input
                data-testid="join-field-label"
                value={d.label}
                maxLength={120}
                onChange={(e) => update(i, { label: e.target.value })}
                placeholder="Question (e.g. Your team)"
                className="min-w-40 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500"
              />
              <select
                data-testid="join-field-type"
                value={d.type}
                onChange={(e) => update(i, { type: e.target.value as "text" | "dropdown" })}
                className="rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm"
              >
                <option value="text">Text</option>
                <option value="dropdown">Dropdown</option>
              </select>
              <label className="flex items-center gap-1.5 text-sm text-stone-700">
                <input
                  data-testid="join-field-required"
                  type="checkbox"
                  checked={d.required}
                  onChange={(e) => update(i, { required: e.target.checked })}
                  className="size-4 accent-brand-600"
                />
                Required
              </label>
              <button
                type="button"
                data-testid="join-field-remove"
                onClick={() => onChange(drafts.filter((_, j) => j !== i))}
                className="rounded-md px-2 py-1 text-sm text-stone-400 hover:bg-stone-200 hover:text-stone-700"
                aria-label={`Remove join field ${i + 1}`}
              >
                ✕
              </button>
            </div>
            {d.type === "dropdown" && (
              <input
                data-testid="join-field-options"
                value={d.options}
                onChange={(e) => update(i, { options: e.target.value })}
                placeholder="Options, comma-separated (e.g. Student, Engineer, Other)"
                className="mt-2 w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500"
              />
            )}
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        data-testid="add-join-field-button"
        className="mt-3"
        onClick={() =>
          onChange([...drafts, { key: "", label: "", type: "text", required: false, options: "" }])
        }
      >
        + Add join question
      </Button>
    </div>
  );
}
