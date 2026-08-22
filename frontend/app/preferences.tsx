import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState, useMemo } from "react";
import { ScrollView, StyleSheet, Switch, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import { CANTONS } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

const CATEGORIES = ["Animals", "Culture", "Playgrounds", "Water", "Nature", "Workshops", "Festivals"];
const AGE_PRESETS: [number, number, string][] = [
  [0, 3, "0-3"],
  [4, 6, "4-6"],
  [7, 12, "7-12"],
  [0, 12, "All"],
];

export default function Preferences() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { preferences, setPreferences, lang } = useApp();
  const [prefs, setPrefs] = useState(preferences);

  const toggleCanton = (c: string) =>
    setPrefs((p) => ({
      ...p,
      favoriteCantons: p.favoriteCantons.includes(c)
        ? p.favoriteCantons.filter((x) => x !== c)
        : [...p.favoriteCantons, c],
    }));

  const toggleCategory = (c: string) =>
    setPrefs((p) => ({
      ...p,
      favoriteCategories: p.favoriteCategories.includes(c)
        ? p.favoriteCategories.filter((x) => x !== c)
        : [...p.favoriteCategories, c],
    }));

  const save = () => {
    setPreferences(prefs);
    router.back();
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="prefs-back">
          <Ionicons name="chevron-back" size={20} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>{t("preferencesTitle", lang)}</Text>
        <TouchableOpacity onPress={save} style={styles.saveBtn} testID="prefs-save">
          <Text style={styles.saveTxt}>{t("save", lang)}</Text>
        </TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Section title={t("ageRange", lang)} styles={styles}>
          <View style={styles.chips}>
            {AGE_PRESETS.map(([min, max, label]) => {
              const active = prefs.ageRange[0] === min && prefs.ageRange[1] === max;
              return (
                <TouchableOpacity
                  key={label}
                  onPress={() => setPrefs({ ...prefs, ageRange: [min, max] })}
                  style={[styles.chip, active && styles.chipActive]}
                  testID={`prefs-age-${label}`}
                >
                  <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Section>

        <Section title={t("favouriteCantons", lang)} styles={styles}>
          <View style={styles.chips}>
            {CANTONS.map((c) => {
              const active = prefs.favoriteCantons.includes(c);
              return (
                <TouchableOpacity
                  key={c}
                  onPress={() => toggleCanton(c)}
                  style={[styles.chip, active && styles.chipActive]}
                  testID={`prefs-canton-${c}`}
                >
                  <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{c}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Section>

        <Section title={t("favouriteCategories", lang)} styles={styles}>
          <View style={styles.chips}>
            {CATEGORIES.map((c) => {
              const active = prefs.favoriteCategories.includes(c);
              return (
                <TouchableOpacity
                  key={c}
                  onPress={() => toggleCategory(c)}
                  style={[styles.chip, active && styles.chipActive]}
                  testID={`prefs-cat-${c}`}
                >
                  <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{c}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Section>

        <Section title={t("notifications", lang)} styles={styles}>
          <View style={styles.row}>
            <Text style={styles.rowTxt}>{t("notifyOnMatch", lang)}</Text>
            <Switch
              value={prefs.notifyOnNew}
              onValueChange={(v) => setPrefs({ ...prefs, notifyOnNew: v })}
              trackColor={{ true: palette.primary, false: palette.border }}
              testID="prefs-notify"
            />
          </View>
          <Text style={styles.hint}>
            {t("notifyBuildHint", lang)}
          </Text>
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

type Styles = ReturnType<typeof makeStyles>;

function Section({
  title,
  styles,
  children,
}: {
  title: string;
  styles: Styles;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  topbar: {
    paddingHorizontal: 18,
    paddingVertical: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surface,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  iconBtn: { width: 38, height: 38, borderRadius: 19, justifyContent: "center", alignItems: "center" },
  h1: { flex: 1, fontSize: 18, fontWeight: "800", color: palette.textPrimary },
  saveBtn: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999, backgroundColor: palette.primary },
  saveTxt: { color: "#fff", fontWeight: "700" },
  scroll: { padding: 20, gap: 18 },
  section: { backgroundColor: palette.surface, padding: 18, borderRadius: radii.lg, ...shadow.soft, gap: 12 },
  sectionTitle: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    backgroundColor: palette.surface,
  },
  chipActive: { backgroundColor: palette.primary, borderColor: palette.primary },
  chipTxt: { fontSize: 12, fontWeight: "600", color: palette.textSecondary },
  chipTxtActive: { color: "#fff" },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  rowTxt: { flex: 1, fontSize: 13, color: palette.textPrimary },
  hint: { fontSize: 11, color: palette.textMuted, lineHeight: 16 },
});
