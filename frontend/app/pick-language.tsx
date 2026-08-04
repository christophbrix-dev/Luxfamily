/**
 * First-run language picker. Shown on cold-start before login/onboarding
 * when the user has never chosen a language.  Once a language is confirmed
 * we persist it and route to /login.
 */
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import type { Lang } from "@/src/data/places";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { radii, type Palette, shadowFor } from "@/src/theme";

type Option = {
  code: Lang;
  native: string;   // language name in that language
  english: string;  // English name (so users always understand)
  flag: string;
  hello: string;    // greeting in that language for a friendly touch
};

// Ordering — put Luxembourgish first ("Wat Elo?" is a Luxembourgish app after
// all), then the country's official languages (DE, FR), then English.
const LANGS: Option[] = [
  { code: "lb", native: "Lëtzebuergesch", english: "Luxembourgish", flag: "🇱🇺", hello: "Moien!"      },
  { code: "de", native: "Deutsch",         english: "German",       flag: "🇩🇪", hello: "Hallo!"       },
  { code: "fr", native: "Français",        english: "French",       flag: "🇫🇷", hello: "Bonjour !"    },
  { code: "en", native: "English",         english: "English",      flag: "🇬🇧", hello: "Hello!"       },
];

export default function PickLanguage() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { setLang, markLangPicked } = useApp();
  const [selected, setSelected] = useState<Lang>("lb");

  const onConfirm = () => {
    setLang(selected);
    markLangPicked();
    router.replace("/login");
  };

  return (
    <SafeAreaView style={styles.safe}>
      <LinearGradient
        colors={["#10B981", "#059669", "#065F46"]}
        style={styles.hero}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      >
        <Text style={styles.wave}>👋</Text>
        <Text style={styles.brand}>Wat Elo?</Text>
        <Text style={styles.tagline}>
          Family Luxembourg
        </Text>
      </LinearGradient>

      <View style={styles.card}>
        <Text style={styles.title}>Choose your language</Text>
        <Text style={styles.sub}>
          Wielt är Sprooch · Wähle deine Sprache · Choisissez votre langue
        </Text>

        <View style={styles.list}>
          {LANGS.map((opt) => {
            const isActive = selected === opt.code;
            return (
              <TouchableOpacity
                key={opt.code}
                onPress={() => setSelected(opt.code)}
                activeOpacity={0.85}
                style={[styles.row, isActive && styles.rowActive]}
                testID={`lang-pick-${opt.code}`}
              >
                <Text style={styles.flag}>{opt.flag}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.native, isActive && styles.nativeActive]}>
                    {opt.native}
                  </Text>
                  <Text style={[styles.english, isActive && styles.englishActive]}>
                    {opt.english} · {opt.hello}
                  </Text>
                </View>
                {isActive ? (
                  <View style={styles.check}>
                    <Ionicons name="checkmark" size={16} color="#FFFFFF" />
                  </View>
                ) : (
                  <View style={styles.dot} />
                )}
              </TouchableOpacity>
            );
          })}
        </View>

        <TouchableOpacity onPress={onConfirm} style={styles.cta} testID="lang-continue">
          <Text style={styles.ctaTxt}>Continue</Text>
          <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const makeStyles = (
  palette: Palette,
  shadow: ReturnType<typeof shadowFor>,
) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: palette.background },
    hero: {
      paddingTop: 24,
      paddingBottom: 40,
      alignItems: "center",
      justifyContent: "center",
      borderBottomLeftRadius: 32,
      borderBottomRightRadius: 32,
    },
    wave: { fontSize: 44, marginBottom: 8 },
    brand: {
      fontSize: 34,
      fontWeight: "800",
      color: "#FFFFFF",
      letterSpacing: -1,
    },
    tagline: {
      fontSize: 14,
      color: "rgba(255,255,255,0.85)",
      marginTop: 4,
      letterSpacing: 1.5,
      textTransform: "uppercase",
      fontWeight: "600",
    },
    card: {
      marginTop: -20,
      marginHorizontal: 20,
      backgroundColor: palette.surface,
      borderRadius: radii.xxl,
      padding: 24,
      ...shadow.card,
      flex: 1,
    },
    title: {
      fontSize: 22,
      fontWeight: "800",
      color: palette.textPrimary,
      textAlign: "center",
    },
    sub: {
      fontSize: 12,
      color: palette.textMuted,
      textAlign: "center",
      marginTop: 6,
      marginBottom: 20,
      lineHeight: 18,
    },
    list: { gap: 10 },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: 14,
      paddingVertical: 14,
      paddingHorizontal: 14,
      borderRadius: radii.md,
      backgroundColor: palette.surfaceMuted,
      borderWidth: 2,
      borderColor: "transparent",
    },
    rowActive: {
      backgroundColor: palette.primaryLight,
      borderColor: palette.primary,
    },
    flag: { fontSize: 32 },
    native: { fontSize: 16, fontWeight: "700", color: palette.textPrimary },
    nativeActive: { color: palette.primaryDark },
    english: { fontSize: 12, color: palette.textMuted, marginTop: 2 },
    englishActive: { color: palette.primaryDark, opacity: 0.85 },
    dot: {
      width: 22,
      height: 22,
      borderRadius: 999,
      borderWidth: 2,
      borderColor: palette.border,
    },
    check: {
      width: 22,
      height: 22,
      borderRadius: 999,
      backgroundColor: palette.primary,
      justifyContent: "center",
      alignItems: "center",
    },
    cta: {
      marginTop: 20,
      backgroundColor: palette.primary,
      borderRadius: radii.md,
      paddingVertical: 16,
      flexDirection: "row",
      justifyContent: "center",
      alignItems: "center",
      gap: 10,
      ...shadow.emerald,
    },
    ctaTxt: { color: "#FFFFFF", fontSize: 16, fontWeight: "700" },
  });
