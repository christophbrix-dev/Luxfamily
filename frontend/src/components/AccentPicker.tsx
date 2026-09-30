// Choosing the app's colour, with the app shown in it.
//
// A row of dots is a guess: nobody can tell from a 24-pixel circle what a whole
// screen will look like, and the two places that matter — a filled button and
// accent text on a card — are exactly where a colour either works or does not.
// So the preview is a real card and a real button, drawn in the colour under
// the finger, in whichever mode the reader is actually in.
//
// One component for both places it appears: the onboarding step where the
// choice is first made, and the settings screen where it is changed later.
// A picker that looked different in the two would make the second one feel
// like a different decision.

import { Ionicons } from "@expo/vector-icons";
import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ACCENTS } from "@/src/accents";
import { useApp } from "@/src/contexts/AppContext";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { t } from "@/src/i18n/strings";
import { paletteFor, radii, type Palette, shadowFor } from "@/src/theme";

type Props = {
  /** Shown above the swatches. Left out when the screen has its own heading. */
  title?: string;
  hint?: string;
};

export function AccentPicker({ title, hint }: Props) {
  const { palette, shadow, effective } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang, accent, setAccent } = useApp();

  // The preview is drawn in the mode the reader is in, not always in light:
  // somebody choosing at night should see what they will actually get.
  const preview = paletteFor(accent, effective);

  return (
    <View style={styles.wrap}>
      {title ? <Text style={styles.title}>{title}</Text> : null}
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}

      <View style={styles.swatches}>
        {ACCENTS.map((a) => {
          const shades = paletteFor(a.id, effective);
          const active = accent === a.id;
          return (
            <Pressable
              key={a.id}
              onPress={() => setAccent(a.id)}
              accessibilityRole="radio"
              accessibilityState={{ selected: active }}
              accessibilityLabel={t(a.labelKey, lang)}
              style={[styles.swatch, active && { borderColor: shades.primary }]}
              testID={`accent-${a.id}`}
            >
              <View style={[styles.dot, { backgroundColor: shades.primary }]}>
                {active ? <Ionicons name="checkmark" size={15} color="#fff" /> : null}
              </View>
              <Text style={[styles.swatchTxt, active && { color: palette.textPrimary, fontWeight: "700" }]}>
                {t(a.labelKey, lang)}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Text style={styles.previewLabel}>{t("accentPreview", lang)}</Text>
      <View style={styles.preview}>
        <View style={styles.previewCard}>
          <View style={[styles.previewBadge, { backgroundColor: preview.primaryLight }]}>
            <Text style={[styles.previewBadgeTxt, { color: preview.primaryDark }]}>
              {t("places", lang)}
            </Text>
          </View>
          <Text style={styles.previewTitle}>Spillplaatz op der Lou</Text>
          <Text style={styles.previewMeta}>0,4 km · Winseler</Text>
        </View>
        <View style={[styles.previewBtn, { backgroundColor: preview.primary }]}>
          <Text style={[styles.previewBtnTxt, { color: effective === "dark" ? "#0B1120" : "#FFFFFF" }]}>
            {t("showResults", lang)}
          </Text>
        </View>
      </View>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) =>
  StyleSheet.create({
    wrap: { gap: 14 },
    title: { fontSize: 22, fontWeight: "800", color: palette.textPrimary },
    hint: { fontSize: 14, color: palette.textSecondary, lineHeight: 20, marginTop: -8 },

    swatches: { flexDirection: "row", flexWrap: "wrap", gap: 9 },
    swatch: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingVertical: 8,
      paddingHorizontal: 12,
      borderRadius: 999,
      borderWidth: 2,
      borderColor: palette.border,
      backgroundColor: palette.surface,
    },
    dot: { width: 22, height: 22, borderRadius: 11, alignItems: "center", justifyContent: "center" },
    swatchTxt: { fontSize: 14, color: palette.textSecondary },

    previewLabel: {
      fontSize: 12,
      fontWeight: "700",
      letterSpacing: 0.6,
      textTransform: "uppercase",
      color: palette.textMuted,
      marginTop: 4,
    },
    preview: {
      gap: 10,
      padding: 14,
      borderRadius: radii.lg,
      backgroundColor: palette.backgroundAlt,
    },
    previewCard: {
      gap: 5,
      padding: 13,
      borderRadius: radii.md,
      backgroundColor: palette.surface,
      ...shadow.card,
    },
    previewBadge: { alignSelf: "flex-start", paddingHorizontal: 9, paddingVertical: 3, borderRadius: 999 },
    previewBadgeTxt: { fontSize: 12, fontWeight: "700" },
    previewTitle: { fontSize: 15, fontWeight: "700", color: palette.textPrimary },
    previewMeta: { fontSize: 12, color: palette.textSecondary },
    previewBtn: { paddingVertical: 13, borderRadius: radii.lg, alignItems: "center" },
    previewBtnTxt: { fontSize: 15, fontWeight: "700" },
  });
