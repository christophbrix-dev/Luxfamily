import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { MapPreview } from "@/src/components/MapPreview";
import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { palette, radii, shadow } from "@/src/theme";
import { api, ApiEvent } from "@/src/utils/api";

export default function EventDetail() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { lang, saved, toggleSave } = useApp();
  const [ev, setEv] = useState<ApiEvent | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/events/${id}`)
      .then(async (r) => {
        const txt = await r.text();
        const data = txt ? JSON.parse(txt) : null;
        if (!r.ok) throw new Error(data?.detail ?? "Failed");
        if (alive) setEv(data);
      })
      .catch((e) => alive && setErr(e instanceof Error ? e.message : "Failed"));
    // Fire-and-forget view ping; backend rate-limits per IP per minute.
    fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/events/${id}/view`, {
      method: "POST",
    }).catch(() => {});
    return () => {
      alive = false;
    };
  }, [id]);

  if (err) {
    return (
      <View style={styles.center}>
        <Text style={styles.errTxt}>{err}</Text>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtnSimple}>
          <Text style={styles.backBtnSimpleTxt}>Back</Text>
        </TouchableOpacity>
      </View>
    );
  }
  if (!ev) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }

  const isSaved = saved.includes(parseInt(ev.id.slice(0, 8), 16) % 1000);
  const localId = parseInt(ev.id.slice(0, 8), 16) % 1000;
  const openMaps = () => {
    Linking.openURL(
      `https://www.openstreetmap.org/?mlat=${ev.lat}&mlon=${ev.lng}#map=16/${ev.lat}/${ev.lng}`,
    );
  };

  return (
    <View style={styles.wrap}>
      <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + 120 }}>
        <View style={styles.hero}>
          {ev.image ? (
            <Image source={{ uri: ev.image }} style={StyleSheet.absoluteFillObject} />
          ) : (
            <View style={[StyleSheet.absoluteFillObject, { backgroundColor: palette.primaryLight }]} />
          )}
          <LinearGradient
            colors={["rgba(0,0,0,0.35)", "rgba(0,0,0,0)", "rgba(0,0,0,0.55)"]}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.heroTop, { paddingTop: insets.top + 8 }]}>
            <TouchableOpacity onPress={() => router.back()} style={styles.roundBtn} testID="event-back">
              <Ionicons name="chevron-back" size={20} color={palette.textPrimary} />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => toggleSave(localId)}
              style={styles.roundBtn}
              testID="event-save"
            >
              <Ionicons
                name={isSaved ? "heart" : "heart-outline"}
                size={20}
                color={isSaved ? palette.red : palette.textPrimary}
              />
            </TouchableOpacity>
          </View>
          <View style={styles.heroBottom}>
            <View style={styles.typeBadge}>
              <Text style={styles.typeBadgeTxt}>EVENT</Text>
            </View>
            <Text style={styles.heroTitle}>{ev.title[lang] ?? ev.title.en}</Text>
            <Text style={styles.heroSub}>{ev.short[lang] ?? ev.short.en}</Text>
          </View>
        </View>

        <View style={styles.body}>
          <View style={styles.weatherPill}>
            <Ionicons name="partly-sunny-outline" size={14} color="#92400E" />
            <Text style={styles.weatherTxt}>
              {t("greatForToday", lang)}: {ev.weather_fit[lang] ?? ev.weather_fit.en}
            </Text>
          </View>

          <View style={styles.statsGrid}>
            <Stat icon="calendar-outline" label={t("date", lang)} value={ev.start_date} />
            <Stat icon="time-outline" label="Time" value={ev.time || "—"} />
            <Stat
              icon="pricetag-outline"
              label="Price"
              value={ev.price_label[lang] ?? ev.price_label.en}
            />
            <Stat
              icon="accessibility-outline"
              label="Access"
              value={ev.accessibility[lang] ?? ev.accessibility.en}
            />
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("location", lang)}</Text>
            <Text style={styles.locTxt}>
              {ev.town}, {ev.canton} · Luxembourg
            </Text>
            <View style={{ marginTop: 14, borderRadius: 18, overflow: "hidden" }}>
              <MapPreview lat={ev.lat} lng={ev.lng} height={170} />
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("about", lang)}</Text>
            <Text style={styles.about}>{ev.description[lang] ?? ev.description.en}</Text>
            <View style={styles.tagRow}>
              {ev.category.map((tag) => (
                <View key={tag} style={styles.tag}>
                  <Text style={styles.tagTxt}>{tag}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) }]}>
        <TouchableOpacity onPress={openMaps} style={styles.footerSecondary}>
          <Text style={styles.footerSecondaryTxt}>{t("openInMaps", lang)}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => router.push(`/sponsor/${ev.id}`)}
          style={[styles.footerPrimary, { backgroundColor: "#F59E0B" }]}
          testID="event-sponsor-btn"
        >
          <Ionicons name="star" size={14} color="#fff" />
          <Text style={styles.footerPrimaryTxt}>Sponsor</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => toggleSave(localId)} style={styles.footerPrimary}>
          <Text style={styles.footerPrimaryTxt}>{isSaved ? t("unsave", lang) : t("save", lang)}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function Stat({
  icon,
  label,
  value,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.statCard}>
      <Ionicons name={icon} size={16} color={palette.primary} />
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: palette.background },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  errTxt: { color: palette.textSecondary, marginBottom: 12 },
  backBtnSimple: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: palette.primary,
  },
  backBtnSimpleTxt: { color: "#fff", fontWeight: "700" },
  hero: { height: 340, overflow: "hidden", borderBottomLeftRadius: 32, borderBottomRightRadius: 32 },
  heroTop: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 18 },
  roundBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.94)",
    justifyContent: "center",
    alignItems: "center",
  },
  heroBottom: { position: "absolute", left: 20, right: 20, bottom: 24 },
  typeBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: "rgba(255,255,255,0.95)",
    borderRadius: 999,
    marginBottom: 10,
  },
  typeBadgeTxt: { fontSize: 10, fontWeight: "800", color: palette.primaryDark, letterSpacing: 1 },
  heroTitle: { color: "#fff", fontSize: 28, fontWeight: "800", letterSpacing: -0.5, lineHeight: 32 },
  heroSub: { color: "rgba(255,255,255,0.9)", marginTop: 6, fontSize: 14 },
  body: { padding: 20, gap: 16 },
  weatherPill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    backgroundColor: palette.amberSoft,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
  },
  weatherTxt: { color: "#92400E", fontSize: 12, fontWeight: "600" },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  statCard: {
    width: "47.5%",
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: 14,
    gap: 6,
    ...shadow.soft,
  },
  statLabel: { fontSize: 11, color: palette.textMuted, fontWeight: "600" },
  statValue: { fontSize: 13, fontWeight: "700", color: palette.textPrimary, lineHeight: 18 },
  card: { backgroundColor: palette.surface, borderRadius: radii.xl, padding: 18, ...shadow.soft },
  cardTitle: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  locTxt: { marginTop: 10, fontSize: 14, color: palette.textSecondary },
  about: { color: palette.textSecondary, marginTop: 10, fontSize: 14, lineHeight: 22 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 14 },
  tag: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, backgroundColor: palette.surfaceMuted },
  tagTxt: { fontSize: 11, fontWeight: "600", color: palette.textSecondary },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    gap: 10,
    paddingHorizontal: 18,
    paddingTop: 14,
    backgroundColor: "rgba(255,255,255,0.98)",
    borderTopWidth: 1,
    borderTopColor: palette.borderSoft,
  },
  footerSecondary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.border,
    alignItems: "center",
    backgroundColor: palette.surface,
  },
  footerSecondaryTxt: { fontWeight: "700", color: palette.textPrimary, fontSize: 14 },
  footerPrimary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 16,
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "center",
    gap: 4,
    backgroundColor: palette.primary,
    ...shadow.emerald,
  },
  footerPrimaryTxt: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
