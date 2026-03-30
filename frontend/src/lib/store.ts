import { create } from "zustand";
import { authAPI } from "./api";

// Theme store — persists the user's dark/light preference in localStorage
interface ThemeState {
  theme: "light" | "dark";
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  // Read saved preference on init, default to light
  theme:
    typeof window !== "undefined"
      ? (localStorage.getItem("theme") as "light" | "dark") ?? "light"
      : "light",

  toggleTheme: () => {
    const next = get().theme === "light" ? "dark" : "light";
    localStorage.setItem("theme", next);
    // Apply/remove the .dark class on <html> immediately
    document.documentElement.classList.toggle("dark", next === "dark");
    set({ theme: next });
  },
}));

interface User {
  id: string;
  username: string;
  email: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token:
    typeof window !== "undefined" ? localStorage.getItem("token") : null,
  loading: true,

  setAuth: (user, token) => {
    localStorage.setItem("token", token);
    set({ user, token, loading: false });
  },

  logout: () => {
    localStorage.removeItem("token");
    set({ user: null, token: null, loading: false });
    window.location.href = "/login";
  },

  checkAuth: async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      set({ loading: false });
      return;
    }
    try {
      const res = await authAPI.me();
      set({ user: res.data, token, loading: false });
    } catch {
      localStorage.removeItem("token");
      set({ user: null, token: null, loading: false });
    }
  },
}));