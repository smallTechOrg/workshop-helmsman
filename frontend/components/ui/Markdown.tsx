"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { cn } from "@/lib/format";

/**
 * The single markdown renderer (spec/architecture.md §Security):
 * react-markdown + remark-gfm + rehype-highlight, NO rehype-raw — raw HTML
 * in markdown source is never injected. Use only for facilitator-authored
 * content (milestones, descriptions, answers). Participant-authored text
 * (names, help messages) must be rendered as plain text nodes instead.
 */

function PreWithCopy(props: React.HTMLAttributes<HTMLPreElement>) {
  const preRef = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    const text = preRef.current?.innerText ?? "";
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Quietly ignore — the user can still select the code.
    }
  };

  return (
    <div className="group relative">
      <pre ref={preRef} {...props} />
      <button
        type="button"
        onClick={onCopy}
        aria-label="Copy code"
        className={cn(
          "absolute top-2 right-2 rounded-md border border-stone-200 bg-white/95 px-2 py-1 text-[11px] font-medium text-stone-600 opacity-0 shadow-sm transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:bg-stone-50",
          copied && "border-emerald-300 text-emerald-700 opacity-100",
        )}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function MdLink(props: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a {...props} target="_blank" rel="noopener noreferrer" />;
}

export function Markdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={cn("md", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{ pre: PreWithCopy, a: MdLink }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
