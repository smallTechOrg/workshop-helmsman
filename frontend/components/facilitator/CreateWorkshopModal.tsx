"use client";

import { useState } from "react";
import {
  ApiError,
  adminCreateWorkshop,
  type MilestoneInput,
  type WorkshopFull,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import {
  JoinFieldsEditor,
  draftsToFields,
  type JoinFieldDraft,
} from "@/components/facilitator/JoinFieldsEditor";
import { Modal } from "@/components/ui/Modal";
import { Markdown } from "@/components/ui/Markdown";
import { StubCard } from "@/components/ui/StubBadge";
import { cn } from "@/lib/format";

interface MilestoneRow {
  key: number;
  title: string;
  content: string;
  minutes: string;
  tab: "write" | "preview";
}

let rowKey = 1;

function newRow(): MilestoneRow {
  return { key: rowKey++, title: "", content: "", minutes: "", tab: "write" };
}

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
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rows, setRows] = useState<MilestoneRow[]>([]);
  const [joinFields, setJoinFields] = useState<JoinFieldDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const patchRow = (key: number, patch: Partial<MilestoneRow>) =>
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const moveRow = (key: number, dir: -1 | 1) =>
    setRows((prev) => {
      const i = prev.findIndex((r) => r.key === key);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });

  const removeRow = (key: number) =>
    setRows((prev) => prev.filter((r) => r.key !== key));

  const reset = () => {
    setJoinFields([]);
    setName("");
    setDescription("");
    setRows([]);
    setError(null);
  };

  const submit = async () => {
    setError(null);
    const trimmedName = name.trim();
    if (trimmedName.length < 1 || trimmedName.length > 120) {
      setError("Give the workshop a name (1–120 characters).");
      return;
    }
    if (description.length > 10000) {
      setError("The description is too long (max 10,000 characters).");
      return;
    }
    // Ignore rows that were added but left entirely empty.
    const meaningful = rows.filter(
      (r) => r.title.trim() !== "" || r.content.trim() !== "",
    );
    if (meaningful.length === 0) {
      setError("Add at least one milestone — participants need something to work through.");
      return;
    }
    const milestones: MilestoneInput[] = [];
    for (const [i, r] of meaningful.entries()) {
      const title = r.title.trim();
      if (title.length < 1 || title.length > 200) {
        setError(`Milestone ${i + 1} needs a title (1–200 characters).`);
        return;
      }
      if (r.content.length > 20000) {
        setError(`Milestone ${i + 1}'s instructions are too long (max 20,000 characters).`);
        return;
      }
      let minutes: number | null = null;
      if (r.minutes.trim() !== "") {
        minutes = Number(r.minutes);
        if (!Number.isInteger(minutes) || minutes < 1 || minutes > 480) {
          setError(`Milestone ${i + 1}: minutes must be a whole number from 1 to 480.`);
          return;
        }
      }
      milestones.push({ title, content_md: r.content, minutes });
    }

    const joinForm = draftsToFields(joinFields);
    if (joinForm.error) {
      setError(joinForm.error);
      return;
    }

    setSubmitting(true);
    try {
      const { workshop } = await adminCreateWorkshop(adminKey, {
        name: trimmedName,
        description_md: description,
        milestones,
        join_form: joinForm.fields,
      });
      reset();
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
        <div>
          <label
            htmlFor="cw-name"
            className="mb-1 block text-sm font-medium text-stone-700"
          >
            Workshop name
          </label>
          <input
            id="cw-name"
            data-testid="workshop-name-input"
            type="text"
            value={name}
            maxLength={120}
            onChange={(e) => setName(e.target.value)}
            placeholder="LangGraph Lab — July"
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
          />
        </div>

        <div>
          <label
            htmlFor="cw-desc"
            className="mb-1 block text-sm font-medium text-stone-700"
          >
            Description{" "}
            <span className="font-normal text-stone-400">(markdown, optional)</span>
          </label>
          <textarea
            id="cw-desc"
            value={description}
            maxLength={10000}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Welcome! Today we're building…"
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
          />
        </div>

        <div>
          <p className="mb-1 block text-sm font-medium text-stone-700">Join form</p>
          <JoinFieldsEditor drafts={joinFields} onChange={setJoinFields} />
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
              onClick={() => setRows((prev) => [...prev, newRow()])}
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
                      onChange={(e) => patchRow(row.key, { minutes: e.target.value })}
                      placeholder="min"
                      aria-label={`Milestone ${i + 1} planned minutes (optional)`}
                      className="w-16 rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
                    />
                    <div className="flex shrink-0 items-center">
                      <button
                        type="button"
                        onClick={() => moveRow(row.key, -1)}
                        disabled={i === 0}
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
                        disabled={i === rows.length - 1}
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
                        aria-label={`Remove milestone ${i + 1}`}
                        className="rounded-md p-1 text-stone-400 hover:bg-red-50 hover:text-red-600"
                      >
                        <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-4">
                          <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 0 0 6 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 1 0 .23 1.482l.149-.022.841 10.518A2.75 2.75 0 0 0 7.596 19h4.807a2.75 2.75 0 0 0 2.742-2.53l.841-10.52.149.023a.75.75 0 0 0 .23-1.482 41.03 41.03 0 0 0-2.365-.298V3.75A2.75 2.75 0 0 0 11.25 1h-2.5ZM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4Z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  <div className="mb-1.5 flex gap-1" role="tablist" aria-label={`Milestone ${i + 1} content editor`}>
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

        {error && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
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
