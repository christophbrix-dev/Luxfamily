import { Ionicons } from "@expo/vector-icons";
import { usePathname, useRouter } from "expo-router";
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useApp } from "@/src/contexts/AppContext";
import { t } from "@/src/i18n/strings";
import { palette } from "@/src/theme";

type Tab = {
  key: "home" | "explore" | "saved" | "calendar" | "profile";
  href:
    | "/(tabs)/home"
    | "/(tabs)/explore"
    | "/(tabs)/saved"
    | "/(tabs)/calendar"
    | "/(tabs)/profile";
  icon: keyof typeof Ionicons.glyphMap;
  iconFocused: keyof typeof Ionicons.glyphMap;
};

const TABS: Tab[] = [
  { key: "home", href: "/(tabs)/home", icon: "home-outline", iconFocused: "home" },
  { key: "explore", href: "/(tabs)/explore", icon: "search-outline", iconFocused: "search" },
  { key: "saved", href: "/(tabs)/saved", icon: "heart-outline", iconFocused: "heart" },
  {
    key: "calendar",
    href: "/(tabs)/calendar",
    icon: "calendar-outline",
    iconFocused: "calendar",
  },
  { key: "profile", href: "/(tabs)/profile", icon: "person-outline", iconFocused: "person" },
];

export function BottomTabBar() {
  const router = useRouter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const { lang } = useApp();

  return (
    <View
      style={[
        styles.wrap,
        { paddingBottom: Math.max(insets.bottom, 10) },
      ]}
      testID="bottom-tab-bar"
    >
      {TABS.map((tab) => {
        const active = pathname.includes(tab.key);
        return (
          <Pressable
            key={tab.key}
            onPress={() => router.replace(tab.href)}
            style={styles.item}
            testID={`tab-${tab.key}`}
          >
            <Ionicons
              name={active ? tab.iconFocused : tab.icon}
              size={22}
              color={active ? palette.primary : palette.textMuted}
            />
            <Text style={[styles.label, active && styles.labelActive]}>
              {t(tab.key, lang)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: "rgba(255,255,255,0.98)",
    borderTopWidth: 1,
    borderTopColor: palette.borderSoft,
    paddingTop: 10,
    paddingHorizontal: 8,
  },
  item: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    paddingVertical: 4,
  },
  label: { fontSize: 11, color: palette.textMuted, fontWeight: "500" },
  labelActive: { color: palette.primary, fontWeight: "700" },
});
