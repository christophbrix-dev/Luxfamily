import { Ionicons } from "@expo/vector-icons";
import * as Application from "expo-application";
import { useRouter } from "expo-router";
import React from "react";
import { Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { palette, radii, shadow } from "@/src/theme";

const ROWS: { icon: keyof typeof import("@expo/vector-icons").Ionicons.glyphMap; label: string; url?: string; sub?: string }[] = [
  { icon: "document-text-outline", label: "Privacy policy", url: "https://familyluxembourg.lu/privacy" },
  { icon: "shield-checkmark-outline", label: "Terms of service", url: "https://familyluxembourg.lu/terms" },
  { icon: "mail-outline", label: "Contact us", url: "mailto:hello@familyluxembourg.lu" },
  { icon: "logo-instagram", label: "Follow on Instagram", url: "https://instagram.com/familyluxembourg" },
  { icon: "logo-facebook", label: "Follow on Facebook", url: "https://facebook.com/familyluxembourg" },
];

export default function About() {
  const router = useRouter();
  const version = Application.nativeApplicationVersion ?? "1.0.0";
  const build = Application.nativeBuildVersion ?? "1";

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="about-back">
          <Ionicons name="chevron-back" size={20} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>About</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.hero}>
          <View style={styles.logo}>
            <Ionicons name="sparkles" size={32} color="#fff" />
          </View>
          <Text style={styles.appName}>Wat Elo?</Text>
          <Text style={styles.tagline}>Discover places, events and workshops curated for your kids.</Text>
          <View style={styles.versionPill}>
            <Text style={styles.versionTxt}>v{version} ({build})</Text>
          </View>
        </View>

        <View style={styles.card}>
          {ROWS.map((row, idx) => (
            <TouchableOpacity
              key={row.label}
              onPress={() => row.url && Linking.openURL(row.url)}
              style={[styles.row, idx < ROWS.length - 1 && styles.rowDivider]}
              testID={`about-${row.label.toLowerCase().replace(/\s+/g, "-")}`}
            >
              <View style={styles.rowIcon}>
                <Ionicons name={row.icon} size={18} color={palette.primary} />
              </View>
              <Text style={styles.rowTxt}>{row.label}</Text>
              <Ionicons name="open-outline" size={16} color={palette.textMuted} />
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.footer}>
          Made with love in Luxembourg. {"\n"}© 2026 Wat Elo?.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
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
  scroll: { padding: 20, gap: 18 },
  hero: { alignItems: "center", padding: 28, gap: 8 },
  logo: {
    width: 80,
    height: 80,
    borderRadius: 22,
    backgroundColor: palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...shadow.emerald,
  },
  appName: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, marginTop: 16 },
  tagline: { fontSize: 13, color: palette.textSecondary, textAlign: "center", maxWidth: 280, lineHeight: 19 },
  versionPill: {
    marginTop: 14,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: palette.surfaceMuted,
  },
  versionTxt: { fontSize: 11, fontWeight: "700", color: palette.textSecondary, letterSpacing: 0.5 },
  card: { backgroundColor: palette.surface, borderRadius: radii.lg, overflow: "hidden", ...shadow.soft },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 14, paddingHorizontal: 16 },
  rowDivider: { borderBottomWidth: 1, borderBottomColor: palette.borderSoft },
  rowIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  rowTxt: { flex: 1, fontSize: 14, fontWeight: "600", color: palette.textPrimary },
  footer: { textAlign: "center", color: palette.textMuted, fontSize: 11, lineHeight: 18, marginTop: 12 },
});
