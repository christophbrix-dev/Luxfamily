// Change the admin password without leaving the app.
//
// Until now the only way was to edit ADMIN_PASSWORD in the hosting
// environment and restart the backend — which meant finding a Secrets tab that
// the preview container does not have, or asking someone else to do it. The
// old password ended up in the repository's git history, and being unable to
// change it without help is what kept it there.
//
// The current password is asked for even though the caller is already signed
// in. A token lives seven days and sits in browser storage; an unattended
// console should not be enough for someone to lock the owner out of their own
// account.

import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { t } from "@/src/i18n/strings";
import { type Palette, radii, shadowFor } from "@/src/theme";
import { api } from "@/src/utils/api";

/** Mirrors MIN_PASSWORD_LENGTH on the backend, which is the real gate. */
const MIN_LENGTH = 12;

export default function AdminPassword() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang } = useApp();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Checked here so the reader is told before they submit, and again on the
  // backend, which is what actually decides.
  const tooShort = next.length > 0 && next.length < MIN_LENGTH;
  const mismatch = repeat.length > 0 && next !== repeat;
  const unchanged = next.length > 0 && next === current;
  const ready =
    current.length > 0 && next.length >= MIN_LENGTH && next === repeat && !unchanged;

  const submit = async () => {
    if (!ready || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await api.changePassword(current, next);
      setDone(true);
      setCurrent("");
      setNext("");
      setRepeat("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : t("adminLoginFailed", lang));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} testID="pw-back">
          <Ionicons name="chevron-back" size={22} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>{t("changePassword", lang)}</Text>
      </View>

      <View style={styles.card}>
        {done ? (
          <View style={styles.doneWrap} testID="pw-done">
            <Ionicons name="checkmark-circle" size={40} color={palette.primaryDark} />
            <Text style={styles.doneTxt}>{t("passwordChanged", lang)}</Text>
            <Text style={styles.hint}>{t("passwordChangedHint", lang)}</Text>
          </View>
        ) : (
          <>
            <Text style={styles.label}>{t("currentPassword", lang)}</Text>
            <TextInput
              value={current}
              onChangeText={setCurrent}
              secureTextEntry
              autoCapitalize="none"
              style={styles.input}
              testID="pw-current"
            />

            <Text style={styles.label}>{t("newPassword", lang)}</Text>
            <TextInput
              value={next}
              onChangeText={setNext}
              secureTextEntry
              autoCapitalize="none"
              style={styles.input}
              testID="pw-new"
            />

            <Text style={styles.label}>{t("repeatPassword", lang)}</Text>
            <TextInput
              value={repeat}
              onChangeText={setRepeat}
              secureTextEntry
              autoCapitalize="none"
              style={styles.input}
              testID="pw-repeat"
            />

            {/* One message at a time, in the order the reader can act on. */}
            {tooShort ? (
              <Text style={styles.warn}>{t("passwordTooShort", lang)}</Text>
            ) : unchanged ? (
              <Text style={styles.warn}>{t("passwordSameAsOld", lang)}</Text>
            ) : mismatch ? (
              <Text style={styles.warn}>{t("passwordsDoNotMatch", lang)}</Text>
            ) : err ? (
              <Text style={styles.errTxt} testID="pw-error">{err}</Text>
            ) : (
              <Text style={styles.hint}>{t("passwordRule", lang)}</Text>
            )}

            <TouchableOpacity
              onPress={submit}
              disabled={!ready || busy}
              style={[styles.btn, (!ready || busy) && styles.btnOff]}
              testID="pw-submit"
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.btnTxt}>{t("changePassword", lang)}</Text>
              )}
            </TouchableOpacity>
          </>
        )}
      </View>

      <Text style={styles.footnote}>{t("passwordEnvNote", lang)}</Text>
    </SafeAreaView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: palette.background },
    headerRow: {
      flexDirection: "row", alignItems: "center", gap: 8,
      paddingHorizontal: 12, paddingTop: 8, paddingBottom: 4,
    },
    backBtn: { padding: 6 },
    h1: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
    card: {
      margin: 16, padding: 20, borderRadius: radii.lg,
      backgroundColor: palette.surface, borderWidth: 1,
      borderColor: palette.borderSoft, ...shadow,
    },
    label: { fontSize: 12, fontWeight: "700", color: palette.textSecondary, marginBottom: 6 },
    input: {
      backgroundColor: palette.background, borderRadius: radii.md,
      paddingHorizontal: 14, paddingVertical: 12, marginBottom: 14,
      color: palette.textPrimary, borderWidth: 1, borderColor: palette.borderSoft,
    },
    hint: { fontSize: 12, color: palette.textMuted, marginBottom: 14 },
    warn: { fontSize: 12, color: palette.amber, marginBottom: 14, fontWeight: "600" },
    errTxt: { fontSize: 12, color: palette.red, marginBottom: 14, fontWeight: "600" },
    btn: {
      backgroundColor: palette.primary, borderRadius: radii.md,
      paddingVertical: 14, alignItems: "center",
    },
    btnOff: { opacity: 0.45 },
    btnTxt: { color: "#fff", fontWeight: "800", fontSize: 14 },
    doneWrap: { alignItems: "center", gap: 10, paddingVertical: 12 },
    doneTxt: { fontSize: 16, fontWeight: "800", color: palette.textPrimary },
    footnote: {
      marginHorizontal: 20, fontSize: 11, color: palette.textMuted, lineHeight: 16,
    },
  });
