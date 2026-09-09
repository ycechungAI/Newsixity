/**
 * Theme context and hook.
 *
 * Kept separate from ThemeProvider so that file only exports components,
 * which is what React Fast Refresh requires — a file mixing component and
 * non-component exports loses hot reloading for everything in it.
 * Mirrors the split in src/lib/video/playerContext.ts.
 */

import { createContext, useContext } from "react";

export type Theme = "light" | "dark";

export interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextType>({
  theme: "dark",
  toggleTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}
