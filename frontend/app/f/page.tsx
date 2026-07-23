"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "next/navigation";
import {
  ApiError,
  facilitatorAdvance,
  facilitatorAnswerHelp,
  facilitatorBroadcast,
  facilitatorClearBroadcast,
  facilitatorDashboard,
  facilitatorPause,
  facilitatorResolveHelp,
  facilitatorUndo,
  facilitatorWorkshop,
  type DashboardParticipant,
  type DashboardPayload,
  type FacilitatorWorkshopPayload,
  type HelpQueueItem,
} from "@/lib/api";
import { usePoll } from "@/lib/poll";
import { useNowTick, cn } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { ConnectionIndicator } from "@/components/ui/ConnectionIndicator";
import { WorkshopStatusBadge } from "@/components/ui/Badge";
import { StubAction } from "@/components/ui/StubBadge";
import { useToast } from "@/components/ui/Toast";
import { StatCards } from "@/components/facilitator/StatCards";
import { MilestoneBars } from "@/components/facilitator/MilestoneBars";
import { DistributionChart } from "@/components/facilitator/DistributionChart";
import { ParticipantTable } from "@/components/facilitator/ParticipantTable";
import { HelpQueue } from "@/components/facilitator/HelpQueue";
import {
  ActiveBroadcastBar,
  BroadcastAction,
  BroadcastComposer,
} from "@/components/facilitator/BroadcastPanel";
import { UndoBanner, type UndoState } from "@/components/facilitator/UndoBanner";
import { PauseControl } from "@/components/facilitator/PauseControl";
import { MilestonesTab } from "@/components/facilitator/MilestonesTab";
import { MilestoneSubmissions } from "@/components/facilitator/MilestoneSubmissions";
import { WorkshopDetailsForm } from "@/components/facilitator/WorkshopDetailsForm";
import { EditParticipantModal } from "@/components/facilitator/EditParticipantModal";
import { AuditPanel } from "@/components/facilitator/AuditPanel";
import { BottleneckCard } from "@/components/facilitator/AlertsCards";
import { PulseCard } from "@/components/facilitator/PulseCard";
import { SettingsControl } from "@/components/facilitator/SettingsControl";

function DashboardSkeleton() {
  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      <Skeleton className="h-20 w-full" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    </main>
  );
}

function ErrorScreen({ title, hint }: { title: string; hint: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-lg p-8 text-center">
        <p aria-hidden="true" className="text-3xl">
          ⛵
        </p>
        <h1 className="mt-2 text-xl font-semibold text-stone-900">{title}</h1>
        <p className="mt-2 text-stone-500">{hint}</p>
      </Card>
    </main>
  );
}

