"use client";

import { useEffect, useState, useRef, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import {
  notebooksAPI,
  sourcesAPI,
  notesAPI,
  chatAPI,
  sessionsAPI,
} from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Markdown } from "@/components/Markdown";
import { MarkdownWithCitations } from "@/components/MarkdownWithCitations";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import {
  ArrowLeft,
  FileText,
  Link,
  Loader2,
  MessageCircle,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Upload,
  StickyNote,
  X,
  CheckCircle2,
  AlertCircle,
  Clock,
  ChevronDown,
  MessageSquare,
} from "lucide-react";

interface NotebookDetail {
  id: string;
  name: string;
  description: string;
  sources: any[];
  notes: any[];
}

interface Reference {
  content: string;
  score: number;
  source_id: string | null;
  source_title: string;
}

interface ChatMessage {
  role: "human" | "ai";
  content: string;
  references?: Reference[];
}

interface Session {
  id: string;
  title: string;
  source_id: string | null;
  notebook_id: string | null;
  created: string | null;
  updated: string | null;
}

const STATUS_CONFIG: Record<string, { icon: any; label: string; color: string }> = {
  pending: { icon: Clock, label: "Pending", color: "text-yellow-500" },
  processing: { icon: Loader2, label: "Processing", color: "text-blue-500" },
  completed: { icon: CheckCircle2, label: "Ready", color: "text-green-500" },
  error: { icon: AlertCircle, label: "Error", color: "text-red-500" },
};

