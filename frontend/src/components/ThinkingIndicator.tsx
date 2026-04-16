// =============================================================================
// ThinkingIndicator — Animated loading state shown while waiting for the LLM
// =============================================================================
// Displayed inside the AI message bubble when content is still empty (i.e.
// the SSE stream has started but no content chunks have arrived yet).
// Three bouncing dots with staggered animation delays create a "typing"
// effect.  As soon as the first content chunk arrives from the SSE stream,
// the parent component replaces this with <MarkdownWithCitations />.
// =============================================================================

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
