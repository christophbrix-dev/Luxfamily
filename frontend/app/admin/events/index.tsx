import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { palette, radii, shadow } from "@/src/theme";
import { api, ApiEventSummary, setAdminToken } from "@/src/utils/api";

export default function AdminEvents() {
  const router = useRouter();
  const [events, setEvents] = useState<ApiEventSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      setEvents(await api.adminEvents());
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed";
      if (msg.includes("401") || msg.toLowerCase().includes("unauth")) {
        await setAdminToken(null);
        router.replace("/admin");
      } else {
        setErr(msg);
      }
    }
  }, [router]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const remove = async (id: string) => {
    if (typeof window !== "undefined" && !window.confirm?.("Delete this event?")) return;
    try {
      await api.deleteEvent(id);
      setEvents((prev) => (prev ? prev.filter((p) => p.id !== id) : prev));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const togglePublish = async (ev: ApiEventSummary) => {
    try {
      await api.updateEvent(ev.id, { published: !ev.published });
      // updateEvent returns a full document; this list deliberately holds
      // summaries, so patch the one field in place.
      setEvents((prev) =>
        prev ? prev.map((p) => (p.id === ev.id ? { ...p, published: !ev.published } : p)) : prev,
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.topbar}>
        <View>
          <Text style={styles.h1}>Events</Text>
          <Text style={styles.sub}>
            {events ? `${events.length} total` : "Loading..."}
          </Text>
        </View>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <TouchableOpacity
            onPress={() => router.push("/admin/partners")}
            style={styles.iconBtn}
            testID="admin-partners"
          >
            <Ionicons name="people-outline" size={18} color={palette.textPrimary} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push("/admin/analytics")}
            style={styles.iconBtn}
            testID="admin-analytics"
          >
            <Ionicons name="stats-chart-outline" size={18} color={palette.textPrimary} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push("/admin/sources")}
            style={styles.iconBtn}
            testID="admin-sources"
          >
            <Ionicons name="cloud-download-outline" size={18} color={palette.textPrimary} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push("/admin/password")}
            style={styles.iconBtn}
            testID="admin-password"
          >
            <Ionicons name="key-outline" size={18} color={palette.textPrimary} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={async () => {
              await setAdminToken(null);
              router.replace("/admin");
            }}
            style={styles.iconBtn}
            testID="admin-logout"
          >
            <Ionicons name="log-out-outline" size={18} color={palette.textPrimary} />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push("/admin/events/new")}
            style={styles.primaryBtn}
            testID="admin-new-event"
          >
            <Ionicons name="add" size={18} color="#fff" />
            <Text style={styles.primaryBtnTxt}>New event</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {err ? <Text style={styles.errTxt}>{err}</Text> : null}
        {events === null ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 40 }} />
        ) : events.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="sparkles-outline" size={40} color={palette.textMuted} />
            <Text style={styles.emptyTitle}>No events yet</Text>
            <Text style={styles.emptyTxt}>
              Tap “New event” to create your first one.
            </Text>
          </View>
        ) : (
          events.map((ev) => (
            <View key={ev.id} style={styles.row} testID={`admin-row-${ev.id}`}>
              <View style={[styles.dot, ev.published ? styles.dotOn : styles.dotOff]} />
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Text style={styles.title} numberOfLines={1}>
                    {ev.title.en}
                  </Text>
                  {ev.featured ? (
                    <View style={styles.sponsorBadge}>
                      <Ionicons name="star" size={9} color="#92400E" />
                      <Text style={styles.sponsorBadgeTxt}>Sponsored</Text>
                    </View>
                  ) : null}
                  {ev.source_name ? (
                    <View style={styles.autoBadge}>
                      <Ionicons name="cloud-download" size={9} color={palette.textMuted} />
                      <Text style={styles.autoBadgeTxt}>{ev.source_name}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.meta} numberOfLines={1}>
                  {ev.start_date} · {ev.town} · {ev.canton} · {ev.view_count} views
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => togglePublish(ev)}
                style={[styles.actionBtn, ev.published ? styles.btnDraft : styles.btnPublish]}
                testID={`admin-toggle-${ev.id}`}
              >
                <Text style={[styles.actionTxt, ev.published ? styles.actionTxtDark : styles.actionTxtLight]}>
                  {ev.published ? "Published" : "Draft"}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => router.push(`/admin/events/${ev.id}`)}
                style={styles.iconBtn}
                testID={`admin-edit-${ev.id}`}
              >
                <Ionicons name="create-outline" size={18} color={palette.textPrimary} />
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => remove(ev.id)}
                style={[styles.iconBtn, styles.iconBtnDanger]}
                testID={`admin-delete-${ev.id}`}
              >
                <Ionicons name="trash-outline" size={18} color={palette.red} />
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  sponsorBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: "#FEF3C7",
  },
  sponsorBadgeTxt: {
    fontSize: 9,
    fontWeight: "800",
    color: "#92400E",
    letterSpacing: 0.4,
  },
  autoBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: palette.borderSoft,
  },
  autoBadgeTxt: {
    fontSize: 9,
    fontWeight: "700",
    color: palette.textMuted,
  },
  wrap: { flex: 1, backgroundColor: "#F1F5F9" },
  topbar: {
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 18,
    backgroundColor: palette.surface,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  h1: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  sub: { color: palette.textSecondary, fontSize: 12, marginTop: 2 },
  primaryBtn: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    backgroundColor: palette.primary,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
    ...shadow.emerald,
  },
  primaryBtnTxt: { color: "#fff", fontWeight: "700", fontSize: 13 },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: palette.borderSoft,
  },
  iconBtnDanger: { borderColor: "#FECACA", backgroundColor: "#FEF2F2" },
  scroll: { padding: 24, gap: 10 },
  errTxt: { color: palette.red, marginBottom: 8 },
  empty: { alignItems: "center", padding: 60, gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: "700", color: palette.textPrimary, marginTop: 8 },
  emptyTxt: { color: palette.textSecondary, textAlign: "center" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 14,
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: palette.borderSoft,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotOn: { backgroundColor: palette.primary },
  dotOff: { backgroundColor: palette.textMuted },
  title: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  meta: { fontSize: 12, color: palette.textSecondary, marginTop: 2 },
  actionBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
  },
  btnPublish: { backgroundColor: palette.primaryLight, borderColor: palette.primaryLight },
  btnDraft: { backgroundColor: palette.surface, borderColor: palette.borderSoft },
  actionTxt: { fontSize: 11, fontWeight: "700" },
  actionTxtDark: { color: palette.textSecondary },
  actionTxtLight: { color: palette.primaryDark },
});
