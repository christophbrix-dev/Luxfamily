// Single source of truth for design tokens (colour, spacing, type scale).
// Mirrors /app/design_guidelines.json.
//
// Palettes are exported both as static values (LIGHT_PALETTE / DARK_PALETTE)
// AND as a `palette` alias that resolves to LIGHT — this keeps *existing*
// `import { palette } from "@/src/theme"` call sites working while allowing
// gradually migrated screens to consume the runtime palette via
// `useAppPalette()` (see /src/hooks/useAppPalette.ts).

import { accentById, DEFAULT_ACCENT, shadesFor } from "@/src/accents";

export type Palette = {
  background: string;
  backgroundAlt: string;
  surface: string;
  surfaceMuted: string;
  primary: string;
  primaryDark: string;
  primaryLight: string;
  primarySoft: string;
  primaryBorder: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  border: string;
  borderSoft: string;
  amber: string;
  amberSoft: string;
  red: string;
  shadow: string;
  shadowStrong: string;
};

/**
 * A palette with the accent still to be filled in.
 *
 * Everything that is not the accent — grounds, text, borders, the semantic
 * red and amber — is fixed. Only `primary`, `primaryDark` and `primaryLight`
 * follow the reader's choice, because those are the three the accent owns.
 * Letting a choice move `red` would take "something went wrong" with it.
 */
type Neutrals = Omit<Palette,
  "primary" | "primaryDark" | "primaryLight" | "primarySoft" | "primaryBorder">;

const LIGHT_NEUTRALS: Neutrals = {
  background:    "#F7F8FA",
  backgroundAlt: "#EEF2F7",
  surface:       "#FFFFFF",
  surfaceMuted:  "#F1F5F9",
  textPrimary:   "#0F172A",
  textSecondary: "#64748B",
  textMuted:     "#94A3B8",
  border:        "#E5E7EB",
  borderSoft:    "#F1F5F9",
  amber:         "#F59E0B",
  amberSoft:     "#FEF3C7",
  red:           "#EF4444",
  shadow:        "rgba(15, 23, 42, 0.08)",
  shadowStrong:  "rgba(15, 23, 42, 0.16)",
};

// Dark palette tuned for a family app — high contrast on charcoal, keeps
// the emerald brand hue but drops saturation on surfaces to reduce glare.
const DARK_NEUTRALS: Neutrals = {
  background:    "#0B1120",   // near-black navy
  backgroundAlt: "#111827",
  surface:       "#1F2937",   // slate-800
  surfaceMuted:  "#111827",   // slate-900
  textPrimary:   "#F1F5F9",   // slate-100
  textSecondary: "#CBD5E1",   // slate-300
  textMuted:     "#94A3B8",   // slate-400
  border:        "#334155",   // slate-700
  borderSoft:    "#1E293B",   // slate-800
  amber:         "#FBBF24",
  amberSoft:     "#78350F",
  red:           "#F87171",
  shadow:        "rgba(0, 0, 0, 0.55)",
  shadowStrong:  "rgba(0, 0, 0, 0.75)",
};

/** The palette for one accent in one mode. */
export function paletteFor(accentId: string, mode: "light" | "dark"): Palette {
  const { hue } = accentById(accentId);
  const neutrals = mode === "dark" ? DARK_NEUTRALS : LIGHT_NEUTRALS;
  return { ...neutrals, ...shadesFor(hue, mode) };
}

// The two that most of the app asks for. Built from the default accent, so a
// screen that has not been told about the reader's choice still gets a palette
// that passes the contrast test rather than the old #10B981.
export const LIGHT_PALETTE: Palette = paletteFor(DEFAULT_ACCENT, "light");
export const DARK_PALETTE: Palette = paletteFor(DEFAULT_ACCENT, "dark");

// Legacy static export — always the LIGHT palette so screens that still
// import { palette } behave identically to before.  Migrated screens
// should call `useAppPalette()` instead.
export const palette: Palette = LIGHT_PALETTE;

export const radii = {
  sm: 12,
  md: 18,
  lg: 24,
  xl: 28,
  xxl: 32,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const shadow = {
  card: {
    boxShadow: "0px 12px 24px rgba(15, 23, 42, 0.08)",
    elevation: 4,
  },
  soft: {
    boxShadow: "0px 4px 12px rgba(15, 23, 42, 0.05)",
    elevation: 2,
  },
  emerald: {
    boxShadow: "0px 10px 20px rgba(16, 185, 129, 0.35)",
    elevation: 6,
  },
};

// Shadow-set adapted for dark surfaces — the light-mode boxShadow disappears
// against a dark background, so migrated screens can pull `shadowFor(effective)`
// to get a palette-appropriate pair.
export function shadowFor(mode: "light" | "dark") {
  if (mode === "dark") {
    return {
      card: {
        boxShadow: "0px 12px 24px rgba(0, 0, 0, 0.55)",
        elevation: 4,
      },
      soft: {
        boxShadow: "0px 4px 12px rgba(0, 0, 0, 0.35)",
        elevation: 2,
      },
      emerald: {
        boxShadow: "0px 10px 20px rgba(16, 185, 129, 0.55)",
        elevation: 6,
      },
    };
  }
  return shadow;
}
