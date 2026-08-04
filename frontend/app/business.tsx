import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState, useMemo } from "react";
import {
  KeyboardAvoidingView,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

export default function Business() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const [name, setName] = useState("");
  const [venue, setVenue] = useState("");
  const [email, setEmail] = useState("");
  const [ig, setIg] = useState("");
  const [fb, setFb] = useState("");
  const [website, setWebsite] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const submit = async () => {
    if (!name.trim() || !email.trim() || !venue.trim()) return;
    try {
      const res = await fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/partners`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          venue: venue.trim(),
          email: email.trim(),
          website: website.trim(),
          instagram: ig.trim(),
          facebook: fb.trim(),
        }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      setSubmitted(true);
    } catch (e) {
      // Fallback to mailto if backend unreachable.
      const body = encodeURIComponent(
        `Name: ${name}\nVenue: ${venue}\nEmail: ${email}\nWebsite: ${website}\nInstagram: ${ig}\nFacebook: ${fb}`,
      );
      Linking.openURL(`mailto:partners@familyluxembourg.lu?subject=Partner submission&body=${body}`);
      setSubmitted(true);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.topbar}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="business-back">
            <Ionicons name="chevron-back" size={20} color={palette.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.h1}>For businesses</Text>
        </View>

        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.intro}>
            <View style={styles.introBadge}>
              <Ionicons name="business-outline" size={20} color={palette.primaryDark} />
            </View>
            <Text style={styles.introTitle}>List your venue or events</Text>
            <Text style={styles.introTxt}>
              Submit your venue and we&apos;ll add it to Wat Elo?. Once approved, we can
              also auto-import your future events from your website or social channels.
            </Text>
          </View>

          {submitted ? (
            <View style={styles.successCard}>
              <Ionicons name="checkmark-circle" size={40} color={palette.primary} />
              <Text style={styles.successTitle}>Submission sent</Text>
              <Text style={styles.successTxt}>
                Thanks — we&apos;ll review your venue within 48h and reach out by email.
              </Text>
            </View>
          ) : (
            <>
              <View style={styles.formCard}>
                <Field label="Your name" value={name} onChange={setName} testID="biz-name" />
                <Field label="Venue / business name" value={venue} onChange={setVenue} testID="biz-venue" />
                <Field
                  label="Contact email"
                  value={email}
                  onChange={setEmail}
                  keyboardType="email-address"
                  testID="biz-email"
                />
                <Field
                  label="Website (optional)"
                  value={website}
                  onChange={setWebsite}
                  placeholder="https://..."
                  testID="biz-website"
                />
                <Field
                  label="Instagram handle (optional)"
                  value={ig}
                  onChange={setIg}
                  placeholder="@yourvenue"
                  testID="biz-ig"
                />
                <Field
                  label="Facebook page (optional)"
                  value={fb}
                  onChange={setFb}
                  placeholder="facebook.com/yourpage"
                  testID="biz-fb"
                />
                <TouchableOpacity onPress={submit} style={styles.cta} testID="biz-submit">
                  <Text style={styles.ctaTxt}>Send submission</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.reality}>
                <Ionicons name="information-circle-outline" size={16} color={palette.textSecondary} />
                <Text style={styles.realityTxt}>
                  Why no &quot;connect with Instagram&quot; button? Meta closed the public Events API
                  in 2018, so third-party apps can no longer pull other accounts&apos; events
                  automatically. We&apos;ll add your venue&apos;s feed manually after approval.
                </Text>
              </View>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  keyboardType,
  testID,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  keyboardType?: "default" | "email-address";
  testID?: string;
}) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <View style={{ gap: 4 }}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={palette.textMuted}
        style={styles.input}
        autoCapitalize={keyboardType === "email-address" ? "none" : "sentences"}
        keyboardType={keyboardType ?? "default"}
        testID={testID}
      />
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
  scroll: { padding: 20, gap: 18 },
  intro: { gap: 10, paddingBottom: 4 },
  introBadge: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  introTitle: { fontSize: 20, fontWeight: "800", color: palette.textPrimary },
  introTxt: { fontSize: 13, color: palette.textSecondary, lineHeight: 19 },
  formCard: { backgroundColor: palette.surface, borderRadius: radii.lg, padding: 18, gap: 12, ...shadow.soft },
  label: { fontSize: 12, fontWeight: "700", color: palette.textSecondary },
  input: {
    backgroundColor: palette.surfaceMuted,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: palette.textPrimary,
  },
  cta: {
    marginTop: 6,
    backgroundColor: palette.primary,
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
    ...shadow.emerald,
  },
  ctaTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
  reality: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-start",
    backgroundColor: palette.surfaceMuted,
    padding: 14,
    borderRadius: radii.md,
  },
  realityTxt: { flex: 1, fontSize: 12, color: palette.textSecondary, lineHeight: 18 },
  successCard: {
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surface,
    padding: 30,
    borderRadius: radii.lg,
    ...shadow.soft,
  },
  successTitle: { fontSize: 18, fontWeight: "800", color: palette.textPrimary, marginTop: 4 },
  successTxt: { color: palette.textSecondary, textAlign: "center", lineHeight: 20 },
});
