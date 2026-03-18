"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { searchAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { ArrowLeft, Search as SearchIcon } from "lucide-react";

export default function SearchPage() {
  const router = useRouter();
  const { user, loading, checkAuth } = useAuthStore();
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("vector");
  const [results, setResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await searchAPI.search({
        query,
        search_type: searchType,
      });
      setResults(res.data.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button
          onClick={() => router.push("/")}
          className="rounded-lg p-2 hover:bg-[var(--secondary)]"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold">Search</h1>
      </header>

      <main className="mx-auto max-w-3xl p-6 space-y-6">
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search your sources and notes..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm"
            />
            <button
              type="submit"
              disabled={searching}
              className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2.5 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
            >
              <SearchIcon size={16} />
              {searching ? "..." : "Search"}
            </button>
          </div>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1">
              <input
                type="radio"
                name="type"
                checked={searchType === "vector"}
                onChange={() => setSearchType("vector")}
              />
              Semantic
            </label>
            <label className="flex items-center gap-1">
              <input
                type="radio"
                name="type"
                checked={searchType === "text"}
                onChange={() => setSearchType("text")}
              />
              Text
            </label>
          </div>
        </form>

        {results.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm text-[var(--muted-foreground)]">
              {results.length} results found
            </p>
            {results.map((r, i) => (
              <div
                key={i}
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium px-2 py-0.5 rounded bg-[var(--secondary)]">
                    {r.type}
                  </span>
                  {r.score && (
                    <span className="text-xs text-[var(--muted-foreground)]">
                      Score: {r.score.toFixed(3)}
                    </span>
                  )}
                </div>
                {r.title && <h3 className="font-medium">{r.title}</h3>}
                <p className="text-sm text-[var(--muted-foreground)] mt-1 line-clamp-3">
                  {r.content}
                </p>
              </div>
            ))}
          </div>
        )}

        {results.length === 0 && query && !searching && (
          <p className="text-center text-[var(--muted-foreground)] py-8">
            No results found.
          </p>
        )}
      </main>
    </div>
  );
}
