/**
 * Runtime theme hook — resolves the reader's chosen theme mode
 * (light / dark / system) against the OS colour scheme, and their chosen
 * accent, into one palette.
 *
 * Usage:
 *   const { palette, effective, shadow } = useAppPalette();
 *   const styles = useMemo(() => makeStyles(palette), [palette]);
 */
import { useMemo } from "react";
import { useColorScheme } from "react-native";

import { useApp } from "@/src/contexts/AppContext";
import { type Palette, paletteFor, shadowFor } from "@/src/theme";

export type EffectiveTheme = "light" | "dark";

export function useAppPalette(): {
  palette: Palette;
  effective: EffectiveTheme;
  shadow: ReturnType<typeof shadowFor>;
} {
  const { theme, accent } = useApp();
  const sys = useColorScheme();
  const effective: EffectiveTheme =
    theme === "system" ? (sys === "dark" ? "dark" : "light") : theme;
  // Built rather than looked up: the shades come out of the accent's hue, so
  // a palette exists for every accent without anybody typing one.
  const palette = useMemo(() => paletteFor(accent, effective), [accent, effective]);
  const shadow  = useMemo(() => shadowFor(effective), [effective]);
  return { palette, effective, shadow };
}
