import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { podcastsAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Play,
  Loader,
  Pencil,
  X,
  Check,
} from "lucide-react";

const VOICE_MODEL_OPTIONS = [
  { value: "", label: "Auto (use default)" },
  { value: "google:gemini-2.5-flash-preview-tts", label: "Gemini 2.5 Flash TTS", group: "Google TTS" },
  { value: "google:gemini-2.5-pro-preview-tts", label: "Gemini 2.5 Pro TTS", group: "Google TTS" },
  { value: "openai:tts-1", label: "TTS-1 (Standard)", group: "OpenAI TTS" },
  { value: "openai:tts-1-hd", label: "TTS-1 HD", group: "OpenAI TTS" },
  { value: "openai:gpt-4o-mini-tts", label: "GPT-4o Mini TTS", group: "OpenAI TTS" },
];

function VoiceModelSelect({ value, onChange, className }: { value: string; onChange: (v: string) => void; className?: string }) {
  const groups = new Map<string, typeof VOICE_MODEL_OPTIONS>();
  for (const o of VOICE_MODEL_OPTIONS) {
    const g = o.group || "__none__";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(o);
  }
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      {groups.get("__none__")?.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
      {[...groups.entries()].filter(([k]) => k !== "__none__").map(([g, opts]) => (
        <optgroup key={g} label={g}>
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function ProgressBar({ progress }: { progress: any }) {
  if (!progress || !progress.stage) return null;
  const pct = progress.pct || 0;
  const stageLabels: Record<string, string> = {
    init: "Initializing",
    outline: "Outline",
    transcript: "Transcript",
    tts: "Audio (TTS)",
    combining: "Combining",
    saving: "Saving",
    done: "Done",
    failed: "Failed",
  };
  const label = stageLabels[progress.stage] || progress.stage;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="font-medium text-[var(--foreground)]">{label}</span>
        <span className="text-[var(--muted-foreground)]">{progress.detail}</span>
      </div>
      <div className="w-full h-2 bg-[var(--secondary)] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: progress.stage === "failed"
              ? "var(--destructive)"
              : "var(--primary)",
          }}
        />
      </div>
      <div className="text-right text-[10px] text-[var(--muted-foreground)] mt-0.5">{pct}%</div>
    </div>
  );
}

const inputCls = "w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm";
const btnCls = "rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--secondary)]";

export default function PodcastsPage() {
  const navigate = useNavigate();
  const { user, loading, checkAuth } = useAuthStore();
  const [episodes, setEpisodes] = useState<any[]>([]);
  const [episodeProfiles, setEpisodeProfiles] = useState<any[]>([]);
  const [speakerProfiles, setSpeakerProfiles] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"episodes" | "profiles">("episodes");
  const [error, setError] = useState("");

  // Create Episode Profile
  const [epName, setEpName] = useState("");
  const [epSpeakerConfig, setEpSpeakerConfig] = useState("default");
  const [epDefaultBriefing, setEpDefaultBriefing] = useState("");
  const [epNumSegments, setEpNumSegments] = useState(5);

  // Create Speaker Profile
  const [spName, setSpName] = useState("");
  const [spDescription, setSpDescription] = useState("");
  const [spVoiceModel, setSpVoiceModel] = useState("");

  // Generate Episode
  const [genEpisodeName, setGenEpisodeName] = useState("");
  const [genEpisodeProfileName, setGenEpisodeProfileName] = useState("");
  const [genSpeakerProfileName, setGenSpeakerProfileName] = useState("");
  const [genContent, setGenContent] = useState("");
  const [genBriefing, setGenBriefing] = useState("");

  // Edit states
  const [editingEpId, setEditingEpId] = useState<string | null>(null);
  const [editEp, setEditEp] = useState<any>({});
  const [editingSpId, setEditingSpId] = useState<string | null>(null);
  const [editSp, setEditSp] = useState<any>({});

  // Audio player
  const [playingEpId, setPlayingEpId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // Transcript editor
  const [reviewEpId, setReviewEpId] = useState<string | null>(null);
  const [editDialogues, setEditDialogues] = useState<any[]>([]);

  // Polling
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { checkAuth(); }, []);

  useEffect(() => {
    if (!loading && !user) navigate("/login");
    else if (user) loadAll();
  }, [user, loading]);

  // Poll episodes while any is processing
  useEffect(() => {
    const hasProcessing = episodes.some((e) => e.status === "processing" || e.status === "pending");
    if (hasProcessing && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await podcastsAPI.listEpisodes();
          setEpisodes(res.data.data || []);
        } catch {}
      }, 3000);
    } else if (!hasProcessing && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); pollRef.current = null; };
  }, [episodes]);

  const loadAll = useCallback(async () => {
    try {
      const [ep, epP, spP] = await Promise.all([
        podcastsAPI.listEpisodes(),
        podcastsAPI.listEpisodeProfiles(),
        podcastsAPI.listSpeakerProfiles(),
      ]);
      setEpisodes(ep.data.data || []);
      setEpisodeProfiles(epP.data.data || []);
      setSpeakerProfiles(spP.data.data || []);
      if (epP.data.data?.length && !genEpisodeProfileName)
        setGenEpisodeProfileName(epP.data.data[0].name);
      if (spP.data.data?.length && !genSpeakerProfileName)
        setGenSpeakerProfileName(spP.data.data[0].name);
      if (spP.data.data?.length && (!epSpeakerConfig || epSpeakerConfig === "default"))
        setEpSpeakerConfig(spP.data.data[0].name);
    } catch {
      setError("Failed to load data.");
    }
  }, []);

  // ── CRUD ──
  const createEpisodeProfile = async () => {
    setError("");
    if (!epName.trim()) { setError("Name required."); return; }
    try {
      await podcastsAPI.createEpisodeProfile({
        name: epName.trim(), description: null,
        speaker_config: epSpeakerConfig.trim() || "default",
        outline_llm: null, transcript_llm: null, language: null,
        default_briefing: epDefaultBriefing, num_segments: epNumSegments,
      });
      setEpName(""); setEpDefaultBriefing(""); setEpNumSegments(5);
      loadAll();
    } catch { setError("Failed to create episode profile."); }
  };

  const saveEditEp = async () => {
    if (!editingEpId) return;
    try {
      const segs = Math.max(3, Math.min(20, editEp.num_segments || 5));
      await podcastsAPI.updateEpisodeProfile(editingEpId, {
        name: editEp.name, description: editEp.description || null,
        speaker_config: editEp.speaker_config || "default",
        outline_llm: null, transcript_llm: null, language: null,
        default_briefing: editEp.default_briefing || "",
        num_segments: segs,
      });
      setEditingEpId(null);
      loadAll();
    } catch { setError("Failed to update episode profile."); }
  };

  const createSpeakerProfile = async () => {
    setError("");
    if (!spName.trim()) { setError("Name required."); return; }
    try {
      const isGoogle = spVoiceModel.startsWith("google:");
      const defaultVoiceId = isGoogle ? "Achernar" : "alloy";
      await podcastsAPI.createSpeakerProfile({
        name: spName.trim(), description: spDescription || null,
        voice_model: spVoiceModel || null,
        speakers: [{ name: "Host", voice_id: spVoiceModel ? defaultVoiceId : "default", backstory: "N/A", personality: "Friendly and concise." }],
      });
      setSpName(""); setSpDescription(""); setSpVoiceModel("");
      loadAll();
    } catch { setError("Failed to create speaker profile."); }
  };

  const saveEditSp = async () => {
    if (!editingSpId) return;
    try {
      const isGoogle = (editSp.voice_model || "").startsWith("google:");
      const defaultVoiceId = isGoogle ? "Achernar" : "alloy";
      await podcastsAPI.updateSpeakerProfile(editingSpId, {
        name: editSp.name, description: editSp.description || null,
        voice_model: editSp.voice_model || null,
        speakers: (editSp.speakers?.length ? editSp.speakers : [
          { name: "Host", voice_id: editSp.voice_model ? defaultVoiceId : "default", backstory: "N/A", personality: "Friendly and concise." },
        ]),
      });
      setEditingSpId(null);
      loadAll();
    } catch { setError("Failed to update speaker profile."); }
  };

  const generateEpisode = async () => {
    setError("");
    if (!genEpisodeName.trim()) { setError("Episode name required."); return; }
    if (!genEpisodeProfileName || !genSpeakerProfileName) { setError("Select both profiles."); return; }
    try {
      await podcastsAPI.generate({
        episode_profile_name: genEpisodeProfileName,
        speaker_profile_name: genSpeakerProfileName,
        episode_name: genEpisodeName.trim(),
        content: genContent.trim() || undefined,
        briefing: genBriefing.trim() || undefined,
      });
      setGenEpisodeName("");
      setGenContent("");
      setGenBriefing("");
      loadAll();
    } catch { setError("Failed to generate episode."); }
  };

  const playAudio = async (epId: string) => {
    if (playingEpId === epId) {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setPlayingEpId(null);
      setAudioUrl(null);
      return;
    }
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/podcasts/episodes/${epId}/audio`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(url);
      setPlayingEpId(epId);
    } catch (e: any) {
      setError(`Failed to load audio: ${e.message?.slice(0, 100)}`);
    }
  };

  const openReview = (ep: any) => {
    setReviewEpId(ep.id);
    setEditDialogues(ep.transcript?.dialogues || []);
  };

  const saveTranscript = async () => {
    if (!reviewEpId) return;
    try {
      await podcastsAPI.updateTranscript(reviewEpId, editDialogues);
      setReviewEpId(null);
      loadAll();
    } catch { setError("Failed to save transcript."); }
  };

  const startAudioGen = async (epId: string) => {
    try {
      await podcastsAPI.generateAudio(epId);
      loadAll();
    } catch { setError("Failed to start audio generation."); }
  };

  const deleteEpisode = async (id: string) => {
    if (!confirm("Delete this episode?")) return;
    await podcastsAPI.deleteEpisode(id);
    loadAll();
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button onClick={() => navigate("/")} className="rounded-lg p-2 hover:bg-[var(--secondary)]">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold">Podcasts</h1>
      </header>

      <main className="mx-auto max-w-4xl p-6">
        <div className="flex gap-4 mb-6 border-b border-[var(--border)]">
          {(["episodes", "profiles"] as const).map((t) => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`pb-2 px-1 text-sm font-medium border-b-2 transition ${activeTab === t ? "border-[var(--primary)] text-[var(--primary)]" : "border-transparent text-[var(--muted-foreground)]"}`}>
              {t === "episodes" ? `Episodes (${episodes.length})` : "Profiles"}
            </button>
          ))}
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">{error}</div>}

        {/* ═══════ EPISODES TAB ═══════ */}
        {activeTab === "episodes" && (
          <div className="space-y-4">
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center justify-between gap-3 mb-3">
                <div>
                  <h3 className="font-semibold">Generate Episode</h3>
                  <p className="text-xs text-[var(--muted-foreground)]">Uses your episode profile + speaker profile.</p>
                </div>
                <button onClick={generateEpisode} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90">
                  <Plus size={16} className="inline-block -mt-0.5 mr-1" /> Generate
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium">Episode Name</label>
                  <input value={genEpisodeName} onChange={(e) => setGenEpisodeName(e.target.value)} className={inputCls} placeholder="e.g., Week 1 - Weekly Update" />
                </div>
                <div>
                  <label className="text-xs font-medium">Episode Profile</label>
                  <select value={genEpisodeProfileName} onChange={(e) => setGenEpisodeProfileName(e.target.value)} className={inputCls}>
                    {episodeProfiles.map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium">Speaker Profile</label>
                  <select value={genSpeakerProfileName} onChange={(e) => setGenSpeakerProfileName(e.target.value)} className={inputCls}>
                    {speakerProfiles.map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs font-medium">Content / Topic</label>
                  <textarea value={genContent} onChange={(e) => setGenContent(e.target.value)}
                    className={`${inputCls} min-h-[80px] resize-none`}
                    placeholder="Paste your material or describe the topic you want to discuss…" />
                  <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">Provide specific content, URLs, or topic description. Leave empty for general conversation.</p>
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs font-medium">Briefing / Style Guide</label>
                  <textarea value={genBriefing} onChange={(e) => setGenBriefing(e.target.value)}
                    className={`${inputCls} min-h-[60px] resize-none`}
                    placeholder="e.g., Let's have a relaxed chat about the trends in AI technology." />
                  <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                    Describe the topic and style. Length is primarily controlled by <b>Num Segments</b> in Episode Profile (3 = short, 5 = medium, 10+ = long).
                  </p>
                </div>
              </div>
            </div>

            {episodes.map((ep) => (
              <div key={ep.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{ep.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        ep.status === "completed" ? "bg-green-100 text-green-700"
                        : ep.status === "review" ? "bg-blue-100 text-blue-700"
                        : ep.status === "failed" ? "bg-red-100 text-red-700"
                        : "bg-yellow-100 text-yellow-700"
                      }`}>
                        {ep.status === "review" ? "Review Transcript" : ep.status}
                      </span>
                      {ep.status === "failed" && ep.error_message && (
                        <span className="text-xs text-red-500 truncate max-w-[300px]" title={ep.error_message}>{ep.error_message.slice(0, 80)}</span>
                      )}
                    </div>
                    {(ep.status === "processing" || ep.status === "pending") && <ProgressBar progress={ep.progress} />}
                    {playingEpId === ep.id && audioUrl && (
                      <audio controls autoPlay src={audioUrl} className="mt-2 w-full" onEnded={() => { if (audioUrl) URL.revokeObjectURL(audioUrl); setPlayingEpId(null); setAudioUrl(null); }} />
                    )}
                  </div>
                  <div className="flex gap-2 ml-3 flex-shrink-0">
                    {ep.status === "review" && (
                      <>
                        <button onClick={() => openReview(ep)} className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">
                          <Pencil size={12} className="inline -mt-0.5 mr-1" /> Edit
                        </button>
                        <button onClick={() => startAudioGen(ep.id)} className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90">
                          <Play size={12} className="inline -mt-0.5 mr-1" /> Generate Audio
                        </button>
                      </>
                    )}
                    {ep.status === "completed" && ep.audio_file && (
                      <button onClick={() => playAudio(ep.id)} className={`rounded p-1.5 hover:bg-[var(--secondary)] ${playingEpId === ep.id ? "bg-[var(--secondary)]" : ""}`}>
                        <Play size={16} className="text-[var(--primary)]" />
                      </button>
                    )}
                    {ep.status === "processing" && <Loader size={16} className="animate-spin text-[var(--muted-foreground)]" />}
                    <button onClick={() => deleteEpisode(ep.id)} className="rounded p-1.5 hover:bg-[var(--secondary)]">
                      <Trash2 size={14} className="text-[var(--destructive)]" />
                    </button>
                  </div>
                </div>

                {/* Transcript preview (review state) */}
                {ep.status === "review" && ep.transcript?.dialogues?.length > 0 && reviewEpId !== ep.id && (
                  <div className="mt-3 border-t border-[var(--border)] pt-3 max-h-48 overflow-y-auto">
                    <p className="text-xs font-medium text-[var(--muted-foreground)] mb-2">Transcript Preview ({ep.transcript.dialogues.length} turns)</p>
                    {ep.transcript.dialogues.slice(0, 6).map((d: any, i: number) => (
                      <div key={i} className="flex gap-2 text-xs mb-1">
                        <span className="font-semibold text-[var(--primary)] flex-shrink-0 w-16 truncate">{d.speaker}:</span>
                        <span className="text-[var(--foreground)] truncate">{d.dialogue}</span>
                      </div>
                    ))}
                    {ep.transcript.dialogues.length > 6 && (
                      <p className="text-[10px] text-[var(--muted-foreground)]">… and {ep.transcript.dialogues.length - 6} more turns</p>
                    )}
                  </div>
                )}

                {/* Transcript editor (expanded) */}
                {reviewEpId === ep.id && (
                  <div className="mt-3 border-t border-[var(--border)] pt-3 space-y-2">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-medium">Edit Transcript ({editDialogues.length} turns)</p>
                      <div className="flex gap-2">
                        <button onClick={saveTranscript} className="rounded-lg bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700">
                          <Check size={12} className="inline -mt-0.5 mr-1" /> Save
                        </button>
                        <button onClick={() => setReviewEpId(null)} className="rounded-lg border border-[var(--border)] px-3 py-1 text-xs hover:bg-[var(--secondary)]">
                          Cancel
                        </button>
                      </div>
                    </div>
                    <div className="max-h-96 overflow-y-auto space-y-2 pr-1">
                      {editDialogues.map((d, i) => (
                        <div key={i} className="flex gap-2 items-start">
                          <input value={d.speaker} onChange={(e) => {
                            const updated = [...editDialogues];
                            updated[i] = { ...d, speaker: e.target.value };
                            setEditDialogues(updated);
                          }} className="w-20 flex-shrink-0 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs font-medium" />
                          <textarea value={d.dialogue} onChange={(e) => {
                            const updated = [...editDialogues];
                            updated[i] = { ...d, dialogue: e.target.value };
                            setEditDialogues(updated);
                          }} className="flex-1 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs min-h-[36px] resize-none" rows={2} />
                          <button onClick={() => setEditDialogues(editDialogues.filter((_, j) => j !== i))} className="rounded p-1 hover:bg-red-50 flex-shrink-0">
                            <Trash2 size={12} className="text-red-400" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <button onClick={() => setEditDialogues([...editDialogues, { speaker: "Host", dialogue: "" }])} className="text-xs text-blue-600 hover:underline">
                      + Add turn
                    </button>
                  </div>
                )}
              </div>
            ))}
            {episodes.length === 0 && <p className="text-center text-[var(--muted-foreground)] py-8">No podcast episodes yet.</p>}
          </div>
        )}

        {/* ═══════ PROFILES TAB ═══════ */}
        {activeTab === "profiles" && (
          <div className="space-y-6">
            {/* ── Episode Profiles ── */}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              <h3 className="font-semibold">Episode Profiles</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium">Name</label>
                  <input value={epName} onChange={(e) => setEpName(e.target.value)} className={inputCls} placeholder="e.g., Tech Weekly" />
                </div>
                <div>
                  <label className="text-xs font-medium">Num Segments</label>
                  <input type="number" value={epNumSegments} onChange={(e) => setEpNumSegments(Number(e.target.value))} className={inputCls} min={3} max={20} />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs font-medium">Speaker Config</label>
                  <input value={epSpeakerConfig} onChange={(e) => setEpSpeakerConfig(e.target.value)} className={inputCls} placeholder="Speaker profile name" />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs font-medium">Default Briefing</label>
                  <textarea value={epDefaultBriefing} onChange={(e) => setEpDefaultBriefing(e.target.value)} className={`${inputCls} min-h-[80px] resize-none`} placeholder="Short guidance…" />
                </div>
              </div>
              <button onClick={createEpisodeProfile} className={btnCls}>Create Episode Profile</button>

              <div className="pt-2 border-t border-[var(--border)] space-y-2">
                {episodeProfiles.map((p) => (
                  <div key={p.id} className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3">
                    {editingEpId === p.id ? (
                      <div className="space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          <input value={editEp.name || ""} onChange={(e) => setEditEp({ ...editEp, name: e.target.value })} className={inputCls} placeholder="Name" />
                          <input type="number" value={editEp.num_segments || 5} onChange={(e) => setEditEp({ ...editEp, num_segments: Number(e.target.value) })} className={inputCls} min={3} max={20} />
                        </div>
                        <input value={editEp.speaker_config || ""} onChange={(e) => setEditEp({ ...editEp, speaker_config: e.target.value })} className={inputCls} placeholder="Speaker config" />
                        <textarea value={editEp.default_briefing || ""} onChange={(e) => setEditEp({ ...editEp, default_briefing: e.target.value })} className={`${inputCls} min-h-[60px] resize-none`} placeholder="Briefing" />
                        <div className="flex gap-2">
                          <button onClick={saveEditEp} className="rounded p-1.5 hover:bg-green-50"><Check size={16} className="text-green-600" /></button>
                          <button onClick={() => setEditingEpId(null)} className="rounded p-1.5 hover:bg-red-50"><X size={16} className="text-red-500" /></button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium">{p.name}</span>
                          <span className="ml-2 text-xs text-[var(--muted-foreground)]">{p.num_segments} segments</span>
                          {p.default_briefing && <p className="text-xs text-[var(--muted-foreground)] mt-0.5 truncate max-w-md">{p.default_briefing}</p>}
                        </div>
                        <div className="flex gap-1">
                          <button onClick={() => { setEditingEpId(p.id); setEditEp({ ...p }); }} className="rounded p-1.5 hover:bg-[var(--secondary)]"><Pencil size={14} /></button>
                          <button onClick={async () => { await podcastsAPI.deleteEpisodeProfile(p.id); loadAll(); }} className="rounded p-1.5 hover:bg-[var(--secondary)]"><Trash2 size={14} className="text-[var(--destructive)]" /></button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {episodeProfiles.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">No episode profiles yet.</p>}
              </div>
            </div>

            {/* ── Speaker Profiles ── */}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              <h3 className="font-semibold">Speaker Profiles</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium">Name</label>
                  <input value={spName} onChange={(e) => setSpName(e.target.value)} className={inputCls} placeholder="e.g., Default Voice" />
                </div>
                <div>
                  <label className="text-xs font-medium">Voice Model</label>
                  <VoiceModelSelect value={spVoiceModel} onChange={setSpVoiceModel} className={inputCls} />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs font-medium">Description (optional)</label>
                  <input value={spDescription} onChange={(e) => setSpDescription(e.target.value)} className={inputCls} placeholder="Short description" />
                </div>
              </div>
              <button onClick={createSpeakerProfile} className={btnCls}>Create Speaker Profile</button>

              <div className="pt-2 border-t border-[var(--border)] space-y-2">
                {speakerProfiles.map((p) => (
                  <div key={p.id} className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3">
                    {editingSpId === p.id ? (
                      <div className="space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          <input value={editSp.name || ""} onChange={(e) => setEditSp({ ...editSp, name: e.target.value })} className={inputCls} placeholder="Name" />
                          <VoiceModelSelect value={editSp.voice_model || ""} onChange={(v) => setEditSp({ ...editSp, voice_model: v })} className={inputCls} />
                        </div>
                        <input value={editSp.description || ""} onChange={(e) => setEditSp({ ...editSp, description: e.target.value })} className={inputCls} placeholder="Description" />
                        <div className="flex gap-2">
                          <button onClick={saveEditSp} className="rounded p-1.5 hover:bg-green-50"><Check size={16} className="text-green-600" /></button>
                          <button onClick={() => setEditingSpId(null)} className="rounded p-1.5 hover:bg-red-50"><X size={16} className="text-red-500" /></button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium">{p.name}</span>
                          <span className="ml-2 text-xs text-[var(--muted-foreground)]">{p.voice_model || "auto"}</span>
                          <span className="ml-2 text-xs text-[var(--muted-foreground)]">{p.speakers?.length || 0} speakers</span>
                        </div>
                        <div className="flex gap-1">
                          <button onClick={() => { setEditingSpId(p.id); setEditSp({ ...p }); }} className="rounded p-1.5 hover:bg-[var(--secondary)]"><Pencil size={14} /></button>
                          <button onClick={async () => { await podcastsAPI.deleteSpeakerProfile(p.id); loadAll(); }} className="rounded p-1.5 hover:bg-[var(--secondary)]"><Trash2 size={14} className="text-[var(--destructive)]" /></button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {speakerProfiles.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">No speaker profiles yet.</p>}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
