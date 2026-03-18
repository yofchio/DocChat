"use client";

import { useState, useRef, useEffect } from "react";
import { X } from "lucide-react";
import { Markdown } from "./Markdown";

interface Reference {
  content: string;
  score: number;
  source_id: string | null;
  source_title: string;
}

interface CitationPopoverProps {
  index: number;
  reference: Reference;
}

export function CitationPopover({ index, reference }: CitationPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <span className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center justify-center h-4 min-w-[1rem] px-0.5 rounded border border-[var(--border)] bg-white text-gray-500 text-[10px] font-medium leading-none align-super hover:bg-gray-100 transition cursor-pointer mx-[1px]"
        title={`Reference ${index}: ${reference.source_title}`}
      >
        {index}
      </button>
      {open && (
        <div
          ref={popoverRef}
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 max-h-64 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl overflow-hidden animate-in fade-in"
        >
          <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2 bg-[var(--secondary)]">
            <div className="flex items-center gap-2 min-w-0">
              <span className="inline-flex items-center justify-center h-5 w-5 rounded-full border border-[var(--border)] bg-white text-gray-500 text-xs font-medium flex-shrink-0">
                {index}
              </span>
              <span className="text-xs font-medium truncate">
                {reference.source_title}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[10px] text-[var(--muted-foreground)]">
                {Math.round(reference.score * 100)}%
              </span>
              <button
                onClick={() => setOpen(false)}
                className="rounded p-0.5 hover:bg-[var(--background)]"
              >
                <X size={12} />
              </button>
            </div>
          </div>
          <div className="p-3 overflow-auto max-h-48 text-xs leading-relaxed text-[var(--foreground)]">
            <Markdown content={reference.content} className="text-xs" />
          </div>
        </div>
      )}
    </span>
  );
}
