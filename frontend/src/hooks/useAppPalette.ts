/**
 * Runtime theme hook — resolves the user's chosen theme mode
 * (light / dark / system) against the OS colour scheme and returns the
 * matching palette + effective mode.
 *
 * Usage:
 *   const { palette, effective, shadow } = useAppPalette();
 *   const styles = useMemo(() => makeStyles(palette), [palette]);
 */
import { useMemo } from "react";
import { useColorScheme } from "react-native";

import { useApp } from "@/src/contexts/AppContext";
import {
  DARK_PALETTE,
  LIGHT_PALETTE,
  type Palette,
  shadowFor,
} from "@/src/theme";

export type EffectiveTheme = "light" | "dark";

export function useAppPalette(): {
  palette: Palette;
  effective: EffectiveTheme;
  shadow: ReturnType<typeof shadowFor>;
} {
  const { theme } = useApp();
  const sys = useColorScheme();
  const effective: EffectiveTheme =
    theme === "system" ? (sys === "dark" ? "dark" : "light") : theme;
  const palette = effective === "dark" ? DARK_PALETTE : LIGHT_PALETTE;
  const shadow  = useMemo(() => shadowFor(effective), [effective]);
  return { palette, effective, shadow };
}
