import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState, useMemo } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { Analytics, api } from "@/src/utils/api";

export default function AdminAnalytics() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang } = useApp();
  const router = useRouter();
  const [data, setData] = useState<Analytics | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setErr(null);
      setData(await api.analytics());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  // Simple revenue projection: featured events × EUR 49 / month.
  const monthlyRevenue = data ? data.featured * 49 : 0;

  return (
    <View style={{ flex: 1, backgroundColor: "#F1F5F9" }}>
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.replace("/admin/events")} style={styles.back}>
          <Ionicons name="chevron-back" size={18} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>{t("adminAnalytics", lang)}</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {err ? <Text style={{ color: palette.red }}>{err}</Text> : null}
        {!data ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 40 }} />
        ) : (
          <>
            <View style={styles.statRow}>
              <Stat label="Total events" value={data.total_events} />
              <Stat label="Published" value={data.published} accent />
              <Stat label="Drafts" value={data.drafts} />
              <Stat label="Featured" value={data.featured} highlight />
            </View>

            <View style={styles.bigCard}>
              <Ionicons name="eye-outline" size={20} color={palette.primary} />
              <Text style={styles.bigLabel}>{t("allTimeViews", lang)}</Text>
              <Text style={styles.bigValue}>{data.total_views.toLocaleString()}</Text>
            </View>

            <View style={[styles.bigCard, styles.revCard]}>
              <Ionicons name="cash-outline" size={20} color="#92400E" />
              <Text style={[styles.bigLabel, { color: "#92400E" }]}>{t("monthlyFeaturedRevenue", lang)}</Text>
              <Text style={[styles.bigValue, { color: "#92400E" }]}>EUR {monthlyRevenue.toFixed(0)}</Text>
              <Text style={styles.revHint}>
                {data.featured} sponsored × EUR 49 / month. Promote partners in /admin/events.
              </Text>
            </View>

            <Text style={styles.section}>{t("topEventsByViews", lang)}</Text>
            <View style={styles.topCard}>
              {data.top_events.length === 0 ? (
                <Text style={{ color: palette.textSecondary, padding: 12 }}>{t("noViewsYet", lang)}</Text>
              ) : (
                data.top_events.map((ev, idx) => (
                  <View key={ev.id} style={styles.topRow}>
                    <View style={styles.rank}>
                      <Text style={styles.rankTxt}>{idx + 1}</Text>
                    </View>
                    <Text style={styles.topTitle} numberOfLines={1}>{ev.title}</Text>
                    <Text style={styles.topViews}>{ev.view_count} views</Text>
                  </View>
                ))
              )}
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

function Stat({ label, value, accent, highlight }: { label: string; value: number; accent?: boolean; highlight?: boolean }) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <View
      style={[
        styles.stat,
        accent && { borderColor: palette.primary, backgroundColor: palette.primaryLight },
        highlight && { borderColor: "#F59E0B", backgroundColor: "#FEF3C7" },
      ]}
    >
      <Text style={styles.statVal}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
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
  back: {
    width: 38,
    height: 38,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: palette.surface,
  },
  h1: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  scroll: { padding: 24, gap: 16 },
  statRow: { flexDirection: "row", gap: 10, flexWrap: "wrap" },
  stat: {
    flex: 1,
    minWidth: 130,
    padding: 16,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    backgroundColor: palette.surface,
  },
  statVal: { fontSize: 26, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  statLabel: { fontSize: 12, color: palette.textSecondary, marginTop: 4 },
  bigCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: 22,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    ...shadow.soft,
  },
  bigLabel: { fontSize: 13, color: palette.textSecondary, marginTop: 8 },
  bigValue: { fontSize: 32, fontWeight: "800", color: palette.textPrimary, marginTop: 4 },
  revCard: { borderColor: "#FCD34D", backgroundColor: "#FFFBEB" },
  revHint: { fontSize: 11, color: "#92400E", marginTop: 6 },
  section: { fontSize: 13, fontWeight: "700", color: palette.textSecondary, marginTop: 8 },
  topCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    overflow: "hidden",
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  rank: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  rankTxt: { color: palette.primaryDark, fontWeight: "800", fontSize: 12 },
  topTitle: { flex: 1, fontWeight: "700", color: palette.textPrimary, fontSize: 13 },
  topViews: { color: palette.primary, fontWeight: "700", fontSize: 12 },
});
