import React from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { Chip } from "@/src/components/Chip";
import { useApp } from "@/src/contexts/AppContext";
import { AGE_OPTIONS, CATEGORIES, DATE_OPTIONS, TYPE_OPTIONS } from "@/src/data/places";
import { t } from "@/src/i18n/strings";
import { palette, radii, shadow, spacing } from "@/src/theme";

export type Filters = {
  age: string;
  type: string;
  category: string[];
  date: string;
  wheelchair: boolean;
  sensoryFriendly: boolean;
  freeParking: boolean;
};

export const DEFAULT_FILTERS: Filters = {
  age: "All",
  type: "All",
  category: [],
  date: "Anytime",
  wheelchair: false,
  sensoryFriendly: false,
  freeParking: false,
};

type Props = {
  open: boolean;
  filters: Filters;
  onChange: (f: Filters) => void;
  onClose: () => void;
};

export function FilterSheet({ open, filters, onChange, onClose }: Props) {
  const { lang } = useApp();

  return (
    <Modal
      animationType="slide"
      transparent
      visible={open}
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet} testID="filter-sheet">
        <View style={styles.handle} />
        <View style={styles.headerRow}>
          <TouchableOpacity
            onPress={onClose}
            hitSlop={10}
            style={styles.closeBtn}
            testID="filter-close-btn"
          >
            <Text style={styles.closeTxt}>✕</Text>
          </TouchableOpacity>
          <Text style={styles.title}>{t("filter", lang)}</Text>
          <TouchableOpacity
            onPress={() => onChange(DEFAULT_FILTERS)}
            testID="filter-reset-btn"
          >
            <Text style={styles.resetTxt}>{t("reset", lang)}</Text>
          </TouchableOpacity>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.body}>
          <Section label={t("age", lang)}>
            {AGE_OPTIONS.map((a) => (
              <Chip
                key={a}
                label={a}
                active={filters.age === a}
                onPress={() => onChange({ ...filters, age: a })}
                testID={`filter-age-${a}`}
              />
            ))}
          </Section>

          <Section label={t("indoorOutdoor", lang)}>
            {TYPE_OPTIONS.map((tp) => (
              <Chip
                key={tp}
                label={tp}
                active={filters.type === tp}
                onPress={() => onChange({ ...filters, type: tp })}
                testID={`filter-type-${tp}`}
              />
            ))}
          </Section>

          <Section label={t("category", lang)}>
            {CATEGORIES.map((c) => {
              const active = filters.category.includes(c);
              return (
                <Chip
                  key={c}
                  label={c}
                  active={active}
                  onPress={() =>
                    onChange({
                      ...filters,
                      category: active
                        ? filters.category.filter((x) => x !== c)
                        : [...filters.category, c],
                    })
                  }
                  testID={`filter-category-${c}`}
                />
              );
            })}
          </Section>

          <Section label={t("date", lang)}>
            {DATE_OPTIONS.map((d) => (
              <Chip
                key={d}
                label={d}
                active={filters.date === d}
                onPress={() => onChange({ ...filters, date: d })}
                testID={`filter-date-${d}`}
              />
            ))}
          </Section>

          <Section label="Family needs">
            <Chip
              label="♿ Wheelchair"
              active={filters.wheelchair}
              onPress={() => onChange({ ...filters, wheelchair: !filters.wheelchair })}
              testID="filter-wheelchair"
            />
            <Chip
              label="🧠 Sensory friendly"
              active={filters.sensoryFriendly}
              onPress={() => onChange({ ...filters, sensoryFriendly: !filters.sensoryFriendly })}
              testID="filter-sensory"
            />
            <Chip
              label="🅿️ Free parking"
              active={filters.freeParking}
              onPress={() => onChange({ ...filters, freeParking: !filters.freeParking })}
              testID="filter-parking"
            />
          </Section>
        </ScrollView>

        <TouchableOpacity
          onPress={onClose}
          style={styles.cta}
          activeOpacity={0.9}
          testID="filter-show-results-btn"
        >
          <Text style={styles.ctaTxt}>{t("showResults", lang)}</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: spacing.xxl }}>
      <Text style={styles.sectionLabel}>{label}</Text>
      <View style={styles.chipRow}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.45)" },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: palette.surface,
    borderTopLeftRadius: radii.xxl,
    borderTopRightRadius: radii.xxl,
    paddingHorizontal: 22,
    paddingTop: 14,
    paddingBottom: 36,
    maxHeight: "82%",
    ...shadow.card,
  },
  handle: {
    width: 56,
    height: 5,
    borderRadius: 999,
    backgroundColor: palette.border,
    alignSelf: "center",
    marginBottom: 18,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 22,
  },
  closeBtn: { width: 32, height: 32, justifyContent: "center", alignItems: "center" },
  closeTxt: { fontSize: 16, color: palette.textSecondary },
  title: { fontSize: 19, fontWeight: "700", color: palette.textPrimary },
  resetTxt: { color: palette.primary, fontWeight: "600", fontSize: 14 },
  body: { paddingBottom: 24 },
  sectionLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: palette.textPrimary,
    marginBottom: 12,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  cta: {
    backgroundColor: palette.primary,
    paddingVertical: 16,
    borderRadius: 18,
    alignItems: "center",
    ...shadow.emerald,
  },
  ctaTxt: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
