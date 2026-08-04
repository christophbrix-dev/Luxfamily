import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState, useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppCard } from "@/src/components/AppCard";
import { Chip } from "@/src/components/Chip";
import { useApp } from "@/src/contexts/AppContext";
import { PLACES } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

export default function Saved() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang, saved } = useApp();
  const [tab, setTab] = useState<"places" | "events" | "itineraries">("places");

  const filtered = PLACES.filter((p) => saved.includes(p.id)).filter((p) => {
    if (tab === "places") return p.type !== "Event";
    if (tab === "events") return p.type === "Event";
    return false;
  });

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.h1}>{t("saved", lang)}</Text>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
          style={styles.chipRowOuter}
        >
          <Chip
            label={t("places", lang)}
            active={tab === "places"}
            onPress={() => setTab("places")}
            testID="saved-tab-places"
          />
          <Chip
            label={t("events", lang)}
            active={tab === "events"}
            onPress={() => setTab("events")}
            testID="saved-tab-events"
          />
          <Chip
            label={t("itineraries", lang)}
            active={tab === "itineraries"}
            onPress={() => setTab("itineraries")}
            testID="saved-tab-itineraries"
          />
        </ScrollView>

        <View style={styles.list}>
          {filtered.length === 0 ? (
            <View style={styles.empty} testID="saved-empty">
              <Ionicons name="heart-outline" size={42} color={palette.textMuted} />
              <Text style={styles.emptyTxt}>{t("noSaved", lang)}</Text>
            </View>
          ) : (
            filtered.map((p) => (
              <AppCard
                key={p.id}
                item={p}
                onPress={() => router.push(`/detail/${p.id}`)}
              />
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  scroll: { padding: 20, paddingBottom: 32 },
  h1: { fontSize: 30, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  chipRowOuter: { marginTop: 16, marginBottom: 4, maxHeight: 56, marginHorizontal: -20 },
  chipRow: { gap: 8, alignItems: "center", height: 56, paddingHorizontal: 20 },
  list: { gap: 14, marginTop: 12 },
  empty: { alignItems: "center", padding: 36, gap: 10 },
  emptyTxt: {
    textAlign: "center",
    color: palette.textSecondary,
    fontSize: 14,
    maxWidth: 260,
    lineHeight: 20,
  },
});
