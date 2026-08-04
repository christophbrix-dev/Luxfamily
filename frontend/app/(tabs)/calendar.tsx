import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppCard } from "@/src/components/AppCard";
import { Chip } from "@/src/components/Chip";
import { useApp } from "@/src/contexts/AppContext";
import { PLACES } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { palette } from "@/src/theme";

export default function Calendar() {
  const router = useRouter();
  const { lang, bookings } = useApp();
  const [chip, setChip] = useState<"weekend" | "7days" | "june" | "bookings">("weekend");

  // Group static demo content by date for the weekend / 7-day view.
  // Labels are formatted per-locale below so the calendar reads naturally
  // in DE/FR too (e.g. "Samstag, 25. Mai").
  const fmtDate = (iso: string) => {
    const d = new Date(iso);
    const locale = lang === "de" ? "de-DE" : lang === "fr" ? "fr-FR" : "en-GB";
    return d.toLocaleDateString(locale, {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  };
  const groups: { label: string; items: typeof PLACES }[] = [
    { label: fmtDate("2026-05-25"), items: [PLACES[2], PLACES[1], PLACES[4]] },
    { label: fmtDate("2026-05-26"), items: [PLACES[0], PLACES[3]] },
    { label: fmtDate("2026-06-01"), items: [PLACES[5], PLACES[6]] },
  ];

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
            label={t("june", lang)}
            active={chip === "june"}
            onPress={() => setChip("june")}
            testID="cal-chip-june"
          />
          <Chip
            label={`${t("yourBooking", lang)} (${bookings.length})`}
            active={chip === "bookings"}
            onPress={() => setChip("bookings")}
            testID="cal-chip-bookings"
          />
        </ScrollView>

        {showGroups ? (
          <View style={styles.groupList}>
            {groups.map((g) => (
              <View key={g.label} style={styles.group}>
                <Text style={styles.groupLabel}>{g.label.toUpperCase()}</Text>
                <View style={styles.groupItems}>
                  {g.items.filter(Boolean).map((p) => (
                    <AppCard
                      key={p.id}
                      item={p}
                      onPress={() => router.push(`/detail/${p.id}`)}
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
              const p = PLACES.find((x) => x.id === b.placeId);
              if (!p) return null;
              return (
                <TouchableOpacity
                  key={b.id}
                  onPress={() => router.push(`/detail/${p.id}`)}
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
                    <Text style={styles.bookingTitle}>{p.title[lang]}</Text>
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

const styles = StyleSheet.create({
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
  chipRowOuter: { marginTop: 18, marginBottom: 4, maxHeight: 56, marginHorizontal: -20 },
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
