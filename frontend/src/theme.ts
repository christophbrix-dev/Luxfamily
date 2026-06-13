// Single source of truth for design tokens (colour, spacing, type scale).
// Mirrors /app/design_guidelines.json.

export const palette = {
  background: "#F7F8FA",
  backgroundAlt: "#EEF2F7",
  surface: "#FFFFFF",
  surfaceMuted: "#F1F5F9",
  primary: "#10B981",
  primaryDark: "#059669",
  primaryLight: "#D1FAE5",
  textPrimary: "#0F172A",
  textSecondary: "#64748B",
  textMuted: "#94A3B8",
  border: "#E5E7EB",
  borderSoft: "#F1F5F9",
  amber: "#F59E0B",
  amberSoft: "#FEF3C7",
  red: "#EF4444",
  shadow: "rgba(15, 23, 42, 0.08)",
  shadowStrong: "rgba(15, 23, 42, 0.16)",
};

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
    shadowColor: "#0F172A",
    shadowOpacity: 0.08,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 },
    elevation: 4,
  },
  soft: {
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  emerald: {
    shadowColor: "#10B981",
    shadowOpacity: 0.35,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },
};
