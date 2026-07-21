"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  facilitatorAddMilestone,
  facilitatorDeleteMilestone,
  facilitatorEditMilestone,
  facilitatorReorder,
  type MilestoneFull,
  type MilestoneInputConfig,
  type MilestoneInputType,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";

interface Row {
  id: number;
  title: string;
  content_md: string;
  minutes: string;
}

interface Draft {
  title: string;
  content_md: string;
  minutes: string;
  inputType: "" | MilestoneInputType;
  inputLabel: string;
  inputOptions: string;
}

const EMPTY_DRAFT: Draft = {
  title: "",
  content_md: "",
  minutes: "",
  inputType: "",
  inputLabel: "",
  inputOptions: "",
};

function draftFromMilestone(m: MilestoneFull): Draft {
  const c = m.input_config;
  return {
    title: m.title,
    content_md: m.content_md,
    minutes: m.minutes === null ? "" : String(m.minutes),
    inputType: c?.type ?? "",
    inputLabel: c?.label ?? "",
    inputOptions: (c?.options ?? []).join("\n"),
  };
}

/** Build the input_config to send: null clears it, an object sets it. */
function buildInputConfig(draft: Draft): {
  ok: boolean;
  value?: MilestoneInputConfig | null;
  error?: string;
} {
  if (draft.inputType === "") return { ok: true, value: null };
  const config: MilestoneInputConfig = {
    type: draft.inputType,
    label: draft.inputLabel.trim(),
  };
  if (draft.inputType === "dropdown") {
    const options = draft.inputOptions
      .split("\n")
      .map((o) => o.trim())
      .filter(Boolean);
    if (options.length === 0) {
      return { ok: false, error: "A dropdown input needs at least one option (one per line)." };
    }
    if (new Set(options).size !== options.length) {
      return { ok: false, error: "Dropdown options must be unique." };
    }
    config.options = options;
  }
  return { ok: true, value: config };
}

const INPUT_TYPE_LABELS: Record<MilestoneInputType, string> = {
  github_url: "GitHub URL",
  url: "Link (URL)",
  text: "Short text",
  dropdown: "Dropdown",
};

