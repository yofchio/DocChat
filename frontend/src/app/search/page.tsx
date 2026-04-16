"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { searchAPI, sessionsAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import {
  ArrowLeft, MessageSquare, Search as SearchIcon,
  FileText, StickyNote, ExternalLink, User as UserIcon, Bot,
} from "lucide-react";

// Tab type definition for switching between content and chat history search
type Tab = "content" | "history";

/**
 * Component for displaying search results with query highlighting
 * @param text - The text to display
 * @param query - The search query to highlight
 */
function HighlightedSnippet({ text, query }: { text: string; query: string }) {
  // If no query is provided, return plain text
  if (!query.trim()) return <span>{text}</span>;
  
  // Escape special regex characters in the query
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  
  // Split text by query and highlight matches
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return (
    <>
      {parts.map((part, i) =>
        // Highlight matching parts with yellow background
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-yellow-200 dark:bg-yellow-700 text-inherit rounded px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

export default function SearchPage() {
  const router = useRouter();
  const { user, loading, checkAuth } = useAuthStore();

  // UI state management
  const [tab, setTab] = useState<Tab>("content");
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("vector"); // "vector" for semantic, "text" for keyword search
  
  // Results state for both search tabs
  const [contentResults, setContentResults] = useState<any[]>([]);
  const [historyResults, setHistoryResults] = useState<any[]>([]);
  
  // Loading and search status
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  
  // Reference to search input for auto-focus
  const inputRef = useRef<HTMLInputElement>(null);

  // Check authentication status on component mount
  useEffect(() => { checkAuth(); }, []);
  
  // Redirect to login if not authenticated
  useEffect(() => { if (!loading && !user) router.push("/login"); }, [user, loading]);
  
  // Auto-focus search input when switching tabs
  useEffect(() => { inputRef.current?.focus(); }, [tab]);

  /**
   * Handle search form submission
   * Calls appropriate API based on selected tab
   */
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setSearching(true);
    setHasSearched(true);
    
    try {
      if (tab === "content") {
        // Search in sources and notes using vector or text search
        const res = await searchAPI.search({ query, search_type: searchType });
        setContentResults(res.data.data || []);
      } else {
        // Search in chat history
        const res = await sessionsAPI.searchHistory(query);
        setHistoryResults(res.data.data || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  /**
   * Navigate to the corresponding session/source/notebook based on search result
   */
  const navigateToSession = (r: any) => {
    const session = encodeURIComponent(r.session_id);
    if (r.notebook_id) {
      // Deep-link into the notebook chat tab and restore the matching session.
      router.push(`/notebooks/${r.notebook_id}?tab=chat&session=${session}`);
    } else if (r.source_id) {
      // Source chat only has one main view, so we only need the session id.
      router.push(`/sources/${r.source_id}?session=${session}`);
    }
  };

  // Get current results based on active tab
  const currentResults = tab === "content" ? contentResults : historyResults;

  return (
    <div className="min-h-screen">
      {/* Header with back button and title */}
      <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button onClick={() => router.push("/")} className="rounded-lg p-2 hover:bg-[var(--secondary)]">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold">Search</h1>
      </header>

      <main className="mx-auto max-w-3xl p-6 space-y-6">
        {/* Tab selector for switching between content and history search */}
        <div className="flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--secondary)] p-1 w-fit">
          {(["content", "history"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex items-center gap-2 rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
                tab === t
                  ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {t === "content" ? <FileText size={14} /> : <MessageSquare size={14} />}
              {t === "content" ? "Sources & Notes" : "Chat History"}
            </button>
          ))}
        </div>

        {/* Search form */}
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex gap-2">
            {/* Search input field */}
            <input
              ref={inputRef}
              type="text"
              placeholder={tab === "content" ? "Search your sources and notes..." : "Search your past conversations..."}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
            {/* Search button */}
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2.5 text-sm text-[var(--primary-foreground)] disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              <SearchIcon size={16} />
              {searching ? "Searching…" : "Search"}
            </button>
          </div>
          
          {/* Search type options for content tab */}
          {tab === "content" && (
            <div className="flex gap-4 text-sm text-[var(--muted-foreground)]">
              {/* Semantic search option */}
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" name="type" checked={searchType === "vector"} onChange={() => setSearchType("vector")} />
                Semantic
              </label>
              {/* Keyword search option */}
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" name="type" checked={searchType === "text"} onChange={() => setSearchType("text")} />
                Text
              </label>
            </div>
          )}
        </form>

        {/* Search results summary */}
        {hasSearched && !searching && (
          <p className="text-sm text-[var(--muted-foreground)]">
            {currentResults.length === 0 ? "No results found."
              : `${currentResults.length} result${currentResults.length !== 1 ? "s" : ""} found`}
          </p>
        )}

        {/* Content search results (sources and notes) */}
        {tab === "content" && contentResults.length > 0 && (
          <div className="space-y-3">
            {contentResults.map((r, i) => (
              <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                {/* Result type badge and relevance score */}
                <div className="flex items-center gap-2 mb-1">
                  <span className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded bg-[var(--secondary)]">
                    {r.type === "note" ? <StickyNote size={11} /> : <FileText size={11} />}
                    {r.type}
                  </span>
                  {r.score != null && (
                    <span className="text-xs text-[var(--muted-foreground)]">Score: {r.score.toFixed(3)}</span>
                  )}
                </div>
                {/* Result title */}
                {r.title && <h3 className="font-medium">{r.title}</h3>}
                {/* Result preview (truncated to 3 lines) */}
                <p className="text-sm text-[var(--muted-foreground)] mt-1 line-clamp-3">{r.content}</p>
              </div>
            ))}
          </div>
        )}

        {/* Chat history search results */}
        {tab === "history" && historyResults.length > 0 && (
          <div className="space-y-3">
            {historyResults.map((r, i) => (
              <div
                key={i}
                onClick={() => navigateToSession(r)}
                className="group rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/40 transition-colors cursor-pointer"
              >
                {/* Session title and match type badge */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare size={15} className="shrink-0 text-[var(--muted-foreground)]" />
                    <span className="font-medium text-sm truncate">{r.session_title}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Badge showing whether match is title or message */}
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      r.match_type === "title"
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                        : "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300"
                    }`}>
                      {r.match_type === "title" ? "title match" : "message match"}
                    </span>
                    {/* External link icon shown on hover */}
                    <ExternalLink size={13} className="text-[var(--muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>

                {/* Message snippet with highlighted query (shown for message matches) */}
                {r.snippet && r.match_type === "message" && (
                  <div className="flex items-start gap-2 rounded-lg bg-[var(--secondary)] px-3 py-2">
                    {/* User or bot icon based on message role */}
                    {r.role === "human"
                      ? <UserIcon size={13} className="mt-0.5 shrink-0 text-[var(--muted-foreground)]" />
                      : <Bot size={13} className="mt-0.5 shrink-0 text-[var(--muted-foreground)]" />
                    }
                    {/* Message snippet with highlighted query terms */}
                    <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-3">
                      <HighlightedSnippet text={r.snippet} query={query} />
                    </p>
                  </div>
                )}

                {/* Metadata: location and last updated date */}
                <p className="text-xs text-[var(--muted-foreground)] mt-2">
                  {r.notebook_id ? "In notebook" : r.source_id ? "In source" : ""}
                  {r.updated ? ` · ${new Date(r.updated).toLocaleDateString()}` : ""}
                </p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
