import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useMemo } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";

export default function SponsorCancel() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang } = useApp();
  const router = useRouter();
  return (
    <View style={styles.wrap}>
      <View style={styles.card}>
        <View style={styles.iconCircle}>
          <Ionicons name="close" size={36} color={palette.textPrimary} />
        </View>
        <Text style={styles.title}>{t("paymentCancelled", lang)}</Text>
        <Text style={styles.sub}>{t("paymentCancelledSub", lang)}</Text>
        <TouchableOpacity onPress={() => router.replace("/(tabs)/events")} style={styles.cta}>
          <Text style={styles.ctaTxt}>{t("backToApp", lang)}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  wrap: { flex: 1, backgroundColor: palette.surfaceMuted, justifyContent: "center", alignItems: "center", padding: 24 },
  card: {
    backgroundColor: palette.surface,
    borderRadius: radii.xxl,
    padding: 36,
    alignItems: "center",
    gap: 12,
    maxWidth: 460,
    width: "100%",
    ...shadow.card,
  },
  iconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: palette.surfaceMuted,
    justifyContent: "center",
    alignItems: "center",
  },
  title: { fontSize: 22, fontWeight: "800", color: palette.textPrimary },
  sub: { color: palette.textSecondary, textAlign: "center", lineHeight: 20 },
  cta: {
    width: "100%",
    backgroundColor: palette.primary,
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
    marginTop: 12,
    ...shadow.emerald,
  },
  ctaTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
});
