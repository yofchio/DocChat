import { create } from "zustand";
import { authAPI } from "./api";

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
