import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { palette, radii, shadow } from "@/src/theme";
import { api, ApiEvent } from "@/src/utils/api";
import { needsToFilters, rankForProfile } from "@/src/utils/personalization";

type EventGroup = { label: string; items: ApiEvent[] };

function groupByMonth(events: ApiEvent[]): EventGroup[] {
  const map = new Map<string, ApiEvent[]>();
  for (const e of events) {
    const d = new Date(e.start_date);
    const key = d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    const arr = map.get(key) ?? [];
    arr.push(e);
    map.set(key, arr);
  }
  return Array.from(map.entries()).map(([label, items]) => ({ label, items }));
}

export default function EventsTab() {
  const router = useRouter();
  const { lang, userProfile } = useApp();
  const [events, setEvents] = useState<ApiEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Family-needs filters (mirrors the Explore tab).
  const [fWheelchair, setFWheelchair] = useState(false);
  const [fSensory, setFSensory] = useState(false);
  const [fFreeParking, setFFreeParking] = useState(false);

  // Personalization on/off — starts ON if the user has a profile, but the
  // user can flip it off with the "Show all" toggle at the top.
  const [personalizationOn, setPersonalizationOn] = useState(true);

  // Auto-preselect chips from the onboarding profile — but only ONCE per
  // profile change, and only on first mount after hydration. Using a ref
  // guard so returning to the tab after the user manually cleared a chip
  // does not re-check it against their will.
  const appliedFor = useRef<string>("");
  useEffect(() => {
    if (!userProfile.persona || userProfile.persona === "skipped") return;
    if (!personalizationOn) return;
    const key = `${userProfile.persona}:${userProfile.needs.join("|")}`;
    if (appliedFor.current === key) return;
    appliedFor.current = key;
    const preset = needsToFilters(userProfile);
    setFWheelchair(preset.wheelchair);
    setFSensory(preset.sensory);
    setFFreeParking(preset.freeParking);
  }, [userProfile, personalizationOn]);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await api.publicEvents();
      setEvents(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load events");
      setEvents([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const filtered = useMemo(() => {
    if (!events) return [];
    return events.filter((e) => {
      if (fWheelchair && !e.accessibility_wheelchair) return false;
      if (fSensory && !e.sensory_friendly) return false;
      if (fFreeParking && !e.free_parking) return false;
      return true;
    });
  }, [events, fWheelchair, fSensory, fFreeParking]);

  const { forYou, others, isPersonalized } = useMemo(() => {
    if (!personalizationOn) {
      return { forYou: [], others: filtered, isPersonalized: false };
    }
    return rankForProfile(filtered, userProfile);
  }, [filtered, userProfile, personalizationOn]);

  const groups = useMemo(() => groupByMonth(others), [others]);
  const activeFilterCount = [fWheelchair, fSensory, fFreeParking].filter(Boolean).length;
  const hasProfile = !!userProfile.persona && userProfile.persona !== "skipped";

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <View>
          <Text style={styles.h1}>Events</Text>
          <Text style={styles.sub}>
            {events
              ? activeFilterCount > 0
                ? `${filtered.length} of ${events.length} (filtered)`
                : `${events.length} ${events.length === 1 ? "activity" : "activities"}`
              : t("loading", lang)}
          </Text>
        </View>
        <View style={styles.headerBadge}>
          <Ionicons name="calendar" size={16} color={palette.primaryDark} />
        </View>
      </View>

      {events && events.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
        >
          <FilterChip
            label="Wheelchair"
            icon="accessibility-outline"
            active={fWheelchair}
            onPress={() => setFWheelchair((v) => !v)}
          />
          <FilterChip
            label="Sensory friendly"
            icon="ear-outline"
            active={fSensory}
            onPress={() => setFSensory((v) => !v)}
          />
          <FilterChip
            label="Free parking"
            icon="car-outline"
            active={fFreeParking}
            onPress={() => setFFreeParking((v) => !v)}
          />
          {activeFilterCount > 0 && (
            <TouchableOpacity
              style={styles.clearChip}
              onPress={() => {
                setFWheelchair(false);
                setFSensory(false);
                setFFreeParking(false);
              }}
              testID="events-clear-filters"
            >
              <Ionicons name="close-circle" size={14} color={palette.textSecondary} />
              <Text style={styles.clearChipTxt}>Clear</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      ) : null}

      {events === null && !error ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator color={palette.primary} />
        </View>
      ) : error ? (
        <View style={styles.errorWrap}>
          <Ionicons name="cloud-offline-outline" size={36} color={palette.textMuted} />
          <Text style={styles.errorTxt}>{error}</Text>
          <TouchableOpacity onPress={load} style={styles.retryBtn} testID="events-retry-btn">
            <Text style={styles.retryTxt}>Try again</Text>
          </TouchableOpacity>
        </View>
      ) : events.length === 0 ? (
        <ScrollView
          contentContainerStyle={styles.emptyWrap}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          <Ionicons name="leaf-outline" size={44} color={palette.textMuted} />
          <Text style={styles.emptyTitle}>No events yet</Text>
          <Text style={styles.emptyTxt}>
            New events are added by the team and partners. Pull to refresh.
          </Text>
        </ScrollView>
      ) : filtered.length === 0 ? (
        <View style={styles.emptyWrap}>
          <Ionicons name="filter-outline" size={40} color={palette.textMuted} />
          <Text style={styles.emptyTitle}>No matches</Text>
          <Text style={styles.emptyTxt}>Try removing a filter above.</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {isPersonalized && forYou.length > 0 ? (
            <View style={styles.forYouWrap}>
              <View style={styles.forYouHeader}>
                <View style={styles.forYouBadge}>
                  <Ionicons name="sparkles" size={12} color="#065F46" />
                  <Text style={styles.forYouBadgeTxt}>FOR YOU</Text>
                </View>
                <TouchableOpacity
                  onPress={() => setPersonalizationOn(false)}
                  hitSlop={8}
                  testID="events-show-all"
                >
                  <Text style={styles.forYouLink}>Show all</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.forYouSub}>
                Matched to your interests
              </Text>
              <View style={styles.groupItems}>
                {forYou.map((ev) => (
                  <EventRow
                    key={`fy-${ev.id}`}
                    event={ev}
                    lang={lang}
                    onPress={() => router.push(`/event/${ev.id}`)}
                  />
                ))}
              </View>
            </View>
          ) : hasProfile && !personalizationOn ? (
            <TouchableOpacity
              style={styles.enableBanner}
              onPress={() => setPersonalizationOn(true)}
              testID="events-enable-personalization"
            >
              <Ionicons name="sparkles-outline" size={14} color={palette.primaryDark} />
              <Text style={styles.enableBannerTxt}>Turn personalization back on</Text>
            </TouchableOpacity>
          ) : null}
          {groups.map((g) => (
            <View key={g.label} style={styles.group}>
              <Text style={styles.groupLabel}>{g.label.toUpperCase()}</Text>
              <View style={styles.groupItems}>
                {g.items.map((ev) => (
                  <EventRow
                    key={ev.id}
                    event={ev}
                    lang={lang}
                    onPress={() => router.push(`/event/${ev.id}`)}
                  />
                ))}
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function EventRow({
  event,
  lang,
  onPress,
}: {
  event: ApiEvent;
  lang: "en" | "de" | "fr";
  onPress: () => void;
}) {
  const date = new Date(event.start_date);
  const day = date.getDate();
  const month = date.toLocaleDateString(undefined, { month: "short" });

  return (
    <TouchableOpacity
      activeOpacity={0.9}
      onPress={onPress}
      style={styles.row}
      testID={`event-row-${event.id}`}
    >
      <View style={styles.dateBox}>
        <Text style={styles.dateDay}>{day}</Text>
        <Text style={styles.dateMonth}>{month}</Text>
      </View>
      {event.image ? (
        <Image source={{ uri: event.image }} style={styles.thumb} contentFit="cover" />
      ) : (
        <View style={[styles.thumb, styles.thumbPlaceholder]}>
          <Ionicons name="image-outline" size={20} color={palette.textMuted} />
        </View>
      )}
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <Text style={styles.title} numberOfLines={1}>
            {event.title[lang] ?? event.title.en}
          </Text>
          {event.featured ? (
            <View style={featuredStyles.badge}>
              <Ionicons name="star" size={9} color="#92400E" />
              <Text style={featuredStyles.txt}>Sponsored</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.metaRow}>
          <Ionicons name="location-outline" size={11} color={palette.textSecondary} />
          <Text style={styles.metaTxt} numberOfLines={1}>
            {event.town} · {event.canton}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Ionicons name="time-outline" size={11} color={palette.textSecondary} />
          <Text style={styles.metaTxt} numberOfLines={1}>
            {event.time || "—"}
          </Text>
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
    </TouchableOpacity>
  );
}

const featuredStyles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: "#FEF3C7",
  },
  txt: { fontSize: 9, fontWeight: "800", color: "#92400E", letterSpacing: 0.4 },
});

function FilterChip({
  label,
  icon,
  active,
  onPress,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      style={[styles.chip, active && styles.chipActive]}
      testID={`events-filter-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <Ionicons
        name={icon}
        size={14}
        color={active ? "#fff" : palette.textSecondary}
      />
      <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  header: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  h1: { fontSize: 30, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  sub: { color: palette.textSecondary, marginTop: 2, fontSize: 13 },
  headerBadge: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingWrap: { flex: 1, justifyContent: "center", alignItems: "center" },
  errorWrap: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, gap: 10 },
  errorTxt: { color: palette.textSecondary, textAlign: "center" },
  retryBtn: {
    marginTop: 8,
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: palette.primary,
  },
  retryTxt: { color: "#fff", fontWeight: "700" },
  emptyWrap: { padding: 40, alignItems: "center", gap: 10, flexGrow: 1, justifyContent: "center" },
  emptyTitle: { fontSize: 16, fontWeight: "700", color: palette.textPrimary, marginTop: 6 },
  emptyTxt: { color: palette.textSecondary, textAlign: "center", maxWidth: 280, lineHeight: 20 },
  scroll: { padding: 20, paddingBottom: 32 },
  group: { marginBottom: 26 },
  groupLabel: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.5,
    color: palette.textMuted,
    marginBottom: 10,
  },
  groupItems: { gap: 10 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: 12,
    ...shadow.soft,
  },
  dateBox: {
    width: 50,
    height: 56,
    borderRadius: 12,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  dateDay: { fontSize: 18, fontWeight: "800", color: palette.primaryDark },
  dateMonth: {
    fontSize: 10,
    fontWeight: "700",
    color: palette.primaryDark,
    textTransform: "uppercase",
  },
  thumb: { width: 56, height: 56, borderRadius: 12 },
  thumbPlaceholder: {
    backgroundColor: palette.surfaceMuted,
    justifyContent: "center",
    alignItems: "center",
  },
  title: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  metaRow: { flexDirection: "row", gap: 4, alignItems: "center", marginTop: 2 },
  metaTxt: { fontSize: 11, color: palette.textSecondary },
  chipsRow: {
    paddingHorizontal: 20,
    paddingBottom: 12,
    gap: 8,
    flexDirection: "row",
    alignItems: "center",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: palette.surfaceMuted,
    borderWidth: 1,
    borderColor: palette.border,
  },
  chipActive: {
    backgroundColor: palette.primary,
    borderColor: palette.primary,
  },
  chipTxt: {
    fontSize: 12,
    fontWeight: "600",
    color: palette.textSecondary,
  },
  chipTxtActive: { color: "#fff" },
  clearChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 7,
    marginLeft: 4,
  },
  clearChipTxt: {
    fontSize: 12,
    fontWeight: "600",
    color: palette.textSecondary,
  },
  forYouWrap: {
    marginHorizontal: 20,
    marginTop: 4,
    marginBottom: 12,
    padding: 14,
    borderRadius: 20,
    backgroundColor: "#F0FDF4",
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  forYouHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  forYouBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: "#D1FAE5",
  },
  forYouBadgeTxt: {
    fontSize: 10,
    fontWeight: "800",
    color: "#065F46",
    letterSpacing: 0.5,
  },
  forYouLink: {
    fontSize: 12,
    fontWeight: "600",
    color: "#065F46",
  },
  forYouSub: {
    fontSize: 12,
    color: "#047857",
    marginBottom: 10,
  },
  enableBanner: {
    marginHorizontal: 20,
    marginTop: 4,
    marginBottom: 8,
    padding: 10,
    borderRadius: 12,
    backgroundColor: "#F0FDF4",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  enableBannerTxt: {
    fontSize: 12,
    fontWeight: "600",
    color: "#065F46",
  },
});
