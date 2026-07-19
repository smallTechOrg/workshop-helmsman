"use client";

import { useRef, useState } from "react";
import { cn } from "@/lib/format";

async function copyText(text: string): Promise<boolean> {
  // Clipboard API needs a secure context; workshops often run over plain
  // HTTP on a LAN, so fall back to the selection trick when unavailable.
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to the fallback
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export interface CopyButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  text: string;
  label?: string;
}

export function CopyButton({ text, label = "Copy", className, ...rest }: CopyButtonProps) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onClick = async () => {
    const ok = await copyText(text);
    setState(ok ? "copied" : "failed");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 1600);
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-md border border-stone-300 bg-white px-2 py-1 text-xs font-medium text-stone-700 shadow-sm transition-colors hover:bg-stone-50",
        state === "copied" && "border-emerald-300 bg-emerald-50 text-emerald-700",
        state === "failed" && "border-red-300 bg-red-50 text-red-700",
        className,
      )}
      {...rest}
    >
      {state === "copied" ? (
        <>
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-3.5">
            <path
              fillRule="evenodd"
              d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
              clipRule="evenodd"
            />
          </svg>
          Copied
        </>
      ) : state === "failed" ? (
        "Copy failed — select it manually"
      ) : (
        <>
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-3.5">
            <path d="M7 3.5A1.5 1.5 0 0 1 8.5 2h3.879a1.5 1.5 0 0 1 1.06.44l3.122 3.12A1.5 1.5 0 0 1 17 6.622V12.5a1.5 1.5 0 0 1-1.5 1.5H14v-3.379a3 3 0 0 0-.879-2.121L10.5 5.879A3 3 0 0 0 8.379 5H7V3.5Z" />
            <path d="M4.5 6A1.5 1.5 0 0 0 3 7.5v9A1.5 1.5 0 0 0 4.5 18h7a1.5 1.5 0 0 0 1.5-1.5v-5.879a1.5 1.5 0 0 0-.44-1.06L9.44 6.439A1.5 1.5 0 0 0 8.378 6H4.5Z" />
          </svg>
          {label}
        </>
      )}
    </button>
  );
}
