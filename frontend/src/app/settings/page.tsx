"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { configAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import {
  ArrowLeft,
  Check,
  Eye,
  EyeOff,
  Loader2,
  Save,
  Settings,
} from "lucide-react";

interface ProviderModels {
  [provider: string]: string[];
}

function maskApiKey(key: string): string {
  const k = key.trim();
  if (!k) return "";
  if (k.length <= 6) return `${k.slice(0, 2)}******`;
  return `${k.slice(0, 4)}******${k.slice(-2)}`;
}

const GOOGLE_KEY_MASK_LS = "docchat_google_key_masked";
const OPENAI_KEY_MASK_LS = "docchat_openai_key_masked";

export default function SettingsPage() {
  const router = useRouter();
  const { user, checkAuth, loading } = useAuthStore();

  const [provider, setProvider] = useState("google");
  const [model, setModel] = useState("gemini-2.0-flash");
  const [googleKey, setGoogleKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [googleKeyMask, setGoogleKeyMask] = useState("");
  const [openaiKeyMask, setOpenaiKeyMask] = useState("");
  const [googleKeySet, setGoogleKeySet] = useState(false);
  const [openaiKeySet, setOpenaiKeySet] = useState(false);
  const [showGoogleKey, setShowGoogleKey] = useState(false);
  const [showOpenaiKey, setShowOpenaiKey] = useState(false);
  const [providers, setProviders] = useState<ProviderModels>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    else if (user) loadData();
  }, [user, loading]);

  const loadData = async () => {
    try {
      const [configRes, providersRes] = await Promise.all([
        configAPI.get(),
        configAPI.getProviders(),
      ]);
      const cfg = configRes.data.data;
      setProvider(cfg.default_provider);
      setModel(cfg.default_model);
      const gVal = cfg.google_api_key_set;
      const oVal = cfg.openai_api_key_set;
      setGoogleKeySet(!!gVal);
      const localGoogleMask =
        typeof window !== "undefined"
          ? window.localStorage.getItem(GOOGLE_KEY_MASK_LS) || ""
          : "";
      setGoogleKeyMask(typeof gVal === "string" ? gVal : localGoogleMask);
      setOpenaiKeySet(!!oVal);
      const localOpenaiMask =
        typeof window !== "undefined"
          ? window.localStorage.getItem(OPENAI_KEY_MASK_LS) || ""
          : "";
      setOpenaiKeyMask(typeof oVal === "string" ? oVal : localOpenaiMask);
      setProviders(providersRes.data.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingConfig(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      // Compute masked values locally (never persist plaintext keys).
      const nextGoogleMask = googleKey ? maskApiKey(googleKey) : googleKeyMask;
      const nextOpenaiMask = openaiKey ? maskApiKey(openaiKey) : openaiKeyMask;

      const data: any = {
        default_provider: provider,
        default_model: model,
      };
      if (googleKey) data.google_api_key = googleKey;
      if (openaiKey) data.openai_api_key = openaiKey;
      await configAPI.update(data);
      setSaved(true);
      if (typeof window !== "undefined") {
        if (googleKey) window.localStorage.setItem(GOOGLE_KEY_MASK_LS, nextGoogleMask);
        if (openaiKey) window.localStorage.setItem(OPENAI_KEY_MASK_LS, nextOpenaiMask);
      }
      if (googleKey) setGoogleKeyMask(nextGoogleMask);
      if (openaiKey) setOpenaiKeyMask(nextOpenaiMask);
      setGoogleKey("");
      setOpenaiKey("");
      loadData();
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  if (loadingConfig) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="animate-spin text-[var(--muted-foreground)]" size={32} />
      </div>
    );
  }

  const currentModels = providers[provider] || [];

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button
          onClick={() => router.push("/")}
          className="rounded-lg p-2 hover:bg-[var(--secondary)]"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex items-center gap-2">
          <Settings size={20} />
          <h1 className="text-lg font-bold">AI Settings</h1>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Provider Selection */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-4">
            <h2 className="text-base font-semibold">Default AI Provider</h2>
            <div className="grid grid-cols-2 gap-3">
              {Object.keys(providers).map((p) => (
                <button
                  key={p}
                  onClick={() => {
                    setProvider(p);
                    const models = providers[p];
                    if (models?.length) setModel(models[0]);
                  }}
                  className={`rounded-lg border px-4 py-3 text-sm font-medium transition ${
                    provider === p
                      ? "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]"
                      : "border-[var(--border)] hover:bg-[var(--secondary)]"
                  }`}
                >
                  {p === "google" ? "Google (Gemini)" : "OpenAI (GPT)"}
                </button>
              ))}
            </div>
          </div>

          {/* Model Selection */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-4">
            <h2 className="text-base font-semibold">Default Model</h2>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm"
            >
              {currentModels.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <p className="text-xs text-[var(--muted-foreground)]">
              This model will be used for chat and content analysis.
            </p>
          </div>

          {/* API Keys */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-5">
            <h2 className="text-base font-semibold">API Keys</h2>

            {/* Google */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Google API Key</label>
                {googleKeySet && (
                  <span className="flex items-center gap-1 text-xs text-green-500">
                    <Check size={12} /> Configured
                  </span>
                )}
              </div>
              <div className="relative">
                <input
                  type={showGoogleKey ? "text" : "password"}
                  value={googleKey}
                  onChange={(e) => setGoogleKey(e.target.value)}
                  placeholder={googleKeySet ? googleKeyMask || "Configured (••••••)" : "AIzaSy..."}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 pr-10 text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowGoogleKey(!showGoogleKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 hover:bg-[var(--secondary)]"
                >
                  {showGoogleKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* OpenAI */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">OpenAI API Key</label>
                {openaiKeySet && (
                  <span className="flex items-center gap-1 text-xs text-green-500">
                    <Check size={12} /> Configured
                  </span>
                )}
              </div>
              <div className="relative">
                <input
                  type={showOpenaiKey ? "text" : "password"}
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={openaiKeySet ? openaiKeyMask || "Configured (••••••)" : "sk-..."}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 pr-10 text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowOpenaiKey(!showOpenaiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 hover:bg-[var(--secondary)]"
                >
                  {showOpenaiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--primary)] px-6 py-3 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50 transition"
          >
            {saving ? (
              <Loader2 size={16} className="animate-spin" />
            ) : saved ? (
              <Check size={16} />
            ) : (
              <Save size={16} />
            )}
            {saving ? "Saving..." : saved ? "Saved!" : "Save Settings"}
          </button>
        </div>
      </main>
    </div>
  );
}
