import { cn } from "@/lib/format";

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0–100 */
  value: number;
  tone?: "brand" | "success";
  size?: "sm" | "md";
  label?: string;
}

export function ProgressBar({
  value,
  tone = "brand",
  size = "md",
  label,
  className,
  ...rest
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label ?? "Progress"}
      className={cn(
        "w-full overflow-hidden rounded-full bg-stone-200",
        size === "sm" ? "h-1.5" : "h-2.5",
        className,
      )}
      {...rest}
    >
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-500 ease-out",
          tone === "success" ? "bg-emerald-500" : "bg-brand-600",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
