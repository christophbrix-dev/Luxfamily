import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DEFAULT_FILTERS, FilterSheet, Filters } from "@/src/components/FilterSheet";
import LeafletMap, {
  type LeafletMapHandle,
  type MapEvent,
} from "@/src/components/LeafletMap";
import { useApp } from "@/src/contexts/AppContext";
import { CANTONS, type Canton } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { pickLang } from "@/src/i18n/pickLang";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { api, type ApiEvent } from "@/src/utils/api";

export default function Explore() {
  const { palette, shadow, effective } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang } = useApp();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [canton, setCanton] = useState<Canton | null>(null);

  // Live data from the API — the same 159 events as the Events tab.
  const [events, setEvents] = useState<ApiEvent[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const data = await api.publicEvents();
      setEvents(data);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Count events per canton for the pill row badges.
  const cantonCounts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const e of events ?? []) {
      if (e.canton) out[e.canton] = (out[e.canton] ?? 0) + 1;
    }
    return out;
  }, [events]);

  // Filter by canton / query / filter-sheet selections.
  const filtered = useMemo<ApiEvent[]>(() => {
    if (!events) return [];
    const q = query.trim().toLowerCase();
    return events.filter((e) => {
      if (canton && e.canton !== canton) return false;
      if (filters.type !== "All" && e.type !== filters.type) return false;
      if (filters.age !== "All") {
        const [min, max] = filters.age.split("-").map(Number);
        if (!(e.age_min <= max && e.age_max >= min)) return false;
      }
      if (filters.category.length && !filters.category.some((c) => e.category.includes(c)))
        return false;
      if (filters.wheelchair && !e.accessibility_wheelchair) return false;
      if (filters.sensoryFriendly && !e.sensory_friendly) return false;
      if (filters.freeParking && !e.free_parking) return false;
      if (q) {
        const hay = `${pickLang(e.title, lang) ?? ""} ${pickLang(e.short, lang) ?? ""} ${e.town ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [events, canton, filters, query, lang]);

  const activeFilterCount =
    (filters.age !== "All" ? 1 : 0) +
    (filters.type !== "All" ? 1 : 0) +
    filters.category.length +
    (filters.date !== "Anytime" ? 1 : 0) +
    (filters.wheelchair ? 1 : 0) +
    (filters.sensoryFriendly ? 1 : 0) +
    (filters.freeParking ? 1 : 0) +
    (canton ? 1 : 0);

  // ---------------------------------------------------------------------
  // Map: push filtered events as markers whenever they change.
  // ---------------------------------------------------------------------
  const mapRef = useRef<LeafletMapHandle | null>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (!mapReady) return;
    const markers: MapEvent[] = filtered
      .filter((e) => e.lat && e.lng && !(e.lat === 0 && e.lng === 0))
      .map((e) => ({
        id: e.id,
        lat: e.lat,
        lng: e.lng,
        title: pickLang(e.title, lang) ?? e.title.en ?? "",
        town: e.town,
        canton: e.canton,
        category: e.category,
        featured: e.featured,
        btnLabel: t("openDetails", lang),
      }));
    mapRef.current?.setEvents(markers);
  }, [filtered, mapReady, lang]);

  // Fly to a canton whenever the pill selection changes.
  useEffect(() => {
    if (!mapReady) return;
    if (canton) mapRef.current?.flyToCanton(canton);
    else mapRef.current?.flyToCountry();
  }, [canton, mapReady]);

  const onMarkerTap = useCallback(
    (id: string) => {
      router.push(`/detail/${id}` as never);
    },
    [router],
  );

  // Push the current effective theme down to Leaflet whenever it changes.
  useEffect(() => {
    if (!mapReady) return;
    mapRef.current?.setTheme(effective);
  }, [effective, mapReady]);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.headerSticky}>
        <Text style={styles.h1}>{t("explore", lang)}</Text>
        <View style={styles.searchRow}>
          <View style={styles.searchField}>
            <Ionicons name="search-outline" size={18} color={palette.textMuted} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder={t("search", lang)}
              placeholderTextColor={palette.textMuted}
              style={styles.searchInput}
              testID="explore-search-input"
            />
          </View>
          <TouchableOpacity
            onPress={() => setOpen(true)}
            style={styles.filterBtn}
            testID="explore-filter-btn"
          >
            <Ionicons name="options-outline" size={20} color={palette.textPrimary} />
            {activeFilterCount > 0 ? (
              <View style={styles.filterBadge}>
                <Text style={styles.filterBadgeTxt}>{activeFilterCount}</Text>
              </View>
            ) : null}
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
      >
        {/* ------------------------------------------------------------ */}
        {/* Canton pill selector (replaces the old cheap SVG silhouette) */}
        {/* ------------------------------------------------------------ */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.cantonRow}
          style={styles.cantonRowOuter}
        >
          <CantonPill
            label={t("allCantons", lang)}
            count={events?.length ?? 0}
            active={canton === null}
            onPress={() => setCanton(null)}
          />
          {CANTONS.map((c) => (
            <CantonPill
              key={c}
              label={c}
              count={cantonCounts[c] ?? 0}
              active={canton === c}
              onPress={() => setCanton(c)}
            />
          ))}
        </ScrollView>

        {/* ------------------------------------------------------------ */}
        {/* Real interactive map — pinch/scroll to street-level zoom.    */}
        {/* ------------------------------------------------------------ */}
        <View style={styles.mapCard} testID="explore-map-card">
          <LeafletMap
            ref={mapRef}
            style={styles.mapInner}
            onReady={() => setMapReady(true)}
            onMarkerTap={onMarkerTap}
          />
        </View>

        {/* Result list underneath */}
        <Text style={styles.sectionTitle}>
          {loadError
            ? t("failedToLoad", lang)
            : events === null
              ? t("loading", lang)
              : `${filtered.length} ${filtered.length === 1 ? t("result", lang) : t("results", lang)}`}
        </Text>

        {events === null && !loadError ? (
          <View style={styles.empty} testID="explore-loading">
            <ActivityIndicator color={palette.primary} />
          </View>
        ) : filtered.length === 0 ? (
          <View style={styles.empty} testID="explore-empty">
            <Ionicons name="leaf-outline" size={40} color={palette.textMuted} />
            <Text style={styles.emptyTxt}>{t("noResults", lang)}</Text>
          </View>
        ) : (
          filtered.slice(0, 30).map((e) => (
            <TouchableOpacity
              key={e.id}
              onPress={() => router.push(`/detail/${e.id}` as never)}
              style={styles.resultCard}
              activeOpacity={0.9}
              testID={`explore-result-${e.id}`}
            >
              <View style={styles.resultIconWrap}>
                <Ionicons
                  name="location"
                  size={18}
                  color={palette.primaryDark}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.resultTitle} numberOfLines={1}>
                  {pickLang(e.title, lang) ?? e.title.en}
                </Text>
                <Text style={styles.resultSub} numberOfLines={1}>
                  {[e.town, e.canton].filter(Boolean).join(" · ")}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
            </TouchableOpacity>
          ))
        )}
      </ScrollView>

      <FilterSheet
        open={open}
        filters={filters}
        onChange={setFilters}
        onClose={() => setOpen(false)}
      />
    </SafeAreaView>
  );
}

// ------------------------------------------------------------------
// Canton pill — mini component with a rounded emerald active state.
// ------------------------------------------------------------------
function CantonPill({
  label,
  count,
  active,
  onPress,
}: {
  label: string;
  count: number;
  active: boolean;
  onPress: () => void;
}) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <TouchableOpacity
      onPress={onPress}
      style={[styles.pill, active && styles.pillActive]}
      activeOpacity={0.85}
      testID={`explore-canton-${label}`}
    >
      <Text style={[styles.pillTxt, active && styles.pillTxtActive]}>{label}</Text>
      {count > 0 ? (
        <View style={[styles.pillBadge, active && styles.pillBadgeActive]}>
          <Text style={[styles.pillBadgeTxt, active && styles.pillBadgeTxtActive]}>
            {count}
          </Text>
        </View>
      ) : null}
    </TouchableOpacity>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  headerSticky: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 4,
    backgroundColor: palette.background,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  h1: {
    fontSize: 30,
    fontWeight: "800",
    color: palette.textPrimary,
    letterSpacing: -0.5,
  },
  searchRow: { marginTop: 14, flexDirection: "row", gap: 10 },
  searchField: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: palette.border,
    height: 44,
  },
  searchInput: { flex: 1, fontSize: 14, color: palette.textPrimary },
  filterBtn: {
    width: 44,
    height: 44,
    borderRadius: radii.md,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.border,
    justifyContent: "center",
    alignItems: "center",
  },
  filterBadge: {
    position: "absolute",
    top: -4,
    right: -4,
    backgroundColor: palette.primary,
    borderRadius: 999,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    justifyContent: "center",
    alignItems: "center",
  },
  filterBadgeTxt: { color: "#FFFFFF", fontSize: 11, fontWeight: "700" },
  list: { paddingBottom: 32 },

  cantonRowOuter: { paddingTop: 14 },
  cantonRow: { paddingHorizontal: 20, gap: 8, paddingBottom: 12 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.border,
  },
  pillActive: {
    backgroundColor: palette.primary,
    borderColor: palette.primaryDark,
  },
  pillTxt: { fontSize: 13, color: palette.textPrimary, fontWeight: "600" },
  pillTxtActive: { color: "#FFFFFF" },
  pillBadge: {
    backgroundColor: palette.primaryLight,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 999,
    minWidth: 22,
    alignItems: "center",
  },
  pillBadgeActive: { backgroundColor: "rgba(255,255,255,0.28)" },
  pillBadgeTxt: { fontSize: 11, fontWeight: "700", color: palette.primaryDark },
  pillBadgeTxtActive: { color: "#FFFFFF" },

  mapCard: {
    marginHorizontal: 20,
    marginTop: 4,
    marginBottom: 20,
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: palette.surface,
    height: 380,
    ...shadow.card,
  },
  mapInner: { flex: 1 },

  sectionTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: palette.textMuted,
    letterSpacing: 1.2,
    marginHorizontal: 20,
    marginTop: 4,
    marginBottom: 12,
    textTransform: "uppercase",
  },

  resultCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surface,
    marginHorizontal: 20,
    marginBottom: 8,
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: palette.borderSoft,
  },
  resultIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 999,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  resultTitle: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  resultSub: { fontSize: 12, color: palette.textMuted, marginTop: 2 },

  empty: {
    alignItems: "center",
    padding: 32,
    marginHorizontal: 20,
    backgroundColor: palette.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: palette.borderSoft,
  },
  emptyTxt: { marginTop: 10, color: palette.textMuted, fontSize: 13 },
});
