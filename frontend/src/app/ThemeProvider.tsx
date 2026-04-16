"use client";

import { useEffect } from "react";
import { useThemeStore } from "@/lib/store";

export default function ThemeProvider() {
  const theme = useThemeStore((s) => s.theme);
  const initializeTheme = useThemeStore((s) => s.initializeTheme);

  useEffect(() => {
    // Sync Zustand with the value that layout bootstrapped from localStorage.
    initializeTheme();
  }, [initializeTheme]);

  useEffect(() => {
    // Re-apply the class when the user toggles between light and dark mode.
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  return null;
}
