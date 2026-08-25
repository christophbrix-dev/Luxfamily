// Browse the OpenStreetMap places: playgrounds, parks, pools, museums.
//
// The ingest has held thousands of these since it ran, and nothing displayed
// them. For a family they are arguably more useful than dated events — a
// playground is open every afternoon, a concert happens once.
//
// Thousands of entries are only usable once they can be narrowed down, which is
// why this leans on the position when there is one: the backend filters by
// radius, so the list becomes "what is near me" rather than "everything in the
// country, alphabetically".

import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Chip } from "@/src/components/Chip";
import { useApp } from "@/src/contexts/AppContext";
import type { Lang } from "@/src/data/places";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { distanceKm, useUserLocation } from "@/src/hooks/useUserLocation";
import { t } from "@/src/i18n/strings";
import { isOpenAt, openLabel } from "@/src/utils/openingHours";
import { type Palette, radii, shadowFor } from "@/src/theme";
import { api, type ApiPlace, type PlaceLabels, type PlacesMeta } from "@/src/utils/api";

/** The taxonomy ships every label; pick the user's, falling back like elsewhere. */
function label(entry: PlaceLabels, lang: Lang): string {
  if (lang === "lb") return entry.label_lb || entry.label_de;
  if (lang === "de") return entry.label_de;
  if (lang === "fr") return entry.label_fr;
  return entry.label_en;
}

const GROUP_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  play: "happy-outline",
  nature: "leaf-outline",
  picnic: "restaurant-outline",
  hike: "trail-sign-outline",
  animals: "paw-outline",
  culture: "school-outline",
  sport: "water-outline",
};

export default function Places() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang } = useApp();
  const { coords, status: locationStatus, request: requestLocation } = useUserLocation();

  const [meta, setMeta] = useState<PlacesMeta | null>(null);
  const [group, setGroup] = useState<string | null>(null);
  const [places, setPlaces] = useState<ApiPlace[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.placesMeta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const load = useCallback(async () => {
    setError(null);
    setPlaces(null);
    try {
      const rows = await api.osmPlaces({
        group: group ?? undefined,
        near: coords ?? undefined,
        radiusKm: 15,
        limit: 60,
      });
      setPlaces(rows);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setPlaces([]);
    }
  }, [group, coords]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Closest first once we know where the user is; otherwise the backend's order. */
  const sorted = useMemo<(ApiPlace & { km?: number })[]>(() => {
    if (!places) return [];
    if (!coords) return places;
    return places
      .map((p) => ({
        ...p,
        km:
          p.lat !== null && p.lng !== null
            ? distanceKm(coords, { lat: p.lat, lng: p.lng })
            : undefined,
      }))
      .sort((a, b) => (a.km ?? Infinity) - (b.km ?? Infinity));
  }, [places, coords]);

  const groups = meta ? Object.entries(meta.groups) : [];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} testID="places-back">
          <Ionicons name="chevron-back" size={22} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>{t("places", lang)}</Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
        style={styles.chipRowOuter}
      >
        <Chip label={t("all", lang)} active={group === null} onPress={() => setGroup(null)} />
        {groups.map(([key, g]) => (
          <Chip
            key={key}
            label={label(g, lang)}
            active={group === key}
            onPress={() => setGroup(key)}
            testID={`places-group-${key}`}
          />
        ))}
      </ScrollView>

      {!coords && locationStatus !== "denied" ? (
        <TouchableOpacity style={styles.prompt} onPress={requestLocation} testID="places-enable-location">
          <Ionicons name="location-outline" size={16} color={palette.primaryDark} />
          <Text style={styles.promptTxt}>{t("enableLocation", lang)}</Text>
        </TouchableOpacity>
      ) : null}

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {places === null && !error ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 40 }} />
        ) : error ? (
          <Text style={styles.empty}>{t("failedToLoad", lang)}</Text>
        ) : sorted.length === 0 ? (
          <Text style={styles.empty}>{t("noEventsYet", lang)}</Text>
        ) : (
          sorted.map((p) => (
            <View key={p.id} style={styles.card} testID={`place-${p.id}`}>
              <View style={[styles.iconWrap, { backgroundColor: meta?.groups[p.group]?.color ?? palette.primaryLight }]}>
                <Ionicons name={GROUP_ICONS[p.group] ?? "location-outline"} size={18} color="#fff" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle} numberOfLines={1}>{p.name}</Text>
                <Text style={styles.cardMeta} numberOfLines={1}>
                  {[
                    meta?.categories[p.kind] ? label(meta.categories[p.kind], lang) : p.kind,
                    p.km !== undefined ? `${p.km.toFixed(1)} km` : null,
                    p.opening_hours || null,
                  ].filter(Boolean).join(" · ")}
                </Text>
                <View style={styles.badgeRow}>
                  {/* Only when we are sure. openLabel returns null for hours
                      written as "by appointment" or with a public-holiday
                      rule, and then the raw text above is all we claim. */}
                  {openLabel(p.opening_hours, lang) ? (
                    <Text
                      style={[
                        styles.openState,
                        isOpenAt(p.opening_hours) === "open" ? styles.openNow : styles.closedNow,
                      ]}
                    >
                      {openLabel(p.opening_hours, lang)}
                    </Text>
                  ) : null}
                  {p.wheelchair ? <Ionicons name="accessibility-outline" size={13} color={palette.textMuted} /> : null}
                  {p.toilets ? <Ionicons name="water-outline" size={13} color={palette.textMuted} /> : null}
                </View>
              </View>
              {p.lat && p.lng ? (
                <TouchableOpacity
                  onPress={() => Linking.openURL(`https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lng}#map=17/${p.lat}/${p.lng}`)}
                  style={styles.mapBtn}
                  testID={`place-map-${p.id}`}
                >
                  <Ionicons name="map-outline" size={18} color={palette.primaryDark} />
                </TouchableOpacity>
              ) : null}
            </View>
          ))
        )}

        {/* ODbL requires attribution wherever the data is shown, not only on the map tiles. */}
        {sorted.length > 0 ? (
          <Text style={styles.attribution}>© OpenStreetMap contributors (ODbL)</Text>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingTop: 8 },
  backBtn: { padding: 6 },
  h1: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
// flexShrink: 0 because maxHeight does not stop a flex child from being
  // squeezed — it only caps how tall it may grow. React Native Web gives
  // every view flexShrink: 1, so this row collapsed to 10px and the filter
  // chips were simply not on screen.
  chipRowOuter: { maxHeight: 56, flexShrink: 0 },
  chipRow: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  prompt: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    marginHorizontal: 16, marginBottom: 8, paddingVertical: 12,
    borderRadius: radii.md, backgroundColor: palette.primaryLight,
  },
  promptTxt: { fontSize: 13, fontWeight: "700", color: palette.primaryDark },
  scroll: { paddingHorizontal: 16, paddingBottom: 32, gap: 10 },
  card: {
    flexDirection: "row", alignItems: "center", gap: 12, padding: 12,
    borderRadius: radii.md, backgroundColor: palette.surface,
    borderWidth: 1, borderColor: palette.borderSoft, ...shadow,
  },
  iconWrap: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center" },
  cardTitle: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  cardMeta: { fontSize: 12, color: palette.textSecondary, marginTop: 2 },
  badgeRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  openState: { fontSize: 11, fontWeight: "700" },
  openNow: { color: palette.primaryDark },
  closedNow: { color: palette.textMuted },
  mapBtn: { padding: 8 },
  empty: { textAlign: "center", color: palette.textSecondary, marginTop: 40 },
  attribution: { textAlign: "center", fontSize: 11, color: palette.textMuted, marginTop: 16 },
});
