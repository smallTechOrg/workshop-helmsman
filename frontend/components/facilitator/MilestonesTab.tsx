"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  facilitatorAddMilestone,
  facilitatorDeleteMilestone,
  facilitatorEditMilestone,
  facilitatorReorder,
  type MilestoneFull,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";

interface Row {
  id: number;
  title: string;
  content_md: string;
  minutes: string;
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
  const [draft, setDraft] = useState<{ title: string; content_md: string; minutes: string }>({
    title: "",
    content_md: "",
    minutes: "",
  });
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

  const startEdit = (row: Row) => {
    setEditing(row.id);
    setDraft({ title: row.title, content_md: row.content_md, minutes: row.minutes });
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
    setBusy(true);
    try {
      await facilitatorEditMilestone(token, editing, {
        title: v.title,
        content_md: draft.content_md,
        minutes: v.minutes,
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
    setDraft({ title: "", content_md: "", minutes: "" });
    setError(null);
  };

  const saveAdd = async () => {
    setError(null);
    const v = validate();
    if (!v) return;
    setBusy(true);
    try {
      await facilitatorAddMilestone(token, {
        title: v.title,
        content_md: draft.content_md,
        minutes: v.minutes,
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
                    <Button variant="ghost" size="sm" onClick={() => startEdit(row)}>
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
