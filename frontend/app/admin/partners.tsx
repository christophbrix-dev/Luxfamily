import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState, useMemo } from "react";
import { ActivityIndicator, Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { apiFetch } from "@/src/utils/api";

type Partner = {
  id: string;
  name: string;
  venue: string;
  email: string;
  website?: string;
  instagram?: string;
  facebook?: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
};

export default function AdminPartners() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang } = useApp();
  const router = useRouter();
  const [items, setItems] = useState<Partner[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setErr(null);
      setItems(await apiFetch<Partner[]>("/api/admin/partners", { admin: true }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const update = async (id: string, status: "approved" | "rejected") => {
    try {
      await apiFetch(`/api/admin/partners/${id}`, { method: "PATCH", body: { status }, admin: true });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: "#F1F5F9" }}>
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.replace("/admin/events")} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={18} color={palette.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.h1}>{t("partnerSubmissions", lang)}</Text>
          <Text style={styles.sub}>{items?.length ?? 0} entries · moderation queue</Text>
        </View>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        {err ? <Text style={{ color: palette.red }}>{err}</Text> : null}
        {items === null ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 30 }} />
        ) : items.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={36} color={palette.textMuted} />
            <Text style={styles.emptyTxt}>{t("noPartnerSubmissions", lang)}</Text>
          </View>
        ) : (
          items.map((p) => (
            <View key={p.id} style={styles.card} testID={`partner-${p.id}`}>
              <View style={{ flex: 1, gap: 4 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <Text style={styles.venue}>{p.venue}</Text>
                  <View style={[styles.statusBadge, statusStyle(p.status, palette)]}>
                    <Text style={styles.statusTxt}>{p.status}</Text>
                  </View>
                </View>
                <Text style={styles.meta}>by {p.name} · {new Date(p.created_at).toLocaleDateString()}</Text>
                <View style={styles.linksRow}>
                  <TouchableOpacity onPress={() => Linking.openURL(`mailto:${p.email}`)}>
                    <Text style={styles.link}>{p.email}</Text>
                  </TouchableOpacity>
                  {p.website ? (
                    <TouchableOpacity onPress={() => Linking.openURL(p.website!)}>
                      <Text style={styles.link}>{p.website}</Text>
                    </TouchableOpacity>
                  ) : null}
                  {p.instagram ? <Text style={styles.tag}>IG: {p.instagram}</Text> : null}
                  {p.facebook ? <Text style={styles.tag}>FB: {p.facebook}</Text> : null}
                </View>
              </View>
              {p.status === "pending" ? (
                <View style={{ gap: 6 }}>
                  <TouchableOpacity
                    onPress={() => update(p.id, "approved")}
                    style={[styles.actionBtn, { backgroundColor: palette.primary }]}
                    testID={`partner-approve-${p.id}`}
                  >
                    <Text style={styles.actionTxt}>{t("approve", lang)}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => update(p.id, "rejected")}
                    style={[styles.actionBtn, { backgroundColor: "#FEF2F2", borderWidth: 1, borderColor: "#FECACA" }]}
                    testID={`partner-reject-${p.id}`}
                  >
                    <Text style={[styles.actionTxt, { color: palette.red }]}>{t("reject", lang)}</Text>
                  </TouchableOpacity>
                </View>
              ) : null}
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

function statusStyle(s: string, palette: Palette) {
  if (s === "approved") return { backgroundColor: palette.primaryLight };
  if (s === "rejected") return { backgroundColor: "#FEF2F2" };
  return { backgroundColor: "#FEF3C7" };
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  topbar: {
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 16,
    backgroundColor: palette.surface,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
  },
  h1: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  sub: { color: palette.textSecondary, fontSize: 12, marginTop: 2 },
  scroll: { padding: 24, gap: 10 },
  empty: { alignItems: "center", padding: 40, gap: 10 },
  emptyTxt: { color: palette.textSecondary },
  card: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    padding: 16,
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    ...shadow.soft,
  },
  venue: { fontSize: 15, fontWeight: "800", color: palette.textPrimary },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  statusTxt: { fontSize: 9, fontWeight: "800", color: palette.textPrimary, letterSpacing: 0.5, textTransform: "uppercase" },
  meta: { color: palette.textSecondary, fontSize: 12 },
  linksRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  link: { color: palette.primary, fontSize: 12, fontWeight: "600" },
  tag: { color: palette.textSecondary, fontSize: 11 },
  actionBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  actionTxt: { color: "#fff", fontWeight: "700", fontSize: 12 },
});
