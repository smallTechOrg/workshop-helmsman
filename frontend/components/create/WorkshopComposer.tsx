"use client";

/**
 * The single workshop composer — name, description, join form and ordered
 * milestone rows (markdown Write/Preview + minutes + reorder/remove).
 *
 * ONE implementation, used by BOTH the admin console (`/app/admin/`, inside the
 * New-workshop modal) and the keyless public create flow (`/app/create/`).
 * Never fork this component: spec/capabilities.md C6 requires the public flow to
 * be the *same* flow the admin already uses.
 *
 * It is fully controlled — the caller owns `value` so a failed submit can keep
 * the composed workshop intact (C6 §Errors: "form preserved, never lost").
 */

import type { CreateWorkshopBody, MilestoneInput } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import {
  JoinFieldsEditor,
  draftsToFields,
  type JoinFieldDraft,
} from "@/components/facilitator/JoinFieldsEditor";
import { Markdown } from "@/components/ui/Markdown";
import { StubCard } from "@/components/ui/StubBadge";
import { cn } from "@/lib/format";

export interface MilestoneRow {
  key: number;
  title: string;
  content: string;
  minutes: string;
  tab: "write" | "preview";
}

export interface ComposerValue {
  name: string;
  description: string;
  rows: MilestoneRow[];
  joinFields: JoinFieldDraft[];
}

let rowKey = 1;

export function newMilestoneRow(): MilestoneRow {
  return { key: rowKey++, title: "", content: "", minutes: "", tab: "write" };
}

export function emptyComposerValue(): ComposerValue {
  return { name: "", description: "", rows: [], joinFields: [] };
}

/**
 * Client-side mirror of the server validation in spec/api.md (§`POST
 * /api/admin/workshops`). Returns the request body, or the first human-readable
 * problem. The server re-validates — this only spares a round-trip.
 */
export function validateComposer(
  value: ComposerValue,
): { ok: true; body: CreateWorkshopBody } | { ok: false; error: string } {
  const trimmedName = value.name.trim();
  if (trimmedName.length < 1 || trimmedName.length > 120) {
    return { ok: false, error: "Give the workshop a name (1–120 characters)." };
  }
  if (value.description.length > 10000) {
    return { ok: false, error: "The description is too long (max 10,000 characters)." };
  }
  // Ignore rows that were added but left entirely empty.
  const meaningful = value.rows.filter(
    (r) => r.title.trim() !== "" || r.content.trim() !== "",
  );
  if (meaningful.length === 0) {
    return {
      ok: false,
      error: "Add at least one milestone — participants need something to work through.",
    };
  }
  const milestones: MilestoneInput[] = [];
  for (const [i, r] of meaningful.entries()) {
    const title = r.title.trim();
    if (title.length < 1 || title.length > 200) {
      return { ok: false, error: `Milestone ${i + 1} needs a title (1–200 characters).` };
    }
    if (r.content.length > 20000) {
      return {
        ok: false,
        error: `Milestone ${i + 1}'s instructions are too long (max 20,000 characters).`,
      };
    }
    let minutes: number | null = null;
    if (r.minutes.trim() !== "") {
      minutes = Number(r.minutes);
      if (!Number.isInteger(minutes) || minutes < 1 || minutes > 480) {
        return {
          ok: false,
          error: `Milestone ${i + 1}: minutes must be a whole number from 1 to 480.`,
        };
      }
    }
    milestones.push({ title, content_md: r.content, minutes });
  }

  const joinForm = draftsToFields(value.joinFields);
  if (joinForm.error) return { ok: false, error: joinForm.error };

  return {
    ok: true,
    body: {
      name: trimmedName,
      description_md: value.description,
      milestones,
      join_form: joinForm.fields,
    },
  };
}

