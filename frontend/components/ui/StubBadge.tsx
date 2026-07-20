import { cn } from "@/lib/format";

/**
 * The labelled-stub primitive. Every future feature surface renders with a
 * `StubBadge` pill so a stub is never mistaken for a bug.
 */
export function StubBadge({ className }: { className?: string }) {
  return (
    <span
      data-testid="stub-badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-stone-300 bg-stone-100 px-2 py-0.5 text-[11px] font-medium whitespace-nowrap text-stone-500",
        className,
      )}
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-3">
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-13a.75.75 0 0 0-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 0 0 0-1.5h-3.25V5Z"
          clipRule="evenodd"
        />
      </svg>
      Coming in a later phase
    </span>
  );
}

/** A muted, non-interactive card for a future feature surface. */
export function StubCard({
  title,
  description,
  className,
}: {
  title: string;
  description: string;
  className?: string;
}) {
  return (
    <div
      aria-disabled="true"
      className={cn(
        "rounded-xl border border-dashed border-stone-300 bg-stone-50/70 p-4",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-stone-500">{title}</h3>
        <StubBadge />
      </div>
      <p className="mt-1.5 text-sm text-stone-400">{description}</p>
    </div>
  );
}

/** A disabled control chip for a future action (Broadcast, Pause, …). */
export function StubAction({ label }: { label: string }) {
  return (
    <span
      aria-disabled="true"
      className="inline-flex items-center gap-2 rounded-lg border border-dashed border-stone-300 bg-stone-50 px-3 py-1.5 text-sm font-medium text-stone-400 select-none"
    >
      {label}
      <StubBadge />
    </span>
  );
}
