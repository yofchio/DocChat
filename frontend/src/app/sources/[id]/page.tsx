"use client";

import { useEffect, useState, useRef, use, useCallback } from "react";
import { useRouter } from "next/navigation";
import { sourcesAPI, chatAPI, sessionsAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import {
  ArrowLeft,
  FileText,
  Loader2,
  Send,
  AlertCircle,
  CheckCircle2,
  Clock,
  RefreshCw,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  MessageSquare,
  Trash2,
  ChevronDown,
} from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { MarkdownWithCitations } from "@/components/MarkdownWithCitations";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";

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

export default function SourceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const sourceId = decodeURIComponent(id);
  const router = useRouter();
  const { user, checkAuth, loading } = useAuthStore();

  const [source, setSource] = useState<any>(null);
  const [loadingSource, setLoadingSource] = useState(true);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [generatingGuide, setGeneratingGuide] = useState(false);
  const [guideCollapsed, setGuideCollapsed] = useState(false);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    else if (user) {
      loadSource();
      loadSessions();
    }
  }, [user, loading]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!sessionDropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [sessionDropdownOpen]);

  const loadSource = async () => {
    try {
      const res = await sourcesAPI.get(sourceId);
      setSource(res.data.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSource(false);
    }
  };

  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      const res = await sessionsAPI.list({ source_id: sourceId });
      setSessions(res.data.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSessions(false);
    }
  };

  const createNewSession = async () => {
    try {
      const res = await sessionsAPI.create({ source_id: sourceId });
      const newSession = res.data.data;
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
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

  useEffect(() => {
    if (!source) return;
    if (source.status === "pending" || source.status === "processing") {
      const timer = setInterval(loadSource, 3000);
      return () => clearInterval(timer);
    }
  }, [source?.status]);

  const handleReprocess = async () => {
    await sourcesAPI.process(sourceId);
    loadSource();
  };

  const handleGenerateGuide = async () => {
    setGeneratingGuide(true);
    try {
      await sourcesAPI.generateGuide(sourceId);
      const poll = setInterval(async () => {
        try {
          const res = await sourcesAPI.get(sourceId);
          const s = res.data.data;
          if (s.summary || s.topics?.length > 0) {
            setSource(s);
            clearInterval(poll);
            setGeneratingGuide(false);
          }
        } catch { /* keep polling */ }
      }, 2000);
      setTimeout(() => { clearInterval(poll); setGeneratingGuide(false); }, 30000);
    } catch (e) {
      console.error(e);
      setGeneratingGuide(false);
    }
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput;
    setChatInput("");

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const res = await sessionsAPI.create({ source_id: sourceId });
        const newSession = res.data.data;
        setSessions((prev) => [newSession, ...prev]);
        sessionId = newSession.id;
        setActiveSessionId(newSession.id);
      } catch (err) {
        console.error(err);
        return;
      }
    }

    setMessages((prev) => [...prev, { role: "human", content: msg }]);
    setChatLoading(true);

    try {
      const res = await chatAPI.sourceStream({
        message: msg,
        source_id: sourceId,
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
              if (parsed.error) {
                aiContent += `\n\nError: ${parsed.error}`;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = { role: "ai", content: aiContent, references: refs };
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

  if (loadingSource) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="animate-spin text-[var(--muted-foreground)]" size={32} />
      </div>
    );
  }

  if (!source) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-[var(--muted-foreground)]">Source not found</p>
      </div>
    );
  }

  const st = STATUS_CONFIG[source.status] || STATUS_CONFIG.pending;
  const StatusIcon = st.icon;
  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex-shrink-0 flex items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-4 py-2.5">
        <button
          onClick={() => router.back()}
          className="rounded-lg p-2 hover:bg-[var(--secondary)]"
        >
          <ArrowLeft size={18} />
        </button>
        <FileText size={20} className="text-[var(--primary)]" />
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold truncate">{source.title || "Untitled Source"}</h1>
          <div className="flex items-center gap-2 text-sm">
            <StatusIcon
              size={12}
              className={`${st.color} ${source.status === "processing" ? "animate-spin" : ""}`}
            />
            <span className={st.color}>{st.label}</span>
            {source.status_message && (
              <span className="text-[var(--muted-foreground)] truncate">
                — {source.status_message}
              </span>
            )}
          </div>
        </div>
        {source.status === "error" && (
          <button
            onClick={handleReprocess}
            className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--secondary)]"
          >
            <RefreshCw size={12} /> Retry
          </button>
        )}
        <button
          onClick={() => setChatCollapsed(!chatCollapsed)}
          className="rounded-lg p-2 hover:bg-[var(--secondary)]"
          title={chatCollapsed ? "Show chat" : "Hide chat"}
        >
          {chatCollapsed ? <PanelRightOpen size={18} /> : <PanelRightClose size={18} />}
        </button>
      </header>

      {/* Split view */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Source content */}
        <div className={`${chatCollapsed ? "w-full" : "w-1/2"} border-r border-[var(--border)] overflow-auto`}>
            {/* Source Guide */}
            {source.status === "completed" && !source.summary && !(source.topics && source.topics.length > 0) && source.full_text && (
              <div className="border-b border-[var(--border)] bg-[var(--card)] p-4 flex items-center justify-between">
                <p className="text-xs text-[var(--muted-foreground)]">
                  No Source Guide available yet.
                </p>
                <button
                  onClick={handleGenerateGuide}
                  disabled={generatingGuide}
                  className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--secondary)] transition disabled:opacity-50"
                >
                  {generatingGuide ? (
                    <><Loader2 size={12} className="animate-spin" /> Generating...</>
                  ) : (
                    <><RefreshCw size={12} /> Generate Guide</>
                  )}
                </button>
              </div>
            )}
            {source.status === "completed" && (source.summary || (source.topics && source.topics.length > 0)) && (
              <div className="border-b border-[var(--border)] bg-gradient-to-b from-[var(--card)] to-[var(--background)]">
                <div
                  className="flex items-center justify-between px-5 pt-4 pb-2 cursor-pointer"
                  onClick={() => setGuideCollapsed(!guideCollapsed)}
                >
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-[var(--primary)]" />
                    <h2 className="text-sm font-bold text-[var(--primary)]">Source Guide</h2>
                  </div>
                  <ChevronDown
                    size={16}
                    className={`text-[var(--muted-foreground)] transition ${guideCollapsed ? "-rotate-90" : ""}`}
                  />
                </div>
                {!guideCollapsed && (
                  <div className="px-5 pb-4 space-y-3">
                    {source.summary && (
                      <p className="text-sm leading-relaxed text-[var(--foreground)]">
                        {source.summary}
                      </p>
                    )}
                    {source.topics && source.topics.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {source.topics.map((topic: string, i: number) => (
                          <span
                            key={i}
                            className="inline-flex items-center rounded-full border border-[var(--border)] bg-[var(--secondary)] px-2.5 py-0.5 text-xs text-[var(--secondary-foreground)]"
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    )}
                    {source.full_text && (
                      <p className="text-[11px] text-[var(--muted-foreground)]">
                        {Math.round(source.full_text.length / 4.5).toLocaleString()} words approx.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Full content */}
            <div className="p-5">
              {source.full_text ? (
                <Markdown content={source.full_text} className="text-[var(--foreground)]" />
              ) : source.status === "completed" ? (
                <p className="text-[var(--muted-foreground)] text-sm">
                  No text content extracted from this source.
                </p>
              ) : (
                <div className="flex flex-col items-center gap-3 py-12 text-[var(--muted-foreground)]">
                  <Loader2 className="animate-spin" size={24} />
                  <p className="text-sm">Content is being processed...</p>
                </div>
              )}
            </div>
          </div>

        {/* Right panel: AI Chat */}
        {!chatCollapsed && (
        <div className="flex flex-col w-1/2">
          {/* Chat header with session selector */}
          <div className="flex-shrink-0 border-b border-[var(--border)] bg-[var(--card)] px-4 py-2.5">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-semibold">Chat with this Source</h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Ask questions about the content of this document
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* Session dropdown */}
                <div className="relative" ref={dropdownRef}>
                  <button
                    onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
                    className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--secondary)] transition max-w-[200px]"
                  >
                    <MessageSquare size={14} />
                    <span className="truncate">
                      {activeSession ? activeSession.title : "Select Chat"}
                    </span>
                    <ChevronDown size={12} className={`transition ${sessionDropdownOpen ? "rotate-180" : ""}`} />
                  </button>
                  {sessionDropdownOpen && (
                    <div className="absolute right-0 top-full mt-1 z-50 w-72 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl overflow-hidden">
                      <div className="border-b border-[var(--border)] p-2">
                        <button
                          onClick={createNewSession}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs hover:bg-[var(--secondary)] transition text-[var(--primary)] font-medium"
                        >
                          <Plus size={14} />
                          New Chat
                        </button>
                      </div>
                      <div className="max-h-64 overflow-auto">
                        {loadingSessions ? (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 size={16} className="animate-spin text-[var(--muted-foreground)]" />
                          </div>
                        ) : sessions.length === 0 ? (
                          <p className="px-3 py-4 text-xs text-center text-[var(--muted-foreground)]">
                            No chat history yet
                          </p>
                        ) : (
                          sessions.map((s) => (
                            <div
                              key={s.id}
                              onClick={() => switchSession(s.id)}
                              className={`flex items-center justify-between gap-2 px-3 py-2.5 text-xs cursor-pointer hover:bg-[var(--secondary)] transition ${
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
                                onClick={(e) => deleteSession(s.id, e)}
                                className="flex-shrink-0 rounded p-1 hover:bg-red-100 hover:text-red-500 transition opacity-0 group-hover:opacity-100"
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
                {/* New Chat button */}
                <button
                  onClick={createNewSession}
                  className="rounded-lg p-2 hover:bg-[var(--secondary)] transition"
                  title="New Chat"
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-auto p-4 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-[var(--muted-foreground)]">
                <FileText size={36} className="opacity-30" />
                <p className="text-base">
                  {activeSessionId ? "Start a new conversation." : "Select a chat or start a new one."}
                </p>
                <div className="flex flex-wrap gap-2 mt-3">
                  {["Summarize this document", "What are the key points?", "Explain the main concepts"].map(
                    (q) => (
                      <button
                        key={q}
                        onClick={() => setChatInput(q)}
                        className="rounded-full border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--secondary)] transition"
                      >
                        {q}
                      </button>
                    )
                  )}
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "human" ? "justify-end" : "justify-start"}`}
              >
                <div className={`max-w-[85%] ${msg.role === "human" ? "" : "space-y-2"}`}>
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
                        chatLoading && i === messages.length - 1 ? <ThinkingIndicator /> : null
                      )
                    ) : (
                      msg.content || "..."
                    )}
                  </div>
                  {msg.role === "ai" && msg.references && msg.references.length > 0 && msg.content && (
                    <p className="text-[10px] text-[var(--muted-foreground)] pl-1">
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
            className="flex-shrink-0 flex gap-2 border-t border-[var(--border)] p-3"
          >
            <input
              type="text"
              placeholder="Ask about this source..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-base"
              disabled={chatLoading}
            />
            <button
              type="submit"
              disabled={chatLoading || source.status !== "completed"}
              className="rounded-lg bg-[var(--primary)] p-3 text-[var(--primary-foreground)] disabled:opacity-50"
            >
              {chatLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </form>
        </div>
        )}
      </div>
    </div>
  );
}
