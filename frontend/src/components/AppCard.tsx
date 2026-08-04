import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import React from "react";
import { Image, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { useApp } from "@/src/contexts/AppContext";
import { pickLang } from "@/src/i18n/pickLang";
import type { Place } from "@/src/data/places";
import { palette, radii, shadow, spacing } from "@/src/theme";

type Props = {
  item: Place;
  large?: boolean;
  onPress: () => void;
  testID?: string;
};

export function AppCard({ item, large = false, onPress, testID }: Props) {
  const { lang, saved, toggleSave } = useApp();
  const isSaved = saved.includes(item.id);

  return (
    <TouchableOpacity
      activeOpacity={0.9}
      onPress={onPress}
      style={[styles.card, large ? styles.cardLarge : styles.cardSmall]}
      testID={testID ?? `place-card-${item.id}`}
    >
      <View style={[styles.imageWrap, large ? styles.imageLarge : styles.imageSmall]}>
        <Image source={{ uri: item.image }} style={styles.image} />
        <LinearGradient
          colors={["rgba(0,0,0,0)", "rgba(0,0,0,0.55)"]}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{item.type}</Text>
        </View>
        <TouchableOpacity
          accessibilityLabel="Toggle save"
          onPress={(e) => {
            e.stopPropagation();
            toggleSave(item.id);
          }}
          style={styles.saveBtn}
          hitSlop={8}
          testID={`save-btn-${item.id}`}
        >
          <Ionicons
            name={isSaved ? "heart" : "heart-outline"}
            size={18}
            color={isSaved ? palette.red : palette.textPrimary}
          />
        </TouchableOpacity>

        {large ? (
          <View style={styles.largeOverlay}>
            <Text style={styles.largeTitle} numberOfLines={2}>
              {pickLang(item.title, lang)}
            </Text>
            <Text style={styles.largeShort} numberOfLines={2}>
              {pickLang(item.short, lang)}
            </Text>
            <View style={styles.largeMetaRow}>
              <View style={styles.metaPill}>
                <Ionicons name="location-outline" size={12} color="#fff" />
                <Text style={styles.metaPillText}>
                  {item.distanceKm.toFixed(1)} km
                </Text>
              </View>
              <View style={styles.metaPill}>
                <Ionicons name="people-outline" size={12} color="#fff" />
                <Text style={styles.metaPillText}>{item.age}</Text>
              </View>
              <View style={styles.metaPill}>
                <Ionicons name="star" size={12} color="#FBBF24" />
                <Text style={styles.metaPillText}>{item.rating.toFixed(1)}</Text>
              </View>
            </View>
          </View>
        ) : null}
      </View>

      {!large ? (
        <View style={styles.cardBody}>
          <Text style={styles.title} numberOfLines={1}>
            {pickLang(item.title, lang)}
          </Text>
          <Text style={styles.short} numberOfLines={2}>
            {pickLang(item.short, lang)}
          </Text>
          <View style={styles.metaRow}>
            <View style={styles.metaItem}>
              <Ionicons name="location-outline" size={12} color={palette.textSecondary} />
              <Text style={styles.metaText}>
                {item.distanceKm.toFixed(1)} km · {item.town}
              </Text>
            </View>
            <View style={styles.metaItem}>
              <Ionicons name="star" size={12} color={palette.amber} />
              <Text style={styles.metaText}>{item.rating.toFixed(1)}</Text>
            </View>
          </View>
        </View>
      ) : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: palette.surface,
    borderRadius: radii.xl,
    overflow: "hidden",
    ...shadow.card,
  },
  cardLarge: {},
  cardSmall: { borderWidth: 1, borderColor: palette.borderSoft },
  imageWrap: { position: "relative" },
  imageLarge: { height: 240 },
  imageSmall: { height: 140 },
  image: { width: "100%", height: "100%" },
  badge: {
    position: "absolute",
    top: 14,
    left: 14,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.92)",
  },
  badgeText: { fontSize: 11, fontWeight: "700", color: palette.primaryDark },
  saveBtn: {
    position: "absolute",
    top: 12,
    right: 12,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "rgba(255,255,255,0.92)",
    justifyContent: "center",
    alignItems: "center",
  },
  largeOverlay: {
    position: "absolute",
    left: 16,
    right: 16,
    bottom: 16,
  },
  largeTitle: { color: "#fff", fontSize: 22, fontWeight: "700", letterSpacing: -0.3 },
  largeShort: { color: "rgba(255,255,255,0.85)", fontSize: 13, marginTop: 4 },
  largeMetaRow: { flexDirection: "row", gap: spacing.sm, marginTop: 12, flexWrap: "wrap" },
  metaPill: {
    flexDirection: "row",
    gap: 4,
    alignItems: "center",
    backgroundColor: "rgba(0,0,0,0.35)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  metaPillText: { color: "#fff", fontSize: 11, fontWeight: "600" },
  cardBody: { padding: 16 },
  title: { fontSize: 16, fontWeight: "700", color: palette.textPrimary },
  short: { marginTop: 4, fontSize: 13, color: palette.textSecondary },
  metaRow: {
    marginTop: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metaItem: { flexDirection: "row", gap: 4, alignItems: "center" },
  metaText: { fontSize: 11, color: palette.textSecondary, fontWeight: "500" },
});
