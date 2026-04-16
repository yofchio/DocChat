"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { searchAPI, sessionsAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import {
  ArrowLeft, MessageSquare, Search as SearchIcon,
  FileText, StickyNote, ExternalLink, User as UserIcon, Bot,
} from "lucide-react";

type Tab = "content" | "history";

function HighlightedSnippet({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <span>{text}</span>;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return (
    <>
      {parts.map((part, i) =>
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

  const [tab, setTab] = useState<Tab>("content");
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("vector");
  const [contentResults, setContentResults] = useState<any[]>([]);
  const [historyResults, setHistoryResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { checkAuth(); }, []);
  useEffect(() => { if (!loading && !user) router.push("/login"); }, [user, loading]);
  useEffect(() => { inputRef.current?.focus(); }, [tab]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setHasSearched(true);
    try {
      if (tab === "content") {
        const res = await searchAPI.search({ query, search_type: searchType });
        setContentResults(res.data.data || []);
      } else {
        const res = await sessionsAPI.searchHistory(query);
        setHistoryResults(res.data.data || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const navigateToSession = (r: any) => {
    if (r.notebook_id) router.push(`/notebooks/${r.notebook_id}`);
    else if (r.source_id) router.push(`/sources/${r.source_id}`);
  };

  const currentResults = tab === "content" ? contentResults : historyResults;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button onClick={() => router.push("/")} className="rounded-lg p-2 hover:bg-[var(--secondary)]">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold">Search</h1>
      </header>

      <main className="mx-auto max-w-3xl p-6 space-y-6">
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

        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              placeholder={tab === "content" ? "Search your sources and notes..." : "Search your past conversations..."}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2.5 text-sm text-[var(--primary-foreground)] disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              <SearchIcon size={16} />
              {searching ? "Searching…" : "Search"}
            </button>
          </div>
          {tab === "content" && (
            <div className="flex gap-4 text-sm text-[var(--muted-foreground)]">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" name="type" checked={searchType === "vector"} onChange={() => setSearchType("vector")} />
                Semantic
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" name="type" checked={searchType === "text"} onChange={() => setSearchType("text")} />
                Text
              </label>
            </div>
          )}
        </form>

        {hasSearched && !searching && (
          <p className="text-sm text-[var(--muted-foreground)]">
            {currentResults.length === 0 ? "No results found."
              : `${currentResults.length} result${currentResults.length !== 1 ? "s" : ""} found`}
          </p>
        )}

        {tab === "content" && contentResults.length > 0 && (
          <div className="space-y-3">
            {contentResults.map((r, i) => (
              <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded bg-[var(--secondary)]">
                    {r.type === "note" ? <StickyNote size={11} /> : <FileText size={11} />}
                    {r.type}
                  </span>
                  {r.score != null && (
                    <span className="text-xs text-[var(--muted-foreground)]">Score: {r.score.toFixed(3)}</span>
                  )}
                </div>
                {r.title && <h3 className="font-medium">{r.title}</h3>}
                <p className="text-sm text-[var(--muted-foreground)] mt-1 line-clamp-3">{r.content}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "history" && historyResults.length > 0 && (
          <div className="space-y-3">
            {historyResults.map((r, i) => (
              <div
                key={i}
                onClick={() => navigateToSession(r)}
                className="group rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 hover:border-[var(--primary)]/40 transition-colors cursor-pointer"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare size={15} className="shrink-0 text-[var(--muted-foreground)]" />
                    <span className="font-medium text-sm truncate">{r.session_title}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      r.match_type === "title"
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                        : "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300"
                    }`}>
                      {r.match_type === "title" ? "title match" : "message match"}
                    </span>
                    <ExternalLink size={13} className="text-[var(--muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>

                {r.snippet && r.match_type === "message" && (
                  <div className="flex items-start gap-2 rounded-lg bg-[var(--secondary)] px-3 py-2">
                    {r.role === "human"
                      ? <UserIcon size={13} className="mt-0.5 shrink-0 text-[var(--muted-foreground)]" />
                      : <Bot size={13} className="mt-0.5 shrink-0 text-[var(--muted-foreground)]" />
                    }
                    <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-3">
                      <HighlightedSnippet text={r.snippet} query={query} />
                    </p>
                  </div>
                )}

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