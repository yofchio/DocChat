"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { FileText, MessageSquare, Sparkles, Loader2, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let res;
      if (isRegister) {
        res = await authAPI.register({ username, email, password });
      } else {
        res = await authAPI.login({ username, password });
      }
      const token = res.data.access_token;
      localStorage.setItem("token", token);
      const meRes = await authAPI.me();
      setAuth(meRes.data, token);
      router.push("/");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style jsx global>{`
        @keyframes float {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-10px) scale(1.02); }
        }
        @keyframes float-slow {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(14px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .anim-float { animation: float 6s ease-in-out infinite; }
        .anim-float-slow { animation: float-slow 8s ease-in-out infinite; }
        .anim-fade-up { animation: fade-up 0.5s ease-out both; }
        .anim-d1 { animation: fade-up 0.5s ease-out 0.08s both; }
        .anim-d2 { animation: fade-up 0.5s ease-out 0.16s both; }
        .anim-d3 { animation: fade-up 0.5s ease-out 0.24s both; }
        .anim-d4 { animation: fade-up 0.5s ease-out 0.32s both; }
        .anim-d5 { animation: fade-up 0.5s ease-out 0.40s both; }
      `}</style>

      <div className="flex min-h-screen">
        {/* Left side - Branding */}
        <div className="hidden lg:flex lg:w-1/2 bg-stone-50 relative overflow-hidden">
          <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-stone-100/80 anim-float" />
          <div className="absolute -bottom-28 -left-12 w-72 h-72 rounded-full bg-stone-100/60 anim-float-slow" />
          <div className="absolute top-1/3 right-8 w-20 h-20 rounded-full bg-stone-200/40 anim-float-slow" />

          {/* Content aligned to the right (toward center) */}
          <div className="relative z-10 ml-auto flex w-full max-w-md flex-col justify-between py-10 pl-8 pr-12">
            <div className="anim-fade-up">
              <div className="flex items-center gap-2.5">
                <div className="rounded-lg bg-stone-900 p-2">
                  <FileText size={18} className="text-white" />
                </div>
                <h1 className="text-2xl font-bold text-stone-900">DocChat</h1>
              </div>
            </div>

            <div className="space-y-8">
              <h2 className="text-4xl font-semibold leading-[1.15] text-stone-900 tracking-tight anim-d1">
                Your documents,<br />
                <span className="text-stone-400">understood.</span>
              </h2>

              <div className="space-y-5">
                <div className="flex items-start gap-3.5 anim-d2">
                  <div className="flex-shrink-0 rounded-full bg-white p-2.5 shadow-sm ring-1 ring-stone-200/60">
                    <FileText size={18} className="text-stone-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-stone-900">Upload sources</h3>
                    <p className="text-sm text-stone-500 mt-0.5">
                      PDFs, Word docs, web pages — AI reads them for you.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3.5 anim-d3">
                  <div className="flex-shrink-0 rounded-full bg-white p-2.5 shadow-sm ring-1 ring-stone-200/60">
                    <MessageSquare size={18} className="text-stone-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-stone-900">Ask anything</h3>
                    <p className="text-sm text-stone-500 mt-0.5">
                      Chat naturally, get answers grounded in your files.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3.5 anim-d4">
                  <div className="flex-shrink-0 rounded-full bg-white p-2.5 shadow-sm ring-1 ring-stone-200/60">
                    <Sparkles size={18} className="text-stone-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-stone-900">Get cited insights</h3>
                    <p className="text-sm text-stone-500 mt-0.5">
                      Summaries, keywords, and references — all traceable.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <p className="text-xs text-stone-400 anim-d5">
              Private & self-hosted. Your data never leaves your control.
            </p>
          </div>
        </div>

        {/* Right side - Login form */}
        <div className="flex flex-1 flex-col bg-white lg:w-1/2">
          {/* Content aligned to the left (toward center) */}
          <div className="flex flex-1 flex-col justify-center w-full max-w-md mr-auto py-10 pr-8 pl-12 max-lg:mx-auto max-lg:px-6">
            <div className="mb-7 text-center lg:text-left anim-fade-up">
              <div className="flex items-center gap-2 mb-5 lg:hidden justify-center">
                <div className="rounded-lg bg-stone-900 p-1.5">
                  <FileText size={16} className="text-white" />
                </div>
                <span className="text-xl font-bold text-stone-900">DocChat</span>
              </div>
              <h2 className="text-2xl font-semibold text-stone-900">
                {isRegister ? "Create account" : "Welcome back"}
              </h2>
              <p className="mt-1 text-sm text-stone-500">
                {isRegister
                  ? "Get started with your document assistant"
                  : "Sign in to your notebooks"}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="anim-d1">
                <label className="block text-sm font-medium text-stone-700 mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="your username"
                  className="w-full rounded-lg border border-stone-300 bg-white px-3.5 py-2.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-900 focus:border-transparent transition"
                  required
                />
              </div>

              {isRegister && (
                <div className="anim-fade-up">
                  <label className="block text-sm font-medium text-stone-700 mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-lg border border-stone-300 bg-white px-3.5 py-2.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-900 focus:border-transparent transition"
                    required
                  />
                </div>
              )}

              <div className="anim-d2">
                <label className="block text-sm font-medium text-stone-700 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••"
                  className="w-full rounded-lg border border-stone-300 bg-white px-3.5 py-2.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-900 focus:border-transparent transition"
                  required
                  minLength={6}
                />
              </div>

              {error && (
                <div className="rounded-lg bg-red-50 border border-red-200 px-3.5 py-2.5 text-sm text-red-600">
                  {error}
                </div>
              )}

              <div className="anim-d3">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-stone-800 active:bg-stone-950 disabled:opacity-50 transition-all flex items-center justify-center gap-2 hover:shadow-md mt-1"
                >
                  {loading ? (
                    <><Loader2 size={16} className="animate-spin" /> Processing...</>
                  ) : isRegister ? (
                    <>Create account <ArrowRight size={16} /></>
                  ) : (
                    <>Sign in <ArrowRight size={16} /></>
                  )}
                </button>
              </div>
            </form>

            <div className="mt-5 text-center anim-d4">
              <p className="text-sm text-stone-500">
                {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
                <button
                  onClick={() => {
                    setIsRegister(!isRegister);
                    setError("");
                  }}
                  className="text-stone-900 font-medium hover:underline"
                >
                  {isRegister ? "Sign in" : "Create one"}
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
