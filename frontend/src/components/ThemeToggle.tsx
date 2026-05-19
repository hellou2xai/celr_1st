import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "celr_theme";

type Theme = "light" | "dark";

function read(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return "light";
}

function apply(theme: Theme) {
  const cls = document.documentElement.classList;
  if (theme === "dark") cls.add("dark");
  else cls.remove("dark");
}

// Apply early so first paint has the right theme.
if (typeof window !== "undefined") apply(read());

export function ThemeToggle({ collapsed }: { collapsed?: boolean }) {
  const [theme, setTheme] = useState<Theme>(() => read());

  useEffect(() => {
    apply(theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      onClick={() => setTheme(next)}
      className={cn(
        "flex items-center gap-2 text-xs text-muted hover:text-fg",
        collapsed ? "justify-center w-full" : "px-1"
      )}
      title={`Switch to ${next} mode`}
      aria-label={`Switch to ${next} mode`}
    >
      {theme === "dark" ? <Sun className="h-4 w-4"/> : <Moon className="h-4 w-4"/>}
      {!collapsed && <span>{theme === "dark" ? "Light" : "Dark"}</span>}
    </button>
  );
}
