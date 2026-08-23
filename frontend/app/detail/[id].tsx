import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useMemo } from "react";
import { Image, Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { MapPreview } from "@/src/components/MapPreview";
import { useApp } from "@/src/contexts/AppContext";
import { PLACES } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { pickLang } from "@/src/i18n/pickLang";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

export default function Detail() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { lang, saved, toggleSave } = useApp();

  const place = PLACES.find((p) => p.id === Number(id));
  if (!place) {
    return (
      <SafeAreaView style={styles.safe}>
        <Text>Not found</Text>
      </SafeAreaView>
    );
  }
  const isSaved = saved.includes(place.id);

  const openMaps = () => {
    const url = `https://www.openstreetmap.org/?mlat=${place.lat}&mlon=${place.lng}#map=16/${place.lat}/${place.lng}`;
    Linking.openURL(url);
  };

  return (
    <View style={styles.safe}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: insets.bottom + 120 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.hero}>
          <Image source={{ uri: place.image }} style={StyleSheet.absoluteFillObject} />
          <LinearGradient
            colors={["rgba(0,0,0,0.35)", "rgba(0,0,0,0)", "rgba(0,0,0,0.55)"]}
            style={StyleSheet.absoluteFill}
          />
          <View style={[styles.heroTop, { paddingTop: insets.top + 8 }]}>
            <TouchableOpacity
              onPress={() => router.back()}
              style={styles.roundBtn}
              testID="detail-back-btn"
            >
              <Ionicons name="chevron-back" size={20} color={palette.textPrimary} />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => toggleSave(place.id)}
              style={styles.roundBtn}
              testID="detail-save-btn"
            >
              <Ionicons
                name={isSaved ? "heart" : "heart-outline"}
                size={20}
                color={isSaved ? palette.red : palette.textPrimary}
              />
            </TouchableOpacity>
          </View>

          <View style={styles.heroBottom}>
            <View style={styles.heroBadgeRow}>
              <View style={styles.typeBadge}>
                <Text style={styles.typeBadgeTxt}>{place.type}</Text>
              </View>
              <View style={styles.ratingBadge}>
                <Ionicons name="star" size={12} color="#FBBF24" />
                <Text style={styles.ratingTxt}>{place.rating.toFixed(1)}</Text>
              </View>
            </View>
            <Text style={styles.heroTitle}>{pickLang(place.title, lang)}</Text>
            <Text style={styles.heroSub}>{pickLang(place.short, lang)}</Text>
          </View>
        </View>

        <View style={styles.body}>
          <View style={styles.weatherPill}>
            <Ionicons name="partly-sunny-outline" size={14} color="#92400E" />
            <Text style={styles.weatherTxt}>
              {t("greatForToday", lang)}: {pickLang(place.weatherFit, lang)}
            </Text>
          </View>

          <View style={styles.statsGrid}>
            <StatCard icon="people-outline" label={t("age", lang)} value={place.age} />
            <StatCard icon="time-outline" label={t("date", lang)} value={place.time} />
            <StatCard icon="pricetag-outline" label="Price" value={pickLang(place.priceLabel, lang)} />
            <StatCard
              icon="accessibility-outline"
              label="Access"
              value={pickLang(place.accessibility, lang)}
            />
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("location", lang)}</Text>
            <View style={styles.locationRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.locationTxt}>{place.town}, Luxembourg</Text>
                <Text style={styles.locationSub}>
                  {place.distanceKm !== undefined
                    ? `${place.distanceKm.toFixed(1)} km ${t("fromYou", lang)}`
                    : place.town}
                </Text>
              </View>
              <TouchableOpacity
                onPress={openMaps}
                style={styles.mapsBtn}
                testID="detail-open-maps-btn"
              >
                <Ionicons name="navigate" size={18} color={palette.primaryDark} />
              </TouchableOpacity>
            </View>
            <View style={{ marginTop: 14, borderRadius: 18, overflow: "hidden" }}>
              <MapPreview lat={place.lat} lng={place.lng} label={pickLang(place.title, lang)} height={170} />
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t("about", lang)}</Text>
            <Text style={styles.about}>{pickLang(place.description, lang)}</Text>
            <View style={styles.tagRow}>
              {place.category.map((tag) => (
                <View key={tag} style={styles.tag}>
                  <Text style={styles.tagTxt}>{tag}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) }]}>
        <TouchableOpacity
          onPress={openMaps}
          style={styles.footerSecondary}
          testID="footer-open-maps-btn"
        >
          <Text style={styles.footerSecondaryTxt}>{t("openInMaps", lang)}</Text>
        </TouchableOpacity>
        {place.bookable ? (
          <TouchableOpacity
            onPress={() => router.push(`/book/${place.id}`)}
            style={styles.footerPrimary}
            testID="footer-book-btn"
          >
            <Text style={styles.footerPrimaryTxt}>{t("bookNow", lang)}</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            onPress={() => toggleSave(place.id)}
            style={styles.footerPrimary}
            testID="footer-save-btn"
          >
            <Text style={styles.footerPrimaryTxt}>
              {isSaved ? t("unsave", lang) : t("save", lang)}
            </Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
}) {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  return (
    <View style={styles.statCard}>
      <Ionicons name={icon} size={16} color={palette.primary} />
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  hero: {
    height: 360,
    borderBottomLeftRadius: 32,
    borderBottomRightRadius: 32,
    overflow: "hidden",
  },
  heroTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 18,
  },
  roundBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.94)",
    justifyContent: "center",
    alignItems: "center",
  },
  heroBottom: {
    position: "absolute",
    bottom: 24,
    left: 20,
    right: 20,
  },
  heroBadgeRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  typeBadge: {
    backgroundColor: "rgba(255,255,255,0.92)",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 999,
  },
  typeBadgeTxt: { color: palette.primaryDark, fontSize: 11, fontWeight: "700" },
  ratingBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.55)",
  },
  ratingTxt: { color: "#fff", fontSize: 11, fontWeight: "700" },
  heroTitle: { color: "#fff", fontSize: 30, fontWeight: "800", letterSpacing: -0.5, lineHeight: 34 },
  heroSub: { color: "rgba(255,255,255,0.9)", fontSize: 14, marginTop: 6 },

  body: { padding: 20, gap: 16 },
  weatherPill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    backgroundColor: palette.amberSoft,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
  },
  weatherTxt: { color: "#92400E", fontSize: 12, fontWeight: "600" },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  statCard: {
    width: "47.5%",
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: 14,
    gap: 6,
    ...shadow.soft,
  },
  statLabel: { fontSize: 11, color: palette.textMuted, fontWeight: "600" },
  statValue: { fontSize: 13, fontWeight: "700", color: palette.textPrimary, lineHeight: 18 },
  card: {
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    padding: 18,
    ...shadow.soft,
  },
  cardTitle: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
    gap: 10,
  },
  locationTxt: { fontSize: 14, fontWeight: "600", color: palette.textPrimary },
  locationSub: { fontSize: 12, color: palette.textSecondary, marginTop: 2 },
  mapsBtn: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  about: { color: palette.textSecondary, marginTop: 10, fontSize: 14, lineHeight: 22 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 14 },
  tag: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: palette.surfaceMuted,
  },
  tagTxt: { fontSize: 11, fontWeight: "600", color: palette.textSecondary },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    gap: 10,
    paddingHorizontal: 18,
    paddingTop: 14,
    backgroundColor: "rgba(255,255,255,0.98)",
    borderTopWidth: 1,
    borderTopColor: palette.borderSoft,
  },
  footerSecondary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: palette.border,
    alignItems: "center",
    backgroundColor: palette.surface,
  },
  footerSecondaryTxt: { fontWeight: "700", color: palette.textPrimary, fontSize: 14 },
  footerPrimary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 16,
    alignItems: "center",
    backgroundColor: palette.primary,
    ...shadow.emerald,
  },
  footerPrimaryTxt: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
