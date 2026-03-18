"use client";

export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
      <div className="flex gap-1">
        <span className="inline-block h-2 w-2 rounded-full bg-[var(--muted-foreground)] animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="inline-block h-2 w-2 rounded-full bg-[var(--muted-foreground)] animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="inline-block h-2 w-2 rounded-full bg-[var(--muted-foreground)] animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
      <span className="text-xs">Thinking...</span>
    </div>
  );
}
