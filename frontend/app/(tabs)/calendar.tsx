import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppCard } from "@/src/components/AppCard";
import { Chip } from "@/src/components/Chip";
import { useApp } from "@/src/contexts/AppContext";
import type { Place } from "@/src/data/places";
import { usePlaces } from "@/src/hooks/useLivePlaces";
import { detailHref } from "@/src/utils/toPlace";
import { t } from "@/src/i18n/strings";
import { pickLang } from "@/src/i18n/pickLang";
import { type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

export default function Calendar() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const { lang, bookings } = useApp();
  const [chip, setChip] = useState<"weekend" | "7days" | "month" | "bookings">("weekend");
  const { places, loading } = usePlaces();

  // Labels are formatted per-locale so the calendar reads naturally in DE/FR
  // too (e.g. "Samstag, 25. Mai"). Luxembourgish borrows the German locale,
  // matching the fallback used everywhere else.
  const locale = lang === "de" || lang === "lb" ? "de-DE" : lang === "fr" ? "fr-FR" : "en-GB";
  const fmtDate = useCallback(
    (iso: string) =>
      new Date(iso).toLocaleDateString(locale, {
        weekday: "long",
        day: "numeric",
        month: "long",
      }),
    [locale],
  );

  /**
   * The window the selected chip covers, as inclusive YYYY-MM-DD bounds.
   *
   * Compared as strings: the dates arrive from the API in that format, and
   * string comparison orders them correctly without building Date objects that
   * would drag the device timezone into it.
   */
  const range = useMemo(() => {
    const iso = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
      ).padStart(2, "0")}`;
    const today = new Date();

    if (chip === "weekend") {
      // The coming Saturday and Sunday. On a Saturday that means today and
      // tomorrow; on a Sunday, today alone rather than a week away.
      const day = today.getDay(); // 0 = Sunday
      const sat = new Date(today);
      if (day === 0) {
        return { from: iso(today), to: iso(today) };
      }
      sat.setDate(today.getDate() + ((6 - day + 7) % 7));
      const sun = new Date(sat);
      sun.setDate(sat.getDate() + 1);
      return { from: iso(sat), to: iso(sun) };
    }

    if (chip === "7days") {
      const end = new Date(today);
      end.setDate(today.getDate() + 7);
      return { from: iso(today), to: iso(end) };
    }

    // Remainder of the current month.
    const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    return { from: iso(today), to: iso(end) };
  }, [chip]);

  /** Events inside the window, grouped by day and in date order. */
  const groups = useMemo(() => {
    const byDay = new Map<string, Place[]>();
    for (const p of places ?? []) {
      if (!p.startDate || p.startDate < range.from || p.startDate > range.to) continue;
      const bucket = byDay.get(p.startDate) ?? [];
      bucket.push(p);
      byDay.set(p.startDate, bucket);
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, items]) => ({ label: fmtDate(date), items }));
  }, [places, range, fmtDate]);

  const showGroups = chip !== "bookings";

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <Text style={styles.h1}>{t("calendar", lang)}</Text>
          <TouchableOpacity style={styles.iconBtn} testID="calendar-icon-btn">
            <Ionicons name="calendar-outline" size={20} color={palette.textPrimary} />
          </TouchableOpacity>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
          style={styles.chipRowOuter}
        >
          <Chip
            label={t("thisWeekend", lang)}
            active={chip === "weekend"}
            onPress={() => setChip("weekend")}
            testID="cal-chip-weekend"
          />
          <Chip
            label={t("next7Days", lang)}
            active={chip === "7days"}
            onPress={() => setChip("7days")}
            testID="cal-chip-7days"
          />
          <Chip
            label={new Date().toLocaleDateString(locale, { month: "long" })}
            active={chip === "month"}
            onPress={() => setChip("month")}
            testID="cal-chip-june"
          />
          <Chip
            label={`${t("yourBooking", lang)} (${bookings.length})`}
            active={chip === "bookings"}
            onPress={() => setChip("bookings")}
            testID="cal-chip-bookings"
          />
        </ScrollView>

        {showGroups && loading ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 32 }} />
        ) : showGroups && groups.length === 0 ? (
          // A window with nothing in it is a normal answer, not an error. Most
          // of the catalogue is undated venues rather than dated events.
          <View style={styles.groupList}>
            <Text style={styles.groupLabel}>{t("noEventsYet", lang).toUpperCase()}</Text>
          </View>
        ) : showGroups ? (
          <View style={styles.groupList}>
            {groups.map((g) => (
              <View key={g.label} style={styles.group}>
                <Text style={styles.groupLabel}>{g.label.toUpperCase()}</Text>
                <View style={styles.groupItems}>
                  {g.items.filter(Boolean).map((p) => (
                    <AppCard
                      key={p.id}
                      item={p}
                      onPress={() => router.push(detailHref(p))}
                    />
                  ))}
                </View>
              </View>
            ))}
          </View>
        ) : bookings.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="ticket-outline" size={40} color={palette.textMuted} />
            <Text style={styles.emptyTxt}>{t("noBookingsYet", lang)}</Text>
          </View>
        ) : (
          <View style={styles.bookingList}>
            {bookings.map((b) => {
              const p = (places ?? []).find((x) => x.id === b.placeId);
              if (!p) return null;
              return (
                <TouchableOpacity
                  key={b.id}
                  onPress={() => router.push(detailHref(p))}
                  style={styles.bookingCard}
                  testID={`booking-card-${b.id}`}
                >
                  <View style={styles.bookingDateBox}>
                    <Text style={styles.bookingDateDay}>
                      {new Date(b.date).getDate()}
                    </Text>
                    <Text style={styles.bookingDateMonth}>
                      {new Date(b.date).toLocaleString(undefined, { month: "short" })}
                    </Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.bookingTitle}>{pickLang(p.title, lang)}</Text>
                    <Text style={styles.bookingSub}>
                      {p.town} · {b.adults} {t("numAdults", lang)} · {b.children}{" "}
                      {t("numChildren", lang)}
                    </Text>
                    <Text style={styles.bookingTotal}>EUR {b.total.toFixed(2)}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={palette.textMuted} />
                </TouchableOpacity>
              );
            })}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  scroll: { padding: 20, paddingBottom: 36 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  h1: { fontSize: 30, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  iconBtn: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
    boxShadow: "0px 4px 8px rgba(15, 23, 42, 0.05)",
    elevation: 2,
  },
// flexShrink: 0 because maxHeight does not stop a flex child from being
  // squeezed — it only caps how tall it may grow. React Native Web gives
  // every view flexShrink: 1, so this row collapsed to 10px and the filter
  // chips were simply not on screen.
  chipRowOuter: { marginTop: 18, marginBottom: 4, maxHeight: 56, flexShrink: 0, marginHorizontal: -20 },
  chipRow: { gap: 8, alignItems: "center", height: 56, paddingHorizontal: 20 },
  groupList: { marginTop: 14, gap: 28 },
  group: { gap: 12 },
  groupLabel: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.5,
    color: palette.textMuted,
  },
  groupItems: { gap: 14 },
  empty: { alignItems: "center", padding: 36, gap: 10 },
  emptyTxt: { color: palette.textSecondary },
  bookingList: { marginTop: 14, gap: 12 },
  bookingCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: palette.surface,
    borderRadius: 22,
    padding: 14,
    boxShadow: "0px 4px 12px rgba(15, 23, 42, 0.05)",
    elevation: 2,
  },
  bookingDateBox: {
    width: 56,
    height: 56,
    borderRadius: 14,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  bookingDateDay: { fontSize: 18, fontWeight: "800", color: palette.primaryDark },
  bookingDateMonth: {
    fontSize: 10,
    fontWeight: "700",
    color: palette.primaryDark,
    textTransform: "uppercase",
  },
  bookingTitle: { fontSize: 15, fontWeight: "700", color: palette.textPrimary },
  bookingSub: { fontSize: 12, color: palette.textSecondary, marginTop: 3 },
  bookingTotal: {
    fontSize: 13,
    fontWeight: "700",
    color: palette.primary,
    marginTop: 4,
  },
});
