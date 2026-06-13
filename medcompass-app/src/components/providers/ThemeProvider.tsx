"use client";

import * as React from "react";

type Theme = "dark" | "light" | "system";

type ThemeProviderProps = {
  children: React.ReactNode;
  attribute?: string;
  defaultTheme?: Theme;
  enableSystem?: boolean;
};

const ThemeContext = React.createContext<{
  theme: Theme;
  setTheme: (t: Theme) => void;
  resolved: "dark" | "light";
} | null>(null);

export function ThemeProvider({
  children,
  attribute = "class",
  defaultTheme = "light",
  enableSystem = true,
}: ThemeProviderProps) {
  const [theme, setThemeState] = React.useState<Theme>(defaultTheme);
  const [resolved, setResolved] = React.useState<"dark" | "light">("light");

  React.useEffect(() => {
    const root = document.documentElement;
    const resolvedTheme =
      theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : theme;
    setResolved(resolvedTheme);
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
    try {
      localStorage.setItem("medcompass-theme", theme);
    } catch {}
  }, [theme]);

  React.useEffect(() => {
    const stored = localStorage.getItem("medcompass-theme") as Theme | null;
    if (stored && ["dark", "light", "system"].includes(stored)) setThemeState(stored);
  }, []);

  const setTheme = React.useCallback((t: Theme) => setThemeState(t), []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolved }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = React.useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