function DashboardInner() {
  const params = useSearchParams();
  const token = params.get("t");
  const toast = useToast();
  const nowMs = useNowTick(30000);

  // ---- dashboard poll (2 s visible / 10 s hidden) -------------------------
  const fetcher = useCallback(
    (v: number) => facilitatorDashboard(token as string, v),
    [token],
  );
  const { data, contentVersion, reconnecting, fatalError, pollNow } =
    usePoll<DashboardPayload>(token ? fetcher : null, {
      visibleMs: 2000,
      hiddenMs: 10000,
    });

  // ---- workshop payload (header, links, milestone bodies) -----------------
  // Fetched on load and re-fetched whenever the poll reports a newer
  // content_version (spec/api.md).
  const [wsPayload, setWsPayload] = useState<FacilitatorWorkshopPayload | null>(
    null,
  );
  const [wsFatal, setWsFatal] = useState<ApiError | null>(null);
  const wsCvRef = useRef<number>(-2); // -2 = never fetched
  const [wsRetry, setWsRetry] = useState(0);
  useEffect(() => {
    if (!token) return;
    if (wsCvRef.current !== -2 && wsCvRef.current >= contentVersion) return;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    facilitatorWorkshop(token)
      .then((payload) => {
        if (cancelled) return;
        wsCvRef.current = payload.content_version;
        setWsPayload(payload);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setWsFatal(err);
        } else {
          retryTimer = setTimeout(() => setWsRetry((x) => x + 1), 3000);
        }
      });
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [token, contentVersion, wsRetry]);

  // ---- optimistic help-queue overrides ------------------------------------
  const [overrides, setOverrides] = useState<
    Record<number, { item: HelpQueueItem; minVersion: number }>
  >({});
  const [busyIds, setBusyIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!data) return;
    setOverrides((prev) => {
      const next: typeof prev = {};
      let changed = false;
      for (const [k, v] of Object.entries(prev)) {
        if (data.version >= v.minVersion) changed = true;
        else next[Number(k)] = v;
      }
      return changed ? next : prev;
    });
  }, [data]);

  const queue = useMemo(
    () =>
      (data?.help_queue ?? []).map((item) => overrides[item.id]?.item ?? item),
    [data, overrides],
  );

  const withBusy = async (id: number, fn: () => Promise<void>) => {
    setBusyIds((prev) => new Set(prev).add(id));
    try {
      await fn();
    } finally {
      setBusyIds((prev) => {
        const copy = new Set(prev);
        copy.delete(id);
        return copy;
      });
    }
  };

  const onAnswer = async (id: number, answerMd: string): Promise<boolean> => {
    if (!token) return false;
    let ok = false;
    await withBusy(id, async () => {
      try {
        const res = await facilitatorAnswerHelp(token, id, answerMd);
        setOverrides((prev) => ({
          ...prev,
          [id]: { item: res.help_request, minVersion: res.version },
        }));
        pollNow();
        ok = true;
      } catch (err) {
        toast.show(
          err instanceof ApiError
            ? `Couldn't send the answer — ${err.message}`
            : "Couldn't send the answer — check your connection and try again.",
          "error",
        );
      }
    });
    return ok;
  };

  const onResolve = async (id: number) => {
    if (!token) return;
    await withBusy(id, async () => {
      try {
        const res = await facilitatorResolveHelp(token, id);
        setOverrides((prev) => ({
          ...prev,
          [id]: { item: res.help_request, minVersion: res.version },
        }));
        pollNow();
      } catch (err) {
        toast.show(
          err instanceof ApiError
            ? `Couldn't resolve that — ${err.message}`
            : "Couldn't resolve that — check your connection and try again.",
          "error",
        );
      }
    });
  };

  // ---- crowd milestone: where the largest group currently sits ------------
  const crowdMilestoneId = useMemo(() => {
    if (!data || data.participants.length === 0) return null;
    const counts = new Map<number, number>();
    for (const p of data.participants) {
      if (p.current_milestone_id !== null) {
        counts.set(
          p.current_milestone_id,
          (counts.get(p.current_milestone_id) ?? 0) + 1,
        );
      }
    }
    let best: number | null = null;
    let bestCount = 0;
    for (const [id, count] of counts) {
      if (count > bestCount) {
        best = id;
        bestCount = count;
      }
    }
    return best;
  }, [data]);

  // ---- broadcast composer + undo toast -------------------------------------
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [broadcastSubmitting, setBroadcastSubmitting] = useState(false);
  const [clearingBroadcast, setClearingBroadcast] = useState(false);
  const [undo, setUndo] = useState<UndoState | null>(null);
  const [undoBusy, setUndoBusy] = useState(false);

  const issueUndo = (actionId: number, label: string) => {
    setUndo({ actionId, label, expiresAt: Date.now() + 30000 });
  };

  const onSendBroadcast = async (messageMd: string): Promise<boolean> => {
    if (!token) return false;
    setBroadcastSubmitting(true);
    try {
      const res = await facilitatorBroadcast(token, messageMd);
      pollNow();
      issueUndo(res.undoable_action_id, "Broadcast sent");
      return true;
    } catch (err) {
      toast.show(
        err instanceof ApiError
          ? `Couldn't send that — ${err.message}`
          : "Couldn't send that — check your connection and try again.",
        "error",
      );
      return false;
    } finally {
      setBroadcastSubmitting(false);
    }
  };

  const onClearBroadcast = async () => {
    if (!token) return;
    setClearingBroadcast(true);
    try {
      await facilitatorClearBroadcast(token);
      pollNow();
    } catch (err) {
      toast.show(
        err instanceof ApiError
          ? `Couldn't clear that — ${err.message}`
          : "Couldn't clear that — check your connection and try again.",
        "error",
      );
    } finally {
      setClearingBroadcast(false);
    }
  };

  // ---- pause/resume ---------------------------------------------------------
  const [pauseBusy, setPauseBusy] = useState(false);
  const onTogglePause = async () => {
    if (!token || !data) return;
    const next = !data.workshop.paused;
    setPauseBusy(true);
    try {
      const res = await facilitatorPause(token, next);
      pollNow();
      issueUndo(res.undoable_action_id, next ? "Workshop paused" : "Workshop resumed");
    } catch (err) {
      toast.show(
        err instanceof ApiError
          ? `Couldn't change that — ${err.message}`
          : "Couldn't change that — check your connection and try again.",
        "error",
      );
    } finally {
      setPauseBusy(false);
    }
  };

  const onUndo = async (actionId: number) => {
    if (!token) return;
    setUndoBusy(true);
    try {
      await facilitatorUndo(token, actionId);
      pollNow();
      toast.show("Undone.", "success");
    } catch (err) {
      toast.show(
        err instanceof ApiError
          ? `Couldn't undo that — ${err.message}`
          : "Couldn't undo that — check your connection and try again.",
        "error",
      );
    } finally {
      setUndoBusy(false);
      setUndo(null);
    }
  };

  // ---- advance (bulk) --------------------------------------------------------
  // Fires immediately like pause/broadcast; the undo toast is the safety net for
  // a fat-fingered advance (spec/roadmap.md Phase 2 — undo, not an upfront gate).
  const [advanceBusy, setAdvanceBusy] = useState(false);

  const runAdvance = async (
    milestoneId: number,
    title: string,
    participantIds: number[] | null,
  ) => {
    if (!token || advanceBusy) return;
    setAdvanceBusy(true);
    try {
      const res = await facilitatorAdvance(token, milestoneId, participantIds);
      pollNow();
      setSelectedIds(new Set());
      issueUndo(res.undoable_action_id, `Advanced ${res.affected_count} to "${title}"`);
    } catch (err) {
      toast.show(
        err instanceof ApiError
          ? `Couldn't advance that — ${err.message}`
          : "Couldn't advance that — check your connection and try again.",
        "error",
      );
    } finally {
      setAdvanceBusy(false);
    }
  };

  // ---- participant selection (advance-selected) ------------------------------
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const toggleSelect = (id: number) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  // ---- milestone management modal --------------------------------------------
  const [manageOpen, setManageOpen] = useState(false);

  // ---- edit-participant modal ------------------------------------------------
  const [editingParticipant, setEditingParticipant] =
    useState<DashboardParticipant | null>(null);

  // ---- right-rail tab: help queue vs audit trail ------------------------------
  const [rightTab, setRightTab] = useState<"help" | "audit" | "settings">("help");

  // ---- render -------------------------------------------------------------
  if (!token) {
    return (
      <ErrorScreen
        title="This facilitator link isn't valid"
        hint="The link is missing its key. Use the exact facilitator link from workshop creation, or Admin Home."
      />
    );
  }
  if (fatalError || wsFatal) {
    return (
      <ErrorScreen
        title="This facilitator link isn't valid"
        hint="Check the link against the one shown when the workshop was created — it's the only key to this dashboard."
      />
    );
  }
  if (!data || !wsPayload) return <DashboardSkeleton />;

  const ws = wsPayload.workshop;

  return (
    <div data-testid="dashboard-page" className="min-h-screen">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h1 className="min-w-0 truncate text-xl font-semibold text-stone-900">
              {ws.name}
            </h1>
            <WorkshopStatusBadge status={data.workshop.status} />
            {data.workshop.paused && (
              <span className="text-sm font-medium text-amber-700">Paused</span>
            )}
            <span className="text-sm text-stone-500 tabular-nums">
              {data.stats.participant_count} participants ·{" "}
              {data.stats.active_count} active
            </span>
            <ConnectionIndicator reconnecting={reconnecting} />
            <div className="ml-auto flex min-w-0 items-center gap-2">
              <span className="hidden max-w-[16rem] truncate font-mono text-xs text-stone-500 md:inline">
                {ws.join_url}
              </span>
              <CopyButton
                text={ws.join_url}
                label="Copy join link"
                aria-label="Copy join link"
              />
            </div>
          </div>
          <div
            aria-label="Facilitator controls"
            className="mt-3 flex flex-wrap items-center gap-2"
          >
            <BroadcastAction onOpen={() => setBroadcastOpen(true)} />
            <PauseControl
              paused={data.workshop.paused}
              busy={pauseBusy}
              onToggle={onTogglePause}
            />
            <Button
              variant="secondary"
              size="sm"
              data-testid="milestones-tab"
              onClick={() => {
                setManageOpen(true);
                setTimeout(
                  () => document.getElementById("manage-workshop")?.scrollIntoView({ behavior: "smooth", block: "start" }),
                  50,
                );
              }}
            >
              Manage workshop
            </Button>
            <StubAction label="End workshop" />
            <StubAction label="AI help-desk" />
          </div>
        </div>
      </header>

      {data.broadcast && (
        <ActiveBroadcastBar
          broadcast={data.broadcast}
          onClear={onClearBroadcast}
          clearing={clearingBroadcast}
        />
      )}

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        <StatCards stats={data.stats} />

        <Card className="p-5">
          <h2 className="mb-3 text-base font-semibold text-stone-900">
            Participants
          </h2>
          <ParticipantTable
            participants={data.participants}
            milestoneStats={data.milestone_stats}
            joinUrl={ws.join_url}
            joinForm={ws.join_form ?? []}
            exportHref={`/api/f/${encodeURIComponent(token)}/participants.csv`}
            onEditParticipant={setEditingParticipant}
            nowMs={nowMs}
            selectable
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            onAdvanceSelected={(id, title, ids) => runAdvance(id, title, ids)}
          />
        </Card>

        {data.milestone_stats.some((m) => m.input_config) && (
          <Card className="p-5">
            <h2 className="mb-3 text-base font-semibold text-stone-900">
              Milestone submissions
            </h2>
            <MilestoneSubmissions
              milestoneStats={data.milestone_stats}
              participants={data.participants}
            />
          </Card>
        )}

        <div className="grid items-start gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            <Card className="p-5">
              <h2 className="mb-3 text-base font-semibold text-stone-900">
                Milestone completion
              </h2>
              {data.milestone_stats.length === 0 ? (
                <p className="text-sm text-stone-500">
                  This workshop has no milestones.
                </p>
              ) : (
                <MilestoneBars
                  milestoneStats={data.milestone_stats}
                  totalParticipants={data.stats.participant_count}
                  crowdMilestoneId={crowdMilestoneId}
                  onAdvanceAll={(id, title) => runAdvance(id, title, null)}
                />
              )}
            </Card>

            <Card className="p-5">
              <h2 className="mb-3 text-base font-semibold text-stone-900">
                Cohort distribution
              </h2>
              {data.stats.participant_count === 0 ? (
                <p className="text-sm text-stone-500">
                  The room's shape appears here once people join.
                </p>
              ) : (
                <DistributionChart distribution={data.distribution} />
              )}
            </Card>
          </div>

          <div className="space-y-4">
            <Card className="p-5">
              <div className="mb-3 flex flex-wrap items-center gap-3" role="tablist" aria-label="Help queue or audit trail">
                <button
                  type="button"
                  role="tab"
                  aria-selected={rightTab === "help"}
                  onClick={() => setRightTab("help")}
                  className={cn(
                    "rounded-md px-2 py-1 text-base font-semibold",
                    rightTab === "help" ? "text-stone-900" : "text-stone-400 hover:text-stone-600",
                  )}
                >
                  Help queue
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={rightTab === "audit"}
                  data-testid="audit-tab"
                  onClick={() => setRightTab("audit")}
                  className={cn(
                    "rounded-md px-2 py-1 text-base font-semibold",
                    rightTab === "audit" ? "text-stone-900" : "text-stone-400 hover:text-stone-600",
                  )}
                >
                  Audit trail
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={rightTab === "settings"}
                  data-testid="settings-tab"
                  onClick={() => setRightTab("settings")}
                  className={cn(
                    "rounded-md px-2 py-1 text-base font-semibold",
                    rightTab === "settings" ? "text-stone-900" : "text-stone-400 hover:text-stone-600",
                  )}
                >
                  Settings
                </button>
              </div>
              {rightTab === "help" ? (
                <HelpQueue
                  queue={queue}
                  nowMs={nowMs}
                  onAnswer={onAnswer}
                  onResolve={onResolve}
                  busyIds={busyIds}
                />
              ) : rightTab === "audit" ? (
                <AuditPanel token={token} nowMs={nowMs} active={rightTab === "audit"} />
              ) : (
                <SettingsControl token={token} onSaved={() => pollNow()} />
              )}
            </Card>

            <div data-testid="alerts-rail" className="space-y-4">
              <BottleneckCard alerts={data.alerts} />
            </div>
            <PulseCard pulse={data.pulse} />
          </div>
        </div>
      </main>

      {manageOpen && (
        <section id="manage-workshop" className="mx-auto w-full max-w-6xl px-4 pb-8 sm:px-6" aria-label="Manage workshop">
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-stone-900">Manage workshop</h2>
              <Button variant="ghost" size="sm" onClick={() => setManageOpen(false)}>
                Close
              </Button>
            </div>
            <WorkshopDetailsForm
              token={token}
              name={ws.name}
              descriptionMd={ws.description_md}
              joinForm={ws.join_form ?? []}
              onSaved={() => {
                pollNow();
                wsCvRef.current = -2;
                setWsRetry((x) => x + 1);
              }}
            />
            <MilestonesTab
              token={token}
              milestones={wsPayload.milestones}
              onChanged={() => {
                pollNow();
                wsCvRef.current = -2;
                setWsRetry((x) => x + 1);
              }}
            />
          </Card>
        </section>
      )}

      <BroadcastComposer
        open={broadcastOpen}
        submitting={broadcastSubmitting}
        onClose={() => setBroadcastOpen(false)}
        onSend={onSendBroadcast}
      />

      <UndoBanner state={undo} busy={undoBusy} onUndo={onUndo} onDismiss={() => setUndo(null)} />

      <EditParticipantModal
        token={token}
        participant={editingParticipant}
        joinForm={ws.join_form ?? []}
        onClose={() => setEditingParticipant(null)}
        onSaved={pollNow}
      />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardInner />
    </Suspense>
  );
}
