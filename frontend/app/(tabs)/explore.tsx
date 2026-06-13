import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AppCard } from "@/src/components/AppCard";
import { Chip } from "@/src/components/Chip";
import { DEFAULT_FILTERS, FilterSheet, Filters } from "@/src/components/FilterSheet";
import { useApp } from "@/src/contexts/AppContext";
import { PLACES } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { palette } from "@/src/theme";

export default function Explore() {
  const router = useRouter();
  const { lang } = useApp();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const list = useMemo(() => {
    return PLACES.filter((p) => {
      if (filters.type !== "All" && p.type !== filters.type) return false;
      if (filters.age !== "All") {
        const [min, max] = filters.age.split("-").map(Number);
        if (!(p.ageMin <= max && p.ageMax >= min)) return false;
      }
      if (filters.category.length && !filters.category.some((c) => p.category.includes(c)))
        return false;
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        const hay = `${p.title[lang]} ${p.short[lang]} ${p.town}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [filters, query, lang]);

  const activeFilterCount =
    (filters.age !== "All" ? 1 : 0) +
    (filters.type !== "All" ? 1 : 0) +
    filters.category.length +
    (filters.date !== "Anytime" ? 1 : 0);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.headerSticky}>
        <Text style={styles.h1}>{t("explore", lang)}</Text>
        <View style={styles.searchRow}>
          <View style={styles.searchField}>
            <Ionicons name="search-outline" size={18} color={palette.textMuted} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder={t("search", lang)}
              placeholderTextColor={palette.textMuted}
              style={styles.searchInput}
              testID="explore-search-input"
            />
          </View>
          <TouchableOpacity
            onPress={() => setOpen(true)}
            style={styles.filterBtn}
            testID="explore-filter-btn"
          >
            <Ionicons name="options-outline" size={20} color={palette.textPrimary} />
            {activeFilterCount > 0 ? (
              <View style={styles.filterBadge}>
                <Text style={styles.filterBadgeTxt}>{activeFilterCount}</Text>
              </View>
            ) : null}
          </TouchableOpacity>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.quickRow}
          style={styles.quickRowOuter}
        >
          {[
            { key: "age", label: t("age", lang) },
            { key: "type", label: t("indoorOutdoor", lang) },
            { key: "category", label: t("category", lang) },
            { key: "date", label: t("date", lang) },
          ].map((it) => (
            <Chip
              key={it.key}
              label={it.label}
              onPress={() => setOpen(true)}
              testID={`explore-quick-${it.key}`}
            />
          ))}
        </ScrollView>
      </View>

      <ScrollView
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.sectionTitle}>
          {list.length} {list.length === 1 ? "result" : "results"}
        </Text>

        {list.length === 0 ? (
          <View style={styles.empty} testID="explore-empty">
            <Ionicons name="leaf-outline" size={40} color={palette.textMuted} />
            <Text style={styles.emptyTxt}>{t("noResults", lang)}</Text>
          </View>
        ) : (
          list.map((p) => (
            <AppCard
              key={p.id}
              item={p}
              onPress={() => router.push(`/detail/${p.id}`)}
            />
          ))
        )}
      </ScrollView>

      <FilterSheet
        open={open}
        filters={filters}
        onChange={setFilters}
        onClose={() => setOpen(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: palette.background },
  headerSticky: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 4,
    backgroundColor: palette.background,
    borderBottomWidth: 1,
    borderBottomColor: palette.borderSoft,
  },
  h1: {
    fontSize: 30,
    fontWeight: "800",
    color: palette.textPrimary,
    letterSpacing: -0.5,
  },
  searchRow: { marginTop: 14, flexDirection: "row", gap: 10 },
  searchField: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: palette.surface,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 18,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  searchInput: { flex: 1, fontSize: 14, color: palette.textPrimary, padding: 0 },
  filterBtn: {
    width: 48,
    backgroundColor: palette.surface,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: 18,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  filterBadge: {
    position: "absolute",
    top: 6,
    right: 6,
    backgroundColor: palette.primary,
    width: 16,
    height: 16,
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
  },
  filterBadgeTxt: { color: "#fff", fontSize: 9, fontWeight: "800" },
  quickRowOuter: { marginTop: 14, maxHeight: 56 },
  quickRow: { gap: 8, alignItems: "center", height: 56 },
  list: { padding: 20, paddingBottom: 28, gap: 14 },
  sectionTitle: { fontSize: 14, fontWeight: "700", color: palette.textSecondary, marginBottom: 4 },
  empty: { alignItems: "center", padding: 40, gap: 10 },
  emptyTxt: { color: palette.textSecondary, fontSize: 14 },
});
