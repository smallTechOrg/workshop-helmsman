"use client";

import { useEffect, useState } from "react";
import { ApiError, facilitatorAudit, type AuditAction } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { timeAgo } from "@/lib/format";

// Keys are the exact action names persisted by the backend (record_action).
const ACTION_LABELS: Record<string, string> = {
  "workshop.create": "created the workshop",
  "workshop.edit": "edited the workshop details",
  "participant.edit": "edited a participant",
  "help.answer": "answered a help request",
  "help.resolve": "resolved a help request",
  "broadcast.send": "sent a broadcast",
  "broadcast.clear": "cleared the broadcast",
  "workshop.pause": "paused the workshop",
  "workshop.resume": "unpaused the workshop",
  "milestone.advance_all": "advanced everyone",
  "milestone.advance_selected": "advanced selected participants",
  "milestone.reorder": "reordered milestones",
  "milestone.edit": "edited a milestone",
  "settings.update": "updated settings",
};

function describe(row: AuditAction): string {
  return ACTION_LABELS[row.action] ?? row.action;
}

export function AuditPanel({
  token,
  nowMs,
  active,
}: {
  token: string;
  nowMs: number;
  /** Only fetches while the tab is active — avoids polling a hidden panel. */
  active: boolean;
}) {
  const [rows, setRows] = useState<AuditAction[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!active || loaded) return;
    setLoading(true);
    facilitatorAudit(token, { limit: 30 })
      .then((res) => {
        setRows(res.actions);
        setHasMore(res.has_more);
        setLoaded(true);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load the audit trail.");
      })
      .finally(() => setLoading(false));
  }, [active, loaded, token]);

  const loadMore = async () => {
    if (rows.length === 0) return;
    setLoading(true);
    try {
      const res = await facilitatorAudit(token, {
        beforeId: rows[rows.length - 1].id,
        limit: 30,
      });
      setRows((prev) => [...prev, ...res.actions]);
      setHasMore(res.has_more);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load more.");
    } finally {
      setLoading(false);
    }
  };

  if (!active) return null;

  if (loading && rows.length === 0) {
    return <p className="text-sm text-stone-500">Loading audit trail…</p>;
  }
  if (error && rows.length === 0) {
    return (
      <p role="alert" className="text-sm text-red-700">
        {error}
      </p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="text-sm text-stone-500">
        Nothing recorded yet — every facilitator action will show up here.
      </p>
    );
  }

  return (
    <div>
      <ul className="space-y-2" data-testid="audit-list">
        {rows.map((row) => (
          <li
            key={row.id}
            data-testid="audit-row"
            className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-stone-800">
                <span data-testid="audit-actor" className="font-medium">
                  {row.actor}
                </span>{" "}
                {describe(row)}
              </span>
              <span
                data-testid="audit-timestamp"
                title={row.created_at}
                className="shrink-0 text-xs text-stone-500"
              >
                {timeAgo(row.created_at, nowMs)}
              </span>
            </div>
            {row.undone_at && (
              <span className="mt-1 inline-block text-xs font-medium text-amber-700">
                Undone
              </span>
            )}
          </li>
        ))}
      </ul>
      {hasMore && (
        <div className="mt-3 text-center">
          <Button variant="secondary" size="sm" onClick={loadMore} loading={loading}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}
