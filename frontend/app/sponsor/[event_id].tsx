import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState, useMemo } from "react";
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { radii, type Palette, shadowFor } from "@/src/theme";
import { useApp } from "@/src/contexts/AppContext";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { t } from "@/src/i18n/strings";
import { pickLang } from "@/src/i18n/pickLang";
import { ApiEvent } from "@/src/utils/api";

export default function SponsorChooser() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang } = useApp();
  const router = useRouter();
  const { event_id } = useLocalSearchParams<{ event_id: string }>();
  const [event, setEvent] = useState<ApiEvent | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // Plans are declared inside so labels/badges can react to language changes.
  const PLANS = useMemo(() => ([
    { id: "1month",  price: 49,  label: t("plan1Month", lang),  badge: t("planTryIt", lang) },
    { id: "3months", price: 129, label: t("plan3Months", lang), badge: t("planMostPopular", lang), save: t("planSave18", lang) },
    { id: "6months", price: 229, label: t("plan6Months", lang), badge: t("planBestValue", lang),  save: t("planSave65", lang) },
  ]), [lang]);

  useEffect(() => {
    if (!event_id) return;
    fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/events/${event_id}`)
      .then((r) => r.json())
      .then(setEvent)
      .catch(() => setErr(t("eventNotFound", lang)));
  }, [event_id, lang]);

  const buy = async (plan: string) => {
    setBusy(plan);
    setErr(null);
    try {
      const res = await fetch(
        `${process.env.EXPO_PUBLIC_BACKEND_URL}/api/sponsor/checkout`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ event_id, plan }),
        },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? t("checkoutFailed", lang));
      Linking.openURL(data.url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("checkoutFailed", lang));
    } finally {
      setBusy(null);
    }
  };

  if (err && !event) {
    return (
      <View style={styles.center}>
        <Text style={styles.err}>{err}</Text>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backTxt}>{t("back", lang)}</Text>
        </TouchableOpacity>
      </View>
    );
  }
  if (!event) return <View style={styles.center}><ActivityIndicator color={palette.primary} /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: palette.surfaceMuted }}>
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={18} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>{t("sponsorTitle", lang)}</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.eventCard}>
          <View style={styles.eventBadge}>
            <Ionicons name="star" size={14} color="#92400E" />
            <Text style={styles.eventBadgeTxt}>{t("featuredPlacement", lang)}</Text>
          </View>
          <Text style={styles.eventTitle}>{pickLang(event.title, lang) ?? event.title.en}</Text>
          <Text style={styles.eventMeta}>{event.start_date} · {event.town}</Text>
        </View>

        <Text style={styles.intro}>{t("sponsorIntro", lang)}</Text>

        {PLANS.map((p) => (
          <TouchableOpacity
            key={p.id}
            onPress={() => buy(p.id)}
            disabled={busy !== null}
            style={[styles.plan, p.id === "3months" && styles.planRecommended]}
            testID={`plan-${p.id}`}
          >
            <View style={styles.planLeft}>
              <View style={styles.planBadge}>
                <Text style={styles.planBadgeTxt}>{p.badge}</Text>
              </View>
              <Text style={styles.planLabel}>{p.label}</Text>
              {p.save ? <Text style={styles.planSave}>{p.save}</Text> : null}
            </View>
            <View style={styles.planRight}>
              {busy === p.id ? (
                <ActivityIndicator color={palette.primary} />
              ) : (
                <>
                  <Text style={styles.planPrice}>EUR {p.price}</Text>
                  <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
                </>
              )}
            </View>
          </TouchableOpacity>
        ))}

        {err ? <Text style={styles.err}>{err}</Text> : null}

        <View style={styles.trust}>
          <Ionicons name="lock-closed-outline" size={14} color={palette.textMuted} />
          <Text style={styles.trustTxt}>{t("sponsorTrust", lang)}</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: palette.surfaceMuted },
  err: { color: palette.red, textAlign: "center", marginVertical: 10 },
  backBtn: { paddingHorizontal: 18, paddingVertical: 10, borderRadius: 999, backgroundColor: palette.primary },
  backTxt: { color: "#fff", fontWeight: "700" },
  topbar: {
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 16,
    backgroundColor: palette.surface,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
  },
  h1: { fontSize: 20, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  scroll: { padding: 24, gap: 12 },
  eventCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: 18,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    gap: 6,
    marginBottom: 6,
  },
  eventBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: "#FEF3C7",
    marginBottom: 4,
  },
  eventBadgeTxt: { fontSize: 9, fontWeight: "800", color: "#92400E", letterSpacing: 0.5 },
  eventTitle: { fontSize: 18, fontWeight: "800", color: palette.textPrimary },
  eventMeta: { fontSize: 13, color: palette.textSecondary },
  intro: { color: palette.textSecondary, lineHeight: 20, marginVertical: 6 },
  plan: {
    flexDirection: "row",
    alignItems: "center",
    padding: 18,
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    borderWidth: 2,
    borderColor: palette.borderSoft,
    ...shadow.soft,
  },
  planRecommended: { borderColor: palette.primary },
  planLeft: { flex: 1, gap: 4 },
  planBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: palette.primaryLight,
  },
  planBadgeTxt: { fontSize: 10, fontWeight: "800", color: palette.primaryDark, letterSpacing: 0.5 },
  planLabel: { fontSize: 18, fontWeight: "800", color: palette.textPrimary },
  planSave: { fontSize: 12, fontWeight: "700", color: palette.primary },
  planRight: { flexDirection: "row", alignItems: "center", gap: 8 },
  planPrice: { fontSize: 22, fontWeight: "800", color: palette.textPrimary },
  trust: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 16,
    paddingHorizontal: 4,
  },
  trustTxt: { color: palette.textMuted, fontSize: 11, flex: 1 },
});
