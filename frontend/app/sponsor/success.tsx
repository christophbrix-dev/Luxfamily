import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { palette, radii, shadow } from "@/src/theme";

export default function SponsorSuccess() {
  const router = useRouter();
  const { session_id } = useLocalSearchParams<{ session_id: string }>();
  const [info, setInfo] = useState<{ paid: boolean; amount_total: number; event_id: string; plan: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!session_id) return;
    fetch(`${process.env.EXPO_PUBLIC_BACKEND_URL}/api/sponsor/session/${session_id}`)
      .then((r) => r.json())
      .then((d) => (d.detail ? setErr(d.detail) : setInfo(d)))
      .catch((e) => setErr(e instanceof Error ? e.message : "Lookup failed"));
  }, [session_id]);

  return (
    <View style={styles.wrap}>
      {!info && !err ? (
        <ActivityIndicator color={palette.primary} />
      ) : err ? (
        <Text style={styles.err}>{err}</Text>
      ) : (
        <View style={styles.card}>
          <View style={styles.iconCircle}>
            <Ionicons name="checkmark" size={36} color="#fff" />
          </View>
          <Text style={styles.title}>{info?.paid ? "Payment successful!" : "Awaiting payment"}</Text>
          <Text style={styles.sub}>
            {info?.paid
              ? `Your featured slot is active. Plan: ${info.plan}.`
              : "Payment is being processed. Please wait a moment."}
          </Text>
          <View style={styles.amountBox}>
            <Text style={styles.amountLbl}>Total paid</Text>
            <Text style={styles.amount}>EUR {((info?.amount_total ?? 0) / 100).toFixed(2)}</Text>
          </View>
          <TouchableOpacity onPress={() => router.replace("/(tabs)/events")} style={styles.cta} testID="sponsor-done">
            <Text style={styles.ctaTxt}>Back to app</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#F1F5F9", justifyContent: "center", alignItems: "center", padding: 24 },
  err: { color: palette.red },
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
    backgroundColor: palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...shadow.emerald,
  },
  title: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, textAlign: "center" },
  sub: { color: palette.textSecondary, textAlign: "center", lineHeight: 20 },
  amountBox: {
    width: "100%",
    backgroundColor: palette.surfaceMuted,
    padding: 14,
    borderRadius: radii.md,
    alignItems: "center",
    marginTop: 8,
  },
  amountLbl: { fontSize: 11, color: palette.textMuted, fontWeight: "700", letterSpacing: 0.5 },
  amount: { fontSize: 24, fontWeight: "800", color: palette.primaryDark, marginTop: 4 },
  cta: {
    width: "100%",
    backgroundColor: palette.primary,
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
    marginTop: 8,
    ...shadow.emerald,
  },
  ctaTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
});
