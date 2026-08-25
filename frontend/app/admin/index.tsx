import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useState, useMemo } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { ApiError } from "@/src/utils/apiError";
import { api, getAdminToken, setAdminToken } from "@/src/utils/api";

import type { Lang } from "@/src/data/places";

/**
 * Turn a failed login into something the reader can act on.
 *
 * The catch block used to render `e.message` straight from fetch, so a backend
 * that was not running showed "Failed to fetch" under the password field. That
 * reads like a rejected password — the natural next move is to try another
 * one, or to reset a password that was never wrong. The request had not left
 * the browser.
 *
 * fetch() rejects with a TypeError when it cannot reach the host at all;
 * anything the server answered arrives as an HTTP error instead. That is the
 * line between "no server" and "no".
 */
export function loginErrorMessage(e: unknown, lang: Lang): string {
  const raw = e instanceof Error ? e.message : "";
  const status = e instanceof ApiError ? e.status : 0;
  const unreachable =
    e instanceof TypeError ||
    /failed to fetch|network request failed|load failed/i.test(raw);

  if (unreachable) return t("adminBackendUnreachable", lang);

  // The status decides, not the wording. Matching on the word "invalid"
  // reported a rejected email address as a wrong password: the account was
  // configured as admin@localhost.invalid, .invalid is a reserved suffix the
  // validator refuses, and the 422 it came back with contained the address —
  // so the message said "email or password is wrong" about a password that had
  // never been looked at. Twenty minutes went into checking a correct
  // password against a correct hash.
  if (status === 422) return t("adminEmailNotAccepted", lang);
  if (status === 401 || status === 403) return t("adminBadCredentials", lang);
  if (status === 429) return t("adminTooManyAttempts", lang);
  if (status) return raw || t("adminLoginFailed", lang);

  // No status: an error from somewhere other than the request itself.
  return raw || t("adminLoginFailed", lang);
}

export default function AdminLogin() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang } = useApp();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  // Auto-redirect when already logged in as admin.
  useEffect(() => {
    (async () => {
      const t = await getAdminToken();
      if (!t) {
        setChecking(false);
        return;
      }
      try {
        const u = await api.me();
        if (u.role === "admin") {
          router.replace("/admin/events");
          return;
        }
      } catch {}
      await setAdminToken(null);
      setChecking(false);
    })();
  }, [router]);

  const submit = async () => {
    if (!email.trim() || !password) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.login(email.trim().toLowerCase(), password);
      if (res.user.role !== "admin") {
        throw new Error("This account is not an admin");
      }
      await setAdminToken(res.access_token);
      router.replace("/admin/events");
    } catch (e) {
      setErr(loginErrorMessage(e, lang));
    } finally {
      setBusy(false);
    }
  };

  if (checking) {
    return (
      <View style={styles.loadingWrap}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.wrap}
    >
      <View style={styles.card} testID="admin-login-card">
        <View style={styles.logo}>
          <Ionicons name="shield-checkmark" size={26} color="#fff" />
        </View>
        <Text style={styles.title}>{t("adminConsole", lang)}</Text>
        <Text style={styles.sub}>{t("adminSub", lang)}</Text>

        <View style={styles.field}>
          <Ionicons name="mail-outline" size={18} color={palette.textSecondary} />
          <TextInput
            placeholder="Email"
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            testID="admin-email"
          />
        </View>

        <View style={styles.field}>
          <Ionicons name="lock-closed-outline" size={18} color={palette.textSecondary} />
          <TextInput
            placeholder="Password"
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            testID="admin-password"
            onSubmitEditing={submit}
          />
        </View>

        {err ? <Text style={styles.errTxt}>{err}</Text> : null}

        <TouchableOpacity
          onPress={submit}
          style={[styles.cta, busy && styles.ctaBusy]}
          disabled={busy}
          testID="admin-submit"
        >
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.ctaTxt}>{t("signIn", lang)}</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.hint}>
          Restricted access. Admins only.
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#F1F5F9",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  loadingWrap: {
    flex: 1,
    backgroundColor: "#F1F5F9",
    justifyContent: "center",
    alignItems: "center",
  },
  card: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: palette.surface,
    borderRadius: radii.xxl,
    padding: 32,
    ...shadow.card,
  },
  logo: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: palette.primary,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 18,
    ...shadow.emerald,
  },
  title: { fontSize: 24, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  sub: { color: palette.textSecondary, marginTop: 4, marginBottom: 22, fontSize: 13 },
  field: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surfaceMuted,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
  },
  input: { flex: 1, fontSize: 14, color: palette.textPrimary, padding: 0 },
  errTxt: { color: palette.red, fontSize: 13, marginTop: 4, marginBottom: 4 },
  cta: {
    marginTop: 8,
    backgroundColor: palette.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    ...shadow.emerald,
  },
  ctaBusy: { opacity: 0.7 },
  ctaTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
  hint: {
    marginTop: 16,
    textAlign: "center",
    fontSize: 11,
    color: palette.textMuted,
  },
});
