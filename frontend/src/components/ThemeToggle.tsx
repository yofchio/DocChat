import { Sun, Moon } from "lucide-react";
import { useThemeStore } from "@/lib/store";
 
// A toggle button that switches between light and dark mode.
// Drop this anywhere in the UI — it reads and updates the global theme store.
export default function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore();
 
  return (
    <button
      onClick={toggleTheme}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className="p-2 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)] transition-colors"
    >
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
 