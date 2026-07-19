import { cn } from "@/lib/format";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  hint?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, hint, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-stone-300 bg-stone-50/60 px-6 py-10 text-center",
        className,
      )}
    >
      {icon && (
        <div aria-hidden="true" className="text-3xl">
          {icon}
        </div>
      )}
      <p className="font-medium text-stone-700">{title}</p>
      {hint && <p className="max-w-sm text-sm text-stone-500">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
