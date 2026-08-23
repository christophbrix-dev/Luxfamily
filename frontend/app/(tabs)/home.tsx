import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppCard } from "@/src/components/AppCard";
import { Chip } from "@/src/components/Chip";
import { WeatherWidget } from "@/src/components/WeatherWidget";
import { useApp } from "@/src/contexts/AppContext";
import type { Lang } from "@/src/data/places";
import { usePlaces } from "@/src/hooks/useLivePlaces";
import { useUserLocation } from "@/src/hooks/useUserLocation";
import { detailHref } from "@/src/utils/toPlace";
import { baseLang } from "@/src/i18n/pickLang";
import { t } from "@/src/i18n/strings";
import { type Palette, radii, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

const HOME_CHIPS = ["All", "Outdoor", "Indoor", "0-3", "4-6", "7-12"] as const;

function chipLabel(c: string, langIn: Lang): string {
  const lang = baseLang(langIn);
  if (c === "All")     return lang === "de" ? "Alle" : lang === "fr" ? "Tout" : "All";
  if (c === "Indoor")  return lang === "de" ? "Drinnen" : lang === "fr" ? "Intérieur" : "Indoor";
  if (c === "Outdoor") return lang === "de" ? "Draußen" : lang === "fr" ? "Extérieur" : "Outdoor";
  return c;   // age ranges — no translation needed
}

function greetingKey(): "goodMorning" | "goodAfternoon" | "goodEvening" {
  const h = new Date().getHours();
  if (h < 12) return "goodMorning";
  if (h < 18) return "goodAfternoon";
  return "goodEvening";
}

export default function Home() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang, user } = useApp();
  const [chip, setChip] = useState<string>("All");
  const { places, loading, error, hasLocation } = usePlaces();
  const { status: locationStatus, request: requestLocation } = useUserLocation();

  const featured = useMemo(() => {
    const all = places ?? [];
    if (chip === "All") return all.slice(0, 3);
    if (chip === "Indoor" || chip === "Outdoor") {
      return all.filter((p) => p.type === chip).slice(0, 3);
    }
    // age chip
    const [min, max] = chip.split("-").map(Number);
    return all.filter((p) => p.ageMin <= max && p.ageMax >= min).slice(0, 3);
  }, [chip, places]);

  /**
   * The three closest entries, once we know where the user is.
   *
   * This used to be `places.slice(3, 6)` — entries four to six of the list,
   * under a heading promising proximity. Without a position there is nothing
   * to sort by, so the section is hidden rather than filled with an untruth.
   */
  const nearYou = useMemo(() => {
    if (!hasLocation) return [];
    return (places ?? [])
      .filter((p) => p.distanceKm !== undefined)
      .sort((a, b) => (a.distanceKm ?? 0) - (b.distanceKm ?? 0))
      .slice(0, 3);
  }, [places, hasLocation]);
  const initial = (user?.name?.[0] ?? "U").toUpperCase();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <WeatherWidget />
            <Text style={styles.greeting}>{t(greetingKey(), lang)}</Text>
            <Text style={styles.sub}>{t("ideasForToday", lang)}</Text>
          </View>
          <View style={styles.headerRight}>
            <TouchableOpacity style={styles.iconBtn} testID="bell-btn">
              <Ionicons name="notifications-outline" size={18} color={palette.textSecondary} />
            </TouchableOpacity>
            <View style={styles.avatar}>
              <Text style={styles.avatarTxt}>{initial}</Text>
            </View>
          </View>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
          style={styles.chipRowOuter}
        >
          {HOME_CHIPS.map((c) => (
            <Chip
              key={c}
              label={chipLabel(c, lang)}
              active={chip === c}
              onPress={() => setChip(c)}
              testID={`home-chip-${c}`}
            />
          ))}
        </ScrollView>

        {loading ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 32 }} />
        ) : error && !places?.length ? (
          <View style={styles.feed}>
            <Text style={styles.sub}>{t("failedToLoad", lang)}</Text>
          </View>
        ) : null}

        <View style={styles.feed}>
          {featured.map((item) => (
            <AppCard
              key={item.id}
              item={item}
              large
              onPress={() => router.push(detailHref(item))}
            />
          ))}
        </View>

        {!hasLocation && locationStatus !== "denied" ? (
          <TouchableOpacity
            style={styles.locationPrompt}
            onPress={requestLocation}
            testID="home-enable-location"
          >
            <Ionicons name="location-outline" size={16} color={palette.primaryDark} />
            <Text style={styles.locationPromptTxt}>{t("enableLocation", lang)}</Text>
          </TouchableOpacity>
        ) : null}

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{t("nearYou", lang)}</Text>
          <TouchableOpacity onPress={() => router.replace("/(tabs)/explore")}>
            <Text style={styles.seeAll}>{t("seeAll", lang)}</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.nearList}>
          {nearYou.map((item) => (
            <AppCard
              key={item.id}
              item={item}
              onPress={() => router.push(detailHref(item))}
            />
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  scroll: { paddingBottom: 32 },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 6,
    gap: 12,
  },
  greeting: {
    marginTop: 14,
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: palette.textPrimary,
  },
  sub: { fontSize: 15, color: palette.textSecondary, marginTop: 4 },
  headerRight: { flexDirection: "row", gap: 8, alignItems: "center" },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
    boxShadow: "0px 4px 8px rgba(15, 23, 42, 0.05)",
    elevation: 2,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 3,
    borderColor: "#fff",
  },
  avatarTxt: { color: palette.primaryDark, fontWeight: "800", fontSize: 16 },
  chipRowOuter: { marginTop: 18, marginBottom: 8, maxHeight: 56 },
  chipRow: { gap: 8, paddingHorizontal: 20, alignItems: "center", height: 56 },
  feed: { paddingHorizontal: 20, paddingTop: 8, gap: 16 },
  locationPrompt: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginHorizontal: 16,
    marginTop: 20,
    paddingVertical: 12,
    borderRadius: radii.md,
    backgroundColor: palette.primaryLight,
  },
  locationPromptTxt: {
    fontSize: 13,
    fontWeight: "700",
    color: palette.primaryDark,
  },
  sectionHeader: {
    marginTop: 24,
    paddingHorizontal: 20,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 20, fontWeight: "700", color: palette.textPrimary },
  seeAll: { color: palette.primary, fontWeight: "600", fontSize: 13 },
  nearList: { paddingHorizontal: 20, gap: 14 },
});