function SourceCard({
  src,
  st,
  StatusIcon,
  onRetry,
  onDelete,
  onClick,
}: {
  src: any;
  st: { icon: any; label: string; color: string };
  StatusIcon: any;
  onRetry: () => void;
  onDelete: () => void;
  onClick: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasSummary = !!src.summary;
  const hasTopics = src.topics && src.topics.length > 0;

  return (
    <div
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden cursor-pointer hover:border-[var(--primary)] hover:shadow-sm transition"
      onClick={onClick}
    >
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`flex-shrink-0 ${st.color}`}>
            <StatusIcon size={20} className={src.status === "processing" ? "animate-spin" : ""} />
          </div>
          <div className="min-w-0">
            <h3 className="text-lg font-medium truncate">{src.title || "Untitled"}</h3>
            <div className="flex items-center gap-2 text-base text-[var(--muted-foreground)]">
              <span className={st.color}>{st.label}</span>
              {src.status_message && (
                <span className="truncate">— {src.status_message}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {src.status === "error" && (
            <button
              onClick={(e) => { e.stopPropagation(); onRetry(); }}
              className="rounded p-1.5 hover:bg-[var(--secondary)]"
              title="Retry processing"
            >
              <RefreshCw size={16} />
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="rounded p-1.5 hover:bg-[var(--secondary)]"
          >
            <Trash2 size={16} className="text-[var(--destructive)]" />
          </button>
        </div>
      </div>

      {(hasSummary || hasTopics) && (
        <div className="border-t border-[var(--border)] px-4 py-3">
          {hasSummary && (
            <p
              className={`text-base text-[var(--muted-foreground)] leading-relaxed ${
                expanded ? "" : "line-clamp-2"
              }`}
            >
              {src.summary}
            </p>
          )}
          {hasTopics && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {(expanded ? src.topics : src.topics.slice(0, 5)).map((t: string, i: number) => (
                <span
                  key={i}
                  className="inline-flex rounded-full border border-[var(--border)] bg-[var(--secondary)] px-2.5 py-0.5 text-sm text-[var(--secondary-foreground)]"
                >
                  {t}
                </span>
              ))}
              {!expanded && src.topics.length > 5 && (
                <span className="text-sm text-[var(--muted-foreground)]">
                  +{src.topics.length - 5} more
                </span>
              )}
            </div>
          )}
          {(hasSummary || (src.topics && src.topics.length > 5)) && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
              className="mt-2 text-sm text-[var(--primary)] hover:underline"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function NotebookPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const notebookId = decodeURIComponent(id);
  const router = useRouter();
  const { user, checkAuth, loading } = useAuthStore();
  const [notebook, setNotebook] = useState<NotebookDetail | null>(null);
  const [tab, setTab] = useState<"sources" | "notes" | "chat">("sources");

  // Sources
  const [showAddSource, setShowAddSource] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Notes
  const [showAddNote, setShowAddNote] = useState(false);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [expandedNoteId, setExpandedNoteId] = useState<string | null>(null);
  const [expandedNoteContent, setExpandedNoteContent] = useState<string | null>(null);
  const [loadingNote, setLoadingNote] = useState(false);

  // Chat + Sessions
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    else if (user) {
      loadNotebook();
      loadSessions();
    }
  }, [user, loading]);

  useEffect(() => {
    if (!sessionDropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (sessionDropdownRef.current && !sessionDropdownRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [sessionDropdownOpen]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadNotebook = useCallback(async () => {
    try {
      const res = await notebooksAPI.get(notebookId);
      setNotebook(res.data.data);
    } catch (e) {
      console.error(e);
    }
  }, [notebookId]);

  // Auto-refresh when sources are still processing
  useEffect(() => {
    if (!notebook?.sources) return;
    const hasProcessing = notebook.sources.some(
      (s: any) => s.status === "pending" || s.status === "processing"
    );
    if (!hasProcessing) return;
    const timer = setInterval(loadNotebook, 3000);
    return () => clearInterval(timer);
  }, [notebook?.sources, loadNotebook]);

  // ── Session handlers ──
  const loadSessions = async () => {
    try {
      const res = await sessionsAPI.list({ notebook_id: notebookId });
      setSessions(res.data.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  const createNewSession = async () => {
    try {
      const res = await sessionsAPI.create({ notebook_id: notebookId });
      const s = res.data.data;
      setSessions((prev) => [s, ...prev]);
      setActiveSessionId(s.id);
      setMessages([]);
      setSessionDropdownOpen(false);
    } catch (e) {
      console.error(e);
    }
  };

  const switchSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setSessionDropdownOpen(false);
    setMessages([]);
    try {
      const res = await sessionsAPI.getMessages(sessionId);
      const msgs: ChatMessage[] = (res.data.data || []).map((m: any) => ({
        role: m.role,
        content: m.content,
        references: m.references || undefined,
      }));
      setMessages(msgs);
    } catch (e) {
      console.error(e);
    }
  };

  const deleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await sessionsAPI.delete(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // ── Source handlers ──
  const handleAddURL = async () => {
    if (!urlInput.trim()) return;
    setUploading(true);
    try {
      await sourcesAPI.createFromURL(urlInput, notebookId);
      setUrlInput("");
      setShowAddSource(false);
      loadNotebook();
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  const handleUploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await sourcesAPI.uploadFile(file, notebookId);
      setShowAddSource(false);
      loadNotebook();
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    await sourcesAPI.delete(sourceId);
    loadNotebook();
  };

  // ── Note handlers ──
  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim()) return;
    await notesAPI.create({
      title: noteTitle,
      content: noteContent,
      notebook_id: notebookId,
    });
    setNoteTitle("");
    setNoteContent("");
    setShowAddNote(false);
    loadNotebook();
  };

  const handleDeleteNote = async (noteId: string) => {
    await notesAPI.delete(noteId);
    if (expandedNoteId === noteId) {
      setExpandedNoteId(null);
      setExpandedNoteContent(null);
    }
    loadNotebook();
  };

  const toggleNoteExpand = async (noteId: string) => {
    if (expandedNoteId === noteId) {
      setExpandedNoteId(null);
      setExpandedNoteContent(null);
      return;
    }
    setExpandedNoteId(noteId);
    setExpandedNoteContent(null);
    setLoadingNote(true);
    try {
      const res = await notesAPI.get(noteId);
      setExpandedNoteContent(res.data.data.content || "No content");
    } catch (e) {
      setExpandedNoteContent("Failed to load note content");
    } finally {
      setLoadingNote(false);
    }
  };

  // ── Chat handler ──
  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput;
    setChatInput("");

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const res = await sessionsAPI.create({ notebook_id: notebookId });
        const s = res.data.data;
        setSessions((prev) => [s, ...prev]);
        sessionId = s.id;
        setActiveSessionId(s.id);
      } catch (err) {
        console.error(err);
        return;
      }
    }

    setMessages((prev) => [...prev, { role: "human", content: msg }]);
    setChatLoading(true);

    try {
      const res = await chatAPI.stream({
        message: msg,
        notebook_id: notebookId,
        session_id: sessionId!,
      });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let aiContent = "";
      let refs: Reference[] = [];
      setMessages((prev) => [...prev, { role: "ai", content: "" }]);

      while (reader) {
        const { value, done } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        const lines = text.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") break;
            try {
              const parsed = JSON.parse(data);
              if (parsed.references) {
                refs = parsed.references;
              }
              if (parsed.content) {
                aiContent += parsed.content;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    role: "ai",
                    content: aiContent,
                    references: refs,
                  };
                  return updated;
                });
              }
            } catch {}
          }
        }
      }

      loadSessions();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "Error: Failed to get response" },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  if (!notebook) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-[var(--muted-foreground)]">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button
          onClick={() => router.push("/")}
          className="rounded-lg p-2 hover:bg-[var(--secondary)]"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{notebook.name}</h1>
          {notebook.description && (
            <p className="text-base text-[var(--muted-foreground)]">
              {notebook.description}
            </p>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div className="flex border-b border-[var(--border)] bg-[var(--card)] px-6">
        {(["sources", "notes", "chat"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-5 py-3.5 text-lg font-medium border-b-2 transition ${
              tab === t
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {t === "sources" && <FileText size={18} />}
            {t === "notes" && <StickyNote size={18} />}
            {t === "chat" && <MessageCircle size={18} />}
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === "sources" && ` (${notebook.sources?.length || 0})`}
            {t === "notes" && ` (${notebook.notes?.length || 0})`}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <main className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-4xl">
          {/* Sources tab */}
          {tab === "sources" && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button
                  onClick={() => setShowAddSource(true)}
                  className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2.5 text-base text-[var(--primary-foreground)]"
                >
                  <Plus size={18} /> Add Source
                </button>
              </div>

              {showAddSource && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !uploading && setShowAddSource(false)}>
                  <div
                    className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl space-y-4"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold">Add Source</h3>
                      <button
                        onClick={() => setShowAddSource(false)}
                        disabled={uploading}
                        className="rounded-lg p-1.5 hover:bg-[var(--secondary)] disabled:opacity-50"
                      >
                        <X size={18} />
                      </button>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium text-[var(--foreground)]">From URL</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="https://example.com/article"
                          value={urlInput}
                          onChange={(e) => setUrlInput(e.target.value)}
                          disabled={uploading}
                          className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-base disabled:opacity-50"
                        />
                        <button
                          onClick={handleAddURL}
                          disabled={uploading || !urlInput.trim()}
                          className="flex items-center gap-1.5 rounded-lg bg-[var(--primary)] px-4 py-2.5 text-base text-[var(--primary-foreground)] disabled:opacity-50"
                        >
                          {uploading ? <Loader2 size={16} className="animate-spin" /> : <Link size={16} />}
                          Add
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-px bg-[var(--border)]" />
                      <span className="text-sm text-[var(--muted-foreground)]">or</span>
                      <div className="flex-1 h-px bg-[var(--border)]" />
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium text-[var(--foreground)]">Upload File</label>
                      <input
                        ref={fileRef}
                        type="file"
                        onChange={handleUploadFile}
                        className="hidden"
                        disabled={uploading}
                      />
                      <button
                        onClick={() => fileRef.current?.click()}
                        disabled={uploading}
                        className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--border)] px-4 py-6 text-base hover:bg-[var(--secondary)] hover:border-[var(--primary)] transition disabled:opacity-50"
                      >
                        {uploading ? (
                          <><Loader2 size={18} className="animate-spin" /> Uploading...</>
                        ) : (
                          <><Upload size={18} /> Click to select a file</>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {notebook.sources?.map((src: any) => {
                const st = STATUS_CONFIG[src.status] || STATUS_CONFIG.pending;
                const Icon = st.icon;
                return (
                  <SourceCard
                    key={src.id}
                    src={src}
                    st={st}
                    StatusIcon={Icon}
                    onRetry={() => { sourcesAPI.process(src.id); loadNotebook(); }}
                    onDelete={() => handleDeleteSource(src.id)}
                    onClick={() => router.push(`/sources/${encodeURIComponent(src.id)}`)}
                  />
                );
              })}

              {!notebook.sources?.length && !showAddSource && (
                <p className="text-center text-base text-[var(--muted-foreground)] py-8">
                  No sources yet. Add a URL or upload a file.
                </p>
              )}
            </div>
          )}

          {/* Notes tab */}
          {tab === "notes" && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button
                  onClick={() => setShowAddNote(true)}
                  className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2.5 text-base text-[var(--primary-foreground)]"
                >
                  <Plus size={18} /> Add Note
                </button>
              </div>

              {showAddNote && (
                <form
                  onSubmit={handleCreateNote}
                  className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3"
                >
                  <input
                    type="text"
                    placeholder="Note title (optional)"
                    value={noteTitle}
                    onChange={(e) => setNoteTitle(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-base"
                  />
                  <textarea
                    placeholder="Note content..."
                    value={noteContent}
                    onChange={(e) => setNoteContent(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-base min-h-[120px]"
                    required
                  />
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      className="rounded-lg bg-[var(--primary)] px-5 py-2.5 text-base text-[var(--primary-foreground)]"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowAddNote(false)}
                      className="rounded-lg border border-[var(--border)] px-5 py-2.5 text-base"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              {notebook.notes?.map((note: any) => (
                <div
                  key={note.id}
                  className={`rounded-xl border bg-[var(--card)] overflow-hidden transition ${
                    expandedNoteId === note.id
                      ? "border-[var(--primary)] shadow-sm"
                      : "border-[var(--border)] hover:border-[var(--primary)]"
                  }`}
                >
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer"
                    onClick={() => toggleNoteExpand(note.id)}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <StickyNote size={18} className="text-[var(--primary)] flex-shrink-0" />
                      <div className="min-w-0">
                        <h3 className="text-base font-medium truncate">{note.title || "Untitled Note"}</h3>
                        <p className="text-sm text-[var(--muted-foreground)]">
                          {note.note_type || "human"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <ChevronDown
                        size={16}
                        className={`text-[var(--muted-foreground)] transition ${
                          expandedNoteId === note.id ? "rotate-180" : ""
                        }`}
                      />
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteNote(note.id); }}
                        className="rounded p-1 hover:bg-[var(--secondary)]"
                      >
                        <Trash2 size={14} className="text-[var(--destructive)]" />
                      </button>
                    </div>
                  </div>
                  {expandedNoteId === note.id && (
                    <div className="border-t border-[var(--border)] px-4 py-3">
                      {loadingNote ? (
                        <div className="flex justify-center py-4">
                          <Loader2 size={18} className="animate-spin text-[var(--muted-foreground)]" />
                        </div>
                      ) : (
                        <Markdown content={expandedNoteContent || ""} className="text-base" />
                      )}
                    </div>
                  )}
                </div>
              ))}

              {!notebook.notes?.length && !showAddNote && (
                <p className="text-center text-base text-[var(--muted-foreground)] py-8">
                  No notes yet. Create your first note.
                </p>
              )}
            </div>
          )}

          {/* Chat tab */}
          {tab === "chat" && (
            <div className="flex flex-col" style={{ height: "calc(100vh - 200px)" }}>
              {/* Session selector */}
              <div className="flex items-center justify-between mb-3">
                <div className="relative" ref={sessionDropdownRef}>
                  <button
                    onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
                    className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--secondary)] transition max-w-[220px]"
                  >
                    <MessageSquare size={14} />
                    <span className="truncate">
                      {sessions.find((s) => s.id === activeSessionId)?.title || "Select Chat"}
                    </span>
                    <ChevronDown size={12} className={`transition ${sessionDropdownOpen ? "rotate-180" : ""}`} />
                  </button>
                  {sessionDropdownOpen && (
                    <div className="absolute left-0 top-full mt-1 z-50 w-72 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl overflow-hidden">
                      <div className="border-b border-[var(--border)] p-2">
                        <button
                          onClick={createNewSession}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm hover:bg-[var(--secondary)] transition text-[var(--primary)] font-medium"
                        >
                          <Plus size={14} />
                          New Chat
                        </button>
                      </div>
                      <div className="max-h-64 overflow-auto">
                        {sessions.length === 0 ? (
                          <p className="px-3 py-4 text-sm text-center text-[var(--muted-foreground)]">
                            No chat history yet
                          </p>
                        ) : (
                          sessions.map((s) => (
                            <div
                              key={s.id}
                              onClick={() => switchSession(s.id)}
                              className={`flex items-center justify-between gap-2 px-3 py-2.5 text-sm cursor-pointer hover:bg-[var(--secondary)] transition ${
                                s.id === activeSessionId ? "bg-[var(--secondary)]" : ""
                              }`}
                            >
                              <div className="flex-1 min-w-0">
                                <p className="font-medium truncate">{s.title || "Untitled"}</p>
                                {s.updated && (
                                  <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                                    {new Date(s.updated).toLocaleString()}
                                  </p>
                                )}
                              </div>
                              <button
                                onClick={(ev) => deleteSession(s.id, ev)}
                                className="flex-shrink-0 rounded p-1 hover:bg-red-100 hover:text-red-500 transition"
                                title="Delete"
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
                <button
                  onClick={createNewSession}
                  className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--secondary)] transition"
                >
                  <Plus size={16} />
                  New Chat
                </button>
              </div>

              <div className="flex-1 overflow-auto space-y-4 mb-4">
                {messages.length === 0 && (
                  <p className="text-center text-base text-[var(--muted-foreground)] py-12">
                    {activeSessionId ? "Start a new conversation." : "Select a chat or start a new one."}
                  </p>
                )}
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === "human" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`max-w-[80%] ${msg.role === "human" ? "" : "space-y-2"}`}>
                      <div
                        className={`rounded-xl px-4 py-3 text-base ${
                          msg.role === "human"
                            ? "bg-[var(--primary)] text-[var(--primary-foreground)] whitespace-pre-wrap"
                            : "bg-[var(--secondary)] text-[var(--secondary-foreground)]"
                        }`}
                      >
                        {msg.role === "ai" ? (
                          msg.content ? (
                            <MarkdownWithCitations content={msg.content} references={msg.references} />
                          ) : (
                            <ThinkingIndicator />
                          )
                        ) : (
                          msg.content || "..."
                        )}
                      </div>
                      {msg.role === "ai" && msg.references && msg.references.length > 0 && msg.content && (
                        <p className="text-xs text-[var(--muted-foreground)] pl-1">
                          Based on {msg.references.length} reference{msg.references.length > 1 ? "s" : ""} from{" "}
                          {[...new Set(msg.references.map((r) => r.source_title))].join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              <form
                onSubmit={handleChat}
                className="flex gap-2 border-t border-[var(--border)] pt-4"
              >
                <input
                  type="text"
                  placeholder="Ask a question..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-base"
                  disabled={chatLoading}
                />
                <button
                  type="submit"
                  disabled={chatLoading}
                  className="rounded-lg bg-[var(--primary)] p-3 text-[var(--primary-foreground)] disabled:opacity-50"
                >
                  <Send size={18} />
                </button>
              </form>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