function InputConfigEditor({
  draft,
  setDraft,
}: {
  draft: Draft;
  setDraft: React.Dispatch<React.SetStateAction<Draft>>;
}) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-3">
      <label className="mb-1 block text-xs font-medium text-stone-600">
        Require an input to complete this milestone
      </label>
      <select
        data-testid="milestone-input-type"
        value={draft.inputType}
        onChange={(e) =>
          setDraft((d) => ({ ...d, inputType: e.target.value as Draft["inputType"] }))
        }
        className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm"
      >
        <option value="">No input required</option>
        {(Object.keys(INPUT_TYPE_LABELS) as MilestoneInputType[]).map((t) => (
          <option key={t} value={t}>
            {INPUT_TYPE_LABELS[t]}
          </option>
        ))}
      </select>
      {draft.inputType !== "" && (
        <div className="mt-2 space-y-2">
          <input
            data-testid="milestone-input-label"
            value={draft.inputLabel}
            maxLength={120}
            placeholder="Field label (e.g. Your repo URL)"
            aria-label="Input field label"
            onChange={(e) => setDraft((d) => ({ ...d, inputLabel: e.target.value }))}
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm"
          />
          {draft.inputType === "dropdown" && (
            <textarea
              data-testid="milestone-input-options"
              value={draft.inputOptions}
              rows={3}
              placeholder="One option per line"
              aria-label="Dropdown options, one per line"
              onChange={(e) => setDraft((d) => ({ ...d, inputOptions: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm"
            />
          )}
          <p className="text-xs text-stone-400">
            Participants must enter a valid value here before they can mark this milestone
            complete.
          </p>
        </div>
      )}
    </div>
  );
}

function toRows(milestones: MilestoneFull[]): Row[] {
  return [...milestones]
    .sort((a, b) => a.position - b.position)
    .map((m) => ({
      id: m.id,
      title: m.title,
      content_md: m.content_md,
      minutes: m.minutes === null ? "" : String(m.minutes),
    }));
}

/**
 * Inline milestone management (reorder, add/edit/delete) — Phase 2 "Milestones" tab.
 */
export function MilestonesTab({
  token,
  milestones,
  onChanged,
}: {
  token: string;
  milestones: MilestoneFull[];
  onChanged: () => void;
}) {
  const [rows, setRows] = useState<Row[]>(() => toRows(milestones));
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setRows(toRows(milestones)), [milestones]);

  const move = async (id: number, dir: -1 | 1) => {
    const i = rows.findIndex((r) => r.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= rows.length) return;
    const next = [...rows];
    [next[i], next[j]] = [next[j], next[i]];
    setRows(next);
    setBusy(true);
    try {
      await facilitatorReorder(token, next.map((r) => r.id));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reorder milestones.");
      setRows(rows);
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (id: number) => {
    const m = milestones.find((x) => x.id === id);
    if (!m) return;
    setEditing(id);
    setDraft(draftFromMilestone(m));
    setError(null);
  };

  const validate = (): { title: string; minutes: number | null } | null => {
    const title = draft.title.trim();
    if (title.length < 1 || title.length > 200) {
      setError("Title must be 1–200 characters.");
      return null;
    }
    let minutes: number | null = null;
    if (draft.minutes.trim() !== "") {
      minutes = Number(draft.minutes);
      if (!Number.isInteger(minutes) || minutes < 1 || minutes > 480) {
        setError("Minutes must be a whole number from 1 to 480.");
        return null;
      }
    }
    return { title, minutes };
  };

  const saveEdit = async () => {
    if (editing === null) return;
    setError(null);
    const v = validate();
    if (!v) return;
    const ic = buildInputConfig(draft);
    if (!ic.ok) {
      setError(ic.error ?? "Invalid input configuration.");
      return;
    }
    setBusy(true);
    try {
      await facilitatorEditMilestone(token, editing, {
        title: v.title,
        content_md: draft.content_md,
        minutes: v.minutes,
        input_config: ic.value,
      });
      setEditing(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save that milestone.");
    } finally {
      setBusy(false);
    }
  };

  const startAdd = () => {
    setAdding(true);
    setDraft(EMPTY_DRAFT);
    setError(null);
  };

  const saveAdd = async () => {
    setError(null);
    const v = validate();
    if (!v) return;
    const ic = buildInputConfig(draft);
    if (!ic.ok) {
      setError(ic.error ?? "Invalid input configuration.");
      return;
    }
    setBusy(true);
    try {
      await facilitatorAddMilestone(token, {
        title: v.title,
        content_md: draft.content_md,
        minutes: v.minutes,
        input_config: ic.value,
      });
      setAdding(false);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't add that milestone.");
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async (id: number, title: string) => {
    if (!window.confirm(`Delete "${title}"? This removes everyone's completion of it too.`)) {
      return;
    }
    setBusy(true);
    try {
      await facilitatorDeleteMilestone(token, id);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete that milestone.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {rows.length === 0 ? (
        <p className="text-sm text-stone-500">No milestones yet — add the first one below.</p>
      ) : (
        <ol className="space-y-2" data-testid="milestone-list">
          {rows.map((row, i) => (
            <li
              key={row.id}
              data-testid="milestone-row"
              className="rounded-lg border border-stone-200 bg-stone-50/60 p-3"
            >
              {editing === row.id ? (
                <div className="space-y-2">
                  <input
                    value={draft.title}
                    maxLength={200}
                    onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                    aria-label="Milestone title"
                    className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm"
                  />
                  <textarea
                    value={draft.content_md}
                    maxLength={20000}
                    rows={3}
                    onChange={(e) => setDraft((d) => ({ ...d, content_md: e.target.value }))}
                    aria-label="Milestone instructions"
                    className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 font-mono text-sm"
                  />
                  <input
                    type="number"
                    value={draft.minutes}
                    onChange={(e) => setDraft((d) => ({ ...d, minutes: e.target.value }))}
                    aria-label="Planned minutes"
                    placeholder="min"
                    className="w-24 rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm"
                  />
                  <InputConfigEditor draft={draft} setDraft={setDraft} />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={saveEdit} loading={busy}>
                      Save
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium text-stone-800">
                    {i + 1}. {row.title}
                  </span>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      data-testid="milestone-move-up"
                      aria-label={`Move milestone ${i + 1} up`}
                      disabled={i === 0 || busy}
                      onClick={() => move(row.id, -1)}
                      className="rounded-md p-1 text-stone-400 hover:bg-stone-200 disabled:opacity-30"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      data-testid="milestone-move-down"
                      aria-label={`Move milestone ${i + 1} down`}
                      disabled={i === rows.length - 1 || busy}
                      onClick={() => move(row.id, 1)}
                      className="rounded-md p-1 text-stone-400 hover:bg-stone-200 disabled:opacity-30"
                    >
                      ↓
                    </button>
                    <Button variant="ghost" size="sm" onClick={() => startEdit(row.id)}>
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => doDelete(row.id, row.title)}>
                      Delete
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {adding ? (
        <div className="space-y-2 rounded-lg border border-stone-200 bg-stone-50/60 p-3">
          <input
            value={draft.title}
            maxLength={200}
            onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
            placeholder="Milestone title"
            aria-label="New milestone title"
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm"
          />
          <textarea
            value={draft.content_md}
            maxLength={20000}
            rows={3}
            onChange={(e) => setDraft((d) => ({ ...d, content_md: e.target.value }))}
            placeholder="Instructions (markdown)"
            aria-label="New milestone instructions"
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 font-mono text-sm"
          />
          <input
            type="number"
            value={draft.minutes}
            onChange={(e) => setDraft((d) => ({ ...d, minutes: e.target.value }))}
            placeholder="min"
            aria-label="New milestone planned minutes"
            className="w-24 rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm"
          />
          <InputConfigEditor draft={draft} setDraft={setDraft} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={saveAdd} loading={busy}>
              Add milestone
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" size="sm" onClick={startAdd}>
          + Add milestone
        </Button>
      )}
    </div>
  );
}
