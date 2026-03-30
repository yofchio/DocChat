"use client";

import { useEffect } from "react";
import { useThemeStore } from "@/lib/store";

// Applies the saved theme class to <html> on first render.
// Runs client-side only, so there's no SSR mismatch.
export default function ThemeProvider() {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  return null;
}