import { cn } from "@/lib/format";
import type { HelpStatus, WorkshopStatus } from "@/lib/api";

export type BadgeTone =
  | "neutral"
  | "brand"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "ai";

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-stone-100 text-stone-700 border-stone-200",
  brand: "bg-brand-50 text-brand-700 border-brand-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  danger: "bg-red-50 text-red-700 border-red-200",
  info: "bg-sky-50 text-sky-700 border-sky-200",
  ai: "bg-violet-50 text-violet-700 border-violet-200",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

export function Badge({ tone = "neutral", className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONES[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

/** Help-request status pill — open = amber "Waiting", answered = blue, resolved = green. */
export function HelpStatusBadge({
  status,
  ...rest
}: { status: HelpStatus } & Omit<BadgeProps, "tone">) {
  const map: Record<HelpStatus, { tone: BadgeTone; label: string }> = {
    open: { tone: "warning", label: "Waiting" },
    answered: { tone: "info", label: "Answered" },
    resolved: { tone: "success", label: "Resolved" },
  };
  const { tone, label } = map[status];
  return (
    <Badge tone={tone} {...rest}>
      {label}
    </Badge>
  );
}

/** Workshop status pill. */
export function WorkshopStatusBadge({ status }: { status: WorkshopStatus }) {
  const map: Record<WorkshopStatus, { tone: BadgeTone; label: string }> = {
    live: { tone: "success", label: "Live" },
    grace: { tone: "warning", label: "Grace period" },
    archived: { tone: "neutral", label: "Archived" },
  };
  const { tone, label } = map[status] ?? { tone: "neutral" as BadgeTone, label: status };
  return (
    <Badge tone={tone}>
      {status === "live" && (
        <span aria-hidden="true" className="size-1.5 rounded-full bg-emerald-500" />
      )}
      {label}
    </Badge>
  );
}
