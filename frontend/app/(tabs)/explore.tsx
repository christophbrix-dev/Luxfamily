import { Ionicons } from "@expo/vector-icons";
import { openMaps } from "@/src/utils/openMaps";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
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
  type MapPlace,
  type MapView,
  type MapEvent,
} from "@/src/components/LeafletMap";
import { useApp } from "@/src/contexts/AppContext";
import { storage } from "@/src/utils/storage";
import { CANTONS, type Canton } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { pickLang } from "@/src/i18n/pickLang";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { useUserLocation } from "@/src/hooks/useUserLocation";
import { api, type ApiEventSummary, type ApiPlace, type PlaceLabels, type PlacesMeta } from "@/src/utils/api";
import { ageWindow, dateWindow, radiusWindow } from "@/src/utils/eventQuery";

export default function Explore() {
  const { palette, shadow, effective } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang } = useApp();
  // Never prompts on mount — it picks up a permission granted earlier, and the
  // prompt only ever follows the user pressing a radius chip.
  const { coords, request: requestLocation } = useUserLocation();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [canton, setCanton] = useState<Canton | null>(null);

  const [events, setEvents] = useState<ApiEventSummary[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  // The filter sheet goes to the server; canton and the search box stay here.
  //
  // Splitting them is deliberate. The canton pills carry a count each, and a
  // count only means something when it is drawn from everything the other
  // filters allow — ask the server for one canton and every pill shows its own
  // selection. The search box would otherwise cost a request per keystroke,
  // and it now searches a complete set rather than a truncated one, so there
  // is nothing left for the server to add.
  const load = useCallback(async () => {
    setLoadError(false);
    try {
      setEvents(await api.publicEvents({
        category: filters.category,
        type: filters.type,
        wheelchair: filters.wheelchair,
        sensory: filters.sensoryFriendly,
        freeParking: filters.freeParking,
        ...ageWindow(filters.age),
        ...dateWindow(filters.date),
        ...radiusWindow(filters.distance, coords),
      }));
    } catch {
      setLoadError(true);
    }
  }, [filters, coords]);

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
  const filtered = useMemo<ApiEventSummary[]>(() => {
    if (!events) return [];
    const q = query.trim().toLowerCase();
    return events.filter((e) => {
      // Only the two the server was not asked for. Everything else has
      // already been applied to the whole calendar rather than to a page of
      // it — including the date chip, which used to be drawn, counted in the
      // badge, and then never applied to anything at all.
      if (canton && e.canton !== canton) return false;
      if (q) {
        const hay = `${pickLang(e.title, lang) ?? ""} ${pickLang(e.short, lang) ?? ""} ${e.town ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [events, canton, query, lang]);

  const activeFilterCount =
    (filters.age !== "All" ? 1 : 0) +
    (filters.type !== "All" ? 1 : 0) +
    filters.category.length +
    (filters.date !== "Anytime" ? 1 : 0) +
    // Counted only when it is actually in effect. Counting a radius the app
    // cannot apply would put a number on the badge for a filter that narrows
    // nothing — which is precisely what the date chip used to do.
    (filters.distance !== "Anywhere" && coords ? 1 : 0) +
    (filters.wheelchair ? 1 : 0) +
    (filters.sensoryFriendly ? 1 : 0) +
    (filters.freeParking ? 1 : 0) +
    (canton ? 1 : 0);

  // ---------------------------------------------------------------------
  // What the map is showing.
  //
  // The map carries four different things now — events, places, hiking trails
  // and cycle routes — and 4,772 of the places are nature and picnic spots.
  // Somebody looking for a bike ride does not want the country's every bench
  // drawn over it, and somebody planning a Saturday does not want 375 cycle
  // routes across their events.
  //
  // Switches, not a filter sheet: this is about what is drawn, and the answer
  // belongs one tap away from the drawing.
  // ---------------------------------------------------------------------
  type LayerKey = "events" | "places" | "hiking" | "cycling";
  const ALL_LAYERS: LayerKey[] = ["events", "places", "hiking", "cycling"];
  const LAYERS_KEY = "lux.map.layers";

  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    events: true, places: true, hiking: true, cycling: true,
  });

  // Stored as the names that are on, comma separated — the storage helper
  // takes only a string, a number or a boolean, and a list of names survives
  // a layer being added later without turning it off for everyone.
  useEffect(() => {
    storage.getItem(LAYERS_KEY, "").then((saved) => {
      if (!saved) return;
      const on = new Set(String(saved).split(","));
      setLayers((current) => {
        const next = { ...current };
        for (const key of ALL_LAYERS) if (on.has(key) !== next[key]) next[key] = on.has(key);
        return next;
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleLayer = useCallback((key: LayerKey) => {
    setLayers((current) => {
      const next = { ...current, [key]: !current[key] };
      void storage.setItem(
        LAYERS_KEY,
        ALL_LAYERS.filter((k) => next[k]).join(","),
      );
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Routes carry a shape; asking for shapes nobody draws is 70 KB wasted. */
  const wantsRoutes = layers.hiking || layers.cycling;

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
    mapRef.current?.setEvents(layers.events ? markers : []);
  }, [filtered, mapReady, lang, layers.events]);

  // ---------------------------------------------------------------------
  // Places on the map.
  //
  // The map carried only events, and events are the half of our data with the
  // worse coordinates — 80.9 % of them know a town and nothing else. Meanwhile
  // 7,856 OpenStreetMap places sat unused, each with a real position: 1,383
  // playgrounds, the picnic spots, the PLOMM Kannermusée. Zooming to a street
  // showed an empty street.
  //
  // They are fetched for whatever the map is looking at, and only once it is
  // close enough to mean something: all 7,856 pins over the whole country
  // would be a green smear, and it would cost a request that answers nothing.
  // ---------------------------------------------------------------------
  const PLACES_FROM_ZOOM = 11;
  const viewRef = useRef<MapView | null>(null);

  // The taxonomy's own translations, so a pin says "Spillplaz" rather than the
  // raw OpenStreetMap tag `playground`.
  const [placesMeta, setPlacesMeta] = useState<PlacesMeta | null>(null);
  useEffect(() => {
    api.placesMeta().then(setPlacesMeta).catch(() => setPlacesMeta(null));
  }, []);

  const kindLabel = useCallback(
    (kind: string): string => {
      const entry: PlaceLabels | undefined = placesMeta?.categories?.[kind];
      if (!entry) return "";   // no invented label for a tag we do not know
      if (lang === "lb") return entry.label_lb || entry.label_de;
      if (lang === "de") return entry.label_de;
      if (lang === "fr") return entry.label_fr;
      return entry.label_en;
    },
    [placesMeta, lang],
  );

  const onViewChanged = useCallback(async (view: MapView) => {
    viewRef.current = view;
    if (view.zoom < PLACES_FROM_ZOOM) {
      mapRef.current?.setPlaces([]);
      return;
    }
    try {
      const rows = await api.osmPlaces({
        near: { lat: view.lat, lng: view.lng },
        // Only when a route layer is on. With both off the shapes are 70 KB
        // nobody draws.
        geometry: wantsRoutes,
        // A little wider than the view, so a small drag does not blank the
        // edges before the next request lands.
        radiusKm: Math.min(Math.max(view.radiusKm * 1.3, 2), 100),
        limit: 300,
      });
      // A slow answer for a view the user has already left must not overwrite
      // the pins for the view they are actually looking at.
      if (viewRef.current !== view) return;
      // Sieved here rather than asked for per layer: one request answers every
      // combination of switches, and flipping one redraws without a round trip.
      const wanted = (p: ApiPlace) => {
        if (p.kind === "hiking_route" || p.kind === "nature_trail") return layers.hiking;
        if (p.kind === "cycle_route") return layers.cycling;
        return layers.places;
      };

      const pins: MapPlace[] = rows
        .filter(wanted)
        // A route has no coordinate at all; it is drawn from its shape.
        .filter((p: ApiPlace) => (p.lat !== null && p.lng !== null) || p.path_parts?.length)
        .map((p: ApiPlace) => ({
          id: p.id,
          lat: (p.lat ?? 0) as number,
          lng: (p.lng ?? 0) as number,
          name: p.name,
          group: p.group,
          kindLabel: kindLabel(p.kind),
          btnLabel: t("openInMaps", lang),
          pathParts: p.path_parts,
        }));
      mapRef.current?.setPlaces(pins);
    } catch {
      // Keep whatever is on the map; a failed request is not an empty country.
    }
  }, [lang, kindLabel, layers, wantsRoutes]);

  // Tapping a place opens it where the rest of the app opens places — there is
  // no detail screen for an OSM entry, and inventing one here would promise
  // information we do not hold.
  const onPlaceTap = useCallback((_id: string, lat: number, lng: number) => {
    openMaps(lat, lng);
  }, []);

  // A switch flipped is not a new view, so onViewChanged does not fire by
  // itself. Re-asking with the view we last saw redraws with the new choice.
  useEffect(() => {
    if (viewRef.current) void onViewChanged(viewRef.current);
  }, [layers, onViewChanged]);

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

  // Several events sharing one coordinate. The map used to fan these into a
  // ring at maximum zoom, which drew distinct places where there is one — most
  // of our events carry only a town name. Now the map says how many it holds
  // and the list says which, without inventing positions for any of them.
  const [atOneSpot, setAtOneSpot] = useState<ApiEventSummary[] | null>(null);

  const onClusterTap = useCallback(
    (ids: string[]) => {
      const wanted = new Set(ids);
      // Order as the list below has them, not as the map happened to hand them
      // over: that order is MarkerCluster's internal one and means nothing.
      const rows = filtered.filter((e) => wanted.has(e.id));
      if (rows.length > 0) setAtOneSpot(rows);
    },
    [filtered],
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

        {/* What the map draws. Above it, because it is about the drawing. */}
        <View style={styles.layerRow}>
          <Text style={styles.layerLabel}>{t("onTheMap", lang)}</Text>
          <View style={styles.layerChips}>
            {([
              ["events", t("events", lang)],
              ["places", t("places", lang)],
              ["hiking", t("hikingTrails", lang)],
              ["cycling", t("cycleRoutes", lang)],
            ] as [LayerKey, string][]).map(([key, label]) => (
              <TouchableOpacity
                key={key}
                onPress={() => toggleLayer(key)}
                activeOpacity={0.8}
                accessibilityRole="switch"
                accessibilityState={{ checked: layers[key] }}
                accessibilityLabel={label}
                style={[styles.layerChip, layers[key] && styles.layerChipOn]}
                testID={`map-layer-${key}`}
              >
                <View style={[styles.layerDot, layers[key] && styles.layerDotOn]} />
                <Text style={[styles.layerChipTxt, layers[key] && styles.layerChipTxtOn]}>
                  {label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* ------------------------------------------------------------ */}
        {/* Real interactive map — pinch/scroll to street-level zoom.    */}
        {/* ------------------------------------------------------------ */}
        <View style={styles.mapCard} testID="explore-map-card">
          <LeafletMap
            ref={mapRef}
            style={styles.mapInner}
            onReady={() => setMapReady(true)}
            onMarkerTap={onMarkerTap}
            onClusterTap={onClusterTap}
            onPlaceTap={onPlaceTap}
            onViewChanged={onViewChanged}
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
        hasLocation={coords !== null}
        onRequestLocation={requestLocation}
      />

      {/* What used to be a ring of pins around a village. */}
      <Modal
        animationType="slide"
        transparent
        visible={atOneSpot !== null}
        onRequestClose={() => setAtOneSpot(null)}
        statusBarTranslucent
      >
        <Pressable style={styles.spotBackdrop} onPress={() => setAtOneSpot(null)} />
        <View style={styles.spotSheet} testID="same-spot-sheet">
          <View style={styles.spotHandle} />
          <Text style={styles.spotTitle}>
            {t("eventsAtThisSpot", lang)}
            {atOneSpot ? ` (${atOneSpot.length})` : ""}
          </Text>
          <Text style={styles.spotNote}>{t("sameSpotNote", lang)}</Text>
          <ScrollView style={styles.spotList} showsVerticalScrollIndicator={false}>
            {(atOneSpot ?? []).map((e) => (
              <TouchableOpacity
                key={e.id}
                style={styles.spotRow}
                onPress={() => {
                  setAtOneSpot(null);
                  router.push(`/detail/${e.id}` as never);
                }}
                testID={`same-spot-${e.id}`}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.spotRowTitle} numberOfLines={2}>
                    {pickLang(e.title, lang) ?? e.title.en}
                  </Text>
                  <Text style={styles.spotRowMeta}>
                    {e.start_date}
                    {e.town ? ` · ${e.town}` : ""}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </Modal>
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
  // The map's layer switches. A dot rather than a tick: it is the colour the
  // layer draws with, so the row doubles as the map's legend.
  layerRow: { paddingHorizontal: 20, paddingBottom: 10, gap: 8 },
  layerLabel: {
    fontSize: 12, fontWeight: "700", letterSpacing: 0.6,
    textTransform: "uppercase", color: palette.textMuted,
  },
  layerChips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  layerChip: {
    flexDirection: "row", alignItems: "center", gap: 7,
    paddingVertical: 7, paddingHorizontal: 12,
    borderRadius: 999, borderWidth: 1,
    borderColor: palette.border, backgroundColor: palette.surface,
  },
  layerChipOn: { borderColor: palette.primary, backgroundColor: palette.primaryLight },
  layerDot: {
    width: 9, height: 9, borderRadius: 999,
    backgroundColor: palette.border,
  },
  layerDotOn: { backgroundColor: palette.primary },
  layerChipTxt: { fontSize: 13, color: palette.textSecondary },
  layerChipTxtOn: { color: palette.primaryDark, fontWeight: "700" },
  // The sheet that replaced the ring of pins.
  spotBackdrop: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.45)" },
  spotSheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    maxHeight: "70%",
    backgroundColor: palette.surface,
    borderTopLeftRadius: radii.xxl,
    borderTopRightRadius: radii.xxl,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 28,
    ...shadow.card,
  },
  spotHandle: {
    width: 56,
    height: 5,
    borderRadius: 999,
    backgroundColor: palette.border,
    alignSelf: "center",
    marginBottom: 14,
  },
  spotTitle: { fontSize: 18, fontWeight: "700", color: palette.textPrimary },
  spotNote: {
    fontSize: 12,
    color: palette.textSecondary,
    lineHeight: 17,
    marginTop: 4,
    marginBottom: 12,
  },
  spotList: { flexGrow: 0 },
  spotRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: palette.border,
  },
  spotRowTitle: { fontSize: 15, fontWeight: "600", color: palette.textPrimary },
  spotRowMeta: { fontSize: 12, color: palette.textSecondary, marginTop: 2 },
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
