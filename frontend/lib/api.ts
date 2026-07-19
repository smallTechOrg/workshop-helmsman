/**
 * Typed API client — implements spec/api.md exactly (Phase 1 surface).
 *
 * Same-origin: all calls hit absolute paths under /api/ (NOT under /app).
 * Success envelope: HTTP 200 -> {"data": <payload>, "error": null}
 * Error envelope:  HTTP 4xx/5xx -> {"detail": {"code": ..., "message": ...}}
 */

// ---------------------------------------------------------------------------
// Envelope + errors
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

interface SuccessEnvelope<T> {
  data: T;
  error: null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      cache: "no-store",
      credentials: "same-origin",
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "network_error",
      "Could not reach the server — check your connection.",
      0,
    );
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // Non-JSON body (proxy error page etc.) — fall through to status handling.
  }

  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } } | null)
      ?.detail;
    throw new ApiError(
      detail?.code ?? "internal_error",
      detail?.message ?? `The server returned an unexpected error (${res.status}).`,
      res.status,
    );
  }

  return (body as SuccessEnvelope<T>).data;
}

// ---------------------------------------------------------------------------
// Shared shapes (spec/api.md — snake_case is normative)
// ---------------------------------------------------------------------------

export type WorkshopStatus = "live" | "grace" | "archived";
export type HelpStatus = "open" | "answered" | "resolved";
export type AnswerSource = "facilitator" | "ai";

/** Unchanged short-circuit for versioned poll endpoints. */
export interface PollUnchanged {
  changed: false;
  version: number;
  content_version: number;
}

export interface MilestoneFull {
  id: number;
  position: number;
  title: string;
  content_md: string;
  minutes: number | null;
}

export interface MilestoneMeta {
  id: number;
  position: number;
  title: string;
  minutes: number | null;
}

// ---------------------------------------------------------------------------
// Admin surface (header X-Admin-Key)
// ---------------------------------------------------------------------------

export interface AdminWorkshopSummary {
  id: number;
  name: string;
  status: WorkshopStatus;
  participant_count: number;
  open_help_count: number;
  created_at: string;
  join_slug: string;
  join_url: string;
  facilitator_url: string;
}

export interface WorkshopFull {
  id: number;
  name: string;
  description_md: string;
  status: WorkshopStatus;
  paused: boolean;
  ai_enabled: boolean;
  admin_token: string;
  join_slug: string;
  join_url: string;
  facilitator_url: string;
  created_at: string;
}

export interface MilestoneInput {
  title: string;
  content_md: string;
  minutes: number | null;
}

export interface CreateWorkshopBody {
  name: string;
  description_md: string;
  milestones: MilestoneInput[];
}

export function adminListWorkshops(
  adminKey: string,
): Promise<{ workshops: AdminWorkshopSummary[] }> {
  return request("/api/admin/workshops", {
    headers: { "X-Admin-Key": adminKey },
  });
}

