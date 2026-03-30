"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { notebooksAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import Image from "next/image";
import {
  BookOpen,
  Plus,
  Search,
  LogOut,
  Podcast,
  Settings,
  Trash2,
  X,
  Loader2,
} from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";

interface Notebook {
  id: string;
  name: string;
  description: string;
  archived: boolean;
  created: string;
  updated: string;
}

export default function HomePage() {
  const router = useRouter();
  const { user, loading, checkAuth, logout } = useAuthStore();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user) {
      loadNotebooks();
    }
  }, [user, loading]);

  const loadNotebooks = async () => {
    try {
      const res = await notebooksAPI.list();
      setNotebooks(res.data.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await notebooksAPI.create({ name: newName, description: newDesc });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      loadNotebooks();
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this notebook and all its contents?")) return;
    await notebooksAPI.delete(id);
    loadNotebooks();
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="animate-spin text-blue-500" size={32} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--card)]/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <Image src="/logo.png" alt="DocChat" width={40} height={40} className="rounded-lg" />
            <h1 className="text-2xl font-bold">DocChat</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/search")}
              className="rounded-lg p-2.5 hover:bg-[var(--secondary)] transition"
              title="Search"
            >
              <Search size={20} />
            </button>
            <button
              onClick={() => router.push("/podcasts")}
              className="rounded-lg p-2.5 hover:bg-[var(--secondary)] transition"
              title="Podcasts"
            >
              <Podcast size={20} />
            </button>
            <button
              onClick={() => router.push("/settings")}
              className="rounded-lg p-2.5 hover:bg-[var(--secondary)] transition"
              title="AI Settings"
            >
              <Settings size={20} />
            </button>
            <ThemeToggle />
            <div className="ml-2 h-6 w-px bg-[var(--border)]" />
            <span className="ml-2 text-base text-[var(--muted-foreground)]">
              {user?.username}
            </span>
            <button
              onClick={logout}
              className="rounded-lg p-2.5 hover:bg-[var(--secondary)] transition"
              title="Logout"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </header>

      {/* Hero section */}
      <div className="border-b border-[var(--border)] bg-gradient-to-b from-blue-50 to-[var(--background)]">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-3xl font-bold text-[var(--foreground)]">
                Your Notebooks
              </h2>
              <p className="mt-1 text-lg text-[var(--muted-foreground)]">
                Upload documents, chat with AI, and discover insights.
              </p>
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-base font-semibold text-white hover:bg-blue-700 active:bg-blue-800 transition shadow-sm"
            >
              <Plus size={20} /> Create new
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        {/* Notebook grid */}
        {notebooks.length > 0 ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {notebooks.map((nb) => (
              <div
                key={nb.id}
                onClick={() => router.push(`/notebooks/${encodeURIComponent(nb.id)}`)}
                className="group relative cursor-pointer rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 transition-all hover:border-blue-300 hover:shadow-lg hover:-translate-y-0.5"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 rounded-lg bg-blue-50 p-2.5">
                    <BookOpen size={22} className="text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold truncate">{nb.name}</h3>
                    {nb.description && (
                      <p className="mt-1 text-base text-[var(--muted-foreground)] line-clamp-2">
                        {nb.description}
                      </p>
                    )}
                  </div>
                </div>
                {nb.created && (
                  <p className="mt-4 text-sm text-[var(--muted-foreground)]">
                    {new Date(nb.created).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                )}
                <button
                  onClick={(e) => handleDelete(nb.id, e)}
                  className="absolute top-4 right-4 rounded-lg p-1.5 opacity-0 hover:bg-red-50 group-hover:opacity-100 transition"
                  title="Delete"
                >
                  <Trash2 size={16} className="text-red-400 hover:text-red-600" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="rounded-2xl bg-blue-50 p-6 mb-6">
              <BookOpen size={48} className="text-blue-400" />
            </div>
            <h3 className="text-2xl font-semibold">No notebooks yet</h3>
            <p className="mt-2 text-lg text-[var(--muted-foreground)] max-w-md">
              Create your first notebook to start uploading documents and chatting with AI.
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-6 flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-base font-semibold text-white hover:bg-blue-700 transition"
            >
              <Plus size={20} /> Create your first notebook
            </button>
          </div>
        )}
      </main>

      {/* Create Notebook Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !creating && setShowCreate(false)}>
          <div
            className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-xl font-semibold">Create new notebook</h3>
              <button
                onClick={() => setShowCreate(false)}
                disabled={creating}
                className="rounded-lg p-1.5 hover:bg-[var(--secondary)] transition"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Name</label>
                <input
                  type="text"
                  placeholder="e.g., Research Project, Study Notes..."
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Description <span className="text-[var(--muted-foreground)] font-normal">(optional)</span>
                </label>
                <textarea
                  placeholder="What's this notebook about?"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-base min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  disabled={creating}
                  className="rounded-xl border border-[var(--border)] px-5 py-2.5 text-base hover:bg-[var(--secondary)] transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="rounded-xl bg-blue-600 px-6 py-2.5 text-base font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition flex items-center gap-2"
                >
                  {creating ? (
                    <><Loader2 size={16} className="animate-spin" /> Creating...</>
                  ) : (
                    "Create"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}