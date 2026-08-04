import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState, useMemo } from "react";
import { Image, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import { PLACES } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

const DATE_OPTS = (() => {
  const out: { label: string; iso: string; day: string; month: string }[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    out.push({
      label: d.toLocaleDateString(undefined, { weekday: "short" }),
      iso: d.toISOString(),
      day: String(d.getDate()),
      month: d.toLocaleDateString(undefined, { month: "short" }),
    });
  }
  return out;
})();

export default function Book() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { lang, addBooking } = useApp();
  const place = PLACES.find((p) => p.id === Number(id));

  const [dateIdx, setDateIdx] = useState(1);
  const [adults, setAdults] = useState(2);
  const [children, setChildren] = useState(1);
  const [confirmed, setConfirmed] = useState(false);

  if (!place) {
    return (
      <SafeAreaView style={styles.safe}>
        <Text>{t("notFound", lang)}</Text>
      </SafeAreaView>
    );
  }

  const total = adults * place.priceAdult + children * place.priceChild;

  const onConfirm = () => {
    addBooking({
      placeId: place.id,
      date: DATE_OPTS[dateIdx].iso,
      adults,
      children,
      total,
    });
    setConfirmed(true);
  };

  if (confirmed) {
    return (
      <SafeAreaView style={[styles.safe, styles.confirmWrap]} edges={["top", "bottom"]}>
        <View style={styles.confirmIcon}>
          <Ionicons name="checkmark" size={48} color="#fff" />
        </View>
        <Text style={styles.confirmTitle}>{t("bookingConfirmed", lang)}</Text>
        <Text style={styles.confirmSub}>{t("bookingConfirmedSub", lang)}</Text>

        <View style={styles.confirmCard}>
          <Image source={{ uri: place.image }} style={styles.confirmImg} />
          <View style={{ padding: 14, gap: 6 }}>
            <Text style={styles.confirmCardTitle}>{place.title[lang]}</Text>
            <Text style={styles.confirmCardMeta}>
              {new Date(DATE_OPTS[dateIdx].iso).toLocaleDateString(undefined, {
                weekday: "long",
                day: "numeric",
                month: "long",
              })}
            </Text>
            <Text style={styles.confirmCardMeta}>
              {adults} {t("numAdults", lang)} · {children} {t("numChildren", lang)}
            </Text>
            <Text style={styles.confirmTotal}>EUR {total.toFixed(2)}</Text>
          </View>
        </View>

        <TouchableOpacity
          onPress={() => router.replace("/(tabs)/calendar")}
          style={styles.confirmBtn}
          testID="booking-done-btn"
        >
          <Text style={styles.confirmBtnTxt}>{t("backToHome", lang)}</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.backBtn}
          testID="book-back-btn"
        >
          <Ionicons name="chevron-back" size={20} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("bookActivity", lang)}</Text>
        <View style={{ width: 42 }} />
      </View>

      <ScrollView
        contentContainerStyle={{ padding: 20, paddingBottom: insets.bottom + 140 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.placeRow}>
          <Image source={{ uri: place.image }} style={styles.placeImg} />
          <View style={{ flex: 1 }}>
            <Text style={styles.placeTitle} numberOfLines={2}>
              {place.title[lang]}
            </Text>
            <Text style={styles.placeMeta}>
              {place.town} · {place.time}
            </Text>
            <Text style={styles.placeMeta}>{place.priceLabel[lang]}</Text>
          </View>
        </View>

        <Text style={styles.sectionLabel}>{t("selectDate", lang)}</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ gap: 10 }}
          style={{ marginHorizontal: -20, paddingHorizontal: 20 }}
        >
          {DATE_OPTS.map((d, i) => {
            const active = i === dateIdx;
            return (
              <TouchableOpacity
                key={d.iso}
                onPress={() => setDateIdx(i)}
                style={[styles.dateChip, active && styles.dateChipActive]}
                testID={`date-chip-${i}`}
              >
                <Text style={[styles.dateLbl, active && styles.dateLblActive]}>{d.label}</Text>
                <Text style={[styles.dateDay, active && styles.dateDayActive]}>{d.day}</Text>
                <Text style={[styles.dateMonth, active && styles.dateMonthActive]}>{d.month}</Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        <Text style={styles.sectionLabel}>{t("guests", lang)}</Text>
        <View style={styles.card}>
          <Stepper
            label={t("numAdults", lang)}
            sub={`${t("eachLabel", lang)} EUR ${place.priceAdult}`}
            value={adults}
            onChange={setAdults}
            min={1}
            testID="adults"
          />
          <View style={styles.divider} />
          <Stepper
            label={t("numChildren", lang)}
            sub={`${t("eachLabel", lang)} EUR ${place.priceChild}`}
            value={children}
            onChange={setChildren}
            min={0}
            testID="children"
          />
        </View>

        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>{t("total", lang)}</Text>
          <Text style={styles.totalValue} testID="book-total">
            EUR {total.toFixed(2)}
          </Text>
        </View>
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) }]}>
        <TouchableOpacity
          onPress={onConfirm}
          style={styles.confirmCta}
          testID="confirm-booking-btn"
        >
          <Text style={styles.confirmCtaTxt}>{t("confirmBooking", lang)}</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function Stepper({
  label,
  sub,
  value,
  onChange,
  min,
  testID,
}: {
  label: string;
  sub: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  testID?: string;
}) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <View style={styles.stepperRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.stepperLbl}>{label}</Text>
        <Text style={styles.stepperSub}>{sub}</Text>
      </View>
      <View style={styles.stepper}>
        <TouchableOpacity
          onPress={() => onChange(Math.max(min, value - 1))}
          style={styles.stepperBtn}
          testID={`${testID}-minus`}
        >
          <Ionicons name="remove" size={16} color={palette.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.stepperVal} testID={`${testID}-val`}>
          {value}
        </Text>
        <TouchableOpacity
          onPress={() => onChange(value + 1)}
          style={styles.stepperBtn}
          testID={`${testID}-plus`}
        >
          <Ionicons name="add" size={16} color={palette.textPrimary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  header: {
    paddingHorizontal: 18,
    paddingTop: 8,
    paddingBottom: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  backBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
    ...shadow.soft,
  },
  headerTitle: { fontSize: 17, fontWeight: "700", color: palette.textPrimary },
  placeRow: {
    flexDirection: "row",
    gap: 12,
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    padding: 12,
    ...shadow.soft,
  },
  placeImg: { width: 76, height: 76, borderRadius: 18 },
  placeTitle: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  placeMeta: { fontSize: 12, color: palette.textSecondary, marginTop: 4 },
  sectionLabel: {
    marginTop: 22,
    marginBottom: 10,
    fontSize: 13,
    fontWeight: "700",
    color: palette.textSecondary,
  },
  dateChip: {
    width: 72,
    paddingVertical: 12,
    borderRadius: 18,
    backgroundColor: palette.surface,
    alignItems: "center",
    ...shadow.soft,
  },
  dateChipActive: {
    backgroundColor: palette.primary,
  },
  dateLbl: { fontSize: 11, color: palette.textSecondary, fontWeight: "600" },
  dateLblActive: { color: "rgba(255,255,255,0.85)" },
  dateDay: { fontSize: 20, fontWeight: "800", color: palette.textPrimary, marginTop: 2 },
  dateDayActive: { color: "#fff" },
  dateMonth: {
    fontSize: 10,
    color: palette.textMuted,
    fontWeight: "600",
    textTransform: "uppercase",
  },
  dateMonthActive: { color: "rgba(255,255,255,0.85)" },
  card: {
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    padding: 16,
    ...shadow.soft,
  },
  stepperRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8 },
  stepperLbl: { fontSize: 15, fontWeight: "700", color: palette.textPrimary },
  stepperSub: { fontSize: 12, color: palette.textSecondary, marginTop: 2 },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surfaceMuted,
    borderRadius: 999,
    paddingHorizontal: 4,
  },
  stepperBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#fff",
    justifyContent: "center",
    alignItems: "center",
    ...shadow.soft,
  },
  stepperVal: { fontSize: 15, fontWeight: "700", minWidth: 20, textAlign: "center" },
  divider: { height: 1, backgroundColor: palette.borderSoft, marginVertical: 4 },
  totalCard: {
    marginTop: 18,
    backgroundColor: palette.primary,
    borderRadius: radii.xl,
    padding: 18,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    ...shadow.emerald,
  },
  totalLabel: { fontSize: 13, color: "rgba(255,255,255,0.85)", fontWeight: "600" },
  totalValue: { fontSize: 22, color: "#fff", fontWeight: "800" },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 18,
    paddingTop: 14,
    backgroundColor: "rgba(255,255,255,0.98)",
    borderTopWidth: 1,
    borderTopColor: palette.borderSoft,
  },
  confirmCta: {
    backgroundColor: palette.primary,
    borderRadius: 16,
    paddingVertical: 16,
    alignItems: "center",
    ...shadow.emerald,
  },
  confirmCtaTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },

  confirmWrap: {
    alignItems: "center",
    paddingHorizontal: 24,
    paddingTop: 36,
  },
  confirmIcon: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...shadow.emerald,
  },
  confirmTitle: {
    marginTop: 22,
    fontSize: 24,
    fontWeight: "800",
    color: palette.textPrimary,
    textAlign: "center",
  },
  confirmSub: {
    marginTop: 8,
    color: palette.textSecondary,
    textAlign: "center",
    lineHeight: 20,
  },
  confirmCard: {
    width: "100%",
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    marginTop: 28,
    overflow: "hidden",
    ...shadow.card,
  },
  confirmImg: { width: "100%", height: 140 },
  confirmCardTitle: { fontSize: 16, fontWeight: "700", color: palette.textPrimary },
  confirmCardMeta: { fontSize: 13, color: palette.textSecondary },
  confirmTotal: { fontSize: 18, fontWeight: "800", color: palette.primary, marginTop: 4 },
  confirmBtn: {
    marginTop: "auto",
    width: "100%",
    backgroundColor: palette.primary,
    borderRadius: 16,
    paddingVertical: 16,
    alignItems: "center",
    ...shadow.emerald,
  },
  confirmBtnTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
});
