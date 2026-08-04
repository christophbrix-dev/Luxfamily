import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState, useMemo } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { radii, type Palette, shadowFor } from "@/src/theme";
import { useAppPalette } from "@/src/hooks/useAppPalette";
import { t } from "@/src/i18n/strings";
import { api, ApiSource } from "@/src/utils/api";

export default function AdminSources() {
  const { palette, shadow } = useAppPalette();
  const styles = useMemo(() => makeStyles(palette, shadow), [palette, shadow]);
  const { lang } = useApp();
  const router = useRouter();
  const [items, setItems] = useState<ApiSource[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Inline "add source" form state.
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<"ical" | "data_public_lu">("ical");
  const [newUrl, setNewUrl] = useState("");
  const [newCanton, setNewCanton] = useState("Luxembourg");

  const load = useCallback(async () => {
    setErr(null);
    try {
      setItems(await api.adminSources());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const addSource = async () => {
    if (!newName.trim() || !newUrl.trim()) return;
    try {
      await api.createSource({
        name: newName.trim(),
        kind: newKind,
        url: newUrl.trim(),
        active: true,
        canton_default: newCanton,
        town_default: newCanton,
        category_default: ["Culture"],
        age_min_default: 0,
        age_max_default: 99,
        lat_default: 49.6116,
        lng_default: 6.1319,
        image_default: "",
      });
      setNewName("");
      setNewUrl("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Create failed");
    }
  };

  const runSource = async (id: string) => {
    setBusyId(id);
    try {
      await api.runSource(id);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Run failed");
    } finally {
      setBusyId(null);
    }
  };

  const toggleActive = async (s: ApiSource) => {
    try {
      const updated = await api.updateSource(s.id, { active: !s.active });
      setItems((prev) => (prev ? prev.map((x) => (x.id === s.id ? updated : x)) : prev));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  const remove = async (id: string) => {
    if (typeof window !== "undefined" && !window.confirm?.("Delete this source?")) return;
    try {
      await api.deleteSource(id);
      setItems((prev) => (prev ? prev.filter((s) => s.id !== id) : prev));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.topbar}>
        <TouchableOpacity onPress={() => router.replace("/admin/events")} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={18} color={palette.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.h1}>{t("importSources", lang)}</Text>
          <Text style={styles.sub}>
            {items ? `${items.length} configured` : "Loading..."} · Runs every 24h
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {err ? <Text style={styles.errTxt}>{err}</Text> : null}

        <View style={styles.formCard}>
          <Text style={styles.formTitle}>{t("addNewFeed", lang)}</Text>
          <TextInput
            value={newName}
            onChangeText={setNewName}
            placeholder="Name (e.g. Mudam events)"
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            testID="src-new-name"
          />
          <View style={styles.kindRow}>
            <TouchableOpacity
              onPress={() => setNewKind("ical")}
              style={[styles.kindChip, newKind === "ical" && styles.kindChipActive]}
              testID="src-kind-ical"
            >
              <Text style={[styles.kindTxt, newKind === "ical" && styles.kindTxtActive]}>iCal feed</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => setNewKind("data_public_lu")}
              style={[styles.kindChip, newKind === "data_public_lu" && styles.kindChipActive]}
              testID="src-kind-ckan"
            >
              <Text style={[styles.kindTxt, newKind === "data_public_lu" && styles.kindTxtActive]}>data.public.lu / JSON</Text>
            </TouchableOpacity>
          </View>
          <TextInput
            value={newUrl}
            onChangeText={setNewUrl}
            placeholder={newKind === "ical" ? "https://example.com/events.ics" : "https://data.public.lu/.../events.json"}
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            autoCapitalize="none"
            testID="src-new-url"
          />
          <TextInput
            value={newCanton}
            onChangeText={setNewCanton}
            placeholder="Default canton"
            placeholderTextColor={palette.textMuted}
            style={styles.input}
            testID="src-new-canton"
          />
          <TouchableOpacity onPress={addSource} style={styles.addBtn} testID="src-add">
            <Ionicons name="add" size={16} color="#fff" />
            <Text style={styles.addBtnTxt}>{t("addSource", lang)}</Text>
          </TouchableOpacity>
        </View>

        {items === null ? (
          <ActivityIndicator color={palette.primary} style={{ marginTop: 30 }} />
        ) : items.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="cloud-download-outline" size={36} color={palette.textMuted} />
            <Text style={styles.emptyTxt}>
              No sources yet. Add a Mudam, Philharmonie or Rockhal iCal feed above. Imports run automatically every 24h and write events as drafts you can publish.
            </Text>
          </View>
        ) : (
          items.map((s) => (
            <View key={s.id} style={styles.row} testID={`src-row-${s.id}`}>
              <View style={[styles.dot, s.active ? styles.dotOn : styles.dotOff]} />
              <View style={{ flex: 1 }}>
                <View style={styles.titleRow}>
                  <Text style={styles.title} numberOfLines={1}>{s.name}</Text>
                  <View style={styles.kindBadge}>
                    <Text style={styles.kindBadgeTxt}>{s.kind === "ical" ? "iCal" : "JSON"}</Text>
                  </View>
                </View>
                <Text style={styles.metaUrl} numberOfLines={1}>{s.url}</Text>
                <Text style={styles.metaInfo}>
                  {s.last_status === "ok" && (
                    <Text style={{ color: palette.primaryDark }}>
                      ✓ Last run: {s.last_imported_count ?? 0} imported · {s.last_skipped_count ?? 0} skipped
                    </Text>
                  )}
                  {s.last_status === "error" && (
                    <Text style={{ color: palette.red }}>✗ Error: {s.last_error}</Text>
                  )}
                  {!s.last_status && (
                    <Text style={{ color: palette.textMuted }}>{t("neverRun", lang)}</Text>
                  )}
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => runSource(s.id)}
                style={[styles.actionBtn, styles.btnRun]}
                disabled={busyId === s.id}
                testID={`src-run-${s.id}`}
              >
                {busyId === s.id ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <>
                    <Ionicons name="play" size={12} color="#fff" />
                    <Text style={styles.btnRunTxt}>Run</Text>
                  </>
                )}
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => toggleActive(s)}
                style={[styles.actionBtn, s.active ? styles.btnOn : styles.btnOff]}
                testID={`src-toggle-${s.id}`}
              >
                <Text style={[styles.actionTxt, s.active ? styles.btnOnTxt : styles.btnOffTxt]}>
                  {s.active ? "Active" : "Paused"}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => remove(s.id)}
                style={[styles.iconBtn, styles.iconDanger]}
                testID={`src-delete-${s.id}`}
              >
                <Ionicons name="trash-outline" size={16} color={palette.red} />
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const makeStyles = (palette: Palette, shadow: ReturnType<typeof shadowFor>) => StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#F1F5F9" },
  topbar: {
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 18,
    backgroundColor: palette.surface,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  h1: { fontSize: 22, fontWeight: "800", color: palette.textPrimary, letterSpacing: -0.5 },
  sub: { color: palette.textSecondary, fontSize: 12, marginTop: 2 },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    justifyContent: "center",
    alignItems: "center",
  },
  iconDanger: { borderColor: "#FECACA", backgroundColor: "#FEF2F2" },
  scroll: { padding: 24, gap: 10 },
  errTxt: { color: palette.red, marginBottom: 8 },
  formCard: {
    backgroundColor: palette.surface,
    borderRadius: radii.lg,
    padding: 18,
    borderWidth: 1,
    borderColor: palette.borderSoft,
    gap: 10,
    marginBottom: 18,
  },
  formTitle: { fontSize: 14, fontWeight: "800", color: palette.textPrimary, marginBottom: 4 },
  input: {
    backgroundColor: palette.surfaceMuted,
    borderRadius: 10,
    padding: 12,
    fontSize: 13,
    color: palette.textPrimary,
  },
  kindRow: { flexDirection: "row", gap: 8 },
  kindChip: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: palette.surfaceMuted,
    alignItems: "center",
    borderWidth: 1,
    borderColor: palette.borderSoft,
  },
  kindChipActive: { backgroundColor: palette.primaryLight, borderColor: palette.primary },
  kindTxt: { fontSize: 12, fontWeight: "600", color: palette.textSecondary },
  kindTxtActive: { color: palette.primaryDark },
  addBtn: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: palette.primary,
    ...shadow.emerald,
  },
  addBtnTxt: { color: "#fff", fontWeight: "700", fontSize: 13 },
  empty: { alignItems: "center", padding: 40, gap: 10 },
  emptyTxt: { color: palette.textSecondary, textAlign: "center", maxWidth: 400, lineHeight: 20 },
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
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { fontSize: 14, fontWeight: "700", color: palette.textPrimary },
  kindBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: palette.surfaceMuted,
  },
  kindBadgeTxt: { fontSize: 9, fontWeight: "800", color: palette.textMuted, letterSpacing: 0.5 },
  metaUrl: { fontSize: 11, color: palette.textMuted, marginTop: 2 },
  metaInfo: { fontSize: 11, marginTop: 4 },
  actionBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  btnRun: { backgroundColor: palette.primary, borderColor: palette.primary },
  btnRunTxt: { color: "#fff", fontWeight: "700", fontSize: 11 },
  btnOn: { backgroundColor: palette.primaryLight, borderColor: palette.primaryLight },
  btnOff: { backgroundColor: palette.surface, borderColor: palette.borderSoft },
  actionTxt: { fontSize: 11, fontWeight: "700" },
  btnOnTxt: { color: palette.primaryDark },
  btnOffTxt: { color: palette.textSecondary },
});