export function adminCreateWorkshop(
  adminKey: string,
  body: CreateWorkshopBody,
): Promise<{ workshop: WorkshopFull }> {
  return request("/api/admin/workshops", {
    method: "POST",
    headers: { "X-Admin-Key": adminKey },
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Facilitator surface (path admin_token)
// ---------------------------------------------------------------------------

export interface FacilitatorWorkshop {
  id: number;
  name: string;
  description_md: string;
  status: WorkshopStatus;
  paused: boolean;
  ai_enabled: boolean;
  join_slug: string;
  join_url: string;
  facilitator_url: string;
  created_at: string;
}

export interface FacilitatorWorkshopPayload {
  content_version: number;
  workshop: FacilitatorWorkshop;
  milestones: MilestoneFull[];
}

export interface DashboardStats {
  participant_count: number;
  active_count: number;
  finished_count: number;
  median_progress_pct: number;
  open_help_count: number;
  answered_help_count: number;
  resolved_help_count: number;
}

export interface MilestoneStat {
  milestone_id: number;
  position: number;
  title: string;
  completed_count: number;
  completed_pct: number;
}

export interface DistributionBucket {
  completed_count: number;
  participants: number;
}

export interface DashboardParticipant {
  id: number;
  name: string;
  joined_at: string;
  last_seen_at: string;
  completed_milestone_ids: number[];
  completed_count: number;
  progress_pct: number;
  current_milestone_id: number | null;
  open_help_count: number;
  participant_url: string;
}

export interface HelpAnswer {
  id: number;
  source: AnswerSource;
  answer_md: string;
  draft: boolean;
  created_at: string;
  ai_confidence: number | null;
  ai_model: string | null;
  ai_context: unknown | null;
}

export interface HelpQueueItem {
  id: number;
  participant_id: number;
  participant_name: string;
  milestone_id: number | null;
  milestone_title: string | null;
  message: string;
  status: HelpStatus;
  escalated: boolean;
  created_at: string;
  updated_at: string;
  answers: HelpAnswer[];
}

export interface DashboardPayload {
  changed: true;
  version: number;
  content_version: number;
  workshop: {
    id: number;
    name: string;
    status: WorkshopStatus;
    paused: boolean;
    ai_enabled: boolean;
  };
  stats: DashboardStats;
  milestone_stats: MilestoneStat[];
  distribution: DistributionBucket[];
  participants: DashboardParticipant[];
  help_queue: HelpQueueItem[];
  broadcast: unknown | null;
  alerts: unknown | null;
  pulse: unknown | null;
  spend: unknown | null;
}

export type DashboardPoll = PollUnchanged | DashboardPayload;

export function facilitatorWorkshop(
  adminToken: string,
): Promise<FacilitatorWorkshopPayload> {
  return request(`/api/f/${encodeURIComponent(adminToken)}/workshop`);
}

export function facilitatorDashboard(
  adminToken: string,
  v: number,
): Promise<DashboardPoll> {
  return request(
    `/api/f/${encodeURIComponent(adminToken)}/dashboard?v=${v}`,
  );
}

export function facilitatorAnswerHelp(
  adminToken: string,
  helpRequestId: number,
  answerMd: string,
): Promise<{ help_request: HelpQueueItem; version: number }> {
  return request(
    `/api/f/${encodeURIComponent(adminToken)}/help/${helpRequestId}/answer`,
    { method: "POST", body: JSON.stringify({ answer_md: answerMd }) },
  );
}

export function facilitatorResolveHelp(
  adminToken: string,
  helpRequestId: number,
): Promise<{ help_request: HelpQueueItem; version: number }> {
  return request(
    `/api/f/${encodeURIComponent(adminToken)}/help/${helpRequestId}/resolve`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

// ---------------------------------------------------------------------------
// Participant surface
// ---------------------------------------------------------------------------

export interface JoinInfo {
  workshop: {
    name: string;
    description_md: string;
    status: WorkshopStatus;
    milestone_count: number;
    participant_count: number;
  };
  me: { participant_token: string; name: string } | null;
}

export interface JoinResult {
  participant_token: string;
  participant_url: string;
  name: string;
}

export interface TrackerMe {
  id: number;
  name: string;
  completed_milestone_ids: number[];
  completed_count: number;
  total_count: number;
  progress_pct: number;
  rank: number;
}

export interface LeaderboardRow {
  rank: number;
  name: string;
  completed_count: number;
  progress_pct: number;
  is_me: boolean;
}

export interface TrackerHelpAnswer {
  id: number;
  source: AnswerSource;
  answer_md: string;
  created_at: string;
}

export interface TrackerHelpRequest {
  id: number;
  message: string;
  status: HelpStatus;
  escalated: boolean;
  milestone_id: number | null;
  created_at: string;
  answers: TrackerHelpAnswer[];
}

export interface StatePayload {
  changed: true;
  version: number;
  content_version: number;
  workshop: { name: string; status: WorkshopStatus; paused: boolean };
  milestones: MilestoneMeta[];
  me: TrackerMe;
  leaderboard: LeaderboardRow[];
  broadcast: unknown | null;
  help_requests: TrackerHelpRequest[];
}

export type StatePoll = PollUnchanged | StatePayload;

export interface ContentPayload {
  changed: true;
  content_version: number;
  workshop: { name: string; description_md: string };
  milestones: MilestoneFull[];
}

export type ContentPoll = { changed: false; content_version: number } | ContentPayload;

export interface CompletionResult {
  completed_milestone_ids: number[];
  completed_count: number;
  progress_pct: number;
  version: number;
}

export function joinInfo(joinSlug: string): Promise<JoinInfo> {
  return request(`/api/join/${encodeURIComponent(joinSlug)}`);
}

export function joinWorkshop(
  joinSlug: string,
  name: string,
): Promise<JoinResult> {
  return request(`/api/join/${encodeURIComponent(joinSlug)}`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function participantState(
  participantToken: string,
  v: number,
): Promise<StatePoll> {
  return request(
    `/api/p/${encodeURIComponent(participantToken)}/state?v=${v}`,
  );
}

export function participantContent(
  participantToken: string,
  cv: number,
): Promise<ContentPoll> {
  return request(
    `/api/p/${encodeURIComponent(participantToken)}/content?cv=${cv}`,
  );
}

export function completeMilestone(
  participantToken: string,
  milestoneId: number,
): Promise<CompletionResult> {
  return request(
    `/api/p/${encodeURIComponent(participantToken)}/milestones/${milestoneId}/complete`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function uncompleteMilestone(
  participantToken: string,
  milestoneId: number,
): Promise<CompletionResult> {
  return request(
    `/api/p/${encodeURIComponent(participantToken)}/milestones/${milestoneId}/uncomplete`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function submitHelp(
  participantToken: string,
  message: string,
): Promise<{ help_request: TrackerHelpRequest; version: number }> {
  return request(`/api/p/${encodeURIComponent(participantToken)}/help`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function participantResolveHelp(
  participantToken: string,
  helpRequestId: number,
): Promise<{ help_request: TrackerHelpRequest; version: number }> {
  return request(
    `/api/p/${encodeURIComponent(participantToken)}/help/${helpRequestId}/resolve`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

// ---------------------------------------------------------------------------
// Pretty-link helpers (architecture.md §Auth — share links use pretty forms)
// ---------------------------------------------------------------------------

export function prettyParticipantUrl(participantToken: string): string {
  return `${window.location.origin}/p/${participantToken}`;
}

export function prettyJoinUrl(joinSlug: string): string {
  return `${window.location.origin}/j/${joinSlug}`;
}

/** Extract the admin token from a facilitator_url ("…/f/<token>"). */
export function tokenFromFacilitatorUrl(facilitatorUrl: string): string {
  const idx = facilitatorUrl.lastIndexOf("/f/");
  return idx >= 0 ? facilitatorUrl.slice(idx + 3) : "";
}

/** Extract the join slug from a join_url ("…/j/<slug>"). */
export function slugFromJoinUrl(joinUrl: string): string {
  const idx = joinUrl.lastIndexOf("/j/");
  return idx >= 0 ? joinUrl.slice(idx + 3) : "";
}
