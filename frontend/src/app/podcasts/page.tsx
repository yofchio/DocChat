"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { podcastsAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { ArrowLeft, Plus, Trash2, Play, Loader } from "lucide-react";

export default function PodcastsPage() {
  const router = useRouter();
  const { user, loading, checkAuth } = useAuthStore();
  const [episodes, setEpisodes] = useState<any[]>([]);
  const [episodeProfiles, setEpisodeProfiles] = useState<any[]>([]);
  const [speakerProfiles, setSpeakerProfiles] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"episodes" | "profiles">("episodes");

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    else if (user) loadAll();
  }, [user, loading]);

  const loadAll = async () => {
    try {
      const [ep, epP, spP] = await Promise.all([
        podcastsAPI.listEpisodes(),
        podcastsAPI.listEpisodeProfiles(),
        podcastsAPI.listSpeakerProfiles(),
      ]);
      setEpisodes(ep.data.data || []);
      setEpisodeProfiles(epP.data.data || []);
      setSpeakerProfiles(spP.data.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  const deleteEpisode = async (id: string) => {
    if (!confirm("Delete this episode?")) return;
    await podcastsAPI.deleteEpisode(id);
    loadAll();
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
        <h1 className="text-lg font-bold">Podcasts</h1>
      </header>

      <main className="mx-auto max-w-4xl p-6">
        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b border-[var(--border)]">
          {(["episodes", "profiles"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className={`pb-2 px-1 text-sm font-medium border-b-2 transition ${
                activeTab === t
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--muted-foreground)]"
              }`}
            >
              {t === "episodes" ? `Episodes (${episodes.length})` : "Profiles"}
            </button>
          ))}
        </div>

        {activeTab === "episodes" && (
          <div className="space-y-4">
            {episodes.map((ep) => (
              <div
                key={ep.id}
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium">{ep.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          ep.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : ep.status === "failed"
                              ? "bg-red-100 text-red-700"
                              : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {ep.status}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {ep.status === "completed" && (
                      <button className="rounded p-1 hover:bg-[var(--secondary)]">
                        <Play size={16} className="text-[var(--primary)]" />
                      </button>
                    )}
                    {ep.status === "processing" && (
                      <Loader
                        size={16}
                        className="animate-spin text-[var(--muted-foreground)]"
                      />
                    )}
                    <button
                      onClick={() => deleteEpisode(ep.id)}
                      className="rounded p-1 hover:bg-[var(--secondary)]"
                    >
                      <Trash2
                        size={14}
                        className="text-[var(--destructive)]"
                      />
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {episodes.length === 0 && (
              <p className="text-center text-[var(--muted-foreground)] py-8">
                No podcast episodes yet.
              </p>
            )}
          </div>
        )}

        {activeTab === "profiles" && (
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold mb-3 text-[var(--muted-foreground)] uppercase tracking-wider">
                Episode Profiles
              </h3>
              {episodeProfiles.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 mb-2"
                >
                  <div>
                    <span className="font-medium">{p.name}</span>
                    {p.description && (
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {p.description}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={async () => {
                      await podcastsAPI.deleteEpisodeProfile(p.id);
                      loadAll();
                    }}
                    className="rounded p-1 hover:bg-[var(--secondary)]"
                  >
                    <Trash2 size={14} className="text-[var(--destructive)]" />
                  </button>
                </div>
              ))}
              {episodeProfiles.length === 0 && (
                <p className="text-sm text-[var(--muted-foreground)]">
                  No episode profiles.
                </p>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold mb-3 text-[var(--muted-foreground)] uppercase tracking-wider">
                Speaker Profiles
              </h3>
              {speakerProfiles.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 mb-2"
                >
                  <div>
                    <span className="font-medium">{p.name}</span>
                    <span className="ml-2 text-xs text-[var(--muted-foreground)]">
                      {p.speakers?.length || 0} speakers
                    </span>
                  </div>
                  <button
                    onClick={async () => {
                      await podcastsAPI.deleteSpeakerProfile(p.id);
                      loadAll();
                    }}
                    className="rounded p-1 hover:bg-[var(--secondary)]"
                  >
                    <Trash2 size={14} className="text-[var(--destructive)]" />
                  </button>
                </div>
              ))}
              {speakerProfiles.length === 0 && (
                <p className="text-sm text-[var(--muted-foreground)]">
                  No speaker profiles.
                </p>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
