"use client";

import { useState, useEffect } from "react";

import { ThemeContext, type Theme } from "@/lib/theme/themeContext";

const THEME_KEY = "newsixity-theme";
const THEME_USER_SELECTED_KEY = "newsixity-theme-user-selected";

export default function ThemeProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "dark";
    const saved = localStorage.getItem(THEME_KEY) as Theme | null;
    // Earlier releases always persisted the system-derived choice, even when
    // a person never chose a theme. Only retain a value after an explicit
    // toggle so existing Windows installs also adopt the new dark default.
    if (localStorage.getItem(THEME_USER_SELECTED_KEY) === "1" && (saved === "dark" || saved === "light")) {
      return saved;
    }
    // The desktop app should be comfortable on first launch regardless of
    // the Windows system preference. A user's explicit later choice is still
    // respected through the stored setting above.
    return "dark";
  });
  // Apply dark class to <html>
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.classList.toggle("light", theme === "light");
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  function toggleTheme() {
    localStorage.setItem(THEME_USER_SELECTED_KEY, "1");
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
