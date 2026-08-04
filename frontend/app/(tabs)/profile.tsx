import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import type { Lang } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { palette, radii, shadow } from "@/src/theme";

const LANGS: { code: Lang; label: string; flag: string }[] = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
];

export default function Profile() {
  const router = useRouter();
  const { lang, setLang, user, signOutUser, bookings, saved, theme, setTheme, userProfile, resetOnboarding } = useApp();
  const initial = (user?.name?.[0] ?? "U").toUpperCase();

  const personaLabel = (() => {
    if (userProfile.persona === "skipped") return "Not set";
    if (!userProfile.persona) return "Not set";
    // Look up the human label from PERSONAS data.
    // Avoid a top-of-file import cycle by requiring inline.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { PERSONAS } = require("@/src/data/onboarding") as typeof import("@/src/data/onboarding");
    const p = PERSONAS.find((x) => x.id === userProfile.persona);
    return p?.labels[lang] ?? "Not set";
  })();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.h1}>{t("profile", lang)}</Text>

        <View style={styles.userCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarTxt}>{initial}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.userName}>{user?.name ?? t("myAccount", lang)}</Text>
            <Text style={styles.userSub}>{user?.email ?? t("familyInLuxembourg", lang)}</Text>
          </View>
        </View>

        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Text style={styles.statVal}>{saved.length}</Text>
            <Text style={styles.statLabel}>{t("saved", lang)}</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.stat}>
            <Text style={styles.statVal}>{bookings.length}</Text>
            <Text style={styles.statLabel}>{t("yourBooking", lang)}</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.stat}>
            <Text style={styles.statVal}>3</Text>
            <Text style={styles.statLabel}>{t("itineraries", lang)}</Text>
          </View>
        </View>

        <Text style={styles.sectionLabel}>{t("language", lang)}</Text>
        <View style={styles.langCard}>
          {LANGS.map((l) => (
            <TouchableOpacity
              key={l.code}
              onPress={() => setLang(l.code)}
              style={[styles.langRow, lang === l.code && styles.langRowActive]}
              testID={`profile-lang-${l.code}`}
            >
              <Text style={styles.langFlag}>{l.flag}</Text>
              <Text style={styles.langLabel}>{l.label}</Text>
              <View style={{ flex: 1 }} />
              {lang === l.code ? (
                <Ionicons name="checkmark-circle" size={22} color={palette.primary} />
              ) : (
                <Ionicons name="ellipse-outline" size={22} color={palette.border} />
              )}
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.sectionLabel}>Settings</Text>
        <View style={styles.settingsCard}>
          <TouchableOpacity
            style={styles.settingsRow}
            onPress={() => {
              resetOnboarding();
              router.push("/onboarding" as never);
            }}
            testID="profile-row-personalization"
          >
            <View style={styles.settingsIcon}>
              <Ionicons name="sparkles-outline" size={18} color={palette.primary} />
            </View>
            <Text style={styles.settingsTxt}>Personalization</Text>
            <View style={{ flex: 1 }} />
            <Text style={{ fontSize: 11, color: palette.textMuted, marginRight: 8 }}>
              {personaLabel}
            </Text>
            <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
          </TouchableOpacity>
          {[
            { icon: "options-outline" as const, label: t("preferencesFilters", lang), to: "/preferences" },
            { icon: "business-outline" as const, label: "For businesses", to: "/business" },
            { icon: "information-circle-outline" as const, label: "About", to: "/about" },
            { icon: "card-outline" as const, label: t("subscription", lang), to: null, hint: "Coming soon" },
          ].map((row) => (
            <TouchableOpacity
              key={row.label}
              style={styles.settingsRow}
              onPress={() => row.to && router.push(row.to as never)}
              disabled={!row.to}
              testID={`profile-row-${row.label.toLowerCase().replace(/\s+/g, "-")}`}
            >
              <View style={styles.settingsIcon}>
                <Ionicons name={row.icon} size={18} color={palette.primary} />
              </View>
              <Text style={styles.settingsTxt}>{row.label}</Text>
              <View style={{ flex: 1 }} />
              {row.hint ? (
                <Text style={{ fontSize: 11, color: palette.textMuted, marginRight: 8 }}>{row.hint}</Text>
              ) : null}
              <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.sectionLabel}>Appearance</Text>
        <View style={styles.langCard}>
          {(["light", "dark", "system"] as const).map((mode, idx) => (
            <TouchableOpacity
              key={mode}
              onPress={() => setTheme(mode)}
              style={[styles.langRow, theme === mode && styles.langRowActive, idx === 2 && { borderBottomWidth: 0 }]}
              testID={`profile-theme-${mode}`}
            >
              <Ionicons
                name={mode === "light" ? "sunny-outline" : mode === "dark" ? "moon-outline" : "phone-portrait-outline"}
                size={20}
                color={palette.primary}
              />
              <Text style={styles.langLabel}>
                {mode === "light" ? "Light" : mode === "dark" ? "Dark (Beta)" : "System"}
              </Text>
              <View style={{ flex: 1 }} />
              {theme === mode ? (
                <Ionicons name="checkmark-circle" size={22} color={palette.primary} />
              ) : (
                <Ionicons name="ellipse-outline" size={22} color={palette.border} />
              )}
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          onPress={() => {
            signOutUser();
            router.replace("/login");
          }}
          style={styles.signOutBtn}
          testID="sign-out-btn"
        >
          <Ionicons name="log-out-outline" size={18} color={palette.red} />
          <Text style={styles.signOutTxt}>{t("signOut", lang)}</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  scroll: { padding: 20, paddingBottom: 36 },
  h1: { fontSize: 30, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  userCard: {
    marginTop: 18,
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    padding: 18,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    ...shadow.soft,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  avatarTxt: { color: palette.primaryDark, fontWeight: "800", fontSize: 22 },
  userName: { fontSize: 17, fontWeight: "700", color: palette.textPrimary },
  userSub: { fontSize: 13, color: palette.textSecondary, marginTop: 2 },
  statsRow: {
    marginTop: 14,
    flexDirection: "row",
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "space-around",
    ...shadow.soft,
  },
  stat: { alignItems: "center", flex: 1 },
  statVal: { fontSize: 22, fontWeight: "800", color: palette.textPrimary },
  statLabel: { fontSize: 11, color: palette.textSecondary, marginTop: 2 },
  statDivider: { width: 1, height: 32, backgroundColor: palette.borderSoft },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: palette.textSecondary,
    marginTop: 24,
    marginBottom: 10,
    paddingLeft: 4,
  },
  langCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    overflow: "hidden",
    ...shadow.soft,
  },
  langRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  langRowActive: { backgroundColor: palette.primaryLight + "55" },
  langFlag: { fontSize: 22 },
  langLabel: { fontSize: 15, fontWeight: "600", color: palette.textPrimary },
  settingsCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    overflow: "hidden",
    ...shadow.soft,
  },
  settingsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  settingsIcon: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  settingsTxt: { fontSize: 14, fontWeight: "600", color: palette.textPrimary },
  signOutBtn: {
    marginTop: 28,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
    paddingVertical: 14,
  },
  signOutTxt: { color: palette.red, fontWeight: "700", fontSize: 14 },
});