export function WorkshopComposer({
  value,
  onChange,
  disabled = false,
  idPrefix = "cw",
}: {
  value: ComposerValue;
  onChange: (next: ComposerValue) => void;
  disabled?: boolean;
  idPrefix?: string;
}) {
  const { name, description, rows, joinFields } = value;

  const patch = (p: Partial<ComposerValue>) => onChange({ ...value, ...p });

  const patchRow = (key: number, p: Partial<MilestoneRow>) =>
    patch({ rows: rows.map((r) => (r.key === key ? { ...r, ...p } : r)) });

  const moveRow = (key: number, dir: -1 | 1) => {
    const i = rows.findIndex((r) => r.key === key);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= rows.length) return;
    const next = [...rows];
    [next[i], next[j]] = [next[j], next[i]];
    patch({ rows: next });
  };

  const removeRow = (key: number) => patch({ rows: rows.filter((r) => r.key !== key) });

  return (
    <div data-testid="composer" className="space-y-5">
      <div>
        <label
          htmlFor={`${idPrefix}-name`}
          className="mb-1 block text-sm font-medium text-stone-700"
        >
          Workshop name
        </label>
        <input
          id={`${idPrefix}-name`}
          data-testid="workshop-name-input"
          type="text"
          value={name}
          maxLength={120}
          disabled={disabled}
          onChange={(e) => patch({ name: e.target.value })}
          placeholder="LangGraph Lab — July"
          className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
        />
      </div>

      <div>
        <label
          htmlFor={`${idPrefix}-desc`}
          className="mb-1 block text-sm font-medium text-stone-700"
        >
          Description{" "}
          <span className="font-normal text-stone-400">(markdown, optional)</span>
        </label>
        <textarea
          id={`${idPrefix}-desc`}
          value={description}
          maxLength={10000}
          disabled={disabled}
          onChange={(e) => patch({ description: e.target.value })}
          rows={2}
          placeholder="Welcome! Today we're building…"
          className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
        />
      </div>

      <div>
        <p className="mb-1 block text-sm font-medium text-stone-700">Join form</p>
        <JoinFieldsEditor
          drafts={joinFields}
          onChange={(drafts) => patch({ joinFields: drafts })}
        />
      </div>

      <StubCard
        title="Start from a template"
        description="Pick a saved agenda template instead of building from scratch."
      />

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-stone-800">
            Milestones{" "}
            <span className="font-normal text-stone-400">(in workshop order)</span>
          </h3>
          <Button
            variant="secondary"
            size="sm"
            data-testid="add-milestone-button"
            disabled={disabled}
            onClick={() => patch({ rows: [...rows, newMilestoneRow()] })}
          >
            + Add milestone
          </Button>
        </div>

        {rows.length === 0 ? (
          <p className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-center text-sm text-stone-500">
            No milestones yet — add the first step participants will work through.
          </p>
        ) : (
          <ol className="space-y-3">
            {rows.map((row, i) => (
              <li
                key={row.key}
                className="rounded-lg border border-stone-200 bg-stone-50/60 p-3"
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                    {i + 1}
                  </span>
                  <input
                    data-testid="milestone-title-input"
                    type="text"
                    value={row.title}
                    maxLength={200}
                    disabled={disabled}
                    onChange={(e) => patchRow(row.key, { title: e.target.value })}
                    placeholder="Milestone title, e.g. Set up your environment"
                    aria-label={`Milestone ${i + 1} title`}
                    className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
                  />
                  <input
                    type="number"
                    min={1}
                    max={480}
                    value={row.minutes}
                    disabled={disabled}
                    onChange={(e) => patchRow(row.key, { minutes: e.target.value })}
                    placeholder="min"
                    aria-label={`Milestone ${i + 1} planned minutes (optional)`}
                    className="w-16 rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
                  />
                  <div className="flex shrink-0 items-center">
                    <button
                      type="button"
                      onClick={() => moveRow(row.key, -1)}
                      disabled={disabled || i === 0}
                      aria-label={`Move milestone ${i + 1} up`}
                      className="rounded-md p-1 text-stone-400 hover:bg-stone-200 hover:text-stone-600 disabled:opacity-30"
                    >
                      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
                        <path fillRule="evenodd" d="M9.47 6.47a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 1 1-1.06 1.06L10 8.06l-3.72 3.72a.75.75 0 0 1-1.06-1.06l4.25-4.25Z" clipRule="evenodd" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      onClick={() => moveRow(row.key, 1)}
                      disabled={disabled || i === rows.length - 1}
                      aria-label={`Move milestone ${i + 1} down`}
                      className="rounded-md p-1 text-stone-400 hover:bg-stone-200 hover:text-stone-600 disabled:opacity-30"
                    >
                      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
                        <path fillRule="evenodd" d="M10.53 13.53a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 1.06-1.06L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25Z" clipRule="evenodd" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      onClick={() => removeRow(row.key)}
                      disabled={disabled}
                      aria-label={`Remove milestone ${i + 1}`}
                      className="rounded-md p-1 text-stone-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
                        <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 0 0 6 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 1 0 .23 1.482l.149-.022.841 10.518A2.75 2.75 0 0 0 7.596 19h4.807a2.75 2.75 0 0 0 2.742-2.53l.841-10.52.149.023a.75.75 0 0 0 .23-1.482 41.03 41.03 0 0 0-2.365-.298V3.75A2.75 2.75 0 0 0 11.25 1h-2.5ZM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4Z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>
                </div>

                <div
                  className="mb-1.5 flex gap-1"
                  role="tablist"
                  aria-label={`Milestone ${i + 1} content editor`}
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={row.tab === "write"}
                    onClick={() => patchRow(row.key, { tab: "write" })}
                    className={cn(
                      "rounded-md px-2 py-1 text-xs font-medium",
                      row.tab === "write"
                        ? "bg-stone-200 text-stone-800"
                        : "text-stone-500 hover:bg-stone-100",
                    )}
                  >
                    Write
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={row.tab === "preview"}
                    onClick={() => patchRow(row.key, { tab: "preview" })}
                    className={cn(
                      "rounded-md px-2 py-1 text-xs font-medium",
                      row.tab === "preview"
                        ? "bg-stone-200 text-stone-800"
                        : "text-stone-500 hover:bg-stone-100",
                    )}
                  >
                    Preview
                  </button>
                </div>

                <textarea
                  data-testid="milestone-content-input"
                  value={row.content}
                  maxLength={20000}
                  disabled={disabled}
                  onChange={(e) => patchRow(row.key, { content: e.target.value })}
                  rows={4}
                  hidden={row.tab !== "write"}
                  placeholder={"Instructions in markdown — links, lists, and code:\n```bash\nuv sync\n```"}
                  aria-label={`Milestone ${i + 1} instructions (markdown)`}
                  className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
                />
                {row.tab === "preview" && (
                  <div className="rounded-lg border border-stone-200 bg-white px-3 py-2">
                    {row.content.trim() === "" ? (
                      <p className="text-sm text-stone-400">
                        Nothing to preview yet — write some markdown first.
                      </p>
                    ) : (
                      <Markdown className="text-sm">{row.content}</Markdown>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
