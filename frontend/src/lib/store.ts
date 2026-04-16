import { create } from "zustand";
import { authAPI } from "./api";

interface ThemeState {
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
  initializeTheme: () => void;
  toggleTheme: () => void;
}

// Keep theme application in one place so layout bootstrapping and store updates
// always manipulate the same `html.dark` class.
function applyTheme(theme: "light" | "dark") {
  if (typeof document !== "undefined") {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: "light",
  setTheme: (theme) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("theme", theme);
    }
    applyTheme(theme);
    set({ theme });
  },
  initializeTheme: () => {
    if (typeof window === "undefined") {
      return;
    }
    // Restore the persisted preference on first client render.
    const savedTheme = window.localStorage.getItem("theme");
    const theme = savedTheme === "dark" ? "dark" : "light";
    applyTheme(theme);
    set({ theme });
  },
  toggleTheme: () => {
    const nextTheme = get().theme === "dark" ? "light" : "dark";
    get().setTheme(nextTheme);
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
  token: typeof window !== "undefined" ? window.localStorage.getItem("token") : null,
  loading: true,

  setAuth: (user, token) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("token", token);
    }
    set({ user, token, loading: false });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("token");
    }
    set({ user: null, token: null, loading: false });
    if (typeof window !== "undefined") {
      // Centralize the post-logout redirect so 401 handlers and manual logout
      // leave the app in the same state.
      window.location.href = "/login";
    }
  },

  checkAuth: async () => {
    if (typeof window === "undefined") {
      set({ loading: false });
      return;
    }
    const token = window.localStorage.getItem("token");
    if (!token) {
      set({ user: null, token: null, loading: false });
      return;
    }
    try {
      // Validate the persisted token by resolving the current user profile.
      const res = await authAPI.me();
      set({ user: res.data, token, loading: false });
    } catch {
      window.localStorage.removeItem("token");
      set({ user: null, token: null, loading: false });
    }
  },
}));
