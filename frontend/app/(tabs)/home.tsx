import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppCard } from "@/src/components/AppCard";
import { Chip } from "@/src/components/Chip";
import { WeatherWidget } from "@/src/components/WeatherWidget";
import { useApp } from "@/src/contexts/AppContext";
import { PLACES } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { palette } from "@/src/theme";

const HOME_CHIPS = ["All", "Outdoor", "Indoor", "0-3", "4-6", "7-12"] as const;

function chipLabel(c: string, lang: "en" | "de" | "fr"): string {
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
  const router = useRouter();
  const { lang, user } = useApp();
  const [chip, setChip] = useState<string>("All");

  const featured = useMemo(() => {
    if (chip === "All") return PLACES.slice(0, 3);
    if (chip === "Indoor" || chip === "Outdoor") {
      return PLACES.filter((p) => p.type === chip).slice(0, 3);
    }
    // age chip
    const [min, max] = chip.split("-").map(Number);
    return PLACES.filter((p) => p.ageMin <= max && p.ageMax >= min).slice(0, 3);
  }, [chip]);

  const nearYou = useMemo(() => PLACES.slice(3, 6), []);
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

        <View style={styles.feed}>
          {featured.map((item) => (
            <AppCard
              key={item.id}
              item={item}
              large
              onPress={() => router.push(`/detail/${item.id}`)}
            />
          ))}
        </View>

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
              onPress={() => router.push(`/detail/${item.id}`)}
            />
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
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
