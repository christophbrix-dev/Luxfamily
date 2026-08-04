import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import React, { useState, useMemo } from "react";
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import type { Lang } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

const LANGS: { code: Lang; label: string; flag: string }[] = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
];

export default function Login() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang, setLang, signIn, signInGuest, signInWithGoogle } = useApp();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = () => {
    if (!email.trim()) return;
    signIn(email.trim().toLowerCase(), mode === "signup" ? name.trim() : undefined);
    // Onboarding gate in _layout will redirect to /onboarding if this is
    // a brand-new user; otherwise the router settles on tabs.
    router.replace("/(tabs)/home");
  };

  const skip = () => {
    signInGuest();
    router.replace("/(tabs)/home");
  };

  const doGoogle = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await signInWithGoogle();
      if (!res) return; // web navigation happened
      if (res.isNewUser) {
        router.replace("/onboarding");
      } else {
        router.replace("/(tabs)/home");
      }
    } catch (e) {
      console.warn("Google sign-in failed:", e);
    } finally {
      setBusy(false);
    }
  };

  const googleLabel = t("continueWithGoogle", lang);

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.hero}>
            <Image
              source={{
                uri: "https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=1200&q=80",
              }}
              style={styles.heroImage}
            />
            <LinearGradient
              colors={["rgba(0,0,0,0.05)", "rgba(15,23,42,0.85)"]}
              style={StyleSheet.absoluteFill}
            />
            <View style={styles.heroOverlay}>
              <View style={styles.langRow}>
                {LANGS.map((l) => (
                  <TouchableOpacity
                    key={l.code}
                    onPress={() => setLang(l.code)}
                    style={[
                      styles.langChip,
                      lang === l.code && styles.langChipActive,
                    ]}
                    testID={`lang-${l.code}`}
                  >
                    <Text style={styles.langFlag}>{l.flag}</Text>
                    <Text
                      style={[
                        styles.langLabel,
                        lang === l.code && styles.langLabelActive,
                      ]}
                    >
                      {l.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <View style={{ flex: 1 }} />
              <Text style={styles.title}>{t("welcomeTitle", lang)}</Text>
              <Text style={styles.subtitle}>{t("welcomeSub", lang)}</Text>
            </View>
          </View>

          <View style={styles.card}>
            <View style={styles.tabsRow}>
              <TouchableOpacity
                onPress={() => setMode("signin")}
                style={[styles.tab, mode === "signin" && styles.tabActive]}
                testID="tab-signin"
              >
                <Text style={[styles.tabTxt, mode === "signin" && styles.tabTxtActive]}>
                  {t("signIn", lang)}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => setMode("signup")}
                style={[styles.tab, mode === "signup" && styles.tabActive]}
                testID="tab-signup"
              >
                <Text style={[styles.tabTxt, mode === "signup" && styles.tabTxtActive]}>
                  {t("createAccount", lang)}
                </Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              onPress={doGoogle}
              disabled={busy}
              style={[styles.googleBtn, busy && { opacity: 0.6 }]}
              testID="google-btn"
              accessibilityLabel={googleLabel}
            >
              <Ionicons name="logo-google" size={18} color="#111827" />
              <Text style={styles.googleTxt}>{googleLabel}</Text>
            </TouchableOpacity>

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerTxt}>
                {t("or", lang).toLowerCase()}
              </Text>
              <View style={styles.dividerLine} />
            </View>

            {mode === "signup" ? (
              <View style={styles.field}>
                <Ionicons name="person-outline" size={18} color={palette.textSecondary} />
                <TextInput
                  placeholder={t("yourName", lang)}
                  placeholderTextColor={palette.textMuted}
                  style={styles.input}
                  value={name}
                  onChangeText={setName}
                  autoCapitalize="words"
                  testID="input-name"
                />
              </View>
            ) : null}

            <View style={styles.field}>
              <Ionicons name="mail-outline" size={18} color={palette.textSecondary} />
              <TextInput
                placeholder={t("email", lang)}
                placeholderTextColor={palette.textMuted}
                style={styles.input}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                testID="input-email"
              />
            </View>

            <View style={styles.field}>
              <Ionicons name="lock-closed-outline" size={18} color={palette.textSecondary} />
              <TextInput
                placeholder={t("password", lang)}
                placeholderTextColor={palette.textMuted}
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                testID="input-password"
              />
            </View>

            <TouchableOpacity onPress={submit} style={styles.cta} testID="continue-btn">
              <Text style={styles.ctaTxt}>{t("continueWithEmail", lang)}</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={skip} style={styles.skipBtn} testID="guest-btn">
              <Text style={styles.skipTxt}>{t("skip", lang)}</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  scroll: { flexGrow: 1 },
  hero: { height: 360, overflow: "hidden" },
  heroImage: { ...StyleSheet.absoluteFillObject, width: "100%", height: "100%" },
  heroOverlay: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 28,
  },
  langRow: { flexDirection: "row", gap: 8 },
  langChip: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.18)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
  },
  langChipActive: { backgroundColor: "#fff", borderColor: "#fff" },
  langFlag: { fontSize: 13 },
  langLabel: { fontSize: 12, fontWeight: "600", color: "#fff" },
  langLabelActive: { color: palette.textPrimary },
  title: {
    color: "#fff",
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.5,
    lineHeight: 36,
  },
  subtitle: { color: "rgba(255,255,255,0.85)", fontSize: 14, marginTop: 8, lineHeight: 20 },
  card: {
    marginTop: -28,
    marginHorizontal: 18,
    backgroundColor: palette.surface,
    borderRadius: radii.xxl,
    padding: 22,
    ...shadow.card,
  },
  tabsRow: {
    flexDirection: "row",
    backgroundColor: palette.surfaceMuted,
    padding: 4,
    borderRadius: 999,
    marginBottom: 18,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: "center",
    borderRadius: 999,
  },
  tabActive: { backgroundColor: palette.surface, ...shadow.soft },
  tabTxt: { fontSize: 13, fontWeight: "600", color: palette.textSecondary },
  tabTxtActive: { color: palette.textPrimary },
  field: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surfaceMuted,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
  },
  input: { flex: 1, fontSize: 14, color: palette.textPrimary, padding: 0 },
  cta: {
    backgroundColor: palette.primary,
    borderRadius: 16,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 6,
    ...shadow.emerald,
  },
  ctaTxt: { color: "#fff", fontSize: 15, fontWeight: "700" },
  skipBtn: { paddingVertical: 14, alignItems: "center", marginTop: 4 },
  skipTxt: { color: palette.textSecondary, fontWeight: "600", fontSize: 14 },
  googleBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    paddingVertical: 14,
    borderWidth: 1.5,
    borderColor: palette.border,
    marginBottom: 14,
  },
  googleTxt: { color: "#111827", fontSize: 15, fontWeight: "700" },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 14,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: palette.border },
  dividerTxt: {
    fontSize: 11,
    color: palette.textMuted,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
});
