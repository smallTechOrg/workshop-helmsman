import { cn } from "@/lib/format";

export function Skeleton({
  className,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-lg bg-stone-200", className)}
      {...rest}
    />
  );
}
